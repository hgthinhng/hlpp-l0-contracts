"""Tests for HlppNormalizedBase + HlppComputedBase Pydantic contracts."""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from hlpp_l0_contracts.schemas.base import HlppComputedBase, HlppNormalizedBase
from hlpp_l0_contracts.schemas.computed import FactorSize, RegimeMarkovVnindex
from hlpp_l0_contracts.schemas.normalized import (
    ForeignFlowDaily,
    PriceDaily,
    PriceIntraday30s,
    ReportTextNormalized,
    Ticker360,
)


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
    assert row.adjustment_type == "unknown"


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
        close_adj=26.0,
        volume=1_000_000,
        value_traded=26_000_000.0,
    )
    assert row.close_adj == 26.0
    assert row.adjustment_type == "backward_adjusted"

def test_normalized_payload_subclasses_set_adjustment_type_defaults():
    intraday = PriceIntraday30s(
        **dict(NORMALIZED_SAMPLE, vendor="fqx", dataset_id="price-intraday-30s"),
        open=25.0,
        high=26.5,
        low=24.8,
        close=26.0,
        volume=1_000_000,
        value=26_000_000.0,
    )
    assert intraday.adjustment_type == "raw"

    foreign_flow = ForeignFlowDaily(
        **dict(NORMALIZED_SAMPLE, dataset_id="foreign-flow-daily"),
        foreign_buy_volume=1_000,
        foreign_sell_volume=500,
        foreign_buy_value=25_000_000.0,
        foreign_sell_value=12_000_000.0,
        foreign_net_volume=500,
        foreign_net_value=13_000_000.0,
    )
    assert foreign_flow.adjustment_type == "raw"

def test_normalized_rejects_unknown_adjustment_type_value():
    with pytest.raises(ValidationError):
        HlppNormalizedBase(**dict(NORMALIZED_SAMPLE, adjustment_type="split_adjusted"))


def test_normalized_payload_rejects_negative_volume():
    with pytest.raises(ValidationError):
        PriceDaily(
            **NORMALIZED_SAMPLE,
            open=25.0,
            high=26.5,
            low=24.8,
            close=26.0,
            close_adj=26.0,
            volume=-1,
            value_traded=26_000_000.0,
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


def test_report_text_normalized_canonical_row():
    row = ReportTextNormalized(
        **dict(NORMALIZED_SAMPLE, vendor="internal", dataset_id="report-text-daily"),
        source_id="masvn_research",
        ctck_source="MASVN",
        title="HPG - Báo cáo cập nhật",
        report_date=date(2026, 5, 27),
        landing_url="https://www.masvn.com/cate/x",
        pdf_url="https://masvn.com/api/attachment/file/123-HPG.pdf",
        ticker_mentions=["HPG"],
        body_text="MUA HPG. Giá mục tiêu 36.600 VND.",
        char_count=33,
        page_count=4,
        content_hash="sha256:abc123",
        extracted_via="pdfplumber",
        extraction_status="OK",
        observation_id="11111111-1111-5111-8111-111111111111",
    )
    assert row.source_id == "masvn_research"
    assert row.ctck_source == "MASVN"
    assert row.ticker_mentions == ["HPG"]
    assert row.extraction_status == "OK"
    assert row.adjustment_type == "raw"
    assert row.vendor == "internal"


def test_report_text_normalized_failure_row_keeps_empty_body():
    row = ReportTextNormalized(
        **dict(NORMALIZED_SAMPLE, vendor="internal", dataset_id="report-text-daily"),
        source_id="dsc_research",
        ctck_source=None,
        title="DSC report",
        body_text="",
        char_count=0,
        page_count=0,
        content_hash="",
        extracted_via="pdfplumber",
        extraction_status="PDF_FETCH_FAILED",
        fetch_error="HTTP 404",
        observation_id="22222222-2222-5222-8222-222222222222",
    )
    assert row.body_text == ""
    assert row.extraction_status == "PDF_FETCH_FAILED"
    assert row.fetch_error == "HTTP 404"
    assert row.ticker_mentions == []


def test_report_text_normalized_rejects_unknown_status():
    payload = dict(
        NORMALIZED_SAMPLE,
        vendor="internal",
        dataset_id="report-text-daily",
        source_id="vndirect_research",
        title="x",
        body_text="x",
        char_count=1,
        page_count=0,
        content_hash="sha256:abc",
        extracted_via="html_summary",
        extraction_status="UNKNOWN_STATUS_LITERAL",
        observation_id="33333333-3333-5333-8333-333333333333",
    )
    with pytest.raises(ValidationError):
        ReportTextNormalized(**payload)


def test_report_text_normalized_rejects_non_internal_vendor():
    payload = dict(
        NORMALIZED_SAMPLE,
        vendor="fqx",  # report_text is vendor="internal" only
        dataset_id="report-text-daily",
        source_id="masvn_research",
        title="x",
        body_text="x",
        char_count=1,
        page_count=0,
        content_hash="sha256:abc",
        extracted_via="pdfplumber",
        extraction_status="OK",
        observation_id="44444444-4444-5444-8444-444444444444",
    )
    with pytest.raises(ValidationError):
        ReportTextNormalized(**payload)


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
