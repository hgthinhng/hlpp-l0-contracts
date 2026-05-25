"""Tests for ResearchPaperV1 Pydantic contract (Wave 8 academic-paper collectors)."""
from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from hlpp_l0_contracts.schemas.research_papers import (
    PaperType,
    ResearchPaperV1,
    ResearchSource,
)

# ---------------------------------------------------------------------------
# Canonical sample — all tests derive from this
# ---------------------------------------------------------------------------
_PUBLISHED = date(2026, 1, 15)
_AS_OF = date(2026, 5, 25)

VALID_SAMPLE: dict = {
    "paper_id": "10.5089/9798400123456",
    "source": "imf_wp",
    "title": "Vietnam Macroprudential Spillovers: A DSGE Approach",
    "authors": ["Nguyen Thi A", "Tran Van B"],
    "abstract": "We study macroprudential transmission in Vietnam's banking system...",
    "published_at": _PUBLISHED,
    "pdf_url": "https://www.imf.org/-/media/Files/Publications/WP/2026/wp2601.pdf",
    "doi": "10.5089/9798400123456",
    "keywords": ["macroprudential", "DSGE", "Vietnam"],
    "ticker_mentions": [],
    "language": "en",
    "paper_type": "working_paper",
    "institution": "IMF",
    "as_of_date": _AS_OF,
    "source_metadata": {"jel_codes": ["E52", "G21"], "wp_number": "2601"},
}


# ---------------------------------------------------------------------------
# Happy-path
# ---------------------------------------------------------------------------


def test_valid_construction():
    row = ResearchPaperV1(**VALID_SAMPLE)
    assert row.paper_id == "10.5089/9798400123456"
    assert row.source == "imf_wp"
    assert row.language == "en"
    assert row.paper_type == "working_paper"
    assert row.ticker_mentions == []
    assert row.source_metadata["jel_codes"] == ["E52", "G21"]


def test_optional_fields_default():
    """abstract, pdf_url, doi, paper_type, institution all optional."""
    minimal = {
        k: v
        for k, v in VALID_SAMPLE.items()
        if k
        not in {
            "abstract",
            "pdf_url",
            "doi",
            "paper_type",
            "institution",
            "keywords",
            "ticker_mentions",
            "source_metadata",
        }
    }
    row = ResearchPaperV1(**minimal)
    assert row.abstract is None
    assert row.pdf_url is None
    assert row.doi is None
    assert row.paper_type is None
    assert row.institution is None
    assert row.keywords == []
    assert row.ticker_mentions == []
    assert row.source_metadata == {}


def test_round_trip_dict():
    row = ResearchPaperV1(**VALID_SAMPLE)
    dumped = row.model_dump()
    # Reconstruct from dump
    row2 = ResearchPaperV1(**dumped)
    assert row2 == row


def test_ticker_mentions_populated_downstream():
    """L2 NLP downstream populates ticker_mentions; L0 schema accepts both."""
    row = ResearchPaperV1(**{**VALID_SAMPLE, "ticker_mentions": ["VCB", "HPG", "FPT"]})
    assert row.ticker_mentions == ["VCB", "HPG", "FPT"]


# ---------------------------------------------------------------------------
# extra="forbid" + frozen
# ---------------------------------------------------------------------------


def test_extra_field_forbidden():
    with pytest.raises(ValidationError):
        ResearchPaperV1(**VALID_SAMPLE, unexpected_field="bad")


def test_model_is_frozen():
    row = ResearchPaperV1(**VALID_SAMPLE)
    with pytest.raises(ValidationError):
        row.title = "modified"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# source enum (8 Wave 8 sources)
# ---------------------------------------------------------------------------


def test_all_8_valid_sources():
    valid_sources: list[ResearchSource] = [
        "ssrn",
        "repec",
        "amro",
        "imf_wp",
        "oecd",
        "heliyon",
        "vepr",
        "fulbright_fsppm",
    ]
    for src in valid_sources:
        row = ResearchPaperV1(**{**VALID_SAMPLE, "source": src})
        assert row.source == src


def test_invalid_source_raises():
    with pytest.raises(ValidationError):
        ResearchPaperV1(**{**VALID_SAMPLE, "source": "arxiv"})


def test_invalid_source_uppercase_raises():
    with pytest.raises(ValidationError):
        ResearchPaperV1(**{**VALID_SAMPLE, "source": "SSRN"})


# ---------------------------------------------------------------------------
# paper_type enum
# ---------------------------------------------------------------------------


def test_all_paper_types_valid():
    types: list[PaperType] = [
        "working_paper",
        "journal",
        "policy_brief",
        "conference",
    ]
    for t in types:
        row = ResearchPaperV1(**{**VALID_SAMPLE, "paper_type": t})
        assert row.paper_type == t


def test_invalid_paper_type_raises():
    with pytest.raises(ValidationError):
        ResearchPaperV1(**{**VALID_SAMPLE, "paper_type": "preprint"})


# ---------------------------------------------------------------------------
# paper_id validation
# ---------------------------------------------------------------------------


