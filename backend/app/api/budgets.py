"""
Budget CRUD — the input every other number in the product depends on.

Without a budget row, `monthly_budget` is 0, so safe-to-spend, forecast, and
velocity all return zero for every user. The app previously had no way to
create one through the API at all.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.budget import Budget, BudgetRule
from app.models.user import User
from app.schemas.budget import BudgetOut, BudgetUpsert
from app.services.financial_context import month_window

router = APIRouter(prefix="/api/v1/budgets", tags=["budgets"])


def _serialize(budget: Budget) -> BudgetOut:
    return BudgetOut(
        id=str(budget.id),
        month=budget.month,
        year=budget.year,
        total_income=budget.total_income,
        savings_target=budget.savings_target,
        created_at=budget.created_at,
        rules=[{"category": r.category, "allocated_amount": r.allocated_amount} for r in budget.rules],
    )


@router.put("", response_model=BudgetOut)
def upsert_budget(
    payload: BudgetUpsert, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """
    Idempotent by (user, month, year): calling it twice updates rather than
    duplicating, which is why it is PUT and not POST.
    """
    today = date.today()
    month = payload.month or today.month
    year = payload.year or today.year

    if payload.savings_target > payload.total_income:
        raise HTTPException(
            status_code=422,
            detail="Savings target cannot exceed total income for the month.",
        )

    budget = db.scalar(
        select(Budget)
        .options(selectinload(Budget.rules))
        .where(Budget.user_id == user.id, Budget.month == month, Budget.year == year)
    )
    if budget is None:
        budget = Budget(user_id=user.id, month=month, year=year, total_income=0)
        db.add(budget)

    budget.total_income = payload.total_income
    budget.savings_target = payload.savings_target

    if payload.rules:
        allocated = sum(r.allocated_amount for r in payload.rules)
        if allocated > payload.total_income:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Category allocations total ₹{allocated:,.0f}, which exceeds the "
                    f"₹{payload.total_income:,.0f} monthly budget."
                ),
            )
        budget.rules.clear()
        db.flush()
        for rule in payload.rules:
            budget.rules.append(
                BudgetRule(category=rule.category, allocated_amount=rule.allocated_amount)
            )

    db.commit()
    db.refresh(budget)
    return _serialize(budget)


@router.get("/current", response_model=BudgetOut)
def get_current_budget(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    window = month_window()
    budget = db.scalar(
        select(Budget)
        .options(selectinload(Budget.rules))
        .where(
            Budget.user_id == user.id,
            Budget.month == window.today.month,
            Budget.year == window.today.year,
        )
    )
    if budget is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No budget set for this month yet.",
        )
    return _serialize(budget)


@router.get("", response_model=list[BudgetOut])
def list_budgets(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    budgets = db.scalars(
        select(Budget)
        .options(selectinload(Budget.rules))
        .where(Budget.user_id == user.id)
        .order_by(Budget.year.desc(), Budget.month.desc())
    ).all()
    return [_serialize(b) for b in budgets]
