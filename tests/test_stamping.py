from datetime import UTC, date, datetime
import hashlib
import json
from pathlib import Path
import sys

import pandas as pd
import pytest
from pandera.errors import SchemaError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import hlpp_l0_contracts
from hlpp_l0_contracts.stamping import stamp_for_bronze


def _expected_row_hash(row: dict[str, object]) -> str:
    payload = json.dumps(
        row,
        default=lambda value: value.isoformat()
        if isinstance(value, (date, datetime))
        else repr(value),
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def test_stamp_for_bronze_adds_default_provenance_and_vintage_without_mutating_input() -> None:
    source_fetched_at = datetime(2026, 5, 5, 9, 15, 0)
    source_rows = [
        {"symbol": "VCB", "close": 100.5, "trade_date": date(2026, 5, 4)},
        {"symbol": "FPT", "close": 88.0, "trade_date": date(2026, 5, 4)},
    ]
    df = pd.DataFrame(source_rows)
    original_columns = list(df.columns)
    before = datetime.now(UTC).replace(tzinfo=None)

    stamped = stamp_for_bronze(
        df,
        source="vci",
        source_fetched_at=source_fetched_at,
    )

    after = datetime.now(UTC).replace(tzinfo=None)

    assert list(df.columns) == original_columns
    assert stamped[original_columns].to_dict("records") == source_rows
    assert stamped["source"].tolist() == ["vci", "vci"]
    assert stamped["source_fetched_at"].tolist() == [source_fetched_at, source_fetched_at]
    assert stamped["vintage"].tolist() == [source_fetched_at, source_fetched_at]
    assert stamped["as_of_date"].tolist() == [source_fetched_at.date(), source_fetched_at.date()]
    assert stamped["status"].tolist() == ["OK", "OK"]
    assert stamped["skip_reason"].isna().all()
    assert stamped["error_category"].isna().all()
    assert stamped["revision_count"].tolist() == [0, 0]
    assert stamped["last_consumed_at"].isna().all()
    assert stamped["ingested_at"].between(before, after).all()
    assert stamped["content_hash"].tolist() == [
        _expected_row_hash(row) for row in source_rows
    ]


def test_stamp_for_bronze_uses_explicit_metadata_overrides() -> None:
    source_fetched_at = datetime(2026, 5, 5, 9, 15, 0)
    ingested_at = datetime(2026, 5, 5, 9, 16, 0)
    vintage = datetime(2026, 5, 4, 15, 0, 0)
    as_of_date = date(2026, 5, 4)
    last_consumed_at = datetime(2026, 5, 5, 10, 0, 0)

    stamped = stamp_for_bronze(
        pd.DataFrame([{"symbol": "VCB", "close": 100.5}]),
        source="kbs",
        source_fetched_at=source_fetched_at,
        ingested_at=ingested_at,
        content_hash="known-hash",
        vintage=vintage,
        as_of_date=as_of_date,
        status="DEGRADED",
        skip_reason="partial payload",
        error_category="upstream_timeout",
        revision_count=3,
        last_consumed_at=last_consumed_at,
    )

    row = stamped.iloc[0]
    assert row["source"] == "kbs"
    assert row["source_fetched_at"] == source_fetched_at
    assert row["ingested_at"] == ingested_at
    assert row["content_hash"] == "known-hash"
    assert row["vintage"] == vintage
    assert row["as_of_date"] == as_of_date
    assert row["status"] == "DEGRADED"
    assert row["skip_reason"] == "partial payload"
    assert row["error_category"] == "upstream_timeout"
    assert row["revision_count"] == 3
    assert row["last_consumed_at"] == last_consumed_at


def test_stamp_for_bronze_raises_schema_error_for_invalid_status() -> None:
    with pytest.raises(SchemaError):
        stamp_for_bronze(
            pd.DataFrame([{"symbol": "VCB", "close": 100.5}]),
            source="vci",
            source_fetched_at=datetime(2026, 5, 5, 9, 15, 0),
            status="BROKEN",
        )


def test_stamp_for_bronze_is_exported_from_top_level_package() -> None:
    assert hlpp_l0_contracts.stamp_for_bronze is stamp_for_bronze
