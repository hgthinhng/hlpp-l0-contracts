"""HLPP schema contracts — NORMALIZED (L1b output) and COMPUTED (L2{a..f} output).

Defines Pydantic base models + per-dataset payload schemas. All L1b/L2 builders
must validate their parquet output against these schemas before write (CI lint enforces).
"""
from .base import HlppNormalizedBase, HlppComputedBase
from . import normalized, computed

__all__ = ["HlppNormalizedBase", "HlppComputedBase", "normalized", "computed"]
