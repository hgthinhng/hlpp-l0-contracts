"""HLPP Alternative Data contracts — L1a alt-data observation schema.

Reference: spec §4 Wave 1 + Q8 ALL WARM tier in
~/.omc/plans/2026-05-22-l1a-maximum-buildout-v2.md

AlternativeDataBase is the canonical contract for all L1a alt-data collectors
(portwatch, f319, viirs, treasury_yield, etc.).  Collectors produce one row per
observation and validate it against this schema before parquet write.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_SOURCE_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")

SourceFamily = Literal[
    "macro",
    "forum",
    "satellite",
    "web3",
    "maritime",
    "academic",
    "governance",
    "sentiment",
    "trade",
    "geospatial",
    "report_text",
]


class AlternativeDataBase(BaseModel):
    """Canonical contract for L1a alternative-data observations.

    Every alt-data collector must produce rows that validate against this schema.
    The payload field holds source-specific JSON; callers are responsible for
    stable observation_id generation within their source.

    Spec constraints:
    - ts and pull_ts must be timezone-aware UTC datetimes.
    - pull_ts >= ts (collector cannot pull future data).
    - source_id must match ^[a-z][a-z0-9_]*$.
    - extra fields are forbidden (strict contract).
    - model is frozen (immutable after construction).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    ts: datetime = Field(..., description="Observation timestamp (UTC, timezone-aware)")
    source_id: str = Field(
        ..., description="Collector source identifier (e.g. 'portwatch', 'f319', 'viirs')"
    )
    source_family: SourceFamily = Field(
        ...,
        description=(
            "Source family classification: macro, forum, satellite, web3, maritime, "
            "academic, governance, sentiment, trade, geospatial, report_text"
        ),
    )
    observation_id: str = Field(
        ...,
        description="Stable unique key per row within source (caller responsibility to make stable)",
    )
    payload: dict[str, Any] = Field(
        ..., description="Flexible JSON payload containing the actual observation data"
    )
    license_url: str | None = Field(
        None, description="Provenance URL for licensed sources"
    )
    pull_ts: datetime = Field(
        ..., description="When collector fetched this observation (UTC, timezone-aware)"
    )
    pit_safe: bool = Field(
        True,
        description=(
            "Point-in-time safety flag. Must be False for any data that "
            "retroactively backfills historical values."
        ),
    )

    @field_validator("ts", "pull_ts", mode="after")
    @classmethod
    def _require_utc_aware(cls, v: datetime) -> datetime:
        """Reject naive datetimes — all timestamps must be UTC-aware."""
        if v.tzinfo is None:
            raise ValueError(
                f"datetime must be timezone-aware (UTC); got naive datetime: {v!r}"
            )
        return v

    @field_validator("source_id", mode="after")
    @classmethod
    def _validate_source_id(cls, v: str) -> str:
        """source_id must be non-empty and match ^[a-z][a-z0-9_]*$."""
        if not v:
            raise ValueError("source_id must not be empty")
        if not _SOURCE_ID_RE.match(v):
            raise ValueError(
                f"source_id must match ^[a-z][a-z0-9_]*$ (lowercase, no leading digit); got {v!r}"
            )
        return v

    @model_validator(mode="after")
    def _pull_ts_gte_ts(self) -> "AlternativeDataBase":
        """pull_ts must be >= ts (collector cannot pull data from the future)."""
        if self.pull_ts < self.ts:
            raise ValueError(
                f"pull_ts ({self.pull_ts!r}) must be >= ts ({self.ts!r}); "
                "collector cannot pull data whose observation timestamp is in the future"
            )
        return self


class GenericAltObservation(AlternativeDataBase):
    """One-off alt-data observation for collectors that don't need a custom subclass.

    Inherits all fields and validators from AlternativeDataBase unchanged.
    Use this when a collector doesn't add any extra typed columns.
    """


__all__ = ["AlternativeDataBase", "GenericAltObservation", "SourceFamily"]
