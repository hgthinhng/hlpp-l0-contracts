from datetime import date, datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd
import pytest
from sqlalchemy import Integer, create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from ht_l1_core.schema.vintage import VintageSchema, _VintageMixin


class Base(DeclarativeBase):
    pass


class VintageRecord(_VintageMixin, Base):
    __tablename__ = "vintage_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)


def make_record(**overrides: object) -> VintageRecord:
    values = {
        "vintage": datetime(2026, 5, 5, 9, 0, 0),
        "as_of_date": date(2026, 5, 5),
        "status": "OK",
    }
    values.update(overrides)
    return VintageRecord(**values)


def test_vintage_columns_have_adr_003_nullability_contract() -> None:
    columns = VintageRecord.__table__.c

    assert [column.name for column in columns if column.name != "id"] == [
        "vintage",
        "as_of_date",
        "status",
        "skip_reason",
        "error_category",
        "revision_count",
        "last_consumed_at",
    ]
    assert not columns.vintage.nullable
    assert not columns.as_of_date.nullable
    assert not columns.status.nullable
    assert columns.skip_reason.nullable
    assert columns.error_category.nullable
    assert not columns.revision_count.nullable
    assert columns.last_consumed_at.nullable


def test_status_check_constraint_rejects_unknown_status() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(make_record(status="BROKEN"))

        with pytest.raises(IntegrityError):
            session.commit()


def test_revision_count_defaults_to_zero_and_last_consumed_at_allows_null() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(make_record(last_consumed_at=None))
        session.commit()

        record = session.scalars(select(VintageRecord)).one()

    assert record.revision_count == 0
    assert record.last_consumed_at is None


def test_vintage_schema_allows_null_last_consumed_at() -> None:
    df = pd.DataFrame(
        [
            {
                "vintage": pd.Timestamp("2026-05-05T09:00:00"),
                "as_of_date": date(2026, 5, 5),
                "status": "SKIPPED",
                "skip_reason": "holiday",
                "error_category": None,
                "revision_count": 0,
                "last_consumed_at": None,
            }
        ]
    )

    validated = VintageSchema.validate(df)

    assert pd.isna(validated.loc[0, "last_consumed_at"])
