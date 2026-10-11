# VIKMO DealerDesk — AI / ML Track Implementation

An AI-native commerce and inventory management backend built with Django REST Framework and PostgreSQL, featuring an autonomous conversational parts ordering agent and a demand forecasting engine.

---

## 1. Supported LLM Providers & Models

The Dealer Assistant (`POST /api/assistant/chat/`) automatically adapts to the available API key in environment variables:

| Provider | Environment Variable | Default Model | SDK Used |
|---|---|---|---|
| **Google Gemini** | `GEMINI_API_KEY` | `gemini-2.5-flash` | `google-genai` |
| **Groq** | `GROQ_API_KEY` | `llama-3.3-70b-versatile` | `groq` |
| **OpenAI** | `OPENAI_API_KEY` | `gpt-4o-mini` | `openai` |
| **Anthropic** | `ANTHROPIC_API_KEY` | `claude-3-5-haiku-20241022` | `anthropic` |
| **Offline / Test Mock** | `USE_MOCK_LLM=1` | Deterministic Rule-Based Agent | Built-in |

---

## 2. Setup & Run Contract

### Prerequisites:
- Python 3.11+
- PostgreSQL database (e.g. Neon, Supabase, or local PostgreSQL)

### Running Locally:
```bash
# 1. Activate virtual environment
python -m venv .venv
source .venv/bin/activate    # On Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your DATABASE_URL and LLM provider key

# 4. Migrate and Seed Database (seeded twice to verify idempotency)
python manage.py migrate --noinput
python manage.py seed_data
python manage.py seed_data

# 5. Start dev server
python manage.py runserver 0.0.0.0:8000 --noreload
```

---

## 3. Verification & Smoke Testing

### Run Pytest Suite:
```bash
pytest
```
*Executes all 22 comprehensive unit tests across core models, draft orders, assistant tool loop, grounding verifications, session isolation, and ML reorder suggestions.*

### Run Smoke Test:
```bash
python smoke_test.py --base-url http://localhost:8000 --track aiml
```
*Validates 10/10 contract checks: Health, Products, Dealers, Inventory, Draft Orders, Validation Errors, Dealer Assistant, and Forecasting endpoints.*

---

## 4. Key Components

- **Backend Core & Order Engine**: Relational schema (`Product`, `Inventory`, `Dealer`, `Order`, `OrderItem`, `IdempotencyKey`), atomic order confirmation with `select_for_update` stock lock, line-by-line 18% GST calculation, and daily sequence order numbering `ORD-YYYYMMDD-NNNN`.
- **Dealer Assistant (GenAI)**: Autonomous multi-step tool-calling agent (`search_parts`, `check_stock`, `create_draft_order`) with live PostgreSQL grounding, prompt injection defenses against adversarial supplier descriptions, and session isolation.
- **Forecasting & Reorder (ML)**: Decomposed demand forecasting model incorporating relative Diwali festive lift (`weeks_to_diwali`), planned promotional boosts, and cold-start mitigations. Generates `ml/forecast.csv` (160 rows across 40 SKUs) and powers `/api/forecast/{sku}/` and `/api/reorder-suggestions/`.
- **Technical Decisions & Viva Answers**: Full explanations, architecture walk-throughs, and code citations are available in [DECISIONS.md](DECISIONS.md).

---

## 5. Video Walkthrough

- **Link**: *[Walkthrough Video Link (Unlisted YouTube / Loom / Google Drive)]*
- **Focus**: AI/ML track assistant tool-calling loop, live database grounding, prompt injection defenses, and ML backtesting results.
