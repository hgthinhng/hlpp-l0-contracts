"""Tests for AlternativeDataBase + GenericAltObservation Pydantic contracts."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from hlpp_l0_contracts.schemas.alt_data import AlternativeDataBase, GenericAltObservation

# ---------------------------------------------------------------------------
# Canonical sample — all tests derive from this
# ---------------------------------------------------------------------------
_TS = datetime(2026, 5, 20, 8, 0, 0, tzinfo=timezone.utc)
_PULL_TS = datetime(2026, 5, 20, 9, 0, 0, tzinfo=timezone.utc)

VALID_SAMPLE: dict = {
    "ts": _TS,
    "source_id": "portwatch",
    "source_family": "maritime",
    "observation_id": "portwatch-2026-05-20-vessel-001",
    "payload": {"vessel_count": 42, "port": "SGSIN"},
    "license_url": "https://portwatch.imf.org/terms",
    "pull_ts": _PULL_TS,
    "pit_safe": True,
}


# ---------------------------------------------------------------------------
# Happy-path
# ---------------------------------------------------------------------------


def test_valid_construction():
    row = AlternativeDataBase(**VALID_SAMPLE)
    assert row.source_id == "portwatch"
    assert row.source_family == "maritime"
    assert row.pit_safe is True
    assert row.payload["vessel_count"] == 42


def test_generic_alt_observation_construction():
    row = GenericAltObservation(**VALID_SAMPLE)
    assert isinstance(row, AlternativeDataBase)
    assert row.source_family == "maritime"


def test_license_url_optional():
    payload = dict(VALID_SAMPLE)
    del payload["license_url"]
    row = AlternativeDataBase(**payload)
    assert row.license_url is None


def test_pit_safe_defaults_true():
    payload = {k: v for k, v in VALID_SAMPLE.items() if k != "pit_safe"}
    row = AlternativeDataBase(**payload)
    assert row.pit_safe is True


def test_pit_safe_can_be_false():
    row = AlternativeDataBase(**{**VALID_SAMPLE, "pit_safe": False})
    assert row.pit_safe is False


# ---------------------------------------------------------------------------
# extra="forbid"
# ---------------------------------------------------------------------------


def test_extra_field_forbidden():
    with pytest.raises(ValidationError):
        AlternativeDataBase(**VALID_SAMPLE, unexpected_column="bad")


# ---------------------------------------------------------------------------
# Timezone-aware datetime enforcement
# ---------------------------------------------------------------------------


def test_naive_ts_raises():
    naive_ts = datetime(2026, 5, 20, 8, 0, 0)  # no tzinfo
    with pytest.raises(ValidationError, match="timezone-aware"):
        AlternativeDataBase(**{**VALID_SAMPLE, "ts": naive_ts})


def test_naive_pull_ts_raises():
    naive_pull = datetime(2026, 5, 20, 9, 0, 0)  # no tzinfo
    with pytest.raises(ValidationError, match="timezone-aware"):
        AlternativeDataBase(**{**VALID_SAMPLE, "pull_ts": naive_pull})


# ---------------------------------------------------------------------------
# source_family Literal enforcement
# ---------------------------------------------------------------------------


def test_valid_source_families():
    valid_families = [
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
    ]
    for family in valid_families:
        row = AlternativeDataBase(**{**VALID_SAMPLE, "source_family": family})
        assert row.source_family == family


def test_invalid_source_family_raises():
    with pytest.raises(ValidationError):
        AlternativeDataBase(**{**VALID_SAMPLE, "source_family": "unknown_family"})


def test_invalid_source_family_bloomberg_raises():
    with pytest.raises(ValidationError):
        AlternativeDataBase(**{**VALID_SAMPLE, "source_family": "bloomberg"})


# ---------------------------------------------------------------------------
# pull_ts >= ts rule
# ---------------------------------------------------------------------------


def test_pull_ts_equal_to_ts_accepted():
    row = AlternativeDataBase(**{**VALID_SAMPLE, "pull_ts": _TS})
    assert row.pull_ts == row.ts


def test_pull_ts_before_ts_raises():
    earlier_pull = datetime(2026, 5, 20, 7, 0, 0, tzinfo=timezone.utc)  # before _TS
    with pytest.raises(ValidationError, match="pull_ts"):
        AlternativeDataBase(**{**VALID_SAMPLE, "pull_ts": earlier_pull})


# ---------------------------------------------------------------------------
# source_id regex
# ---------------------------------------------------------------------------


def test_source_id_valid_patterns():
    valid_ids = ["portwatch", "f319", "viirs", "treasury_yield", "a", "x1_y2"]
    for sid in valid_ids:
        row = AlternativeDataBase(**{**VALID_SAMPLE, "source_id": sid})
        assert row.source_id == sid


def test_source_id_leading_digit_raises():
    with pytest.raises(ValidationError, match="source_id"):
        AlternativeDataBase(**{**VALID_SAMPLE, "source_id": "1portwatch"})


def test_source_id_uppercase_raises():
    with pytest.raises(ValidationError, match="source_id"):
        AlternativeDataBase(**{**VALID_SAMPLE, "source_id": "PortWatch"})


def test_source_id_empty_raises():
    with pytest.raises(ValidationError):
        AlternativeDataBase(**{**VALID_SAMPLE, "source_id": ""})


def test_source_id_hyphen_raises():
    with pytest.raises(ValidationError, match="source_id"):
        AlternativeDataBase(**{**VALID_SAMPLE, "source_id": "port-watch"})


# ---------------------------------------------------------------------------
# Frozen model (immutability)
# ---------------------------------------------------------------------------


def test_model_is_frozen():
    row = AlternativeDataBase(**VALID_SAMPLE)
    with pytest.raises(ValidationError):
        row.source_id = "modified"  # type: ignore[misc]
