import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class TransactionCreate(BaseModel):
    amount: float = Field(gt=0, le=10_000_000)
    merchant: str | None = Field(default=None, max_length=255)
    category: str = Field(min_length=1, max_length=100)
    subcategory: str | None = Field(default=None, max_length=100)
    transaction_date: date
    payment_method: str | None = Field(default="upi", max_length=50)
    is_essential: bool = False
    is_recurring: bool = False
    is_income: bool = False
    notes: str | None = Field(default=None, max_length=500)


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    amount: float
    merchant: str | None
    category: str
    subcategory: str | None
    transaction_date: date
    payment_method: str | None
    is_essential: bool
    is_recurring: bool
    is_income: bool
    impulse_score: int
    source: str
    notes: str | None
