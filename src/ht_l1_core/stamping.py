"""DataFrame helpers for stamping bronze provenance and vintage columns."""

from __future__ import annotations

from collections.abc import Hashable
from datetime import UTC, date, datetime
import hashlib
import json
from typing import Any

import pandas as pd

from ht_l1_core.schema.provenance import BronzeProvenanceSchema
from ht_l1_core.schema.vintage import VintageSchema


def stamp_for_bronze(
    df: pd.DataFrame,
    *,
    source: str,
    source_fetched_at: datetime,
    ingested_at: datetime | None = None,
    content_hash: str | None = None,
    vintage: datetime | None = None,
    as_of_date: date | None = None,
    status: str = "OK",
    skip_reason: str | None = None,
    error_category: str | None = None,
    revision_count: int = 0,
    last_consumed_at: datetime | None = None,
) -> pd.DataFrame:
    """Return a copy of ``df`` stamped with bronze provenance and vintage columns."""

    stamped = df.copy(deep=True)
    source_rows = stamped.to_dict("records")
    resolved_ingested_at = ingested_at or _utc_now()
    resolved_vintage = vintage or source_fetched_at
    resolved_as_of_date = as_of_date or resolved_vintage.date()

    stamped["source"] = source
    stamped["source_fetched_at"] = source_fetched_at
    stamped["ingested_at"] = resolved_ingested_at
    stamped["content_hash"] = (
        [_sha256_row(row) for row in source_rows]
        if content_hash is None
        else content_hash
    )
    stamped["vintage"] = resolved_vintage
    stamped["as_of_date"] = resolved_as_of_date
    stamped["status"] = status
    stamped["skip_reason"] = skip_reason
    stamped["error_category"] = error_category
    stamped["revision_count"] = revision_count
    stamped["last_consumed_at"] = last_consumed_at

    BronzeProvenanceSchema.validate(stamped[list(BronzeProvenanceSchema.columns)])
    VintageSchema.validate(stamped[list(VintageSchema.columns)])
    return stamped


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _sha256_row(row: dict[Hashable, Any]) -> str:
    payload = json.dumps(
        _jsonable(row),
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _jsonable(value: Any) -> Any:
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, pd.Timestamp):
        return None if pd.isna(value) else value.isoformat()
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if _is_missing_scalar(value):
        return None
    if hasattr(value, "item"):
        try:
            return value.item()
        except ValueError:
            return repr(value)
    return value


def _is_missing_scalar(value: Any) -> bool:
    try:
        missing = pd.isna(value)
    except (TypeError, ValueError):
        return False
    return bool(missing) if not isinstance(missing, (list, tuple)) else False
