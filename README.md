# SpendShield AI
### *"Know before you spend."*

An AI-powered financial behaviour intelligence platform for Indian college students,
PG residents, and young professionals — built to answer **"why am I spending this,
and what happens if I keep going?"**, not just "where did my money go?"

---

## 1. Product thesis

Digital payments (UPI, cards, wallets) removed the friction that used to make
spending *feel* like spending. A student can lose ₹3,000/month to twenty ₹150
payments without ever "deciding" to spend ₹3,000.

SpendShield doesn't just log transactions — it:

- Computes a live **Safe-to-Spend-Today** figure from real budget arithmetic
- Scores **impulse purchases** with an explainable, itemised breakdown
- Projects **end-of-month overspend** before it happens
- Introduces deliberate, non-shaming **friction** ahead of risky discretionary spending
- Lets an **AI copilot** explain all of it — using tools, never invented numbers

**The rule the whole architecture is built around:**

> The LLM never calculates a rupee figure. It only explains numbers that came out
> of deterministic, unit-tested backend code.

That is why `app/services/safe_to_spend.py` has zero dependency on FastAPI, the
database, or any LLM. It is pure, tested, swappable logic.

---

## 2. Quick start

```bash
docker compose up --build
```

That's the whole setup. The backend applies its own database migrations on
startup, so there is no separate schema step.

- Dashboard → http://localhost:5173
- API docs → http://localhost:8000/docs
- Health → http://localhost:8000/health

Then click **"Explore with demo data"** on the login screen. It provisions a
throwaway account with a budget and two months of realistic synthetic
transactions, so you get a fully populated dashboard without typing anything.

> If a native Postgres already occupies port 5432 on your machine, start with
> `DB_PORT=55432 docker compose up --build` — the host binding is overridable.

No Docker? Run the pieces directly:

```bash
cd backend
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
DATABASE_URL="sqlite:///./dev.sqlite3" .venv/bin/alembic upgrade head
DATABASE_URL="sqlite:///./dev.sqlite3" .venv/bin/uvicorn app.main:app --reload
```

```bash
cd frontend && npm install && npm run dev
```

The copilot is the only feature that needs an API key. Leave `LLM_API_KEY` unset
and everything else works; `/api/v1/copilot/chat` returns a clear 503.

---

## 3. Tests

```bash
cd backend && pytest -q          # 74 passing
cd frontend && npm test          # 28 passing
```

Three layers:

- **Financial engine tests** — pure functions, no database, no framework.
  Safe-to-spend, impulse scoring, intervention escalation, runway, forecasting,
  velocity, anomaly detection.
- **API integration tests** — real routers, real SQLAlchemy, real JWT auth,
  against an in-memory database. Covers auth and rate limiting, per-user data
  isolation, budget validation, demo provisioning, and regressions for specific
  bugs (see §7).
- **Copilot tool-loop tests** — the tool-calling loop driven by a scripted stub
  of the Anthropic client, so it is covered without an API key or spend. Asserts
  that tool results reaching the model are byte-identical to what the REST API
  returns, that parallel tool calls come back in a single user message, and that
  no failure path (unknown tool, tool exception, iteration cap, refusal, rate
  limit, auth error, upstream 500) produces a 500 or leaks a provider message.
  `app/api/copilot.py` and `app/services/financial_context.py` are at 100%
  statement coverage.

The frontend has its own 28 tests (Vitest + Testing Library): the fetch client's
error and 401 handling, the gauge's mapping from health score to arc, budget
validation, and the dashboard's no-budget empty state. See `frontend/README.md`.

The suite runs against **both SQLite and Postgres** in CI, because SQLite is the
more permissive engine and silently accepts queries Postgres rejects.

```bash
TEST_DATABASE_URL="postgresql+psycopg://spendshield:spendshield@localhost:55432/spendshield" pytest -q
```

---

## 4. What's implemented

