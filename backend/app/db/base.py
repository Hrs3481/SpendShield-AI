from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Imported for their side effect: Alembic's autogenerate and Base.metadata both
# need every model registered before they run.
def import_all_models() -> None:
    from app.models import budget, transaction, user  # noqa: F401
