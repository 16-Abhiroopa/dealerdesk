"""Unified LLM provider adapter supporting Gemini, Groq, OpenAI, Anthropic, and Mock fallback.

Selects the provider based on active environment variables in priority order:
1. GEMINI_API_KEY  (Google Gemini via official google-genai SDK)
2. GROQ_API_KEY    (Groq via groq SDK)
3. OPENAI_API_KEY  (OpenAI via openai SDK)
4. ANTHROPIC_API_KEY (Anthropic via anthropic SDK)
5. MockAdapter fallback (for testing and offline execution)
"""
import json
import logging
import os
import time
from typing import Dict, Any, List, Optional, Tuple, Set

logger = logging.getLogger(__name__)


class LLMResponse:
    def __init__(self, content: str = "", tool_calls: Optional[List[Dict[str, Any]]] = None):
        self.content = content or ""
        self.tool_calls = tool_calls or []


class BaseLLMAdapter:
    def generate_turn(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        tools: List[Dict[str, Any]],
    ) -> LLMResponse:
        raise NotImplementedError


class GeminiAdapter(BaseLLMAdapter):
    """Google Gemini adapter using the official google-genai SDK."""

    def __init__(self, api_key: str, model_name: Optional[str] = None):
        from google import genai
        from google.genai import types

        self.client = genai.Client(api_key=api_key)
        self.model = model_name or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        self.types = types

    def _convert_schema(self, schema_dict: Dict[str, Any]):
        t = schema_dict.get("type", "object").upper()
        type_enum = getattr(self.types.Type, t, self.types.Type.OBJECT)

        props = None
        if "properties" in schema_dict:
            props = {}
            for k, v in schema_dict["properties"].items():
                props[k] = self._convert_schema(v)

        items = None
        if "items" in schema_dict:
            items = self._convert_schema(schema_dict["items"])

        return self.types.Schema(
            type=type_enum,
            description=schema_dict.get("description"),
            properties=props,
            items=items,
            required=schema_dict.get("required"),
        )

    def generate_turn(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        tools: List[Dict[str, Any]],
    ) -> LLMResponse:
        function_decls = []
        for t in tools:
            param_schema = self._convert_schema(t["parameters"])
            decl = self.types.FunctionDeclaration(
                name=t["name"],
                description=t["description"],
                parameters=param_schema,
            )
            function_decls.append(decl)

        genai_tools = [self.types.Tool(function_declarations=function_decls)] if function_decls else None

        config = self.types.GenerateContentConfig(
            temperature=0.0,
            system_instruction=system_prompt,
            tools=genai_tools,
        )

        # Build contents from messages
        contents = []
        for m in messages:
            role = "user" if m["role"] in ("user", "system") else "model"
            if m["role"] == "tool":
                part = self.types.Part(
                    function_response=self.types.FunctionResponse(
                        name=m.get("tool_name", "tool"),
                        response={"result": m["content"]},
                    )
                )
                contents.append(self.types.Content(role="user", parts=[part]))
            elif m.get("tool_calls"):
                parts = []
                if m.get("content"):
                    parts.append(self.types.Part(text=m["content"]))
                for tc in m["tool_calls"]:
                    parts.append(
                        self.types.Part(
                            function_call=self.types.FunctionCall(
                                name=tc["name"],
                                args=tc["arguments"],
                            )
                        )
                    )
                contents.append(self.types.Content(role="model", parts=parts))
            else:
                contents.append(self.types.Content(role=role, parts=[self.types.Part(text=m["content"])]))

        for attempt in range(3):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=config,
                )
                break
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "401" in err_str or "403" in err_str:
                    raise
                if attempt == 2:
                    raise
                time.sleep(1.0 * (2**attempt))

        candidate = response.candidates[0]
        text_content = ""
        tool_calls = []

        if candidate.content and candidate.content.parts:
            for part in candidate.content.parts:
                if part.text:
                    text_content += part.text
                if part.function_call:
                    tool_calls.append({
                        "id": getattr(part.function_call, "id", None) or f"call_{len(tool_calls)}",
                        "name": part.function_call.name,
                        "arguments": dict(part.function_call.args) if part.function_call.args else {},
                    })

        return LLMResponse(content=text_content, tool_calls=tool_calls)