| Component | Status |
|---|---|
| Safe-to-Spend engine (deterministic, unit-tested) | ✅ |
| Impulse-score engine (explainable heuristic v1) | ✅ |
| Intervention escalation engine (levels 0–5) | ✅ |
| Financial runway calculator | ✅ |
| Purchase evaluation ("Should I buy this?") | ✅ |
| Forecasting (exponential smoothing) + velocity + z-score anomalies | ✅ |
| Budget CRUD with per-category allocations | ✅ |
| Transactions: create (impulse-scored on write), filter, paginate, delete | ✅ |
| JWT auth, bcrypt hashing, per-IP rate limiting, account deletion | ✅ |
| Tool-calling AI copilot (`POST /api/v1/copilot/chat`, 4 tools) | ✅ |
| One-click demo account with synthetic data | ✅ |
| Alembic migrations, applied automatically on deploy | ✅ |
| React + TypeScript dashboard | ✅ |
| Docker Compose, Render blueprint, Vercel config, GitHub Actions CI | ✅ |
| ML classifier, Prophet/XGBoost forecasting, OCR, RAG, LangGraph agents | 📋 Designed, not built |

### API surface

| Method | Path | |
|---|---|---|
| POST | `/api/v1/auth/register` | JSON body |
| POST | `/api/v1/auth/login` | OAuth2 password form |
| GET / DELETE | `/api/v1/auth/me` | current user; delete cascades all data |
| POST | `/api/v1/demo` | provision a populated demo account |
| PUT / GET | `/api/v1/budgets` | upsert (idempotent per month) / list |
| GET | `/api/v1/budgets/current` | this month's budget |
| POST / GET | `/api/v1/transactions` | create (impulse-scored) / list with filters |
| DELETE | `/api/v1/transactions/{id}` | |
| GET | `/api/v1/safe-to-spend` | the headline number + why |
| POST | `/api/v1/purchase/evaluate` | recommendation, impulse signals, intervention level |
| GET | `/api/v1/forecast` | month-end projection |
| GET | `/api/v1/analytics/velocity` | ₹/day actual vs. required |
| GET | `/api/v1/analytics/categories` | this month's spend by category |
| POST | `/api/v1/copilot/chat` | tool-calling copilot |
| GET | `/health` | 503 when the database is unreachable |

---

## 5. Architecture

```mermaid
flowchart TD
    UI[React + TypeScript dashboard] -->|REST + JWT| API[FastAPI routes]
    COPILOT[Copilot: Anthropic tool-use loop] --> API
    API --> FC[services/financial_context.py<br/>DB → engine adapter]
    COPILOT -->|same tools| FC
    FC --> ENG[Pure engines:<br/>safe_to_spend · impulse_score<br/>intervention · forecasting]
    FC --> DB[(PostgreSQL)]
    ENG -.->|no DB, no framework, no LLM| ENG
```

The important edge is that **the copilot and the REST API both go through
`financial_context`**, so the chat and the dashboard can never disagree about a
number. The engines below it have no imports from FastAPI, SQLAlchemy, or any
LLM SDK, which is what makes them unit-testable in isolation.

### Safe-to-Spend formula

```
remaining_budget        = monthly_budget − spent_so_far
protected_pool          = upcoming_obligations + predicted_essential_spend + savings_target
free_discretionary_pool = max(remaining_budget − protected_pool, 0)
safe_to_spend_today     = free_discretionary_pool / days_remaining
```

Risk compares **current spending velocity** against the velocity required to hit
budget *and* savings target — a ratio, not a vibe. Every response carries an
`explanation_factors` list stating each input in plain language.

### Copilot

```
User: "Can I spend ₹700 on dinner tonight?"
   ↓ LLM selects a tool
evaluate_purchase(price=700, category="food_delivery")
   ↓ backend runs the deterministic engine against real rows
{affordability_score, recommendation, impulse_reasons, intervention_level}
   ↓
LLM explains it conversationally — it never produced the numbers
```

Tool schemas and executors: `backend/app/agents/copilot_tools.py`.

---

## 6. Data model

```mermaid
erDiagram
    USERS ||--o{ TRANSACTIONS : has
    USERS ||--o{ BUDGETS : has
    BUDGETS ||--o{ BUDGET_RULES : contains
```

`users` → `transactions` (amount, merchant, category, date, essential/recurring/income
flags, impulse_score, source) and `budgets` (month, year, total_income,
savings_target) → `budget_rules` (per-category allocation).

Deletes cascade from the user, so "delete my account" removes every row.
`(user_id, month, year)` is unique on budgets, enforced by the database rather
than by a check-then-insert in application code.

---

## 7. Correctness notes

Several bugs found and fixed by running the thing rather than reading it — each
has a regression test:

