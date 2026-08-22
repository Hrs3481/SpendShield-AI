from pydantic import BaseModel, Field


class SafeToSpendOut(BaseModel):
    safe_to_spend_today: float
    remaining_budget: float
    days_remaining: int
    recommended_daily_discretionary: float
    overspend_risk: str
    financial_health_score: int
    explanation_factors: list[str]
    has_budget: bool = Field(
        description="False when the user has not set a budget this month, in which "
                    "case every figure above is zero for lack of input, not because "
                    "the user is broke."
    )


class PurchaseEvaluateIn(BaseModel):
    price: float = Field(gt=0, le=10_000_000)
    category: str = Field(min_length=1, max_length=100)


class PurchaseEvaluateOut(BaseModel):
    affordability_score: int
    budget_impact_pct: float
    recommendation: str
    reason: str
    intervention_level: int
    impulse_score: int
    impulse_label: str
    impulse_reasons: list[str]
    intervention_triggers: list[str]


class CategorySpend(BaseModel):
    category: str
    total: float
    transaction_count: int