class GroqAdapter(BaseLLMAdapter):
    """Groq adapter using official groq SDK."""

    def __init__(self, api_key: str, model_name: Optional[str] = None):
        import groq
        self.client = groq.Groq(api_key=api_key)
        self.model = model_name or os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

    def generate_turn(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        tools: List[Dict[str, Any]],
    ) -> LLMResponse:
        openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["parameters"],
                },
            }
            for t in tools
        ]

        formatted_messages = [{"role": "system", "content": system_prompt}]
        for m in messages:
            msg = {"role": m["role"], "content": m.get("content", "")}
            if m.get("tool_calls"):
                msg["tool_calls"] = [
                    {
                        "id": tc.get("id", f"call_{i}"),
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["arguments"]),
                        },
                    }
                    for i, tc in enumerate(m["tool_calls"])
                ]
            if m["role"] == "tool":
                msg["tool_call_id"] = m.get("tool_call_id", "call_0")
            formatted_messages.append(msg)

        resp = self.client.chat.completions.create(
            model=self.model,
            messages=formatted_messages,
            tools=openai_tools if openai_tools else None,
            temperature=0.0,
        )

        choice = resp.choices[0].message
        content = choice.content or ""
        tool_calls = []
        if choice.tool_calls:
            for tc in choice.tool_calls:
                args = {}
                try:
                    args = json.loads(tc.function.arguments)
                except Exception:
                    pass
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": args,
                })

        return LLMResponse(content=content, tool_calls=tool_calls)


class OpenAIAdapter(BaseLLMAdapter):
    """OpenAI adapter."""

    def __init__(self, api_key: str, model_name: Optional[str] = None):
        import openai
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model_name or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    def generate_turn(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        tools: List[Dict[str, Any]],
    ) -> LLMResponse:
        openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["parameters"],
                },
            }
            for t in tools
        ]

        formatted_messages = [{"role": "system", "content": system_prompt}]
        for m in messages:
            msg = {"role": m["role"], "content": m.get("content", "")}
            if m.get("tool_calls"):
                msg["tool_calls"] = [
                    {
                        "id": tc.get("id", f"call_{i}"),
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["arguments"]),
                        },
                    }
                    for i, tc in enumerate(m["tool_calls"])
                ]
            if m["role"] == "tool":
                msg["tool_call_id"] = m.get("tool_call_id", "call_0")
            formatted_messages.append(msg)

        resp = self.client.chat.completions.create(
            model=self.model,
            messages=formatted_messages,
            tools=openai_tools if openai_tools else None,
            temperature=0.0,
        )

        choice = resp.choices[0].message
        content = choice.content or ""
        tool_calls = []
        if choice.tool_calls:
            for tc in choice.tool_calls:
                args = {}
                try:
                    args = json.loads(tc.function.arguments)
                except Exception:
                    pass
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": args,
                })

        return LLMResponse(content=content, tool_calls=tool_calls)


class AnthropicAdapter(BaseLLMAdapter):
    """Anthropic adapter."""

    def __init__(self, api_key: str, model_name: Optional[str] = None):
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model_name or os.environ.get("ANTHROPIC_MODEL", "claude-3-5-haiku-20241022")

    def generate_turn(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        tools: List[Dict[str, Any]],
    ) -> LLMResponse:
        anthropic_tools = [
            {
                "name": t["name"],
                "description": t["description"],
                "input_schema": t["parameters"],
            }
            for t in tools
        ]

        formatted_messages = []
        for m in messages:
            if m["role"] == "system":
                continue
            role = "user" if m["role"] in ("user", "tool") else "assistant"
            content = m.get("content", "")
            formatted_messages.append({"role": role, "content": content})

        resp = self.client.messages.create(
            model=self.model,
            system=system_prompt,
            messages=formatted_messages,
            tools=anthropic_tools,
            temperature=0.0,
            max_tokens=1024,
        )

        content = ""
        tool_calls = []
        for block in resp.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "arguments": block.input,
                })

        return LLMResponse(content=content, tool_calls=tool_calls)


