"""Tests for ht_l1_core.backfillable — Backfillable Protocol + @backfillable_check decorator."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

import pytest

from ht_l1_core.backfillable import (
    Backfillable,
    BackfillResult,
    BackfillRow,
    BackfillTargetYearUnavailable,
    backfillable_check,
)


# ---------------------------------------------------------------------------
# Protocol conformance helpers
# ---------------------------------------------------------------------------


class RealBackfiller:
    """Correctly-implemented backfiller: returns rows dated to target_year."""

    @backfillable_check
    def backfill(self, target_year: int) -> list[BackfillRow]:
        return [
            {"as_of_date": date(target_year, 6, 15), "value": 42.0},
            {"as_of_date": date(target_year, 9, 30), "value": 99.0},
        ]


class FakeBackfiller:
    """Broken backfiller: ignores target_year and always returns today's data."""

    @backfillable_check
    def backfill(self, target_year: int) -> list[BackfillRow]:
        # Uses today's date regardless of target_year — classic fake backfill.
        return [
            {"as_of_date": date.today(), "value": 1.0},
        ]


class ProtocolConformingBackfiller:
    """Conforms to the Backfillable Protocol (keyword-only target_year)."""

    def backfill(self, *, target_year: int, **kw: object) -> BackfillResult:
        return BackfillResult(target_year=target_year, rows=3, status="OK")


class NonBackfiller:
    """Does NOT conform to Backfillable (no backfill method)."""

    def collect(self) -> None:
        return None


# ---------------------------------------------------------------------------
# Protocol contract tests
# ---------------------------------------------------------------------------


def test_backfillable_protocol_accepts_conforming_implementer() -> None:
    adapter = ProtocolConformingBackfiller()

    assert isinstance(adapter, Backfillable)
    result = adapter.backfill(target_year=2023)
    assert result.target_year == 2023
    assert result.rows == 3
    assert result.status == "OK"


def test_backfillable_protocol_rejects_non_implementer() -> None:
    assert not isinstance(NonBackfiller(), Backfillable)


def test_backfill_result_fields_are_correct() -> None:
    result = BackfillResult(target_year=2022, rows=10, status="OK", message="done")
    assert result.target_year == 2022
    assert result.rows == 10
    assert result.status == "OK"
    assert result.message == "done"


def test_backfill_target_year_unavailable_is_structured() -> None:
    exc = BackfillTargetYearUnavailable(
        target_year=2020,
        available_years=(2022, 2023),
        source="test-source",
    )
    assert exc.target_year == 2020
    assert exc.available_years == (2022, 2023)
    assert exc.source == "test-source"
    assert "target_year=2020 unavailable" in str(exc)


# ---------------------------------------------------------------------------
# @backfillable_check decorator — real backfill passes
# ---------------------------------------------------------------------------


def test_decorator_passes_real_backfill_producing_target_year_data() -> None:
    collector = RealBackfiller()
    rows = collector.backfill(2023)

    assert len(rows) == 2
    assert all(row["as_of_date"].year == 2023 for row in rows)


def test_decorator_passes_when_target_year_is_current_year() -> None:
    """When target_year == today.year the re-stamp check is skipped (ambiguous)."""
    today_year = date.today().year

    class CurrentYearBackfiller:
        @backfillable_check
        def backfill(self, target_year: int) -> list[BackfillRow]:
            return [{"as_of_date": date.today(), "value": 7.0}]

    collector = CurrentYearBackfiller()
    # Must NOT raise even though dates are "today"
    rows = collector.backfill(today_year)
    assert len(rows) == 1


def test_decorator_passes_when_result_is_empty() -> None:
    class EmptyBackfiller:
        @backfillable_check
        def backfill(self, target_year: int) -> list[BackfillRow]:
            return []

    collector = EmptyBackfiller()
    rows = collector.backfill(2020)
    assert rows == []


def test_decorator_passes_rows_without_date_columns() -> None:
    """Rows with no date field are un-checkable — decorator should not raise."""

    class NoDatesBackfiller:
        @backfillable_check
        def backfill(self, target_year: int) -> list[BackfillRow]:
            return [{"value": 99, "label": "aggregate"}]

    collector = NoDatesBackfiller()
    rows = collector.backfill(2021)
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# @backfillable_check decorator — fake backfill caught
# ---------------------------------------------------------------------------


def test_decorator_catches_fake_backfill_that_restamps_today() -> None:
    """Fake backfiller returning today's date for a historical target must raise."""
    collector = FakeBackfiller()
    today_year = date.today().year
    historical_year = today_year - 3  # definitely not today

    with pytest.raises(RuntimeError, match="fake backfill"):
        collector.backfill(historical_year)


def test_decorator_error_message_includes_target_year() -> None:
    collector = FakeBackfiller()
    historical_year = date.today().year - 5

    with pytest.raises(RuntimeError) as exc_info:
        collector.backfill(historical_year)

    assert str(historical_year) in str(exc_info.value)


# ---------------------------------------------------------------------------
# @backfillable_check — keyword-style target_year invocation
# ---------------------------------------------------------------------------


def test_decorator_works_with_keyword_target_year() -> None:
    collector = RealBackfiller()
    rows = collector.backfill(target_year=2019)
    assert all(row["as_of_date"].year == 2019 for row in rows)


def test_decorator_catches_fake_backfill_with_keyword_target_year() -> None:
    collector = FakeBackfiller()
    historical_year = date.today().year - 2

    with pytest.raises(RuntimeError, match="fake backfill"):
        collector.backfill(target_year=historical_year)


# ---------------------------------------------------------------------------
# @backfillable_check — iterable return type support
# ---------------------------------------------------------------------------


def test_decorator_materialises_generator_into_list() -> None:
    class GenBackfiller:
        @backfillable_check
        def backfill(self, target_year: int) -> Iterable[BackfillRow]:  # type: ignore[override]
            yield {"as_of_date": date(target_year, 1, 1), "v": 1}
            yield {"as_of_date": date(target_year, 7, 1), "v": 2}

    collector = GenBackfiller()
    result = collector.backfill(2018)
    # decorator returns a list, not a generator
    assert isinstance(result, list)
    assert len(result) == 2
