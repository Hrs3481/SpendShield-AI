"""
Impulse Score Engine (heuristic v1)
====================================
Phase 1 uses a transparent, explainable weighted heuristic instead of a
trained classifier so it works from day one with zero historical data.
Phase 2 (see spec section 23) swaps this for a personalized ML model
(gradient boosted trees) trained on user-corrected labels, WITHOUT
changing the calling contract — evaluate() always returns an ImpulseResult.
"""

from dataclasses import dataclass, field
from datetime import datetime

DISCRETIONARY_CATEGORIES = {
    "food_delivery", "shopping", "entertainment", "coffee_snacks", "subscriptions_impulse",
}


@dataclass
class ImpulseInput:
    amount: float
    category: str
    timestamp: datetime
    category_spend_this_week: float
    category_weekly_budget: float
    transactions_same_category_last_7d: int
    is_recurring: bool


@dataclass
class ImpulseResult:
    score: int  # 0-100
    label: str  # LOW | MEDIUM | HIGH
    reasons: list[str] = field(default_factory=list)


def evaluate(inp: ImpulseInput) -> ImpulseResult:
    if inp.is_recurring:
        return ImpulseResult(
            score=0, label="LOW",
            reasons=["Recurring/subscription payment — not impulse-scored."],
        )

    score = 0
    reasons = []

    if inp.category in DISCRETIONARY_CATEGORIES:
        score += 25
        reasons.append("Unplanned/discretionary category.")

    hour = inp.timestamp.hour
    if hour >= 22 or hour < 5:
        score += 20
        reasons.append("Late-night transaction (10 PM–5 AM).")

    if inp.category_weekly_budget > 0:
        over_ratio = inp.category_spend_this_week / inp.category_weekly_budget
        if over_ratio > 1.0:
            score += 25
            reasons.append(f"Category spend is already {over_ratio * 100:.0f}% of its weekly budget.")
        elif over_ratio > 0.75:
            score += 12
            reasons.append(f"Category spend is at {over_ratio * 100:.0f}% of its weekly budget.")

    if inp.transactions_same_category_last_7d >= 5:
        score += 20
        reasons.append(
            f"{inp.transactions_same_category_last_7d} transactions in this category "
            f"in the last 7 days."
        )
    elif inp.transactions_same_category_last_7d >= 3:
        score += 10
        reasons.append(
            f"{inp.transactions_same_category_last_7d} transactions in this category "
            f"in the last 7 days."
        )

    if inp.amount >= 1000:
        score += 10
        reasons.append("Above-average transaction size for a discretionary purchase.")

    score = max(0, min(100, score))
    label = "HIGH" if score >= 65 else "MEDIUM" if score >= 35 else "LOW"

    if not reasons:
        reasons.append("No notable impulse indicators detected.")

    return ImpulseResult(score=score, label=label, reasons=reasons)
