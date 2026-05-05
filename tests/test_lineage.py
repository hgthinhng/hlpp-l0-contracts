from pathlib import Path
import sys

import pandas as pd
import pytest
from pandera.errors import SchemaError
from sqlalchemy import Date, String, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ht_l1_core.schema.lineage import LineageSchema, _LineageMixin
from ht_l1_core.schema.vintage import _VintageMixin


LINEAGE_COLUMNS = [
    "run_id",
    "code_sha",
    "inputs_hash",
    "computed_at",
]


class Base(DeclarativeBase):
    pass


class SilverTable(_LineageMixin, Base):
    __tablename__ = "silver_table"

    id: Mapped[int] = mapped_column(primary_key=True)


def _lineage_frame(code_sha: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "run_id": ["run-20260505"],
            "code_sha": [code_sha],
            "inputs_hash": ["inputs-hash"],
            "computed_at": [pd.Timestamp("2026-05-05T09:30:00")],
        }
    )


def test_lineage_mixin_and_schema_define_four_lineage_columns() -> None:
    table = SilverTable.__table__

    assert list(LineageSchema.columns) == LINEAGE_COLUMNS
    assert len(LineageSchema.columns) == 4

    assert isinstance(table.c.run_id.type, String)
    assert isinstance(table.c.code_sha.type, String)
    assert isinstance(table.c.inputs_hash.type, String)
    assert "as_of_date" not in table.c
    assert isinstance(table.c.computed_at.type, TIMESTAMP)


def test_lineage_and_vintage_mixins_compose_with_vintage_as_of_date() -> None:
    class SilverVintageTable(_LineageMixin, _VintageMixin, Base):
        __tablename__ = "silver_vintage_table"

        id: Mapped[int] = mapped_column(primary_key=True)

    table = SilverVintageTable.__table__

    assert isinstance(table.c.computed_at.type, TIMESTAMP)
    assert isinstance(table.c.as_of_date.type, Date)


def test_lineage_schema_rejects_dirty_code_sha_suffix() -> None:
    clean_sha = "a" * 40

    LineageSchema.validate(_lineage_frame(clean_sha))

    with pytest.raises(SchemaError):
        LineageSchema.validate(_lineage_frame(f"{clean_sha}-dirty"))
