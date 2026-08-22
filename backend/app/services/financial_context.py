"""
Database -> pure engine adapter.

The engines in this package (safe_to_spend, forecasting, impulse_score,
intervention) are pure and know nothing about SQLAlchemy. The API routes know
nothing about money math. This module is the only place the two meet: it reads
a user's real rows, shapes them into engine inputs, and returns engine results.

Why it exists: the copilot's tools and the REST routes must return *identical*
numbers for the same question. Previously the copilot imported the route
handlers directly (agents -> api -> services), which inverted the dependency
order and meant a change to a route signature silently broke the AI tools.
Both layers now call these functions instead.
"""
import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.budget import Budget, BudgetRule
from app.models.transaction import Transaction
from app.models.user import User
from app.services.forecasting import (
    DailySpend,
    ForecastResult,
    VelocityResult,
    calculate_spending_velocity,
    forecast_month_end_spend,
)
from app.services.impulse_score import ImpulseInput, ImpulseResult
from app.services.impulse_score import evaluate as evaluate_impulse
from app.services.intervention import InterventionDecision, InterventionInput
from app.services.intervention import decide as decide_intervention
from app.services.safe_to_spend import (
    PurchaseEvaluation,
    SafeToSpendInput,
    SafeToSpendResult,
    calculate_safe_to_spend,
    evaluate_purchase,
)

IMPULSE_LOOKBACK_DAYS = 7


@dataclass(frozen=True)
class MonthWindow:
    """The calendar month `today` falls in. All day counts are inclusive of today."""

    today: date
    start: date
    end: date

    @property
    def elapsed_days(self) -> int:
        return (self.today - self.start).days + 1

    @property
    def days_remaining(self) -> int:
        return (self.end - self.today).days + 1

    @property
    def total_days(self) -> int:
        return (self.end - self.start).days + 1


def month_window(today: date | None = None) -> MonthWindow:
    today = today or date.today()
    last_day = calendar.monthrange(today.year, today.month)[1]
    return MonthWindow(today=today, start=today.replace(day=1), end=today.replace(day=last_day))


def _spend_query(user_id) -> Select:
    """Base filter shared by every spend total: this user, money out (not income)."""
    return select(func.coalesce(func.sum(Transaction.amount), 0.0)).where(
        Transaction.user_id == user_id,
        Transaction.is_income.is_(False),
    )


def get_budget(db: Session, user: User, window: MonthWindow) -> Budget | None:
    return db.scalar(
        select(Budget).where(
            Budget.user_id == user.id,
            Budget.month == window.today.month,
            Budget.year == window.today.year,
        )
    )


def spent_so_far(db: Session, user: User, window: MonthWindow) -> float:
    return float(
        db.scalar(
            _spend_query(user.id).where(
                Transaction.transaction_date >= window.start,
                Transaction.transaction_date <= window.today,
            )
        )
        or 0.0
    )


def upcoming_obligations(db: Session, user: User, window: MonthWindow) -> float:
    """
    Recurring costs (rent, subscriptions) that are due this month but not logged yet.

    Method: last month's recurring charges are the template for this month's. Any
    template charge whose (category, merchant) pair has not appeared yet this month
    is still owed. Charges already logged are excluded — they are inside
    `spent_so_far` and double-counting them would suppress safe-to-spend to zero.

    This replaces a query that summed *every* recurring transaction ever dated
    before the month start, which grew without bound: after six months of ₹8,000
    rent it reserved ₹48,000 of "upcoming" obligations against a ₹15,000 budget.
    """
    prev_month_end = window.start - timedelta(days=1)
    prev_month_start = prev_month_end.replace(day=1)

    def _recurring_between(start: date, end: date) -> dict[tuple[str, str], float]:
        # Group by the plain columns and normalise NULL merchants in Python.
        # Grouping by `coalesce(merchant, '')` renders the empty string as a bound
        # parameter, and Postgres will not match that against the same expression
        # in the select list ("must appear in the GROUP BY clause"). SQLite accepts
        # it, so this only fails on the real database.
        rows = db.execute(
            select(
                Transaction.category,
                Transaction.merchant,
                func.max(Transaction.amount),
            )
            .where(
                Transaction.user_id == user.id,
                Transaction.is_recurring.is_(True),
                Transaction.is_income.is_(False),
                Transaction.transaction_date >= start,
                Transaction.transaction_date <= end,
            )
            .group_by(Transaction.category, Transaction.merchant)
        ).all()
        return {(c, (m or "").lower()): float(a) for c, m, a in rows}

    template = _recurring_between(prev_month_start, prev_month_end)
    already_paid = _recurring_between(window.start, window.today)
    return sum(amount for key, amount in template.items() if key not in already_paid)


