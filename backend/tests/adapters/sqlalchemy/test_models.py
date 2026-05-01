from app.adapters.sqlalchemy.models import Contractor


def test_contractor_inn_is_unique_in_metadata() -> None:
    assert Contractor.__table__.c.inn.unique is True


def test_contractor_created_at_is_non_nullable_in_metadata() -> None:
    assert Contractor.__table__.c.created_at.nullable is False
