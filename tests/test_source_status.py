"""Tests for hlpp_l0_contracts.source_status — SourceStatus enum, SourceManifestEntry, emit_skipped_row."""

from __future__ import annotations

import logging
from datetime import date

import pytest

from hlpp_l0_contracts.source_status import (
    SourceManifestEntry,
    SourceStatus,
    emit_skipped_row,
)
from hlpp_l0_contracts.schema.crawler_base import CRAWLER_BASE_COLUMNS


# ---------------------------------------------------------------------------
# SourceStatus enum
# ---------------------------------------------------------------------------


def test_source_status_values_are_correct_strings() -> None:
    assert SourceStatus.ACTIVE == "active"
    assert SourceStatus.EXTERNAL_DEAD == "external_dead"
    assert SourceStatus.EXPERIMENTAL == "experimental"


def test_source_status_is_str_enum() -> None:
    assert isinstance(SourceStatus.ACTIVE, str)
    assert isinstance(SourceStatus.EXTERNAL_DEAD, str)
    assert isinstance(SourceStatus.EXPERIMENTAL, str)


def test_source_status_string_comparison() -> None:
    assert SourceStatus.ACTIVE == "active"
    assert SourceStatus.EXTERNAL_DEAD == "external_dead"
    assert SourceStatus.EXPERIMENTAL == "experimental"


def test_source_status_has_exactly_three_members() -> None:
    assert set(SourceStatus) == {
        SourceStatus.ACTIVE,
        SourceStatus.EXTERNAL_DEAD,
        SourceStatus.EXPERIMENTAL,
    }


# ---------------------------------------------------------------------------
# SourceManifestEntry dataclass
# ---------------------------------------------------------------------------


def test_source_manifest_entry_fields() -> None:
    entry = SourceManifestEntry(
        status=SourceStatus.EXTERNAL_DEAD,
        reason="API shut down 2025-Q4",
        last_checked=date(2026, 1, 10),
        revival_blocker="No alternative endpoint exists",
        revival_priority="low",
    )
    assert entry.status == SourceStatus.EXTERNAL_DEAD
    assert entry.reason == "API shut down 2025-Q4"
    assert entry.last_checked == date(2026, 1, 10)
    assert entry.revival_blocker == "No alternative endpoint exists"
    assert entry.revival_priority == "low"


def test_source_manifest_entry_default_revival_priority() -> None:
    entry = SourceManifestEntry(
        status=SourceStatus.ACTIVE,
        reason="Healthy",
        last_checked=date(2026, 5, 10),
        revival_blocker="",
    )
    assert entry.revival_priority == "low"


def test_source_manifest_entry_all_revival_priorities() -> None:
    for priority in ("low", "medium", "high"):
        entry = SourceManifestEntry(
            status=SourceStatus.EXPERIMENTAL,
            reason="Testing",
            last_checked=date(2026, 5, 10),
            revival_blocker="TBD",
            revival_priority=priority,  # type: ignore[arg-type]
        )
        assert entry.revival_priority == priority


# ---------------------------------------------------------------------------
# emit_skipped_row — 20-col alignment
# ---------------------------------------------------------------------------


def test_emit_skipped_row_produces_all_20_crawler_base_columns() -> None:
    row = emit_skipped_row(
        source="test-source",
        status=SourceStatus.ACTIVE,
        reason="test skip",
        base_columns={},
    )
    for col in CRAWLER_BASE_COLUMNS:
        assert col in row, f"Missing column: {col}"
    assert len([k for k in row if k in CRAWLER_BASE_COLUMNS]) == 20


def test_emit_skipped_row_sets_status_to_skipped() -> None:
    row = emit_skipped_row(
        source="src",
        status=SourceStatus.EXPERIMENTAL,
        reason="testing",
        base_columns={},
    )
    assert row["status"] == "SKIPPED"


def test_emit_skipped_row_skip_reason_contains_status_and_reason() -> None:
    row = emit_skipped_row(
        source="src",
        status=SourceStatus.EXTERNAL_DEAD,
        reason="endpoint gone",
        base_columns={},
    )
    assert "external_dead" in row["skip_reason"]
    assert "endpoint gone" in row["skip_reason"]


def test_emit_skipped_row_error_category_is_source_status_string() -> None:
    row = emit_skipped_row(
        source="src",
        status=SourceStatus.EXTERNAL_DEAD,
        reason="gone",
        base_columns={},
    )
    assert row["error_category"] == "external_dead"


def test_emit_skipped_row_overrides_caller_status_field() -> None:
    """Caller cannot override skip-semantic columns via base_columns."""
    row = emit_skipped_row(
        source="src",
        status=SourceStatus.ACTIVE,
        reason="reason",
        base_columns={"status": "OK"},  # caller tried to set OK — must be overwritten
    )
    assert row["status"] == "SKIPPED"


def test_emit_skipped_row_merges_base_columns() -> None:
    row = emit_skipped_row(
        source="my-source",
        status=SourceStatus.ACTIVE,
        reason="skip",
        base_columns={
            "as_of_date": date(2023, 6, 1),
            "content_hash": "abc123",
        },
    )
    assert row["as_of_date"] == date(2023, 6, 1)
    assert row["content_hash"] == "abc123"
    assert row["source"] == "my-source"


def test_emit_skipped_row_source_column_from_arg() -> None:
    row = emit_skipped_row(
        source="fred-proxy",
        status=SourceStatus.EXPERIMENTAL,
        reason="wip",
        base_columns={},
    )
    assert row["source"] == "fred-proxy"


# ---------------------------------------------------------------------------
# emit_skipped_row — EXTERNAL_DEAD loud warning
# ---------------------------------------------------------------------------


def test_emit_skipped_row_logs_warning_for_external_dead(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="hlpp_l0_contracts.source_status"):
        emit_skipped_row(
            source="dead-api",
            status=SourceStatus.EXTERNAL_DEAD,
            reason="host unreachable",
            base_columns={},
        )

    assert any(
        "EXTERNAL_DEAD" in record.message for record in caplog.records
    ), "Expected a WARNING log mentioning EXTERNAL_DEAD"


def test_emit_skipped_row_does_not_warn_for_active(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="hlpp_l0_contracts.source_status"):
        emit_skipped_row(
            source="live-api",
            status=SourceStatus.ACTIVE,
            reason="intentional skip",
            base_columns={},
        )

    dead_warnings = [r for r in caplog.records if "EXTERNAL_DEAD" in r.message]
    assert len(dead_warnings) == 0


def test_emit_skipped_row_does_not_warn_for_experimental(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="hlpp_l0_contracts.source_status"):
        emit_skipped_row(
            source="exp-api",
            status=SourceStatus.EXPERIMENTAL,
            reason="under test",
            base_columns={},
        )

    dead_warnings = [r for r in caplog.records if "EXTERNAL_DEAD" in r.message]
    assert len(dead_warnings) == 0


# ---------------------------------------------------------------------------
# emit_skipped_row — sentinel code_sha
# ---------------------------------------------------------------------------


def test_emit_skipped_row_sentinel_code_sha_is_40_zeros() -> None:
    row = emit_skipped_row(
        source="src",
        status=SourceStatus.ACTIVE,
        reason="skip",
        base_columns={},
    )
    # When caller doesn't supply code_sha, default sentinel is 40 zeros.
    assert row["code_sha"] == "0" * 40


def test_emit_skipped_row_caller_can_override_code_sha() -> None:
    sha = "a" * 40
    row = emit_skipped_row(
        source="src",
        status=SourceStatus.ACTIVE,
        reason="skip",
        base_columns={"code_sha": sha},
    )
    assert row["code_sha"] == sha
