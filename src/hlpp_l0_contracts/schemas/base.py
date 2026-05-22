"""Base Pydantic models for HLPP-NORMALIZED + HLPP-COMPUTED schemas.

Reference: spec §7 (NORMALIZED) + §8 (COMPUTED) in
~/.omc/plans/2026-05-20-hlpp-v1-architecture.md
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class HlppNormalizedBase(BaseModel):
    """Mandatory columns for every L1b NORMALIZED dataset.

    Spec §7.1. Per-builder payload schema extends via subclass + adds payload fields.
    Stored partition: as_of_date=YYYY-MM-DD/part-*.parquet
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    ticker: str = Field(..., description="Uppercase, vendor-canonical")
    as_of_date: date = Field(..., description="Partition key (build date)")
    business_date: date = Field(..., description="Data effective date")
    business_time: datetime | None = Field(
        None, description="Intraday only; null for daily"
    )
    vendor: Literal["fqx", "vnstock", "bctc", "internal"] = Field(
        ..., description="Source identifier"
    )
    ingested_at: datetime = Field(..., description="Builder run timestamp")
    schema_id: Literal["hlpp-normalized/v1"] = "hlpp-normalized/v1"
    adjustment_type: Literal[
        "raw", "backward_adjusted", "forward_adjusted", "unknown"
    ] = "unknown"
    dataset_id: str = Field(
        ..., description="e.g. 'price-intraday-30s', 'fundamentals-quarterly'"
    )
    builder_version: str = Field(
        ..., description="Auto-injected git_commit_hash of producing builder"
    )


class HlppComputedBase(HlppNormalizedBase):
    """Mandatory columns for every L2 COMPUTED dataset.

    Spec §8. Extends NORMALIZED base + adds analysis lineage fields.
    Stored partition: COMPUTED/{market}/{asset}/{frequency}/l2{a..f}/{domain}/{name}/as_of_date=*
    """

    schema_id: Literal["hlpp-computed/v1"] = "hlpp-computed/v1"  # type: ignore[assignment]
    analysis_version: str = Field(
        ..., description="Auto-injected git_commit_hash of producing analysis"
    )
    input_partitions: list[str] = Field(
        ...,
        description=(
            "List of input partition IDs, e.g. "
            "['normalized:price-daily:as_of_date=2026-05-20', "
            "'computed:vn/equity/daily/l2a/factor/size:as_of_date=2026-05-20']"
        ),
    )
    chain_depth: Literal["l2a", "l2b", "l2c", "l2d", "l2e", "l2f"] = Field(
        ..., description="DAG depth encoding"
    )
    domain: Literal["factor", "ta", "fa", "signal", "regime", "alert"] = Field(
        ..., description="Domain category (path component)"
    )
    lookback_days: int | None = Field(None, description="Rolling window if applicable")
