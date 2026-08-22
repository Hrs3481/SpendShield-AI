import logging
import time
import uuid

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api import auth, budgets, copilot, demo, insights, transactions
from app.core.config import get_settings
from app.db.session import engine

settings = get_settings()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("spendshield")

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description=(
        "Financial behaviour intelligence API. Every monetary figure is computed by "
        "deterministic, unit-tested engines in `app/services/` — the LLM copilot only "
        "explains those figures, it never produces them."
    ),
    # A public /docs page that lets anyone probe the API isn't wanted in production.
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    """Tags every request with an id and logs its latency — the minimum needed to
    debug a deployed instance from logs alone."""
    request_id = request.headers.get("x-request-id", uuid.uuid4().hex[:12])
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "%s %s -> %s (%.1fms) [%s]",
        request.method, request.url.path, response.status_code, elapsed_ms, request_id,
    )
    return response


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    """Flattens Pydantic's nested error list into one readable sentence, so the
    frontend's `detail` field is always a displayable string."""
    problems = "; ".join(
        f"{'.'.join(str(p) for p in e['loc'][1:]) or 'body'}: {e['msg']}" for e in exc.errors()
    )
    return JSONResponse(
        status_code=422,
        content={"detail": problems or "Invalid request."},
    )


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    """Logs the traceback server-side; returns a generic message so internal
    details never leak to a client."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Something went wrong on our side. Please try again."},
    )


for router in (auth, demo, budgets, transactions, insights, copilot):
    app.include_router(router.router)


@app.get("/health", tags=["meta"])
def health():
    """Liveness + dependency check. Render points its health check here, so it must
    fail when the database is unreachable rather than reporting a healthy app."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        logger.exception("Health check could not reach the database")
        db_ok = False

    body = {
        "status": "ok" if db_ok else "degraded",
        "app": settings.APP_NAME,
        "version": app.version,
        "database": "up" if db_ok else "down",
        "copilot": "configured" if settings.LLM_API_KEY else "disabled",
    }
    return JSONResponse(
        status_code=status.HTTP_200_OK if db_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
        content=body,
    )
