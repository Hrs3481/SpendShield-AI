"""
One-click demo account.

A brand-new user sees an empty dashboard with every figure at zero, which makes
the product look broken rather than new. This endpoint provisions a throwaway
account pre-loaded with a budget and two months of realistic synthetic spending,
so a deployed instance is explorable in one click.

The data is synthetic; the numbers computed from it are not — they run through
exactly the same engines as a real account.
"""
import secrets
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.rate_limit import RateLimiter, enforce
from app.core.security import create_access_token, hash_password
from app.db.session import get_db
from app.models.budget import Budget, BudgetRule
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.auth import TokenResponse
from app.services.demo_data import (
    CATEGORY_RULES,
    MONTHLY_INCOME,
    SAVINGS_TARGET,
    generate_transactions,
)
from app.services.financial_context import month_window, score_impulse

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])
settings = get_settings()

# Generous enough that a shared campus/office IP doesn't lock visitors out,
# tight enough that nobody can fill the database with demo rows.
demo_limiter = RateLimiter(attempts=10, window_seconds=600)


@router.post("", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def create_demo_account(request: Request, db: Session = Depends(get_db)):
    if not settings.DEMO_MODE_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Demo mode is disabled."
        )
    enforce(demo_limiter, request)

    today = date.today()
    suffix = secrets.token_hex(4)
    user = User(
        email=f"demo-{suffix}@spendshield.local",
        # Random unguessable password: the account is reachable only via the
        # token returned below, never by logging in.
        hashed_password=hash_password(secrets.token_urlsafe(32)),
        full_name="Demo User",
        is_demo=True,
    )
    db.add(user)
    db.flush()

    budget = Budget(
        user_id=user.id,
        month=today.month,
        year=today.year,
        total_income=MONTHLY_INCOME,
        savings_target=SAVINGS_TARGET,
    )
    budget.rules = [
        BudgetRule(category=c, allocated_amount=a) for c, a in CATEGORY_RULES.items()
    ]
    db.add(budget)
    db.flush()

    for demo_txn in generate_transactions(today):
        db.add(
            Transaction(
                user_id=user.id,
                amount=demo_txn.amount,
                merchant=demo_txn.merchant,
                category=demo_txn.category,
                transaction_date=demo_txn.transaction_date,
                payment_method=demo_txn.payment_method,
                is_essential=demo_txn.is_essential,
                is_recurring=demo_txn.is_recurring,
                source="demo",
            )
        )
    db.flush()

    # Backfill impulse scores now that the history exists, so the demo shows the
    # same scores a real account would have accumulated.
    window = month_window(today)
    for txn in db.query(Transaction).filter(
        Transaction.user_id == user.id,
        Transaction.transaction_date >= window.start,
    ):
        txn.impulse_score = score_impulse(
            db,
            user,
            amount=txn.amount,
            category=txn.category,
            is_recurring=txn.is_recurring,
            today=today,
        ).score

    db.commit()
    return TokenResponse(access_token=create_access_token(user.id))
