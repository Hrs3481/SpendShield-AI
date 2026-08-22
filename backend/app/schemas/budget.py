from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BudgetRuleIn(BaseModel):
    category: str = Field(min_length=1, max_length=100)
    allocated_amount: float = Field(ge=0)


class BudgetRuleOut(BudgetRuleIn):
    model_config = ConfigDict(from_attributes=True)


class BudgetUpsert(BaseModel):
    """
    Creates or replaces the budget for one month. Month/year default to the
    current month so the common case ("set my budget") needs one field.
    """

    total_income: float = Field(gt=0, description="Total money available this month, in INR")
    savings_target: float = Field(default=0.0, ge=0)
    month: int | None = Field(default=None, ge=1, le=12)
    year: int | None = Field(default=None, ge=2000, le=2100)
    rules: list[BudgetRuleIn] = Field(default_factory=list)


class BudgetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    month: int
    year: int
    total_income: float
    savings_target: float
    created_at: datetime | None = None
    rules: list[BudgetRuleOut] = []