def test_paper_id_doi_form_accepted():
    row = ResearchPaperV1(**{**VALID_SAMPLE, "paper_id": "10.1234/abc-def_ghi"})
    assert row.paper_id == "10.1234/abc-def_ghi"


def test_paper_id_hash_fallback_accepted():
    row = ResearchPaperV1(**{**VALID_SAMPLE, "paper_id": "ssrn-abc123def456"})
    assert row.paper_id == "ssrn-abc123def456"


def test_paper_id_empty_raises():
    with pytest.raises(ValidationError):
        ResearchPaperV1(**{**VALID_SAMPLE, "paper_id": ""})


def test_paper_id_leading_special_raises():
    with pytest.raises(ValidationError, match="paper_id"):
        ResearchPaperV1(**{**VALID_SAMPLE, "paper_id": "-bad-leading"})


# ---------------------------------------------------------------------------
# title validation
# ---------------------------------------------------------------------------


def test_title_empty_raises():
    with pytest.raises(ValidationError, match="title"):
        ResearchPaperV1(**{**VALID_SAMPLE, "title": ""})


def test_title_whitespace_only_raises():
    with pytest.raises(ValidationError, match="title"):
        ResearchPaperV1(**{**VALID_SAMPLE, "title": "    "})


# ---------------------------------------------------------------------------
# authors validation
# ---------------------------------------------------------------------------


def test_authors_empty_list_raises():
    with pytest.raises(ValidationError):
        ResearchPaperV1(**{**VALID_SAMPLE, "authors": []})


def test_authors_anonymous_accepted():
    row = ResearchPaperV1(**{**VALID_SAMPLE, "authors": ["anonymous"]})
    assert row.authors == ["anonymous"]


def test_authors_empty_string_in_list_raises():
    with pytest.raises(ValidationError, match="authors"):
        ResearchPaperV1(**{**VALID_SAMPLE, "authors": ["Real Author", ""]})


# ---------------------------------------------------------------------------
# language ISO 639-1
# ---------------------------------------------------------------------------


def test_language_vi_accepted():
    row = ResearchPaperV1(**{**VALID_SAMPLE, "language": "vi"})
    assert row.language == "vi"


def test_language_en_accepted():
    row = ResearchPaperV1(**{**VALID_SAMPLE, "language": "en"})
    assert row.language == "en"


def test_language_uppercase_raises():
    with pytest.raises(ValidationError, match="language"):
        ResearchPaperV1(**{**VALID_SAMPLE, "language": "EN"})


def test_language_three_letter_raises():
    with pytest.raises(ValidationError, match="language"):
        ResearchPaperV1(**{**VALID_SAMPLE, "language": "vie"})


def test_language_empty_raises():
    with pytest.raises(ValidationError):
        ResearchPaperV1(**{**VALID_SAMPLE, "language": ""})


# ---------------------------------------------------------------------------
# DOI canonical form
# ---------------------------------------------------------------------------


def test_doi_canonical_accepted():
    row = ResearchPaperV1(**{**VALID_SAMPLE, "doi": "10.1016/j.heliyon.2026.01.001"})
    assert row.doi == "10.1016/j.heliyon.2026.01.001"


def test_doi_none_accepted():
    row = ResearchPaperV1(**{**VALID_SAMPLE, "doi": None})
    assert row.doi is None


def test_doi_with_http_prefix_raises():
    with pytest.raises(ValidationError, match="doi"):
        ResearchPaperV1(
            **{**VALID_SAMPLE, "doi": "https://doi.org/10.1016/j.heliyon.2026.01.001"}
        )


def test_doi_garbage_raises():
    with pytest.raises(ValidationError, match="doi"):
        ResearchPaperV1(**{**VALID_SAMPLE, "doi": "not-a-doi"})


# ---------------------------------------------------------------------------
# PIT discipline: as_of_date >= published_at
# ---------------------------------------------------------------------------


def test_as_of_date_equal_to_published_accepted():
    row = ResearchPaperV1(
        **{**VALID_SAMPLE, "as_of_date": _PUBLISHED, "published_at": _PUBLISHED}
    )
    assert row.as_of_date == row.published_at


def test_as_of_date_before_published_raises():
    earlier = date(2025, 12, 1)
    with pytest.raises(ValidationError, match="as_of_date"):
        ResearchPaperV1(
            **{**VALID_SAMPLE, "as_of_date": earlier, "published_at": _PUBLISHED}
        )


def test_as_of_date_required():
    payload = {k: v for k, v in VALID_SAMPLE.items() if k != "as_of_date"}
    with pytest.raises(ValidationError):
        ResearchPaperV1(**payload)


# ---------------------------------------------------------------------------
# Public import surface
# ---------------------------------------------------------------------------


def test_schema_exported_from_schemas_package():
    from hlpp_l0_contracts.schemas import ResearchPaperV1 as Exported

    assert Exported is ResearchPaperV1


def test_research_source_type_exported():
    from hlpp_l0_contracts.schemas.research_papers import ResearchSource as RS

    assert RS is ResearchSource


def test_paper_type_exported():
    from hlpp_l0_contracts.schemas.research_papers import PaperType as PT

    assert PT is PaperType
