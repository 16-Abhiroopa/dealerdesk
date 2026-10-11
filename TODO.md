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
  - Committed in `a597ccd`.

- [x] **Phase 3: Forecasting & Reorder Suggestions (Part D - ML)**
  - Feature engineering and chronological backtesting (zero future leakage, strictly using data <= train_cutoff).
  - Multiplicative decomposition model capturing moving Diwali lift curve (`weeks_to_diwali`) and planned promotional boosts.
  - Beats all three baselines (Naive last, 4-week moving average, same-week last year) on all evaluation splits.
  - Generated and committed `ml/forecast.csv` (160 rows across 40 SKUs for the 4 forecast weeks).
  - Implemented endpoints:
    - `GET /api/forecast/{sku}/` (4-week forecast or 404 with exact contract error shape).
    - `GET /api/reorder-suggestions/` (40 items computed using exact formulas for lead time demand, sample std dev $\sigma$, safety stock, and live stock).
  - Comprehensive unit tests in `tests/test_forecasting.py` passing (4 tests).
  - Committed in `b824bbc`.

- [x] **Phase 4: Supplier Sync Integration (Part B - Bonus)**
  - Implemented resilient paginated feed fetcher adhering strictly to §8 of API_CONTRACT.md.
  - Resilient retries on 429 (`Retry-After`), 5xx (exponential backoff), and connection errors up to 5 attempts per page.
  - All-or-nothing guarantee: returns 502 `SUPPLIER_UNAVAILABLE` on unrecovered failures without dirty writes.
  - Data hygiene: filters and lists `rejected` for invalid prices or missing SKUs, deduplicates by latest `updated_at`.
  - Catalogue reconciliation: updates differing fields, creates new items with stock 0, never touches local inventory stock.
  - Idempotent: verified subsequent runs change nothing (`created: 0, updated: 0`).
  - Passes 12/12 checks in `smoke_test.py --all` and 2 dedicated unit tests.

- [x] **Phase 5: Full Smoke Test Validation & Comprehensive Documentation**
  - Full smoke test passing: `smoke_test.py --track aiml` (10/10) and `smoke_test.py --all` (12/12).
  - Total test suite: 24/24 unit tests passing in pytest across all apps.
  - Complete `DECISIONS.md` thoroughly answering all 8 viva questions with exact code citations and ML metrics.
  - Updated `README.md` with LLM provider details, default models, setup instructions, and architecture breakdown.
