"""SourceStatus enum, SourceManifestEntry, and emit_skipped_row helper (L1-W6.JB4).

Design notes
------------
- ``SourceStatus`` uses ``enum.StrEnum`` (Python 3.11+) so values compare equal
  to their string literal without an explicit ``.value`` dereference.
- ``emit_skipped_row`` fills the full 20-col ``CrawlerBaseSchema`` shape with
  skip semantics.  It logs a WARNING when ``status=EXTERNAL_DEAD`` — even though
  that status is expected, the log cadence lets the operator observe how often
  dead sources are hit at runtime (loud-fail discipline).
- ``base_columns`` keys that conflict with the skip fields (``status``,
  ``skip_reason``, ``error_category``) are **overwritten** — callers must not
  rely on passing pre-set vintage status through ``base_columns``.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import StrEnum
from typing import Any, Literal

__all__ = [
    "SourceStatus",
    "SourceManifestEntry",
    "emit_skipped_row",
]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Enum
# ---------------------------------------------------------------------------


class SourceStatus(StrEnum):
    """Lifecycle status of a data source."""

    ACTIVE = "active"
    EXTERNAL_DEAD = "external_dead"
    EXPERIMENTAL = "experimental"


# ---------------------------------------------------------------------------
# Manifest entry
# ---------------------------------------------------------------------------


@dataclass
class SourceManifestEntry:
    """Human-readable record describing why a source is in its current state.

    Fields
    ------
    status
        Current lifecycle status of the source.
    reason
        Short free-text explanation of the current status.
    last_checked
        Date the status was last verified against the live source.
    revival_blocker
        Free text describing what blocks reviving the source (empty string if
        ``status=ACTIVE``).
    revival_priority
        Triage priority for revival work.  Defaults to ``"low"``.
    """

    status: SourceStatus
    reason: str
    last_checked: date
    revival_blocker: str
    revival_priority: Literal["low", "medium", "high"] = "low"


# ---------------------------------------------------------------------------
# emit_skipped_row
# ---------------------------------------------------------------------------

# All 20 CrawlerBaseSchema columns, ordered as defined in crawler_base.py.
_CRAWLER_BASE_COLUMNS: tuple[str, ...] = (
    # BronzeProvenanceMixin (4)
    "source",
    "source_fetched_at",
    "ingested_at",
    "content_hash",
    # VintageMixin (7)
    "vintage",
    "as_of_date",
    "status",
    "skip_reason",
    "error_category",
    "revision_count",
    "last_consumed_at",
    # LineageMixin (4)
    "run_id",
    "code_sha",
    "inputs_hash",
    "computed_at",
    # ToS / extraction-risk fields (5)
    "tos_status",
    "robots_status",
    "tos_citation_required",
    "disabled_reason",
    "llm_extraction_risk",
)

_SENTINEL_CODE_SHA = "0" * 40  # 40-char all-zero SHA — signals skip row


def emit_skipped_row(
    source: str,
    status: SourceStatus,
    reason: str,
    base_columns: dict[str, Any],
) -> dict[str, Any]:
    """Return a 20-col ``CrawlerBaseSchema``-shaped row with skip semantics.

    Parameters
    ----------
    source:
        Identifier of the data source being skipped (used for logging and the
        ``source`` provenance column if not already in ``base_columns``).
    status:
        ``SourceStatus`` value — controls skip reason tag and triggers a loud
        WARNING when ``EXTERNAL_DEAD``.
    reason:
        Human-readable explanation written to ``skip_reason``.
    base_columns:
        Caller-supplied column values.  Any key present here is merged into the
        result; the skip-semantic columns (``status``, ``skip_reason``,
        ``error_category``) are **always overwritten** regardless of what the
        caller passes.

    Returns
    -------
    dict[str, Any]
        A dict with all 20 ``CrawlerBaseSchema`` columns populated.  Columns not
        supplied by ``base_columns`` are filled with sentinel / None values.

    Raises
    ------
    No exceptions are raised.  The function always returns a valid skip row.
    """
    if status == SourceStatus.EXTERNAL_DEAD:
        logger.warning(
            "emit_skipped_row: source=%r is EXTERNAL_DEAD — reason=%r.  "
            "Row emitted with SKIPPED status.  "
            "Update SourceManifestEntry revival_priority if this is recurring.",
            source,
            reason,
        )

    now = datetime.now(tz=timezone.utc)

    # Build the row: start from defaults, merge caller base_columns, then
    # enforce skip-semantic overrides.
    row: dict[str, Any] = {
        # Provenance defaults
        "source": source,
        "source_fetched_at": now,
        "ingested_at": now,
        "content_hash": "",
        # Vintage defaults
        "vintage": now,
        "as_of_date": now.date(),
        "revision_count": 0,
        "last_consumed_at": None,
        # Lineage defaults
        "run_id": str(uuid.uuid4()),
        "code_sha": _SENTINEL_CODE_SHA,
        "inputs_hash": "",
        "computed_at": now,
        # ToS / extraction-risk defaults
        "tos_status": None,
        "robots_status": None,
        "tos_citation_required": None,
        "disabled_reason": None,
        "llm_extraction_risk": None,
    }

    # Merge caller-supplied columns (may override some defaults above).
    row.update(base_columns)

    # Skip-semantic columns always win — enforce VINTAGE_STATUSES value "SKIPPED".
    row["status"] = "SKIPPED"
    row["skip_reason"] = f"[{status}] {reason}"
    row["error_category"] = str(status)

    # Ensure every CrawlerBase column is present (fill missing with None).
    for col in _CRAWLER_BASE_COLUMNS:
        row.setdefault(col, None)

    return row
