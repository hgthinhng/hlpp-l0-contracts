"""Vintage tracking columns as a SQLAlchemy declarative mixin and Pandera schema.

Exports ``_VintageMixin`` (vintage, status, skip_reason, revision_count,
last_consumed_at) and ``VintageSchema`` (Pandera DataFrameSchema with status checks).
"""

from datetime import date, datetime
from typing import Any

import pandera.pandas as pa
from sqlalchemy import CheckConstraint, Date, Integer, String, TIMESTAMP, text
from sqlalchemy.orm import Mapped, declarative_mixin, declared_attr, mapped_column


VINTAGE_STATUSES = ("OK", "DEGRADED", "SKIPPED")


@declarative_mixin
class _VintageMixin:
    vintage: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    skip_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    error_category: Mapped[str | None] = mapped_column(String, nullable=True)
    revision_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    last_consumed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP,
        nullable=True,
    )

    @declared_attr.directive
    def __table_args__(cls: type[Any]) -> tuple[CheckConstraint]:
        table_name = getattr(cls, "__tablename__")
        return (
            CheckConstraint(
                "status IN ('OK', 'DEGRADED', 'SKIPPED')",
                name=f"ck_{table_name}_vintage_status",
            ),
        )


VintageSchema = pa.DataFrameSchema(
    {
        "vintage": pa.Column(pa.DateTime, nullable=False, required=True),
        "as_of_date": pa.Column(pa.Date, nullable=False, required=True),
        "status": pa.Column(
            pa.String,
            checks=pa.Check.isin(VINTAGE_STATUSES),
            nullable=False,
            required=True,
        ),
        "skip_reason": pa.Column(pa.String, nullable=True, required=True),
        "error_category": pa.Column(pa.String, nullable=True, required=True),
        "revision_count": pa.Column(
            pa.Int,
            nullable=False,
            required=True,
            default=0,
        ),
        "last_consumed_at": pa.Column(pa.DateTime, nullable=True, required=True),
    },
    strict=True,
    coerce=True,
)
