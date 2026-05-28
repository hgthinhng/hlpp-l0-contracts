"""HLPP-NORMALIZED payload schemas per L1b dataset.

Each class extends HlppNormalizedBase + adds dataset-specific payload columns.
Builder must instantiate this class for each row before parquet write.

Per spec §9 classification (11 L1b datasets):
- price-intraday-30s, price-daily, foreign-flow-daily, index-daily
- block-deals, insider-trades, large-shareholders, corp-events-parsed
- liquidity-filters-daily, fundamentals-quarterly, ticker-360
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field

from .base import HlppNormalizedBase


class PriceIntraday30s(HlppNormalizedBase):
    """30-second OHLC bars from m12-fqx-ohlcv-intraday raw snapshots."""

    adjustment_type: Literal["raw"] = "raw"
    open: float = Field(..., ge=0)
    high: float = Field(..., ge=0)
    low: float = Field(..., ge=0)
    close: float = Field(..., ge=0)
    volume: int = Field(..., ge=0)
    value: float = Field(..., ge=0)


class PriceDaily(HlppNormalizedBase):
    """Daily OHLC + adjustments from vnstock VCI EOD."""

    adjustment_type: Literal["backward_adjusted"] = "backward_adjusted"
    open: float = Field(..., ge=0)
    high: float = Field(..., ge=0)
    low: float = Field(..., ge=0)
    close: float = Field(..., ge=0)
    close_adjusted: float = Field(..., ge=0, description="Split + dividend adjusted")
    volume: int = Field(..., ge=0)
    value: float = Field(..., ge=0)


class ForeignFlowDaily(HlppNormalizedBase):
    """Daily foreign buy/sell flow aggregate."""

    adjustment_type: Literal["raw"] = "raw"
    buy_volume: int = Field(..., ge=0)
    sell_volume: int = Field(..., ge=0)
    buy_value: float = Field(..., ge=0)
    sell_value: float = Field(..., ge=0)
    net_volume: int  # can be negative
    net_value: float


class FundamentalsQuarterly(HlppNormalizedBase):
    """Quarterly BCTC fundamentals — normalized 3 statements."""

    fiscal_year: int = Field(..., ge=2000, le=2100)
    fiscal_quarter: int = Field(..., ge=1, le=4)
    revenue: float | None = None
    net_income: float | None = None
    total_assets: float | None = None
    total_equity: float | None = None
    total_debt: float | None = None
    eps: float | None = None
    book_value_per_share: float | None = None


class Ticker360(HlppNormalizedBase):
    """Ticker info aggregate — industry, mcap, free-float, foreign room, etc."""

    exchange: str = Field(..., description="HOSE/HNX/UPCOM")
    icb_code: str | None = None
    icb_name: str | None = None
    market_cap: float | None = Field(None, ge=0)
    free_float_pct: float | None = Field(None, ge=0, le=1)
    foreign_room_pct: float | None = Field(None, ge=0, le=1)
    state_owner_pct: float | None = Field(None, ge=0, le=1)
    listed_shares: int | None = Field(None, ge=0)


class ReportTextNormalized(HlppNormalizedBase):
    """Raw analyst report / market-commentary text from research collectors.

    Source: dsc_research / masvn_research / yuanta_research / vndirect_research
    pulled through ``ai-api-crawlers`` text-only wirings (PDF → pdfplumber →
    boilerplate strip → body_text). This is the SUBSTRATE the future
    sentiment / tone / numbers extraction tier (L2) reads — NO LLM extraction
    in this layer per operator directive ("chỉ pull chữ relevant thôi").

    Row granularity: ONE row per (report × primary_ticker). Reports that name
    no ticker (daily bulletins, macro commentary) use ticker="MARKET". Reports
    that name multiple tickers (cross-section notes) explode into one row per
    ticker, with the full mention list preserved in ``ticker_mentions``.
    """

    vendor: Literal["internal"] = "internal"
    adjustment_type: Literal["raw"] = "raw"

    # Source identification
    source_id: str = Field(
        ..., description="upstream collector source_id (e.g. 'masvn_research')"
    )
    ctck_source: str | None = Field(
        None, description="broker shorthand ('DSC' / 'MASVN' / 'YUANTA' / 'VNDIRECT')"
    )

    # Report metadata
    title: str = Field(..., min_length=1)
    report_date: date | None = Field(None, description="published_at date")
    landing_url: str | None = None
    pdf_url: str | None = None
    ticker_mentions: list[str] = Field(
        default_factory=list,
        description="Full ticker mention list from the report; row's `ticker` is the primary",
    )

    # Text extraction provenance
    body_text: str = Field(..., description="Cleaned relevant text; may be '' on failure")
    char_count: int = Field(..., ge=0)
    page_count: int = Field(..., ge=0, description="0 for HTML/summary inputs")
    content_hash: str = Field(
        ..., description="sha256:HEX of body_text; '' when status != OK"
    )
    extracted_via: Literal["pdfplumber", "html_summary", "html_body"] = "pdfplumber"
    # Renamed from "status" to avoid collision with the silver-stamping
    # row-level provenance status (ACTIVE/DEGRADED/DEAD) set by
    # ``hlpp_pipelines.utils.stamping.stamp_silver_per_row``.
    extraction_status: Literal[
        "OK", "PDF_FETCH_FAILED", "INVALID_PDF", "NO_TEXT_EXTRACTED"
    ] = "OK"
    fetch_error: str | None = None

    # Lineage
    origin_observation_id: str | None = Field(
        None, description="uuid of upstream collector's observation"
    )
    observation_id: str = Field(
        ..., description="uuid5 over (source_id, content_hash || status, ticker) — stable per row"
    )


# TODO: Add remaining 6 L1b payload classes during Phase 4 builder migration:
# - BlockDeals, InsiderTrades, LargeShareholders, CorpEventsParsed,
#   IndexDaily, LiquidityFiltersDaily

__all__ = [
    "ForeignFlowDaily",
    "FundamentalsQuarterly",
    "PriceDaily",
    "PriceIntraday30s",
    "ReportTextNormalized",
    "Ticker360",
]
