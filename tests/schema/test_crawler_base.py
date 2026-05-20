"""Tests for hlpp_l0_contracts.schema.crawler_base (Wave-3 0.1.2 deliverable)."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pandas as pd
import pytest

from hlpp_l0_contracts.schema.crawler_base import CRAWLER_BASE_COLUMNS, CrawlerBaseSchema


_EXPECTED_COLUMNS = frozenset(
    {
        "source",
        "source_fetched_at",
        "ingested_at",
        "content_hash",
        "vintage",
        "as_of_date",
        "status",
        "skip_reason",
        "error_category",
        "revision_count",
        "last_consumed_at",
        "run_id",
        "code_sha",
        "inputs_hash",
        "computed_at",
        "tos_status",
        "robots_status",
        "tos_citation_required",
        "disabled_reason",
        "llm_extraction_risk",
    }
)


def test_crawler_base_has_20_columns() -> None:
    assert frozenset(CRAWLER_BASE_COLUMNS) == _EXPECTED_COLUMNS
    assert len(CRAWLER_BASE_COLUMNS) == 20


def _minimal_row(now: datetime) -> dict[str, object]:
    return {
        "source": "m12-newscrawlers-articles-v1",
        "source_fetched_at": now,
        "ingested_at": now,
        "content_hash": "a" * 64,
        "vintage": now,
        "as_of_date": date.today(),
        "status": "OK",
        "skip_reason": None,
        "error_category": None,
        "revision_count": 0,
        "last_consumed_at": None,
        "run_id": "run-001",
        "code_sha": "0" * 40,
        "inputs_hash": "b" * 64,
        "computed_at": now,
        "tos_status": None,
        "robots_status": None,
        "tos_citation_required": None,
        "disabled_reason": None,
        "llm_extraction_risk": None,
    }


def test_crawler_base_validates_minimal_row() -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    df = pd.DataFrame([_minimal_row(now)])
    CrawlerBaseSchema.validate(df)


def test_crawler_base_rejects_invalid_status() -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    row = _minimal_row(now)
    row["status"] = "INVALID"
    df = pd.DataFrame([row])
    with pytest.raises(Exception):
        CrawlerBaseSchema.validate(df)


def test_crawler_base_accepts_extra_payload_columns() -> None:
    """Per-crawler schemas extend the base with payload columns; strict=False allows this."""
    now = datetime.now(UTC).replace(tzinfo=None)
    row = _minimal_row(now)
    row["title"] = "Example article"
    row["url"] = "https://example.test"
    df = pd.DataFrame([row])
    CrawlerBaseSchema.validate(df)
