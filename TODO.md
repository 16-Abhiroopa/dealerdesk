# VIKMO DealerDesk Project Implementation Plan & Progress

- [x] **Phase 1: Backend Core (A1) & Order Engine (A2)**
  - Schema design: Product, Inventory, Dealer, Order, OrderItem, IdempotencyKey.
  - Endpoints: Products (list/filter, create, detail, patch), Inventory PUT, Dealers (list, create, detail).
  - Orders: DRAFT creation, update, cancel, confirm (atomic with select_for_update stock lock, all-or-nothing), dispatch, deliver.
  - Financial calculations: 18% GST line-by-line ROUND_HALF_UP exact paisa, order numbers `ORD-YYYYMMDD-NNNN` in Asia/Kolkata.
  - Tests passing: Products, Dealers, Inventory, Orders, Seeding idempotency.
  - Committed in `d9a9473`.

- [x] **Phase 2: Dealer Assistant (Part C - GenAI)**
  - Architecture: Multi-step tool-calling agent with native adapters (Gemini, Groq, OpenAI, Anthropic, Mock fallback).
  - Tools: `search_parts`, `check_stock`, `create_draft_order` (reusing `orders.services.create_draft_order`).
  - Strict grounding: Price and stock numbers verified against live DB tool results in the current turn.
  - Defenses: Neutralizes prompt injection in untrusted supplier descriptions (e.g., CHN-1037 discount codes, BDY-1070 instructions).
  - Memory: PostgreSQL session-isolated message history; refuses to mix session context.
  - Safety: Never confirms orders, declines off-topic prompts, asks clarifying questions on ambiguous queries.
  - Tests passing: 6 tests covering validation, off-topic, ambiguity, grounding, multi-turn, isolation.

- [ ] **Phase 3: Forecasting & Reorder Suggestions (Part D - ML)**
  - Data ingestion & feature engineering on `sales_history.csv`, `lead_times.csv`, `promo_calendar.csv`, `festival_calendar.csv`.
  - Chronological backtesting with zero future leakage (rolling window validation).
  - Model comparison: Baselines (Naive/Last value, 4-week moving average, same-week last year seasonal) vs. ML (LightGBM/Ridge regression with lag features, promo, and festive distance).
  - Forecast generation: Export exactly 160 rows into `ml/forecast.csv` for the 40 SKUs across the 4 future weeks.
  - API endpoints:
    - `GET /api/forecast/{sku}/`: returns 4-week forecast for valid forecast SKUs, 404 otherwise.
    - `GET /api/reorder-suggestions/`: 40 items computed using exact formulas for lead time demand, sample std dev $\sigma$, safety stock, and live stock.
  - Unit tests for forecasting APIs and calculation fidelity.

- [ ] **Phase 4: Smoke Test Validation & Comprehensive Documentation**
  - Run full `smoke_test.py --track aiml` and `--all`.
  - Complete `DECISIONS.md` addressing all 8 questions required in the assignment brief.
  - Update `README.md` with instructions, model details, setup steps, and architecture overview.