def predicted_essential_spend(db: Session, user: User, window: MonthWindow) -> float:
    """
    Average daily essential spend so far, projected across the days still to come.

    Recurring essentials are excluded from the average. Rent is a single ₹6,500
    charge on the 3rd, not ₹300/day: averaging it over elapsed days and projecting
    it forward invents thousands of rupees of phantom future spend, and
    `upcoming_obligations` already reserves fixed costs that are genuinely still
    due. Only day-to-day essentials (food, transport) recur at a daily rate.
    """
    essential_so_far = float(
        db.scalar(
            _spend_query(user.id).where(
                Transaction.is_essential.is_(True),
                Transaction.is_recurring.is_(False),
                Transaction.transaction_date >= window.start,
                Transaction.transaction_date <= window.today,
            )
        )
        or 0.0
    )
    days_after_today = max(window.days_remaining - 1, 0)
    return (essential_so_far / window.elapsed_days) * days_after_today


def category_budget(db: Session, user: User, window: MonthWindow, category: str) -> float | None:
    """The allocation for one category this month, or None if the user set no rule."""
    amount = db.scalar(
        select(BudgetRule.allocated_amount)
        .join(Budget, Budget.id == BudgetRule.budget_id)
        .where(
            Budget.user_id == user.id,
            Budget.month == window.today.month,
            Budget.year == window.today.year,
            BudgetRule.category == category,
        )
    )
    return float(amount) if amount is not None else None


def safe_to_spend(db: Session, user: User, today: date | None = None) -> SafeToSpendResult:
    window = month_window(today)
    budget = get_budget(db, user, window)
    return calculate_safe_to_spend(
        SafeToSpendInput(
            monthly_budget=budget.total_income if budget else 0.0,
            spent_so_far=spent_so_far(db, user, window),
            upcoming_obligations=upcoming_obligations(db, user, window),
            predicted_essential_spend=predicted_essential_spend(db, user, window),
            today=window.today,
            month_start=window.start,
            month_end=window.end,
            savings_target=budget.savings_target if budget else 0.0,
        )
    )


def score_impulse(
    db: Session,
    user: User,
    *,
    amount: float,
    category: str,
    when: datetime | None = None,
    is_recurring: bool = False,
    today: date | None = None,
) -> ImpulseResult:
    """
    Impulse score for a purchase — used both to evaluate a hypothetical one and to
    stamp a score onto a transaction as it is written.
    """
    window = month_window(today)
    when = when or datetime.now()
    lookback_start = window.today - timedelta(days=IMPULSE_LOOKBACK_DAYS)

    spend_last_7d = float(
        db.scalar(
            _spend_query(user.id).where(
                Transaction.category == category,
                Transaction.transaction_date >= lookback_start,
                Transaction.transaction_date <= window.today,
            )
        )
        or 0.0
    )
    # Previously this counted every transaction ever in the category, so a user with
    # 40 lifetime food orders was permanently pinned at the maximum frequency penalty.
    count_last_7d = int(
        db.scalar(
            select(func.count(Transaction.id)).where(
                Transaction.user_id == user.id,
                Transaction.category == category,
                Transaction.transaction_date >= lookback_start,
                Transaction.transaction_date <= window.today,
            )
        )
        or 0
    )

    monthly_allocation = category_budget(db, user, window, category)
    # No rule for this category means "unknown", not "₹0 budget". Passing 0.0 makes the
    # engine skip the over-budget factor; the old `(x or 0)/4 or 1` fallback implied a
    # ₹1 weekly budget, which flagged every single purchase as over budget.
    weekly_allocation = (monthly_allocation / 4.345) if monthly_allocation else 0.0

    return evaluate_impulse(
        ImpulseInput(
            amount=amount,
            category=category,
            timestamp=when,
            category_spend_this_week=spend_last_7d,
            category_weekly_budget=weekly_allocation,
            transactions_same_category_last_7d=count_last_7d,
            is_recurring=is_recurring,
        )
    )


