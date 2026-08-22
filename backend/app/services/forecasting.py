"""
Forecasting Engine (Phase 2)
=============================
v1 uses classical time-series methods (exponential smoothing) rather than
XGBoost/Prophet, deliberately: with a brand-new user you have days, not
years, of history — a heavy model overfits immediately and can't even run.
Exponential smoothing degrades gracefully with 3-30 data points, which is
the realistic range for a student's first month.

Upgrade path (documented, not yet built): once a user has 90+ days of
history, swap `forecast_month_end_spend` for a gradient-boosted regressor
trained on day-of-month, day-of-week, and category features — same
function signature, so nothing calling this module has to change.

Everything below is pure Python (stdlib only) and independently testable.
"""

from dataclasses import dataclass
from datetime import date
from statistics import mean, pstdev


@dataclass
class DailySpend:
    day: date
    amount: float


@dataclass
class ForecastResult:
    predicted_total_month_spend: float
    predicted_remaining_spend: float
    target_budget: float
    projected_overspend: float
    risk: str  # LOW | MEDIUM | HIGH
    method: str


def exponential_smoothing_forecast(
    daily_spend: list[DailySpend],
    days_remaining: int,
    alpha: float = 0.3,
) -> float:
    """
    Returns a single smoothed daily-spend estimate, then the caller multiplies
    by days_remaining. alpha=0.3 weights recent days more heavily without
    being whipsawed by a single large one-off purchase.
    """
    if not daily_spend:
        return 0.0
    amounts = [d.amount for d in daily_spend]
    level = amounts[0]
    for a in amounts[1:]:
        level = alpha * a + (1 - alpha) * level
    return max(level, 0.0) * days_remaining


def forecast_month_end_spend(
    daily_spend: list[DailySpend],
    days_remaining: int,
    monthly_budget: float,
    spent_so_far: float,
) -> ForecastResult:
    predicted_remaining = exponential_smoothing_forecast(daily_spend, days_remaining)
    predicted_total = spent_so_far + predicted_remaining
    overspend = predicted_total - monthly_budget

    if monthly_budget <= 0:
        risk = "LOW"
    elif overspend > monthly_budget * 0.1:
        risk = "HIGH"
    elif overspend > 0:
        risk = "MEDIUM"
    else:
        risk = "LOW"

    return ForecastResult(
        predicted_total_month_spend=round(predicted_total, 2),
        predicted_remaining_spend=round(predicted_remaining, 2),
        target_budget=monthly_budget,
        projected_overspend=round(max(overspend, 0.0), 2),
        risk=risk,
        method="exponential_smoothing_v1",
    )


@dataclass
class VelocityResult:
    current_velocity: float          # ₹/day actually spent so far
    required_velocity: float         # ₹/day to land on budget AND hit the savings target
    deviation_pct: float             # (+ over pace, - under pace)
    label: str                       # ON_PACE | AHEAD | BEHIND


def calculate_spending_velocity(
    spent_so_far: float,
    elapsed_days: int,
    monthly_budget: float,
    total_days_in_month: int,
    savings_target: float = 0.0,
) -> VelocityResult:
    """
    `savings_target` is subtracted from the budget before deriving the required
    pace, because money you intend to save is not money you may spend.

    It defaults to 0.0 for backward compatibility, but callers should pass it:
    safe_to_spend.py has always netted savings out of its own required-velocity
    figure, so omitting it here made the dashboard show two different "target
    pace" numbers for the same user, with contradictory ON_PACE / HIGH-risk labels.
    """
    elapsed_days = max(elapsed_days, 1)
    total_days_in_month = max(total_days_in_month, 1)

    current = spent_so_far / elapsed_days
    required = max(monthly_budget - savings_target, 0.0) / total_days_in_month

    deviation = ((current - required) / required * 100) if required > 0 else 0.0

    if deviation > 10:
        label = "AHEAD"      # spending ahead of pace = bad
    elif deviation < -10:
        label = "BEHIND"     # spending behind pace = good, under budget
    else:
        label = "ON_PACE"

    return VelocityResult(
        current_velocity=round(current, 2),
        required_velocity=round(required, 2),
        deviation_pct=round(deviation, 1),
        label=label,
    )


@dataclass
class AnomalyFlag:
    is_anomalous: bool
    z_score: float
    reason: str


def detect_transaction_anomaly(
    amount: float,
    historical_amounts_same_category: list[float],
    z_threshold: float = 2.5,
) -> AnomalyFlag:
    """
    Simple, explainable z-score anomaly detector (robust-statistics baseline,
    per spec section 23). Needs at least 4 prior transactions in the category
    to be meaningful; otherwise we don't flag anything (too little signal).
    """
    if len(historical_amounts_same_category) < 4:
        return AnomalyFlag(is_anomalous=False, z_score=0.0, reason="Not enough history in this category yet.")

    mu = mean(historical_amounts_same_category)
    sigma = pstdev(historical_amounts_same_category)
    z = 0.0 if sigma == 0 else (amount - mu) / sigma

    is_anomalous = z >= z_threshold
    reason = (
        f"₹{amount:.0f} is {z:.1f} standard deviations above your usual ₹{mu:.0f} "
        f"in this category." if is_anomalous else "Within normal range for this category."
    )
    return AnomalyFlag(is_anomalous=is_anomalous, z_score=round(z, 2), reason=reason)
