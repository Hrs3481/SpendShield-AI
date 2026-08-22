import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.transaction import TransactionCreate, TransactionOut
from app.services.financial_context import score_impulse

router = APIRouter(prefix="/api/v1/transactions", tags=["transactions"])
settings = get_settings()


@router.post("", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
def create_transaction(
    payload: TransactionCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    txn = Transaction(user_id=user.id, **payload.model_dump())

    # Score at write time against the state of the account *before* this row exists —
    # that is the moment the user actually made the decision. The column existed but
    # nothing ever populated it, so every impulse_score in the database was 0.
    if not payload.is_income:
        impulse = score_impulse(
            db,
            user,
            amount=payload.amount,
            category=payload.category,
            when=datetime.now(),
            is_recurring=payload.is_recurring,
        )
        txn.impulse_score = impulse.score

    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


@router.get("", response_model=list[TransactionOut])
def list_transactions(
    limit: int = Query(default=50, gt=0),
    offset: int = Query(default=0, ge=0),
    category: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    limit = min(limit, settings.MAX_TRANSACTION_PAGE_SIZE)
    stmt = select(Transaction).where(Transaction.user_id == user.id)
    if category:
        stmt = stmt.where(Transaction.category == category)
    if start_date:
        stmt = stmt.where(Transaction.transaction_date >= start_date)
    if end_date:
        stmt = stmt.where(Transaction.transaction_date <= end_date)
    stmt = (
        stmt.order_by(desc(Transaction.transaction_date), desc(Transaction.created_at))
        .offset(offset)
        .limit(limit)
    )
    return db.scalars(stmt).all()


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    transaction_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    txn = db.get(Transaction, transaction_id)
    # 404 rather than 403 when it belongs to someone else: a 403 would confirm
    # that the id exists.
    if txn is None or txn.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    db.delete(txn)
    db.commit()