class MockLLMAdapter(BaseLLMAdapter):
    """Deterministic Mock Adapter for tests and when no external LLM key is configured.

    Parses the message intent, simulates function calling (search_parts, check_stock, create_draft_order),
    and enforces strict grounding and prompt injection defenses.
    """

    def generate_turn(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        tools: List[Dict[str, Any]],
    ) -> LLMResponse:
        import re

        last_msg = messages[-1] if messages else {}

        # 1. If previous message was a tool result, formulate the grounded response
        if last_msg.get("role") == "tool":
            tool_content = last_msg.get("content", "")
            tool_name = last_msg.get("tool_name")

            if tool_name == "create_draft_order":
                try:
                    res_json = json.loads(tool_content)
                    if "error" in res_json:
                        short_lines = res_json.get("short_lines", [])
                        if short_lines:
                            desc = ", ".join(f"{s['name']} ({s['sku']}) has only {s['available']} units in stock (requested {s['requested']})" for s in short_lines)
                            return LLMResponse(content=f"Cannot create draft order: Requested quantity exceeds available stock. {desc}.")
                        return LLMResponse(content=f"Cannot create draft order: {res_json['error']}")
                    ord_no = res_json.get("order_number", "")
                    gt = res_json.get("grand_total", "")
                    return LLMResponse(
                        content=f"I have created a DRAFT order {ord_no} for you with total ₹{gt}. Please note that draft orders do not reserve stock until confirmed."
                    )
                except Exception:
                    return LLMResponse(content=f"Order response: {tool_content}")

            if tool_name == "get_order_status":
                try:
                    res_json = json.loads(tool_content)
                    if "error" in res_json:
                        return LLMResponse(content=f"Order status check: {res_json['error']}")
                    if "order_number" in res_json:
                        return LLMResponse(
                            content=f"Order {res_json['order_number']} is currently in {res_json['status']} status with {res_json['items_count']} items, grand total ₹{res_json['grand_total']}."
                        )
                    recent = res_json.get("recent_orders", [])
                    if not recent:
                        return LLMResponse(content="You have no recorded orders at this time.")
                    summary = "; ".join(f"{o['order_number']} ({o['status']}, ₹{o['grand_total']})" for o in recent[:3])
                    return LLMResponse(content=f"Here are your latest dealership orders: {summary}.")
                except Exception:
                    return LLMResponse(content=f"Order status info: {tool_content}")

            if tool_name == "check_stock":
                try:
                    res_json = json.loads(tool_content)
                    if "error" in res_json:
                        return LLMResponse(content=f"Sorry, {res_json['error']}")
                    sku = res_json.get("sku")
                    name = res_json.get("name")
                    price = res_json.get("price")
                    stock = res_json.get("stock")
                    return LLMResponse(
                        content=f"{name} ({sku}) is currently priced at ₹{price} with {stock} units in stock."
                    )
                except Exception:
                    return LLMResponse(content=f"Stock info: {tool_content}")

            if tool_name == "search_parts":
                try:
                    res_json = json.loads(tool_content)
                    parts = res_json.get("parts", [])
                    if not parts:
                        return LLMResponse(content="I could not find any matching parts in our catalogue.")
                    p0 = parts[0]
                    return LLMResponse(
                        content=f"We have {p0['name']} ({p0['sku']}) for ₹{p0['price']} with {p0['stock']} units available."
                    )
                except Exception:
                    return LLMResponse(content=f"Catalogue results: {tool_content}")

        # 2. Inspect latest user message to decide on tool call or text reply
        user_text = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_text = m.get("content", "")
                break

        lower = user_text.lower()
        sku_match = re.search(r"\b[A-Z]{3}-\d{4}\b", user_text.upper())
        qty_match = re.search(r"\b(?:order|put|reserve|aside|need|take)\s+(\d+)", lower) or re.search(r"(\d+)\s+(?:units|pieces|sets|items)", lower)

        # Check for off-topic queries
        off_topic_keywords = ["weather", "poem", "python code", "president", "politics", "recipe", "write a story", "tell me a joke"]
        if any(kw in lower for kw in off_topic_keywords):
            return LLMResponse(
                content="I am DealerDesk's assistant and can only assist with automotive parts, catalogue inquiries, stock checks, and draft orders."
            )

        # Check for greeting or capability questions (when not asking for a specific part or order)
        greeting_words = {"hello", "hi", "hey", "good morning", "good afternoon", "good evening", "greetings"}
        capability_phrases = ["what can you do", "who are you", "what are your features", "how do you work", "help me"]
        tokens = set(re.findall(r"\w+", lower))
        has_part_intent = any(k in lower for k in ["brake", "pad", "oil", "filter", "chain", "sprocket", "plug", "tyre", "tire", "battery", "light", "stock", "price", "cost", "order", "status"])
        if (tokens.intersection(greeting_words) or any(phrase in lower for phrase in capability_phrases) or lower.strip() in ("help", "help?")) and not sku_match and not has_part_intent:
            return LLMResponse(
                content="Hello! I am your DealerDesk Assistant. I can help you search our automotive parts catalogue, check real-time stock and prices, verify order status, and create draft orders. How can I assist you today?"
            )

        # Check for ambiguity (e.g. "brake pads" without vehicle)
        if "brake pad" in lower or "brake shoe" in lower or "brakes" in lower:
            # Check if any vehicle is mentioned
            has_vehicle = any(v.lower() in lower for v in [
                "duke", "pulsar", "apache", "bullet", "classic", "hunter", "r15", "gixxer",
                "swift", "creta", "thar", "splendor", "shine", "hornet", "dominar", "fz", "mt"
            ])
            if not has_vehicle:
                return LLMResponse(
                    content="Which vehicle model do you need brake pads for? (e.g., KTM Duke 390, Bajaj Pulsar 150)"
                )

        # Check for order status intent: e.g. "what is the status of ORD-20261011-0001", "check my recent orders"
        ord_pattern = re.search(r"\bORD-\d{8}-\d{4}\b", user_text.upper())
        if ord_pattern or any(w in lower for w in ["order status", "my order", "my orders", "status of order", "recent order"]):
            return LLMResponse(
                tool_calls=[{
                    "id": "call_order_status",
                    "name": "get_order_status",
                    "arguments": {"order_number": ord_pattern.group(0) if ord_pattern else None},
                }]
            )

        # Check for order creation intent: e.g. "put 10 aside for me", "order 5 units of BRK-1044"
        if "put" in lower and "aside" in lower and not sku_match:
            # Ambiguous: put aside without SKU
            # Check if previous message discussed a SKU
            prev_sku = None
            for m in reversed(messages[:-1]):
                m_sku = re.search(r"\b[A-Z]{3}-\d{4}\b", m.get("content", ""))
                if m_sku:
                    prev_sku = m_sku.group(0)
                    break
            if not prev_sku:
                return LLMResponse(content="Which product SKU would you like to put aside?")
            qty = int(qty_match.group(1)) if qty_match else 10
            return LLMResponse(
                tool_calls=[{
                    "id": "call_draft_order",
                    "name": "create_draft_order",
                    "arguments": {"items": [{"sku": prev_sku, "quantity": qty}]},
                }]
            )

        # Incomplete order intent: e.g. "I want to place an order", "buy some parts", or general "order" without sku
        if any(w in lower for w in ["draft order", "place order", "place an order", "want to order", "create order", "buy parts", "make an order"]) or ("order" in lower and not sku_match and not qty_match):
            return LLMResponse(content="Which product SKU and how many units would you like to include in this draft order?")
        if sku_match and not qty_match and any(w in lower for w in ["order", "put aside", "draft", "reserve", "buy"]):
            return LLMResponse(content=f"How many units of {sku_match.group(0)} would you like to draft?")

        if any(w in lower for w in ["order", "put", "reserve", "draft", "buy"]) and sku_match:
            sku = sku_match.group(0)
            qty = int(qty_match.group(1)) if qty_match else 1
            return LLMResponse(
                tool_calls=[{
                    "id": "call_draft_order",
                    "name": "create_draft_order",
                    "arguments": {"items": [{"sku": sku, "quantity": qty}]},
                }]
            )

        # Check for SKU inquiry intent (if user mentions a SKU and is not ordering)
        if sku_match:
            sku = sku_match.group(0)
            return LLMResponse(
                tool_calls=[{
                    "id": "call_check_stock",
                    "name": "check_stock",
                    "arguments": {"sku": sku},
                }]
            )

        # Broad browsing intent: "what products do you have", "show catalogue", "list available products"
        if any(w in lower for w in ["list products", "available products", "catalogue", "what products", "show products", "what parts"]):
            return LLMResponse(
                tool_calls=[{
                    "id": "call_search_parts",
                    "name": "search_parts",
                    "arguments": {"query": "filter", "category": "Filters"},
                }]
            )

        # Default catalogue search:
        # Extract vehicle and category using hybrid retrieval normalization
        from assistant.retrieval import normalize_vehicle, normalize_category
        vehicle = normalize_vehicle(user_text)
        category = normalize_category(user_text)

        return LLMResponse(
            tool_calls=[{
                "id": "call_search_parts",
                "name": "search_parts",
                "arguments": {"query": user_text, "vehicle": vehicle, "category": category},
            }]
        )


