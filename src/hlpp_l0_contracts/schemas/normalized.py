"""HLPP-NORMALIZED payload schemas per L1b dataset.

Each class extends HlppNormalizedBase + adds dataset-specific payload columns.
Builder must instantiate this class for each row before parquet write.

Per spec §9 classification (11 L1b datasets):
- price-intraday-30s, price-daily, foreign-flow-daily, index-daily
- block-deals, insider-trades, large-shareholders, corp-events-parsed
- liquidity-filters-daily, fundamentals-quarterly, ticker-360
"""
from __future__ import annotations

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


# TODO: Add remaining 6 L1b payload classes during Phase 4 builder migration:
# - BlockDeals, InsiderTrades, LargeShareholders, CorpEventsParsed,
#   IndexDaily, LiquidityFiltersDaily

__all__ = [
    "ForeignFlowDaily",
    "FundamentalsQuarterly",
    "PriceDaily",
    "PriceIntraday30s",
    "Ticker360",
]
