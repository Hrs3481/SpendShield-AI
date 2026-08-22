import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Budget(Base):
    __tablename__ = "budgets"
    __table_args__ = (
        # One budget per user per month — enforced by the DB, not just by app code,
        # so a double-submit can't create two competing budgets for August.
        UniqueConstraint("user_id", "month", "year", name="uq_budget_user_month_year"),
        CheckConstraint("month >= 1 AND month <= 12", name="ck_budget_month_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    month: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)

    total_income: Mapped[float] = mapped_column(Float, nullable=False)
    savings_target: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="budgets")  # noqa: F821
    rules: Mapped[list["BudgetRule"]] = relationship(
        back_populates="budget", cascade="all, delete-orphan"
    )


class BudgetRule(Base):
    """Per-category allocation inside a Budget, e.g. food_delivery -> 2800."""

    __tablename__ = "budget_rules"
    __table_args__ = (
        UniqueConstraint("budget_id", "category", name="uq_budget_rule_category"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    budget_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("budgets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    allocated_amount: Mapped[float] = mapped_column(Float, nullable=False)

    budget: Mapped["Budget"] = relationship(back_populates="rules")
