"""Shared crawler m12 base schema (Wave-3 deliverable, hlpp-l0-contracts 0.1.2).

Composes ``_BronzeProvenanceMixin`` + ``_VintageMixin`` + ``_LineageMixin`` and
adds the 5 ToS/extraction-risk fields per ADR-002 amendment 2026-05-05 FX-9.
All 3 Wave-3 crawler m12 contracts (m12-newscrawlers-articles-v1,
m12-macrodata-timeseries-v1, m12-researchcrawlers-reports-v1) MUST inherit
this mixin / extend this Pandera schema.
"""

from __future__ import annotations

import pandera.pandas as pa
from sqlalchemy import String
from sqlalchemy.orm import Mapped, declarative_mixin, mapped_column

from hlpp_l0_contracts.schema.lineage import LineageSchema, _LineageMixin
from hlpp_l0_contracts.schema.provenance import BronzeProvenanceSchema, _BronzeProvenanceMixin
from hlpp_l0_contracts.schema.vintage import VintageSchema, _VintageMixin


@declarative_mixin
class _CrawlerBaseMixin(
    _BronzeProvenanceMixin,
    _VintageMixin,
    _LineageMixin,
):
    """Wave-3 crawler m12 base mixin — 15 base cols + 5 ToS/extraction fields.

    Inherits 15 columns from upstream mixins (4 provenance + 7 vintage + 4 lineage).
    Adds 5 ToS/extraction-risk columns per ADR-002 amendment 2026-05-05 FX-9.
    """

    tos_status: Mapped[str | None] = mapped_column(String, nullable=True)
    robots_status: Mapped[str | None] = mapped_column(String, nullable=True)
    tos_citation_required: Mapped[str | None] = mapped_column(String, nullable=True)
    disabled_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    llm_extraction_risk: Mapped[str | None] = mapped_column(String, nullable=True)


_TOS_EXTRACTION_FIELDS = pa.DataFrameSchema(
    {
        "tos_status": pa.Column(pa.String, nullable=True, required=True),
        "robots_status": pa.Column(pa.String, nullable=True, required=True),
        "tos_citation_required": pa.Column(pa.String, nullable=True, required=True),
        "disabled_reason": pa.Column(pa.String, nullable=True, required=True),
        "llm_extraction_risk": pa.Column(pa.String, nullable=True, required=True),
    },
    strict=False,
    coerce=True,
)


def _merge_columns(*schemas: pa.DataFrameSchema) -> dict[str, pa.Column]:
    merged: dict[str, pa.Column] = {}
    for schema in schemas:
        for name, col in schema.columns.items():
            if name in merged:
                raise ValueError(f"duplicate column {name!r} across crawler-base subschemas")
            merged[name] = col
    return merged


CrawlerBaseSchema = pa.DataFrameSchema(
    _merge_columns(
        BronzeProvenanceSchema,
        VintageSchema,
        LineageSchema,
        _TOS_EXTRACTION_FIELDS,
    ),
    strict=False,
    coerce=True,
)


CRAWLER_BASE_COLUMNS: tuple[str, ...] = tuple(CrawlerBaseSchema.columns.keys())
"""20-column tuple for cross-JB schema lint (Wave-3 plan §7 G11/G12)."""