@dataclass
class PurchaseDecision:
    evaluation: PurchaseEvaluation
    impulse: ImpulseResult
    intervention: InterventionDecision


def purchase_decision(
    db: Session, user: User, *, price: float, category: str, today: date | None = None
) -> PurchaseDecision:
    window = month_window(today)
    sts = safe_to_spend(db, user, today=window.today)

    spend_this_month = float(
        db.scalar(
            _spend_query(user.id).where(
                Transaction.category == category,
                Transaction.transaction_date >= window.start,
                Transaction.transaction_date <= window.today,
            )
        )
        or 0.0
    )

    evaluation = evaluate_purchase(
        price=price,
        remaining_discretionary_budget=sts.remaining_budget,
        days_remaining=sts.days_remaining,
        recent_category_spend=spend_this_month,
        category_budget=category_budget(db, user, window, category),
    )
    impulse = score_impulse(
        db, user, amount=price, category=category, today=window.today
    )
    intervention = decide_intervention(
        InterventionInput(
            impulse_score=impulse.score,
            budget_impact_pct=evaluation.budget_impact_pct,
            overspend_risk=sts.overspend_risk,
            remaining_budget=sts.remaining_budget,
        )
    )
    return PurchaseDecision(evaluation=evaluation, impulse=impulse, intervention=intervention)


def forecast(db: Session, user: User, today: date | None = None) -> ForecastResult:
    window = month_window(today)
    budget = get_budget(db, user, window)

    rows = db.execute(
        select(Transaction.transaction_date, func.sum(Transaction.amount))
        .where(
            Transaction.user_id == user.id,
            Transaction.is_income.is_(False),
            Transaction.transaction_date >= window.start,
            Transaction.transaction_date <= window.today,
        )
        .group_by(Transaction.transaction_date)
        .order_by(Transaction.transaction_date)
    ).all()
    daily = [DailySpend(day=d, amount=float(a)) for d, a in rows]

    return forecast_month_end_spend(
        daily_spend=daily,
        days_remaining=max(window.days_remaining - 1, 0),   # today is already banked
        monthly_budget=budget.total_income if budget else 0.0,
        spent_so_far=sum(d.amount for d in daily),
    )


def velocity(db: Session, user: User, today: date | None = None) -> VelocityResult:
    window = month_window(today)
    budget = get_budget(db, user, window)
    return calculate_spending_velocity(
        spent_so_far=spent_so_far(db, user, window),
        elapsed_days=window.elapsed_days,
        monthly_budget=budget.total_income if budget else 0.0,
        total_days_in_month=window.total_days,
        savings_target=budget.savings_target if budget else 0.0,
    )


def category_breakdown(db: Session, user: User, today: date | None = None) -> list[dict]:
    """This month's spend grouped by category, largest first — powers the dashboard chart."""
    window = month_window(today)
    rows = db.execute(
        select(
            Transaction.category,
            func.sum(Transaction.amount),
            func.count(Transaction.id),
        )
        .where(
            Transaction.user_id == user.id,
            Transaction.is_income.is_(False),
            Transaction.transaction_date >= window.start,
            Transaction.transaction_date <= window.today,
        )
        .group_by(Transaction.category)
        .order_by(func.sum(Transaction.amount).desc())
    ).all()
    return [
        {"category": c, "total": round(float(t), 2), "transaction_count": int(n)}
        for c, t, n in rows
    ]
