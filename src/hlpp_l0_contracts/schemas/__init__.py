"""HLPP schema contracts — NORMALIZED (L1b output), COMPUTED (L2{a..f} output),
and ALT-DATA (L1a alternative-data observations).

Defines Pydantic base models + per-dataset payload schemas. All L1b/L2 builders
must validate their parquet output against these schemas before write (CI lint enforces).
"""
from .base import HlppNormalizedBase, HlppComputedBase
from . import normalized, computed, research_papers
from .normalized import (
    BlockDeals,
    CorpEventsParsed,
    ForeignFlowDaily,
    FundamentalsAnnual,
    FundamentalsQuarterly,
    IndexDaily,
    InsiderTrades,
    IntradaySnapshot,
    LargeShareholders,
    LiquidityFiltersDaily,
    PriceDaily,
    PriceIntraday30s,
    ReportTextNormalized,
    Ticker360,
)
from .alt_data import AlternativeDataBase, GenericAltObservation
from .research_papers import PaperType, ResearchPaperV1, ResearchSource

__all__ = [
    "HlppNormalizedBase",
    "HlppComputedBase",
    "normalized",
    "computed",
    "research_papers",
    # L1b normalized contracts
    "BlockDeals",
    "CorpEventsParsed",
    "ForeignFlowDaily",
    "FundamentalsAnnual",
    "FundamentalsQuarterly",
    "IndexDaily",
    "InsiderTrades",
    "IntradaySnapshot",
    "LargeShareholders",
    "LiquidityFiltersDaily",
    "PriceDaily",
    "PriceIntraday30s",
    "ReportTextNormalized",
    "Ticker360",
    # L1a alt-data contracts
    "AlternativeDataBase",
    "GenericAltObservation",
    # Research papers
    "ResearchPaperV1",
    "ResearchSource",
    "PaperType",
]
