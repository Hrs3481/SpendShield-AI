"""
Safe-to-Spend Engine
=====================
This is the single most important module in SpendShield AI.

Design principle (non-negotiable, see spec sections 12 & 34):
    The LLM NEVER computes a financial number. It only explains numbers
    that come out of this module. Every function here is pure, deterministic,
    unit-testable, and has no dependency on FastAPI, SQLAlchemy, or any LLM.

This lets us:
    1. Unit test financial correctness in isolation (see tests/test_safe_to_spend.py)
    2. Swap the LLM provider freely without touching money math
    3. Explain every number with a structured "why" breakdown (Explainable AI, section 24)
"""

from dataclasses import dataclass, field
from datetime import date


@dataclass
class SafeToSpendInput:
    monthly_budget: float          # total discretionary+essential budget for the month
    spent_so_far: float            # sum of transactions this month
    upcoming_obligations: float    # known recurring/fixed costs still due this month (rent, subs)
    predicted_essential_spend: float  # forecasted remaining essential spend (food, travel)
    today: date
    month_start: date
    month_end: date                # last calendar day of the month
    savings_target: float = 0.0    # optional monthly savings goal to protect


@dataclass
class SafeToSpendResult:
    safe_to_spend_today: float
    remaining_budget: float
    days_remaining: int
    recommended_daily_discretionary: float
    overspend_risk: str             # LOW | MEDIUM | HIGH
    financial_health_score: int     # 0-100
    explanation_factors: list[str] = field(default_factory=list)


def _days_remaining(today: date, month_end: date) -> int:
    delta = (month_end - today).days
    return max(delta, 0) + 1  # inclusive of today


def calculate_safe_to_spend(inp: SafeToSpendInput) -> SafeToSpendResult:
    factors: list[str] = []

    remaining_budget = inp.monthly_budget - inp.spent_so_far
    factors.append(
        f"Remaining monthly budget is ₹{remaining_budget:.0f} "
        f"(₹{inp.monthly_budget:.0f} budget minus ₹{inp.spent_so_far:.0f} spent so far)."
    )

    days_remaining = _days_remaining(inp.today, inp.month_end)
    factors.append(f"{days_remaining} day(s) remain in the month, including today.")

    # Money that is already spoken for and must not be touched.
    protected = inp.upcoming_obligations + inp.predicted_essential_spend + inp.savings_target
    if inp.upcoming_obligations > 0:
        factors.append(f"₹{inp.upcoming_obligations:.0f} of upcoming fixed obligations are reserved.")
    if inp.predicted_essential_spend > 0:
        factors.append(
            f"₹{inp.predicted_essential_spend:.0f} of essential spending is forecast "
            f"for the rest of the month."
        )
    if inp.savings_target > 0:
        factors.append(f"₹{inp.savings_target:.0f} is reserved to protect your savings goal.")

    free_discretionary_pool = max(remaining_budget - protected, 0.0)
    if free_discretionary_pool <= 0:
        # Without this the dashboard shows HIGH risk beside an on-pace velocity and
        # no overspend forecast, with nothing explaining the apparent contradiction.
        factors.append(
            "Every rupee left this month is already committed to essentials, fixed "
            "costs, and your savings goal, so there is no discretionary room left."
        )

    recommended_daily = free_discretionary_pool / days_remaining if days_remaining else 0.0
    safe_today = round(recommended_daily, 0)

    # Risk model: compare current velocity vs. required velocity to hit target.
    # Inclusive of today, matching days_remaining. Exclusive counting made a
    # 20-day-elapsed month read as 19, inflating current_velocity and overstating risk.
    elapsed_days = max((inp.today - inp.month_start).days + 1, 1)
    current_velocity = inp.spent_so_far / elapsed_days
    total_days_in_month = (inp.month_end - inp.month_start).days + 1
    required_velocity = (
        (inp.monthly_budget - inp.savings_target) / total_days_in_month if total_days_in_month else 0
    )

    if required_velocity <= 0:
        velocity_deviation = 0.0
    else:
        velocity_deviation = (current_velocity - required_velocity) / required_velocity

    if free_discretionary_pool <= 0 or velocity_deviation > 0.35:
        risk = "HIGH"
    elif velocity_deviation > 0.10:
        risk = "MEDIUM"
    else:
        risk = "LOW"

    factors.append(
        f"Spending velocity is ₹{current_velocity:.0f}/day vs a target pace of "
        f"₹{required_velocity:.0f}/day ({velocity_deviation * 100:+.0f}% deviation)."
    )

    # Financial health score: simple weighted composite (documented, not a black box).
    budget_adherence = max(0.0, 1 - max(velocity_deviation, 0))
    buffer_ratio = max(0.0, min(free_discretionary_pool / inp.monthly_budget, 1)) if inp.monthly_budget else 0
    health_score = round((0.6 * budget_adherence + 0.4 * buffer_ratio) * 100)
    health_score = max(0, min(100, health_score))

    return SafeToSpendResult(
        safe_to_spend_today=max(safe_today, 0.0),
        remaining_budget=round(remaining_budget, 2),
        days_remaining=days_remaining,
        recommended_daily_discretionary=round(recommended_daily, 2),
        overspend_risk=risk,
        financial_health_score=health_score,
        explanation_factors=factors,
    )


