"""HLPP schema contracts — NORMALIZED (L1b output), COMPUTED (L2{a..f} output),
and ALT-DATA (L1a alternative-data observations).

Defines Pydantic base models + per-dataset payload schemas. All L1b/L2 builders
must validate their parquet output against these schemas before write (CI lint enforces).
"""
from .base import HlppNormalizedBase, HlppComputedBase
from . import normalized, computed
from .normalized import (
    ForeignFlowDaily,
    FundamentalsQuarterly,
    PriceDaily,
    PriceIntraday30s,
    Ticker360,
)
from .alt_data import AlternativeDataBase, GenericAltObservation

__all__ = [
    "HlppNormalizedBase",
    "HlppComputedBase",
    "normalized",
    "computed",
    "ForeignFlowDaily",
    "FundamentalsQuarterly",
    "PriceDaily",
    "PriceIntraday30s",
    "Ticker360",
    "AlternativeDataBase",
    "GenericAltObservation",
]