_FAILED_PROVIDERS: Set[str] = set()


class ResilientLLMAdapter(BaseLLMAdapter):
    """Wraps an external LLM adapter with automatic seamless fallback to MockLLMAdapter."""

    def __init__(self, primary: BaseLLMAdapter, fallback: BaseLLMAdapter):
        self.primary = primary
        self.fallback = fallback
        provider_name = type(primary).__name__
        self.primary_failed = provider_name in _FAILED_PROVIDERS
        self.mode = "rule_based" if self.primary_failed else ("gemini" if isinstance(primary, GeminiAdapter) else "external")

    def generate_turn(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        tools: List[Dict[str, Any]],
    ) -> LLMResponse:
        provider_name = type(self.primary).__name__
        if not self.primary_failed and provider_name not in _FAILED_PROVIDERS:
            try:
                return self.primary.generate_turn(messages, system_prompt, tools)
            except Exception as e:
                logger.warning(
                    "Primary LLM adapter (%s) request failed (%s). Falling back to MockLLMAdapter.",
                    provider_name,
                    e,
                )
                self.primary_failed = True
                _FAILED_PROVIDERS.add(provider_name)
                self.mode = "rule_based"

        return self.fallback.generate_turn(messages, system_prompt, tools)


def get_llm_adapter() -> BaseLLMAdapter:
    """Instantiate and return the highest priority available LLM adapter, wrapped with resilient fallback."""
    # Check force mock flag (e.g. in test environment)
    if os.environ.get("USE_MOCK_LLM", "0") == "1":
        return MockLLMAdapter()

    fallback = MockLLMAdapter()

    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if gemini_key:
        try:
            return ResilientLLMAdapter(GeminiAdapter(api_key=gemini_key), fallback)
        except Exception as e:
            logger.warning("Failed to initialize GeminiAdapter: %s", e)

    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    if groq_key:
        try:
            return ResilientLLMAdapter(GroqAdapter(api_key=groq_key), fallback)
        except Exception as e:
            logger.warning("Failed to initialize GroqAdapter: %s", e)

    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if openai_key:
        try:
            return ResilientLLMAdapter(OpenAIAdapter(api_key=openai_key), fallback)
        except Exception as e:
            logger.warning("Failed to initialize OpenAIAdapter: %s", e)

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if anthropic_key:
        try:
            return ResilientLLMAdapter(AnthropicAdapter(api_key=anthropic_key), fallback)
        except Exception as e:
            logger.warning("Failed to initialize AnthropicAdapter: %s", e)

    # Fallback to MockAdapter if no provider keys are configured
    logger.info("No active LLM provider keys found; falling back to MockLLMAdapter.")
    return fallback
