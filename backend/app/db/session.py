from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

_engine_kwargs: dict = {"pool_pre_ping": True}
if settings.DATABASE_URL.startswith("postgresql"):
    # Render's free Postgres caps connections; recycle before it drops them for us.
    _engine_kwargs.update(pool_size=5, max_overflow=5, pool_recycle=1800)

engine = create_engine(settings.DATABASE_URL, **_engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        # Nothing to commit here — routes commit explicitly. The rollback below
        # guarantees a failed request never leaves a half-applied transaction
        # on a pooled connection for the next request to inherit.
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