- **Recurring costs accumulated forever.** `upcoming_obligations` summed *every*
  recurring transaction ever dated before the current month, so after six months
  of ₹8,000 rent it reserved ₹48,000 against a ₹15,000 budget and pinned
  safe-to-spend at zero. It now projects last month's recurring charges forward
  and excludes the ones already paid this month.
- **Rent was projected as a daily rate.** A single ₹6,500 charge on the 3rd was
  averaged over elapsed days and extrapolated across the rest of the month,
  inventing thousands of rupees of phantom essential spend. Recurring essentials
  are now excluded from that average; fixed costs are handled by
  `upcoming_obligations` instead.
- **Two different "required pace" numbers.** The dashboard showed HIGH risk at
  +9% deviation next to ON_PACE at −3.2%, because safe-to-spend netted out the
  savings target and the velocity endpoint didn't. They now share one definition.
- **`transactions_same_category_last_7d` ignored the 7-day window**, counting all
  transactions ever in the category, so a heavy user was permanently pinned at
  the maximum frequency penalty.
- **A missing category budget implied a ₹1 weekly budget** (`(x or 0)/4 or 1`),
  which flagged every purchase as over budget. Unknown now means unknown.
- **`impulse_score` was never computed.** The column existed and every row held 0;
  it is now scored at write time against the account state before the row exists.
- **Elapsed days were counted exclusively** while remaining days were inclusive,
  so a 20-day-elapsed month read as 19 and overstated velocity.

---

## 8. Security

- Registration takes a **JSON body**. It previously took `?email=&password=` as
  query parameters, which writes credentials into access logs, browser history,
  and `Referer` headers.
- **PyJWT** instead of `python-jose` 3.3.0 (CVE-2024-33663 algorithm confusion,
  CVE-2024-33664 JWT bomb). The decode call pins the algorithm list rather than
  trusting the token header.
- **bcrypt directly** instead of `passlib`, which has been unmaintained since 2020
  and crashes against bcrypt ≥ 4.1. Passwords are SHA-256 pre-hashed so bcrypt's
  72-byte truncation can't make `<72 correct bytes> + anything` a valid password.
- **Per-IP rate limiting** on register, login, demo provisioning, and the copilot.
- **Login is uniform** on unknown-email and wrong-password, so it can't be used to
  enumerate registered addresses.
- **`ENV=production` refuses to boot** with the default or short `JWT_SECRET`, or
  with `localhost` still in `CORS_ORIGINS`, and disables `/docs`.
- Unhandled exceptions log server-side and return a generic message; provider
  errors from the LLM are never forwarded to the client.
- Cross-user access is tested: another user's transaction is a 404, not a 403,
  so the response can't confirm that an id exists.

---

## 9. Dependencies

`pandas`, `scikit-learn`, `xgboost`, `qdrant-client`, `celery`, and `redis` were
declared as runtime requirements but **not imported by a single line of code**.
They added roughly 700 MB to the image and made `pip install` fail outright on
Python 3.13. They were removed; the backend image is now 360 MB. They come back
when the Phase 2–4 code that needs them actually lands.

Redis and Qdrant were dropped from `docker-compose.yml` for the same reason.

---

## 10. Roadmap

- **Phase 2 — Intelligence:** ML transaction classifier, Prophet/XGBoost
  forecasting once a user has 90+ days of history, Isolation Forest anomalies.
- **Phase 3 — Agentic:** LangGraph multi-agent orchestration, "what-if" simulator.
- **Phase 4 — Advanced:** OCR receipt extraction, RAG financial-education base,
  behavioural clustering, SHAP explainability.
- **Phase 5 — Production:** observability and token/cost tracking, CSV import,
  refresh tokens, Redis-backed rate limiting.

**Why exponential smoothing and not XGBoost yet:** a new student user has days,
not years, of history. A gradient-boosted model needs volume to avoid overfitting
noise; exponential smoothing degrades gracefully at 3–5 data points.
`forecast_month_end_spend` is written so a heavier model can replace it without
touching a single caller.

---

## 11. Responsible AI

SpendShield is a personal finance assistant, not a licensed financial advisor. It
never guarantees outcomes, always separates predictions from facts, and lets users
override every recommendation. The intervention engine returns a *level* and
machine-readable trigger tags; the UI owns the wording, so tone can change without
touching decision logic, and none of it uses shame or guilt.

Full data deletion is implemented, not aspirational: `DELETE /api/v1/auth/me`
cascades to every transaction and budget.

---

## License

MIT — see [LICENSE](./LICENSE).
