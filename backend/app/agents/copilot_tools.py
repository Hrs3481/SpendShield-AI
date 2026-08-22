"""
Copilot Tool Registry
======================
The rule the whole architecture is built around:

    The LLM never calculates a rupee figure. It only explains numbers that came
    out of deterministic, unit-tested backend code.

Each entry below is a tool the LLM may call. The LLM's job is (a) pick tools and
(b) turn structured JSON into plain language. Every executor delegates to
`services.financial_context`, the same module the REST routes use, so the
copilot and the dashboard can never disagree about a number.

(These executors used to call the FastAPI route handlers directly, which made
the agent layer depend on the HTTP layer and coupled tool output to response
model changes.)
"""
from collections.abc import Callable
from dataclasses import asdict

from sqlalchemy.orm import Session

from app.models.user import User
from app.services import financial_context as fc

TOOL_SCHEMAS: list[dict] = [
    {
        "name": "get_safe_to_spend",
        "description": (
            "The user's safe-to-spend-today figure, remaining budget, days left in the "
            "month, overspend risk, financial health score, and the list of factors "
            "that produced the number. Call this for any question about how much the "
            "user can spend, how they are doing this month, or why a number is what it is."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "evaluate_purchase",
        "description": (
            "Evaluate a specific prospective purchase against the user's real budget. "
            "Returns affordability score, budget impact %, a BUY_NOW/WAIT/SKIP "
            "recommendation, an impulse score with its reasons, and an intervention level. "
            "Call this whenever the user asks whether they should or can buy something."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "price": {"type": "number", "description": "Price of the item in INR"},
                "category": {
                    "type": "string",
                    "description": "Spending category, e.g. 'shopping', 'food_delivery', "
                                   "'entertainment', 'travel', 'coffee_snacks'",
                },
            },
            "required": ["price", "category"],
        },
    },
    {
        "name": "get_month_end_forecast",
        "description": (
            "Projected total spend for the current month, projected overspend against "
            "budget, and a LOW/MEDIUM/HIGH risk rating, plus spending velocity "
            "(₹/day actual vs. the pace required to land on budget). Call this for "
            "questions about what happens if current habits continue."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_spending_by_category",
        "description": (
            "This month's spend broken down by category, largest first, with a "
            "transaction count per category. Call this when the user asks where their "
            "money is going or which category is the problem."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
]


def build_tool_executor(db: Session, user: User) -> dict[str, Callable[[dict], dict]]:
    """Returns a name -> callable map the agent loop dispatches tool_use blocks to."""

    def _safe_to_spend(_args: dict) -> dict:
        result = fc.safe_to_spend(db, user)
        payload = asdict(result)
        if not fc.get_budget(db, user, fc.month_window()):
            # Without this the model sees zeros and tells the user they are broke.
            payload["note"] = (
                "This user has NOT set a budget for this month, so every figure above "
                "is zero for lack of input rather than because they have no money. "
                "Tell them to set a monthly budget first."
            )
        return payload

    def _evaluate_purchase(args: dict) -> dict:
        decision = fc.purchase_decision(
            db, user, price=float(args["price"]), category=str(args["category"])
        )
        return {
            "evaluation": asdict(decision.evaluation),
            "impulse": asdict(decision.impulse),
            "intervention": {
                "level": int(decision.intervention.level),
                "level_name": decision.intervention.level.name,
                "triggers": decision.intervention.triggers,
            },
        }

    def _forecast(_args: dict) -> dict:
        return {
            "forecast": asdict(fc.forecast(db, user)),
            "velocity": asdict(fc.velocity(db, user)),
        }

    def _categories(_args: dict) -> dict:
        return {"categories": fc.category_breakdown(db, user)}

    return {
        "get_safe_to_spend": _safe_to_spend,
        "evaluate_purchase": _evaluate_purchase,
        "get_month_end_forecast": _forecast,
        "get_spending_by_category": _categories,
    }


SYSTEM_PROMPT = """You are the SpendShield Copilot, a supportive personal finance \
assistant for Indian college students, PG residents, and young professionals.

Rules you must always follow:
1. Never invent, estimate, or do arithmetic on a rupee figure yourself. Call a tool and \
report what it returns. If no tool can answer, say so rather than guessing.
2. Explain numbers in plain, encouraging language. Never shame or guilt the user about \
their spending.
3. Clearly separate facts (which came from tools) from suggestions (your judgement).
4. If the user asks something outside their personal finances, say that's outside what \
you can help with.
5. You are not a licensed financial advisor. Never guarantee an outcome, and never give \
investment advice.
6. Amounts are Indian rupees. Format them as ₹1,250 — Indian digit grouping, no decimals \
unless the paise matter.
"""
