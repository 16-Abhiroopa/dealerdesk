"""Native tool declarations and executions for DealerDesk Assistant.

Tools:
1. search_parts(query, vehicle=None, category=None)
2. check_stock(sku)
3. create_draft_order(items=[{"sku", "quantity"}])
"""
from typing import Dict, Any, List, Optional, Tuple
from core.utils import format_money
from products.models import Product
from orders import services
from assistant.retrieval import search_catalogue

# JSON Schema for function declarations
TOOL_DEFINITIONS = [
    {
        "name": "search_parts",
        "description": "Search the parts catalogue for motorcycle and car spares. Returns top matching products with live stock and current price.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search terms such as part name, type, or brand (e.g. 'brake pads', 'oil filter', 'chain kit').",
                },
                "vehicle": {
                    "type": "string",
                    "description": "Specific vehicle make and model (e.g. 'KTM Duke 390', 'Bajaj Pulsar 150', 'Universal').",
                },
                "category": {
                    "type": "string",
                    "description": "Product category (e.g. 'Brakes', 'Engine & Oils', 'Filters', 'Drivetrain').",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "check_stock",
        "description": "Check real-time stock quantity and catalogue price for a specific product SKU.",
        "parameters": {
            "type": "object",
            "properties": {
                "sku": {
                    "type": "string",
                    "description": "The exact product SKU code (e.g. 'BRK-1044', 'OIL-1001').",
                },
            },
            "required": ["sku"],
        },
    },
    {
        "name": "create_draft_order",
        "description": "Create a DRAFT order for the dealer with the specified items. Note: DRAFT orders do NOT deduct stock and require dealer confirmation later.",
        "parameters": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "description": "List of items to include in the order.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "sku": {
                                "type": "string",
                                "description": "The product SKU.",
                            },
                            "quantity": {
                                "type": "integer",
                                "description": "Quantity to order (must be an integer >= 1).",
                            },
                        },
                        "required": ["sku", "quantity"],
                    },
                },
            },
            "required": ["items"],
        },
    },
]


def execute_tool(
    name: str,
    arguments: Dict[str, Any],
    dealer_id: int,
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    """Execute a tool call safely.

    Returns (tool_result_dict, action_or_none).
    Exceptions are caught and returned as error dicts so the model can handle them.
    """
    try:
        if name == "search_parts":
            query = arguments.get("query", "")
            vehicle = arguments.get("vehicle")
            category = arguments.get("category")
            results = search_catalogue(query=query, vehicle=vehicle, category=category)
            if not results:
                return {"message": "No matching parts found for the given search criteria.", "parts": []}, None
            return {"parts": results}, None

        elif name == "check_stock":
            sku = (arguments.get("sku") or "").strip()
            if not sku:
                return {"error": "SKU parameter is required."}, None
            product = Product.objects.select_related("inventory").filter(sku=sku).first()
            if not product:
                return {"error": f"SKU '{sku}' not found in catalogue."}, None
            return {
                "sku": product.sku,
                "name": product.name,
                "category": product.category,
                "brand": product.brand,
                "vehicle_fitment": product.vehicle_fitment,
                "price": format_money(product.price),
                "stock": product.stock,
            }, None

        elif name == "create_draft_order":
            items = arguments.get("items")
            if not items or not isinstance(items, list):
                return {"error": "Items list is required to create a draft order."}, None

            short_lines = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                sku = item.get("sku")
                quantity = item.get("quantity")
                if not isinstance(sku, str) or isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
                    continue
                product = Product.objects.select_related("inventory").filter(sku=sku).first()
                if product and quantity > product.stock:
                    short_lines.append({
                        "sku": product.sku,
                        "name": product.name,
                        "requested": quantity,
                        "available": product.stock,
                    })
            if short_lines:
                return {
                    "error": "Requested quantity exceeds current available stock.",
                    "short_lines": short_lines,
                }, None

            order, created = services.create_draft_order(
                dealer_id=dealer_id,
                items_data=items,
            )
            action = {
                "type": "draft_order_created",
                "order_number": order.order_number,
            }
            return {
                "order_number": order.order_number,
                "status": order.status,
                "subtotal": format_money(order.subtotal),
                "tax_total": format_money(order.tax_total),
                "grand_total": format_money(order.grand_total),
                "message": f"Draft order {order.order_number} created successfully.",
            }, action

        else:
            return {"error": f"Unknown tool: '{name}'"}, None

    except Exception as e:
        return {"error": f"Tool execution failed: {str(e)}"}, None
