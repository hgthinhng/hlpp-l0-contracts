"""HLPP-COMPUTED payload schemas per L2 analysis.

Per spec §9 classification (~23 L2 datasets):
- L2a (base, read L1b only): factor/*, ta/*, fa/*, capm-beta, liquidity-alerts
- L2b (compose-1, read L2a): residual-momentum, idio-vol, regime-markov-vnindex, peg (future)
- L2c+ (compose-2): signal-blend (future)
"""
from __future__ import annotations

from pydantic import Field

from .base import HlppComputedBase


# ─── L2a · factor domain ────────────────────────────────────────────

class FactorBase(HlppComputedBase):
    """Common base for factor metrics (L2a / l2a/factor/)."""

    score: float = Field(..., description="Raw factor value")
    rank: int | None = Field(None, ge=1, description="Cross-sectional rank (1=highest)")
    zscore: float | None = Field(None, description="Cross-sectional z-score")


class FactorSize(FactorBase):
    """Market-cap size factor (-log(mcap))."""
    market_cap: float = Field(..., ge=0)


class FactorMomentum_12_1m(FactorBase):
    """12-month return ex last month."""
    return_12_1m: float


class FactorQuality(FactorBase):
    """ROE + Debt/Equity composite quality score."""
    roe: float | None = None
    debt_to_equity: float | None = None


class CapmBeta(HlppComputedBase):
    """CAPM beta vs VN-Index, rolling window."""
    beta: float
    alpha: float
    r_squared: float = Field(..., ge=0, le=1)


# ─── L2a · ta domain ────────────────────────────────────────────────

class TaIndicator(HlppComputedBase):
    """Generic TA indicator output (1 value per ticker per day)."""
    value: float
    signal: str | None = Field(None, description="e.g. 'buy', 'sell', 'neutral'")


# ─── L2a · fa domain ────────────────────────────────────────────────

class FaDupont3Way(HlppComputedBase):
    """DuPont 3-way ROE decomposition: NM × AT × EM."""
    net_margin: float | None = None
    asset_turnover: float | None = None
    equity_multiplier: float | None = None
    roe_dupont: float | None = None


# ─── L2b · compose-1 ────────────────────────────────────────────────

class FactorResidualMomentum(FactorBase):
    """Residual momentum after regressing on style factors."""
    residual: float


class Peg(HlppComputedBase):
    """PEG = P/E ÷ Growth (forward-looking).

    Input lineage: L1b price-daily (for P/E) + L2a fa/growth-metrics-quarterly.
    """
    pe_ratio: float | None = None
    growth_rate: float | None = None
    peg_ratio: float | None = None
    peg_band: str | None = Field(None, description="e.g. 'undervalued', 'fair', 'overvalued'")


class RegimeMarkovVnindex(HlppComputedBase):
    """Markov regime detection on VN-Index returns."""
    regime: str = Field(..., description="e.g. 'bull', 'bear', 'sideways'")
    regime_prob: float = Field(..., ge=0, le=1)
    regime_duration_days: int = Field(..., ge=0)


# ─── L2c · compose-2 ────────────────────────────────────────────────

class SignalBlend(HlppComputedBase):
    """Multi-factor signal blend (e.g. α·PEG + β·momentum + γ·quality).

    Input lineage: ≥1 L2b output.
    """
    blend_score: float
    components: dict[str, float] = Field(
        ..., description="Component contributions, e.g. {'peg': 0.4, 'momentum': 0.3, ...}"
    )
    decile: int | None = Field(None, ge=1, le=10)


# TODO: Add remaining L2 payload classes during Phase 4 migration.
