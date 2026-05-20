"""Tests for hlpp_l0_contracts.validators — pre-write parquet gates."""
from __future__ import annotations

from datetime import date, datetime, timezone

import pandas as pd
import pytest

from hlpp_l0_contracts.validators import (
    SchemaValidationError,
    validate_computed,
    validate_normalized,
)


def _normalized_row(**overrides):
    row = {
        "ticker": "HPG",
        "as_of_date": date(2026, 5, 20),
        "business_date": date(2026, 5, 20),
        "business_time": None,
        "vendor": "vnstock",
        "ingested_at": datetime(2026, 5, 20, 16, 0, tzinfo=timezone.utc),
        "schema_id": "hlpp-normalized/v1",
        "dataset_id": "price-daily",
        "builder_version": "abc1234",
    }
    row.update(overrides)
    return row


def _computed_row(**overrides):
    row = _normalized_row(
        schema_id="hlpp-computed/v1",
        dataset_id="factor-size",
    )
    row.update(
        analysis_version="def5678",
        input_partitions=["normalized:ticker-360:as_of_date=2026-05-20"],
        chain_depth="l2a",
        domain="factor",
        lookback_days=None,
    )
    row.update(overrides)
    return row


def test_validate_normalized_happy_path():
    df = pd.DataFrame([_normalized_row(), _normalized_row(ticker="VNM")])
    validate_normalized(df, dataset_id="price-daily")


def test_validate_normalized_missing_column_raises():
    df = pd.DataFrame([_normalized_row()]).drop(columns=["builder_version"])
    with pytest.raises(SchemaValidationError, match="builder_version"):
        validate_normalized(df, dataset_id="price-daily")


def test_validate_normalized_mismatched_dataset_id_raises():
    df = pd.DataFrame([_normalized_row()])
    with pytest.raises(SchemaValidationError, match="dataset_id"):
        validate_normalized(df, dataset_id="foreign-flow-daily")


def test_validate_normalized_non_uniform_dataset_id_raises():
    df = pd.DataFrame(
        [_normalized_row(), _normalized_row(dataset_id="ticker-360")]
    )
    with pytest.raises(SchemaValidationError, match="uniform"):
        validate_normalized(df, dataset_id="price-daily")


def test_validate_computed_happy_path():
    df = pd.DataFrame([_computed_row(), _computed_row(ticker="VNM")])
    validate_computed(
        df,
        dataset_id="factor-size",
        chain_depth="l2a",
        domain="factor",
    )


def test_validate_computed_rejects_bad_chain_depth():
    df = pd.DataFrame([_computed_row()])
    with pytest.raises(SchemaValidationError, match="chain_depth"):
        validate_computed(
            df,
            dataset_id="factor-size",
            chain_depth="l2z",
            domain="factor",
        )


def test_validate_computed_rejects_bad_domain():
    df = pd.DataFrame([_computed_row()])
    with pytest.raises(SchemaValidationError, match="domain"):
        validate_computed(
            df,
            dataset_id="factor-size",
            chain_depth="l2a",
            domain="macro",
        )


def test_validate_computed_mismatched_chain_depth_column_raises():
    df = pd.DataFrame(
        [_computed_row(), _computed_row(chain_depth="l2b")]
    )
    with pytest.raises(SchemaValidationError, match="chain_depth column"):
        validate_computed(
            df,
            dataset_id="factor-size",
            chain_depth="l2a",
            domain="factor",
        )


def test_validate_normalized_pydantic_row_failure_raises():
    df = pd.DataFrame([_normalized_row(vendor="bloomberg")])
    with pytest.raises(SchemaValidationError, match="fails"):
        validate_normalized(df, dataset_id="price-daily")
