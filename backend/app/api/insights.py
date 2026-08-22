"""
Read-only analytics: safe-to-spend, purchase evaluation, forecast, velocity,
category breakdown.

Every handler has the same shape — resolve the user, call one function in
`services.financial_context`, serialize. No money math lives in this file.
(These were previously split across safe_to_spend.py and forecast.py with the
month-boundary helper duplicated in both.)
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.forecast import ForecastOut, VelocityOut
from app.schemas.safe_to_spend import (
    CategorySpend,
    PurchaseEvaluateIn,
    PurchaseEvaluateOut,
    SafeToSpendOut,
)
from app.services import financial_context as fc

router = APIRouter(prefix="/api/v1", tags=["insights"])


@router.get("/safe-to-spend", response_model=SafeToSpendOut)
def get_safe_to_spend(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    result = fc.safe_to_spend(db, user)
    has_budget = fc.get_budget(db, user, fc.month_window()) is not None
    return SafeToSpendOut(
        **result.__dict__,
        has_budget=has_budget,
    )


@router.post("/purchase/evaluate", response_model=PurchaseEvaluateOut)
def evaluate_purchase(
    payload: PurchaseEvaluateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    decision = fc.purchase_decision(db, user, price=payload.price, category=payload.category)
    return PurchaseEvaluateOut(
        affordability_score=decision.evaluation.affordability_score,
        budget_impact_pct=decision.evaluation.budget_impact_pct,
        recommendation=decision.evaluation.recommendation,
        reason=decision.evaluation.reason,
        intervention_level=int(decision.intervention.level),
        impulse_score=decision.impulse.score,
        impulse_label=decision.impulse.label,
        impulse_reasons=decision.impulse.reasons,
        intervention_triggers=decision.intervention.triggers,
    )


@router.get("/forecast", response_model=ForecastOut)
def get_forecast(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return fc.forecast(db, user)


@router.get("/analytics/velocity", response_model=VelocityOut)
def get_velocity(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return fc.velocity(db, user)


@router.get("/analytics/categories", response_model=list[CategorySpend])
def get_category_breakdown(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return fc.category_breakdown(db, user)
