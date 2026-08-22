import uuid
from datetime import date as date_
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Transaction(Base):
    __tablename__ = "transactions"
    # Every hot query filters user + date range, so index the pair, not just the columns.
    __table_args__ = (Index("ix_transactions_user_date", "user_id", "transaction_date"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    amount: Mapped[float] = mapped_column(Float, nullable=False)
    merchant: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    subcategory: Mapped[str | None] = mapped_column(String(100), nullable=True)

    transaction_date: Mapped[date_] = mapped_column(Date, index=True, nullable=False)
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)  # upi|card|cash

    is_essential: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_income: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    impulse_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    classification_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    source: Mapped[str] = mapped_column(String(30), default="manual", nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="transactions")  # noqa: F821
