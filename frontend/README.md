# SpendShield AI — frontend

Vite + React + TypeScript + Tailwind. Talks to the FastAPI backend in `../backend`.

## Setup

```bash
cp .env.example .env      # set VITE_API_URL if the API isn't on localhost:8000
npm install
npm run dev               # http://localhost:5173
```

Requires the backend running — `docker compose up` from the repo root, or
`uvicorn app.main:app --reload` inside `backend/`. There is no mock-data
fallback; every number on screen came from the API.

`VITE_*` variables are inlined at **build** time, so changing `VITE_API_URL`
requires a rebuild, not just a restart of the deployed app.

## What's here

- `src/lib/api.ts` — typed fetch client, one function per endpoint, JWT attached
  automatically. Broadcasts an event on a 401 so the app can drop to the login
  screen instead of rendering a dashboard full of failed requests. Exports
  `formatINR`, which uses Indian digit grouping (₹1,20,000, not ₹120,000).
- `src/context/AuthContext.tsx` — login, register, demo provisioning, logout.
- `src/pages/Login.tsx` — includes **"Explore with demo data"**, which creates a
  populated throwaway account in one click.
- `src/pages/Dashboard.tsx` — when no budget exists for the month it renders the
  budget form instead of a gauge full of zeros, because zero-for-lack-of-input
  looks identical to zero-because-you're-broke.
- `src/components/BudgetForm.tsx` — set monthly budget, savings target, and
  per-category limits, with client-side validation mirroring the API's.
- `src/components/SafeToSpendGauge.tsx` — the ring tracks `financial_health_score`,
  a real 0–100 metric. It previously scaled safe-to-spend against a hard-coded
  ₹500 "reference ceiling", so the arc meant nothing you could point at.
- `src/components/PurchaseEvaluator.tsx` — calls `/api/v1/purchase/evaluate` and
  shows the impulse signals and intervention copy, not just a verdict.
- `src/components/CategoryChart.tsx` — this month's spend by category (recharts).
- `src/components/ForecastPanel.tsx` — month-end projection and spending velocity.
- `src/components/CopilotChat.tsx` — restores your message to the input box if a
  send fails, so nothing is lost.

## Design tokens

In `tailwind.config.js`: `ink` (deep indigo backgrounds), `marigold` (primary
accent), `tulsi` (positive), `sindoor` (danger), `paper` (off-white text).
Display type is Space Grotesk, body is Inter, and every rupee amount is IBM Plex
Mono — deliberately, so money reads like a ledger entry rather than UI copy.

## Tests

```bash
npm test          # vitest run — 28 passing
npm run test:watch
```

Vitest + Testing Library against jsdom. What's covered:

- `src/lib/__tests__/api.test.ts` — Indian digit grouping in `formatINR`, bearer
  token attachment, the 401 path (clears the token and broadcasts, but only when
  a token existed), the unreachable-backend message, and a guard that
  registration credentials never appear in the URL.
- `SafeToSpendGauge` — the ring is driven by `financial_health_score`, so the
  same score yields the same arc no matter the rupee amount, plus the aria-label.
- `BudgetForm` — client-side validation matches the API's, and a rejected save
  surfaces rather than failing silently.
- `Dashboard` — with no budget it renders the budget form instead of a zeroed
  gauge; a 404 from `getCurrentBudget` is an expected state, not a page error;
  an unreachable API shows an actionable message with a retry.

jsdom implements neither `Element.scrollTo` nor `ResizeObserver`; both are
stubbed in `src/test/setup.ts` rather than worked around in components.

## Build

```bash
npm run build     # tsc -b && vite build
npx tsc --noEmit  # type check only
```

Vendor chunks are split in `vite.config.ts`: recharts alone is larger than the
whole app, so a code change ships a ~29 kB chunk instead of invalidating a
550 kB monolith.
