# Deploying SpendShield AI

Roughly 15 minutes end to end. The backend applies its own database migrations
on every deploy, so there is no manual schema step.

## 1. Push to GitHub

```bash
cd spendshield-3
git init
git add .
git commit -m "SpendShield AI"
gh repo create spendshield-ai --public --source=. --push
```

## 2. Backend + database → Render

1. [render.com](https://render.com) → **New → Blueprint** → connect the repo.
2. Render reads `render.yaml` and provisions a **Postgres** database
   (`spendshield-db`) plus a **web service** (`spendshield-backend`) built from
   `backend/Dockerfile`, wired together via `DATABASE_URL`.
3. Two variables are marked `sync: false` and must be set in the dashboard
   before the first deploy finishes:
   - `LLM_API_KEY` — your Anthropic key. Leave it unset if you don't want the
     copilot; everything else still works and `/api/v1/copilot/chat` returns a
     clear 503.
   - `CORS_ORIGINS` — your frontend origin, e.g. `["https://spendshield-ai.vercel.app"]`.
     You can set this after step 3 and redeploy.
4. Check it:
   ```bash
   curl https://spendshield-backend.onrender.com/health
   ```
   A healthy response is `{"status":"ok","database":"up",...}`. If the database
   is unreachable this returns **503**, not a cheerful 200 — the health check is
   wired to fail when the app can't actually serve requests.

**Migrations run automatically.** `backend/entrypoint.sh` runs `alembic upgrade head`
before starting uvicorn, so the schema is created on first boot and updated on
every subsequent deploy. No shell access required.

**`ENV=production` is set in the blueprint**, which makes the app refuse to start if
`JWT_SECRET` is still the development default or shorter than 32 characters, or if
`CORS_ORIGINS` still contains `localhost`. This is deliberate: it turns the two most
common "shipped insecure" mistakes into a loud startup failure instead of a silent one.
It also disables `/docs` and `/redoc`.

## 3. Frontend → Vercel

1. [vercel.com](https://vercel.com) → **Add New → Project** → import the same repo,
   set **root directory** to `frontend`.
2. Vercel auto-detects Vite via `frontend/vercel.json`.
3. Add environment variable `VITE_API_URL = https://spendshield-backend.onrender.com`.
   Vite inlines `VITE_*` at build time, so changing it later needs a redeploy.
4. Deploy, then set `CORS_ORIGINS` on Render to the Vercel URL you got back and
   redeploy the backend.

## 4. Verify end to end

Open the Vercel URL and click **"Explore with demo data"**. That provisions a
throwaway account with two months of synthetic transactions and a budget, so you
get a fully populated dashboard without typing anything. If the gauge, forecast,
and category chart render, the whole stack is wired correctly.

To check the API directly:

```bash
curl -X POST https://spendshield-backend.onrender.com/api/v1/demo
```

That returns a bearer token you can use against any endpoint.

## 5. CI

`.github/workflows/ci.yml` runs on every push and PR:

- **backend** — `ruff` lint, the full `pytest` suite against both SQLite and Postgres, a from-scratch
  `alembic upgrade head` + `downgrade base`, and `alembic check` to catch a model
  change that has no matching migration.
- **frontend** — `tsc --noEmit` type check and a production build.
- **docker** — builds both images.

Render and Vercel redeploy on push once connected; CI is the pre-merge gate, not
the deploy mechanism.

## Operational notes

- **Render's free tier sleeps after inactivity.** The first request after an idle
  period takes ~30s to cold start. Fine for a portfolio demo, not for real use.
- **Rate limiting is per process.** `app/core/rate_limit.py` keeps its counters in
  memory, so with N replicas the effective limit is N x the configured value. That
  is enough to stop credential stuffing from one IP, which is what it is for. Move
  the counter to Redis before scaling out — `RateLimiter.hit` is the only signature
  a Redis version needs to match.
- **Turn off demo mode** for anything other than a public demo: set
  `DEMO_MODE_ENABLED=false`. Each demo click writes a user plus ~60 transactions.
- **The copilot costs money per message.** It is rate limited to 20 requests per
  minute per IP and capped at 5 tool-calling iterations per turn.

## Not built yet

- No CSV/OCR import — transactions are entered through the UI or API.
- No refresh tokens; access tokens last 24h and then require a fresh login.
- No background workers. Celery/Redis/Qdrant were previously declared as
  dependencies but nothing imported them, so they were removed; they come back
  when Phase 3/4 code actually needs them.
