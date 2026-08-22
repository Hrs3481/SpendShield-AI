"""
AI Copilot chat endpoint — the tool-calling loop.

The LLM decides which financial tool to call, the backend executes the real
deterministic calculation, and the LLM turns the structured result into a
natural-language explanation. Every number in a reply traces back to a
tool_result block produced by `services.financial_context`.

Provider-agnostic by configuration (`LLM_PROVIDER`); the wire format below is
Anthropic's Messages API. Supporting another vendor means adding a sibling
`_run_<vendor>_loop` with the same signature — the tool definitions and
executors in `agents/copilot_tools.py` are shared and stay untouched.
"""
import json
import logging

import anthropic
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.agents.copilot_tools import SYSTEM_PROMPT, TOOL_SCHEMAS, build_tool_executor
from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.rate_limit import RateLimiter, enforce
from app.db.session import get_db
from app.models.user import User
from app.schemas.copilot import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/v1/copilot", tags=["copilot"])
settings = get_settings()
logger = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 5  # hard cap so a confused model cannot loop forever

# Each turn costs real money, so it is limited independently of the auth endpoints.
copilot_limiter = RateLimiter(attempts=20, window_seconds=60)


@router.post("/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not settings.LLM_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Copilot is not configured — set LLM_API_KEY in the environment.",
        )
    enforce(copilot_limiter, request)

    client = anthropic.Anthropic(api_key=settings.LLM_API_KEY)
    tool_executor = build_tool_executor(db, user)

    messages: list[dict] = [{"role": m.role, "content": m.content} for m in payload.history]
    messages.append({"role": "user", "content": payload.message})

    tool_calls_made: list[str] = []

    for _ in range(MAX_TOOL_ITERATIONS):
        try:
            response = client.messages.create(
                model=settings.LLM_MODEL_NAME,
                max_tokens=settings.LLM_MAX_TOKENS,
                system=SYSTEM_PROMPT,
                tools=TOOL_SCHEMAS,
                messages=messages,
            )
        except anthropic.RateLimitError as exc:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="The copilot is busy right now. Try again in a moment.",
            ) from exc
        except anthropic.AuthenticationError as exc:
            logger.error("LLM rejected the configured API key")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Copilot is misconfigured — the LLM API key was rejected.",
            ) from exc
        except anthropic.APIError as exc:
            # Never surface a raw provider error to the client; it can carry
            # request metadata and it isn't actionable for the user.
            logger.exception("LLM call failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="The copilot is unavailable right now. Your data is unaffected.",
            ) from exc

        if response.stop_reason == "refusal":
            return ChatResponse(
                reply="I can't help with that one. Try asking me about your budget, "
                      "your spending this month, or whether you can afford something.",
                tool_calls_made=tool_calls_made,
            )

        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

        if not tool_use_blocks:
            text = "".join(b.text for b in response.content if b.type == "text").strip()
            if not text:
                text = "I couldn't put an answer together for that. Could you rephrase?"
            return ChatResponse(reply=text, tool_calls_made=tool_calls_made)

        # The model wants tools. Execute each for real, then feed every result back
        # in a single user message — splitting them across messages trains the model
        # out of making parallel calls.
        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in tool_use_blocks:
            executor = tool_executor.get(block.name)
            is_error = False
            if executor is None:
                result, is_error = {"error": f"Unknown tool '{block.name}'"}, True
            else:
                try:
                    result = executor(block.input)
                except Exception as exc:  # noqa: BLE001 - a tool bug must not 500 the chat
                    logger.exception("Copilot tool %s failed", block.name)
                    result, is_error = {"error": f"{type(exc).__name__}: {exc}"}, True
            tool_calls_made.append(block.name)
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result, default=str),
                    "is_error": is_error,
                }
            )
        messages.append({"role": "user", "content": tool_results})

    logger.warning("Copilot hit the %s-iteration tool limit", MAX_TOOL_ITERATIONS)
    return ChatResponse(
        reply="I looked that up a few different ways but couldn't settle on an answer. "
              "Could you ask it more specifically?",
        tool_calls_made=tool_calls_made,
    )
