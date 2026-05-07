from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime
from typing import Any

import pytest

from ht_l1_core.protocols import (
    Backfillable,
    BackfillResult,
    BackfillTargetYearUnavailable,
    BarCallback,
    BarData,
    TierAStreamConsumer,
    TierAStreamSession,
)


class YearlyBackfiller:
    def backfill(self, *, target_year: int, **kw: object) -> BackfillResult:
        if target_year != 2025:
            raise BackfillTargetYearUnavailable(
                target_year=target_year,
                available_years=(2025,),
                source="unit-source",
            )
        return BackfillResult(target_year=target_year, rows=3, status="OK")


class NotBackfillable:
    def collect(self) -> None:
        return None


class FakeSession:
    def __init__(self) -> None:
        self.started = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.started = False


class FakeConsumer:
    def __init__(self) -> None:
        self.session = FakeSession()

    def start(self, tickers: tuple[str, ...], callback: BarCallback) -> TierAStreamSession:
        self.session.start()
        callback(
            BarData(
                ticker=tickers[0],
                observed_at=datetime(2026, 5, 7, 2, 30, tzinfo=UTC),
                price=42.5,
                volume=1000,
            )
        )
        return self.session

    def stop(self) -> None:
        self.session.stop()


def test_backfill_result_is_frozen_dataclass_with_contract_fields() -> None:
    result = BackfillResult(target_year=2025, rows=7, status="OK_EMPTY")

    assert [field.name for field in fields(result)] == [
        "target_year",
        "rows",
        "status",
        "message",
    ]
    assert result.message == ""
    with pytest.raises(FrozenInstanceError):
        result.rows = 8  # type: ignore[misc]


def test_backfillable_protocol_accepts_target_year_backfill_implementer() -> None:
    adapter = YearlyBackfiller()

    assert isinstance(adapter, Backfillable)
    assert adapter.backfill(target_year=2025) == BackfillResult(
        target_year=2025,
        rows=3,
        status="OK",
    )


def test_backfillable_protocol_rejects_objects_without_backfill() -> None:
    assert not isinstance(NotBackfillable(), Backfillable)


def test_backfill_target_year_unavailable_is_loud_and_structured() -> None:
    with pytest.raises(BackfillTargetYearUnavailable) as exc_info:
        YearlyBackfiller().backfill(target_year=2024)

    exc = exc_info.value
    assert exc.target_year == 2024
    assert exc.available_years == (2025,)
    assert exc.source == "unit-source"
    assert "target_year=2024 unavailable" in str(exc)
    assert "available_years=(2025,)" in str(exc)


def test_backfill_target_year_unavailable_message_handles_unknown_availability() -> None:
    exc = BackfillTargetYearUnavailable(target_year=2023)

    assert exc.available_years == ()
    assert str(exc) == "target_year=2023 unavailable"


def test_bar_data_is_frozen_dataclass_with_raw_payload_default() -> None:
    bar = BarData(
        ticker="VCB",
        observed_at=datetime(2026, 5, 7, 2, 31, tzinfo=UTC),
        price=88.2,
        volume=10_000,
    )

    assert [field.name for field in fields(bar)] == [
        "ticker",
        "observed_at",
        "price",
        "volume",
        "raw",
    ]
    assert bar.raw == {}
    with pytest.raises(FrozenInstanceError):
        bar.price = 89.0  # type: ignore[misc]


def test_bar_data_rejects_naive_observed_at() -> None:
    with pytest.raises(ValueError, match="observed_at must be timezone-aware"):
        BarData(
            ticker="VCB",
            observed_at=datetime(2026, 5, 7, 2, 31),
            price=88.2,
            volume=10_000,
        )


def test_tier_a_stream_session_protocol_tracks_start_stop_lifecycle() -> None:
    session = FakeSession()

    assert isinstance(session, TierAStreamSession)
    session.start()
    assert session.started is True
    session.stop()
    assert session.started is False


def test_tier_a_stream_consumer_protocol_invokes_bar_callback_and_returns_session() -> None:
    seen: list[BarData] = []
    consumer = FakeConsumer()

    assert isinstance(consumer, TierAStreamConsumer)
    session = consumer.start(("VCB",), seen.append)

    assert isinstance(session, TierAStreamSession)
    assert session.started is True
    assert seen == [
        BarData(
            ticker="VCB",
            observed_at=datetime(2026, 5, 7, 2, 30, tzinfo=UTC),
            price=42.5,
            volume=1000,
        )
    ]


def test_bar_callback_alias_accepts_bar_data_callables() -> None:
    seen: list[BarData] = []
    callback: BarCallback = seen.append
    bar = BarData(
        ticker="VCB",
        observed_at=datetime(2026, 5, 7, 2, 32, tzinfo=UTC),
        price=91.0,
        volume=2500,
        raw={"source": "fiin"},
    )

    callback(bar)

    assert seen == [bar]


def test_protocol_exports_are_available_from_package_namespace() -> None:
    import ht_l1_core.protocols as protocols

    assert protocols.__all__ == [
        "Backfillable",
        "BackfillResult",
        "BackfillTargetYearUnavailable",
        "BarCallback",
        "BarData",
        "TierAStreamConsumer",
        "TierAStreamSession",
    ]


def test_public_protocol_classes_are_reexported_from_top_level_package() -> None:
    import ht_l1_core

    expected: dict[str, Any] = {
        "Backfillable": Backfillable,
        "BackfillResult": BackfillResult,
        "BackfillTargetYearUnavailable": BackfillTargetYearUnavailable,
        "BarData": BarData,
        "TierAStreamConsumer": TierAStreamConsumer,
        "TierAStreamSession": TierAStreamSession,
    }

    for name, value in expected.items():
        assert getattr(ht_l1_core, name) is value
        assert name in ht_l1_core.__all__
