"""Schema validators — gate parquet writes from L1b + L2 builders.

Per spec §7.4 + §8 — builders MUST call validate_normalized() / validate_computed()
before parquet write. CI lint enforces presence of validate_*() call upstream
of every write_parquet() / to_parquet() in pipelines source code.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .schemas.base import HlppComputedBase, HlppNormalizedBase

if TYPE_CHECKING:
    import pandas as pd


class SchemaValidationError(ValueError):
    """Raised when DataFrame fails schema check before parquet write."""


def validate_normalized(
    df: "pd.DataFrame",
    *,
    dataset_id: str,
    sample_rows: int = 5,
) -> None:
    """Validate L1b output DataFrame against HLPP-NORMALIZED schema.

    Args:
        df: pandas DataFrame to write.
        dataset_id: e.g. 'price-intraday-30s'. Must match df['dataset_id'].
        sample_rows: how many rows to Pydantic-validate (full validation = slow).

    Raises:
        SchemaValidationError: if mandatory columns missing or sample rows invalid.
    """
    _validate_mandatory_cols(df, HlppNormalizedBase, "HLPP-NORMALIZED")
    _validate_dataset_id(df, dataset_id)
    _validate_sample_rows(df, HlppNormalizedBase, sample_rows)


def validate_computed(
    df: "pd.DataFrame",
    *,
    dataset_id: str,
    chain_depth: str,
    domain: str,
    sample_rows: int = 5,
) -> None:
    """Validate L2 output DataFrame against HLPP-COMPUTED schema.

    Args:
        df: pandas DataFrame to write.
        dataset_id: e.g. 'factor-momentum-12-1m', 'peg', 'signal-blend-v1'.
        chain_depth: one of 'l2a'..'l2f'.
        domain: one of 'factor', 'ta', 'fa', 'signal', 'regime', 'alert'.
        sample_rows: how many rows to Pydantic-validate.

    Raises:
        SchemaValidationError: if mandatory columns missing or row invalid.
    """
    _validate_mandatory_cols(df, HlppComputedBase, "HLPP-COMPUTED")
    _validate_dataset_id(df, dataset_id)
    _validate_chain_depth(df, chain_depth)
    _validate_domain(df, domain)
    _validate_sample_rows(df, HlppComputedBase, sample_rows)


# ─── Internal checks ────────────────────────────────────────────────

def _validate_mandatory_cols(df: Any, base_cls: type, label: str) -> None:
    required = set(base_cls.model_fields.keys())
    actual = set(df.columns)
    missing = required - actual
    if missing:
        raise SchemaValidationError(
            f"{label} mandatory columns missing: {sorted(missing)}. "
            f"Got: {sorted(actual)}"
        )


def _validate_dataset_id(df: Any, expected: str) -> None:
    unique_ids = df["dataset_id"].unique()
    if len(unique_ids) != 1 or unique_ids[0] != expected:
        raise SchemaValidationError(
            f"dataset_id must be uniform = '{expected}', got: {sorted(unique_ids)}"
        )


def _validate_chain_depth(df: Any, expected: str) -> None:
    if expected not in {"l2a", "l2b", "l2c", "l2d", "l2e", "l2f"}:
        raise SchemaValidationError(
            f"chain_depth must be l2a..l2f, got '{expected}'"
        )
    unique = df["chain_depth"].unique()
    if len(unique) != 1 or unique[0] != expected:
        raise SchemaValidationError(
            f"chain_depth column must be uniform = '{expected}', got: {sorted(unique)}"
        )


def _validate_domain(df: Any, expected: str) -> None:
    if expected not in {"factor", "ta", "fa", "signal", "regime", "alert"}:
        raise SchemaValidationError(
            f"domain must be factor/ta/fa/signal/regime/alert, got '{expected}'"
        )


def _validate_sample_rows(df: Any, base_cls: type, n: int) -> None:
    sample = df.head(n).to_dict(orient="records")
    for i, row in enumerate(sample):
        try:
            base_cls.model_validate(row)
        except Exception as e:
            raise SchemaValidationError(
                f"Row {i} fails {base_cls.__name__} validation: {e}"
            ) from e


__all__ = [
    "SchemaValidationError",
    "validate_normalized",
    "validate_computed",
]
