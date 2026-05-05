"""Silver-builder lineage columns as a SQLAlchemy declarative mixin and Pandera schema.

Exports ``_LineageMixin`` (run_id, code_sha, inputs_hash, as_of_date, computed_at)
and ``LineageSchema`` (Pandera DataFrameSchema for validation).
"""

from datetime import date, datetime

import pandera.pandas as pa
from sqlalchemy import Date, String, TIMESTAMP
from sqlalchemy.orm import Mapped, declarative_mixin, mapped_column


_CODE_SHA_REGEX = r"^[0-9a-f]{40}$"


@declarative_mixin
class _LineageMixin:
    """HTAP F1 silver-builder lineage columns for SQLAlchemy models."""

    run_id: Mapped[str] = mapped_column(String, nullable=False)
    code_sha: Mapped[str] = mapped_column(String, nullable=False)
    inputs_hash: Mapped[str] = mapped_column(String, nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)


LineageSchema = pa.DataFrameSchema(
    {
        "run_id": pa.Column(pa.String, nullable=False, required=True),
        "code_sha": pa.Column(
            pa.String,
            checks=pa.Check.str_matches(_CODE_SHA_REGEX),
            nullable=False,
            required=True,
        ),
        "inputs_hash": pa.Column(pa.String, nullable=False, required=True),
        "as_of_date": pa.Column(pa.Date, nullable=False, required=True),
        "computed_at": pa.Column(pa.DateTime, nullable=False, required=True),
    },
    strict=True,
    coerce=True,
)