@dataclass
class RunwayResult:
    estimated_runway_days: float
    target_runway_days: int
    explanation: str


def calculate_financial_runway(
    available_discretionary_money: float,
    current_avg_daily_discretionary_spend: float,
    target_runway_days: int,
) -> RunwayResult:
    if current_avg_daily_discretionary_spend <= 0:
        runway = float("inf")
        explanation = (
            "No recent discretionary spending detected, so runway is effectively "
            "unlimited at the current rate."
        )
    else:
        runway = available_discretionary_money / current_avg_daily_discretionary_spend
        explanation = (
            f"At ₹{current_avg_daily_discretionary_spend:.0f}/day, your ₹{available_discretionary_money:.0f} "
            f"discretionary balance lasts about {runway:.1f} day(s)."
        )
    return RunwayResult(
        estimated_runway_days=runway,
        target_runway_days=target_runway_days,
        explanation=explanation,
    )


@dataclass
class PurchaseEvaluation:
    affordability_score: int        # 0-100
    budget_impact_pct: float
    recommendation: str             # BUY_NOW | WAIT | SKIP
    reason: str


def evaluate_purchase(
    price: float,
    remaining_discretionary_budget: float,
    days_remaining: int,
    recent_category_spend: float,
    category_budget: float | None = None,
) -> PurchaseEvaluation:
    if remaining_discretionary_budget <= 0:
        impact_pct = 100.0
    else:
        impact_pct = min((price / remaining_discretionary_budget) * 100, 999)

    # Affordability drops as the purchase eats a larger share of what's left.
    affordability = max(0, min(100, round(100 - impact_pct)))

    if impact_pct >= 40 or affordability < 40:
        recommendation = "WAIT"
        reason = (
            f"This purchase would consume approximately {impact_pct:.0f}% of your remaining "
            f"discretionary budget for the next {days_remaining} day(s)."
        )
    elif impact_pct >= 15:
        recommendation = "WAIT"
        reason = (
            f"This is a moderate hit ({impact_pct:.0f}%) to your remaining discretionary "
            f"budget — consider waiting a few days."
        )
    else:
        recommendation = "BUY_NOW"
        reason = f"This purchase only uses about {impact_pct:.0f}% of your remaining discretionary budget."

    if category_budget and (recent_category_spend + price) > category_budget:
        recommendation = "SKIP" if recommendation != "BUY_NOW" else "WAIT"
        overage = recent_category_spend + price - category_budget
        reason += f" It would also push this category ₹{overage:.0f} over its budget."

    return PurchaseEvaluation(
        affordability_score=affordability,
        budget_impact_pct=round(impact_pct, 1),
        recommendation=recommendation,
        reason=reason,
    )
