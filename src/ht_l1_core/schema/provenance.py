"""Shared bronze-layer provenance columns and Pandera validation schema.

Exports ``_BronzeProvenanceMixin`` (source, source_fetched_at, ingested_at,
content_hash) and ``BronzeProvenanceSchema`` (Pandera DataFrameSchema for validation).
"""

from datetime import datetime

import pandera.pandas as pa
from sqlalchemy import TIMESTAMP, String
from sqlalchemy.orm import Mapped, declarative_mixin, mapped_column


@declarative_mixin
class _BronzeProvenanceMixin:
    """SQLAlchemy declarative mixin for bronze ingestion provenance."""

    source: Mapped[str] = mapped_column(String, nullable=False)
    source_fetched_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)
    content_hash: Mapped[str] = mapped_column(String, nullable=False)


BronzeProvenanceSchema = pa.DataFrameSchema(
    {
        "source": pa.Column(pa.String, nullable=False, required=True),
        "source_fetched_at": pa.Column(pa.DateTime, nullable=False, required=True),
        "ingested_at": pa.Column(pa.DateTime, nullable=False, required=True),
        "content_hash": pa.Column(pa.String, nullable=False, required=True),
    }
)
