"""Tests for HlppNormalizedBase + HlppComputedBase Pydantic contracts."""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from hlpp_l0_contracts.schemas.base import HlppComputedBase, HlppNormalizedBase
from hlpp_l0_contracts.schemas.computed import FactorSize, RegimeMarkovVnindex
from hlpp_l0_contracts.schemas.normalized import PriceDaily, Ticker360


# Shared identity columns (no dataset_id — caller supplies per scenario)
_IDENTITY = {
    "ticker": "HPG",
    "as_of_date": date(2026, 5, 20),
    "business_date": date(2026, 5, 20),
    "business_time": None,
    "vendor": "vnstock",
    "ingested_at": datetime(2026, 5, 20, 16, 0, tzinfo=timezone.utc),
    "builder_version": "abc1234",
}

NORMALIZED_SAMPLE = {**_IDENTITY, "dataset_id": "price-daily"}

COMPUTED_SAMPLE = {
    **_IDENTITY,
    "schema_id": "hlpp-computed/v1",
    "dataset_id": "factor-size",
    "analysis_version": "def5678",
    "input_partitions": ["normalized:ticker-360:as_of_date=2026-05-20"],
    "chain_depth": "l2a",
    "domain": "factor",
    "lookback_days": None,
}


def test_normalized_base_accepts_canonical_row():
    row = HlppNormalizedBase(**NORMALIZED_SAMPLE)
    assert row.ticker == "HPG"
    assert row.schema_id == "hlpp-normalized/v1"
    assert row.vendor == "vnstock"


def test_normalized_base_is_frozen():
    row = HlppNormalizedBase(**NORMALIZED_SAMPLE)
    with pytest.raises(ValidationError):
        row.ticker = "VNM"  # type: ignore[misc]


def test_normalized_base_forbids_extra_fields():
    payload = dict(NORMALIZED_SAMPLE, unexpected_col=42)
    with pytest.raises(ValidationError):
        HlppNormalizedBase(**payload)


def test_normalized_base_rejects_invalid_vendor():
    payload = dict(NORMALIZED_SAMPLE, vendor="bloomberg")
    with pytest.raises(ValidationError):
        HlppNormalizedBase(**payload)


def test_computed_base_extends_normalized():
    row = HlppComputedBase(**COMPUTED_SAMPLE)
    assert row.schema_id == "hlpp-computed/v1"
    assert row.chain_depth == "l2a"
    assert row.domain == "factor"
    assert row.input_partitions[0].startswith("normalized:")


def test_computed_base_rejects_unknown_chain_depth():
    bad = dict(COMPUTED_SAMPLE, chain_depth="l2z")
    with pytest.raises(ValidationError):
        HlppComputedBase(**bad)


def test_computed_base_rejects_unknown_domain():
    bad = dict(COMPUTED_SAMPLE, domain="macro")
    with pytest.raises(ValidationError):
        HlppComputedBase(**bad)


def test_normalized_payload_subclass_validates_price_daily():
    row = PriceDaily(
        **NORMALIZED_SAMPLE,
        open=25.0,
        high=26.5,
        low=24.8,
        close=26.0,
        close_adjusted=26.0,
        volume=1_000_000,
        value=26_000_000.0,
    )
    assert row.close_adjusted == 26.0


def test_normalized_payload_rejects_negative_volume():
    with pytest.raises(ValidationError):
        PriceDaily(
            **NORMALIZED_SAMPLE,
            open=25.0,
            high=26.5,
            low=24.8,
            close=26.0,
            close_adjusted=26.0,
            volume=-1,
            value=26_000_000.0,
        )


def test_ticker360_free_float_must_be_in_unit_interval():
    base = dict(NORMALIZED_SAMPLE, dataset_id="ticker-360")
    with pytest.raises(ValidationError):
        Ticker360(
            **base,
            exchange="HOSE",
            free_float_pct=1.5,
        )


def test_computed_payload_subclass_factor_size():
    row = FactorSize(
        **COMPUTED_SAMPLE,
        score=-3.21,
        market_cap=15_000_000_000.0,
    )
    assert row.score == -3.21


def test_regime_markov_probability_bounded():
    payload = dict(
        COMPUTED_SAMPLE,
        dataset_id="regime-markov-vnindex",
        domain="regime",
        chain_depth="l2b",
    )
    with pytest.raises(ValidationError):
        RegimeMarkovVnindex(
            **payload,
            regime="bull",
            regime_prob=1.1,
            regime_duration_days=12,
        )
