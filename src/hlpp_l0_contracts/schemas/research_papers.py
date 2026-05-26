"""HLPP Research Papers contract — Wave 8 academic/research paper observations.

Reference: plan v2 lines 200-206 in
~/.omc/plans/2026-05-22-l1a-maximum-buildout-v2.md

ResearchPaperV1 is the canonical contract for all Wave 8 academic-paper collectors
(SSRN, RePEc, AMRO, IMF working-papers, OECD, Heliyon, VEPR, Fulbright FSPPM).
Collectors produce one row per paper and validate it against this schema before
parquet write.

Monthly polling cadence (PDF + metadata). Downstream L2 NLP (TickerResolver)
populates ticker_mentions; collectors at L0 may leave it empty.

Schema lives parallel to ALT-DATA (source_family="academic"), but uses a
purpose-built typed contract because academic papers have rich consistent
metadata (DOI, authors, abstract, paper_type, institution) worth columnizing
beyond the opaque payload dict.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_PAPER_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-:/]*$")
_LANG_RE = re.compile(r"^[a-z]{2}$")
_DOI_RE = re.compile(r"^10\.\d{4,9}/[-._;()/:A-Za-z0-9]+$")

ResearchSource = Literal[
    "ssrn",
    "repec",
    "amro",
    "imf_wp",
    "oecd",
    "heliyon",
    "vepr",
    "fulbright_fsppm",
    # Wave 8.1 expansion (2026-05-26) — 3-LLM consensus academic gap closure.
    "wb_prwp",  # World Bank Policy Research Working Papers
    "adb_wp",  # ADB Economics Working Papers
    "bis_wp",  # BIS Working Papers
    "ueh_jabes",  # UEH Journal of Asian Business and Economic Studies
    "neu_journals",  # NEU domestic journals (Vietnamese-language)
]

PaperType = Literal[
    "working_paper",
    "journal",
    "policy_brief",
    "conference",
]


class ResearchPaperV1(BaseModel):
    """Canonical contract for Wave 8 academic/research paper observations.

    Every research-paper collector must produce rows that validate against this
    schema. Required fields cover identity (paper_id), provenance (source,
    pdf_url, doi), bibliographic metadata (title, authors, abstract,
    published_at, language), classification (paper_type, institution,
    keywords), downstream join (ticker_mentions populated by L2 NLP), and PIT
    discipline (as_of_date = crawl date).

    Spec constraints:
    - paper_id non-empty, matches ^[A-Za-z0-9][A-Za-z0-9._\\-:/]*$ (DOI-safe).
    - source must be one of 8 Wave 8 sources (enum).
    - title non-empty after strip().
    - authors must be a non-empty list (anonymous papers use ["anonymous"]).
    - published_at and as_of_date are dates (not datetimes).
    - as_of_date >= published_at (cannot crawl from before publication).
    - language is ISO 639-1 (lowercase 2-letter).
    - paper_type, if present, must be one of 4 enum values.
    - doi, if present, must match ^10\\.\\d{4,9}/... canonical DOI form.
    - ticker_mentions defaults to [] (L0 collectors don't populate; L2 NLP does).
    - source_metadata defaults to {} for raw vendor-specific fields.
    - extra fields are forbidden (strict contract).
    - model is frozen (immutable after construction).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    paper_id: str = Field(
        ...,
        description=(
            "Canonical paper identifier. Use DOI when available; "
            "fallback to stable hash of source+url+title."
        ),
    )
    source: ResearchSource = Field(
        ...,
        description=(
            "Research source identifier: ssrn, repec, amro, imf_wp, oecd, "
            "heliyon, vepr, fulbright_fsppm"
        ),
    )
    title: str = Field(..., description="Paper title (raw, not normalized)")
    authors: list[str] = Field(
        ...,
        min_length=1,
        description="Ordered list of author names (anonymous → ['anonymous'])",
    )
    abstract: str | None = Field(None, description="Abstract text if available")
    published_at: date = Field(
        ..., description="Publication date as reported by source"
    )
    pdf_url: str | None = Field(
        None, description="Direct PDF URL if available (else landing-page-only)"
    )
    doi: str | None = Field(
        None,
        description="DOI in canonical form 10.NNNN/suffix (no http:// prefix)",
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="Raw vendor keywords/tags (downstream NLP may augment)",
    )
    ticker_mentions: list[str] = Field(
        default_factory=list,
        description=(
            "VN ticker symbols mentioned in title/abstract/body. Populated by "
            "L2 TickerResolver NLP; collectors at L0 leave empty []."
        ),
    )
    language: str = Field(
        ...,
        description="ISO 639-1 lowercase 2-letter code (e.g. 'vi', 'en')",
    )
    paper_type: PaperType | None = Field(
        None,
        description="working_paper / journal / policy_brief / conference",
    )
    institution: str | None = Field(
        None,
        description=(
            "Publishing university/think-tank/agency name "
            "(e.g. 'IMF', 'VEPR', 'Fulbright FSPPM')"
        ),
    )
    as_of_date: date = Field(
        ...,
        description="Crawl timestamp date (PIT partition key)",
    )
    source_metadata: dict[str, object] = Field(
        default_factory=dict,
        description=(
            "Vendor-specific raw fields preserved verbatim "
            "(JEL codes, citation counts, paper_number, etc.)"
        ),
    )

    @field_validator("paper_id", mode="after")
    @classmethod
    def _validate_paper_id(cls, v: str) -> str:
        if not v:
            raise ValueError("paper_id must not be empty")
        if not _PAPER_ID_RE.match(v):
            raise ValueError(
                f"paper_id must match ^[A-Za-z0-9][A-Za-z0-9._\\-:/]*$; got {v!r}"
            )
        return v

    @field_validator("title", mode="after")
    @classmethod
    def _validate_title(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("title must not be empty after strip()")
        return v

    @field_validator("language", mode="after")
    @classmethod
    def _validate_language(cls, v: str) -> str:
        if not _LANG_RE.match(v):
            raise ValueError(
                f"language must be ISO 639-1 lowercase 2-letter code; got {v!r}"
            )
        return v

    @field_validator("doi", mode="after")
    @classmethod
    def _validate_doi(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not _DOI_RE.match(v):
            raise ValueError(
                f"doi must match canonical form 10.NNNN/suffix; got {v!r}"
            )
        return v

    @field_validator("authors", mode="after")
    @classmethod
    def _validate_authors_nonempty_strings(cls, v: list[str]) -> list[str]:
        for i, a in enumerate(v):
            if not isinstance(a, str) or not a.strip():
                raise ValueError(
                    f"authors[{i}] must be non-empty string; got {a!r}"
                )
        return v

    @model_validator(mode="after")
    def _as_of_date_gte_published(self) -> "ResearchPaperV1":
        """as_of_date must be >= published_at (cannot crawl before publication)."""
        if self.as_of_date < self.published_at:
            raise ValueError(
                f"as_of_date ({self.as_of_date!r}) must be >= "
                f"published_at ({self.published_at!r}); "
                "collector cannot crawl a paper before its publication date"
            )
        return self


__all__ = ["ResearchPaperV1", "ResearchSource", "PaperType"]
