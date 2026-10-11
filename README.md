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
- PostgreSQL database (e.g. Neon, Supabase, Render, or local PostgreSQL)

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

## 3. Cloud Deployment (Render / Railway / Docker)

The repository includes ready-to-deploy Infrastructure-as-Code configurations:

### Option A: Deploy to Render (Recommended Free PaaS)
1. Push this repository to GitHub.
2. Sign up on [Render.com](https://render.com) and click **New > Blueprint**.
3. Select your GitHub repository.
4. Render automatically parses [`render.yaml`](render.yaml), provisions a **free PostgreSQL database** (`dealerdesk-db`), runs migrations, seeds data, and launches the web service with Gunicorn.
5. In your Render Dashboard, add your `GEMINI_API_KEY` (or `GROQ_API_KEY`) under Environment Variables.

### Option B: Deploy to Railway
1. Sign up on [Railway.app](https://railway.app).
2. Click **New Project > Deploy from GitHub repo**.
3. Add a **PostgreSQL** database service in Railway.
4. Set the `DATABASE_URL` environment variable reference `${{Postgres.DATABASE_URL}}`.
5. Railway automatically detects [`railway.toml`](railway.toml) and [`Procfile`](Procfile), runs migrations, seeds data, and starts the service.

### Option C: Containerized Deployment (Docker Compose)
To run locally or on any VPS using Docker:
```bash
docker compose up --build
```
This spins up PostgreSQL on port `5432` and DealerDesk on port `8000`, running automatic migrations and idempotent data seeding.

---

## 4. Verification & Smoke Testing

### Run Pytest Suite:
```bash
pytest
```
*Executes all 24 comprehensive unit tests across core models, draft orders, assistant tool loop, grounding verifications, session isolation, ML reorder suggestions, and supplier sync.*

### Run Smoke Test:
```bash
# AI/ML track verification
python smoke_test.py --base-url http://localhost:8000 --track aiml

# Complete contract verification (12/12 passing including all optional parts)
python smoke_test.py --base-url http://localhost:8000 --all
```

---

## 5. Key Architecture Components

- **Backend Core & Order Engine**: Relational schema (`Product`, `Inventory`, `Dealer`, `Order`, `OrderItem`, `IdempotencyKey`), atomic order confirmation with `select_for_update` stock locks, line-by-line 18% GST calculation, and daily sequence order numbering `ORD-YYYYMMDD-NNNN`.
- **Dealer Assistant (GenAI)**: Autonomous multi-step tool-calling agent (`search_parts`, `check_stock`, `create_draft_order`) with live PostgreSQL grounding, prompt injection defenses against adversarial supplier descriptions, and session isolation.
- **Forecasting & Reorder (ML)**: Decomposed demand forecasting model incorporating relative Diwali festive lift (`weeks_to_diwali`), planned promotional boosts, and cold-start mitigations. Generates `ml/forecast.csv` (160 rows across 40 SKUs) and powers `/api/forecast/{sku}/` and `/api/reorder-suggestions/`.
- **Resilient Supplier Sync**: Paginated sync engine with 429 `Retry-After` honoring, exponential backoff for 5xx/network errors, all-or-nothing transactional commits, and invalid/duplicate SKU sanitation.
- **Technical Decisions & Viva Answers**: Full explanations, architecture walk-throughs, and code citations are available in [DECISIONS.md](DECISIONS.md).

---

## 6. Video Walkthrough

- **Link**: *[Walkthrough Video Link (Unlisted YouTube / Loom / Google Drive)]*
- **Focus**: AI/ML track assistant tool-calling loop, live database grounding, prompt injection defenses, and ML backtesting results.
