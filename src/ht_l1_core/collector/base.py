"""Base collector interface with automatic bronze provenance stamping.

Provides ``RawArticle`` (the standard row type) and ``BaseCollector`` (abstract base
class). Subclasses override ``_collect()``; ``collect()`` stamps lineage, provenance,
and vintage fields automatically.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import logging
import os
import subprocess
from abc import ABC
from collections.abc import Awaitable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from ht_l1_core.schema.lineage import _LineageMixin
from ht_l1_core.schema.provenance import _BronzeProvenanceMixin
from ht_l1_core.schema.vintage import _VintageMixin

log = logging.getLogger(__name__)

CollectResult = list["RawArticle"] | Awaitable[list["RawArticle"]]

AUTO_STAMP_COLUMNS = tuple(
    dict.fromkeys(
        (
            *_BronzeProvenanceMixin.__annotations__,
            *_LineageMixin.__annotations__,
            *_VintageMixin.__annotations__,
        )
    )
)


@dataclass
class RawArticle:
    """Raw article collected from a source, before dedup/processing."""

    title: str
    url: str | None = None
    summary: str | None = None
    source_id: str = ""
    language: str = "en"
    published_at: datetime | None = None
    extra: dict[str, Any] = field(default_factory=dict)
    source: str | None = None
    source_fetched_at: datetime | None = None
    ingested_at: datetime | None = None
    content_hash: str | None = None
    run_id: str | None = None
    code_sha: str | None = None
    inputs_hash: str | None = None
    as_of_date: date | None = None
    computed_at: datetime | None = None
    vintage: datetime | None = None
    status: str | None = None
    skip_reason: str | None = None
    error_category: str | None = None
    revision_count: int | None = None
    last_consumed_at: datetime | None = None


class BaseCollector(ABC):
    """Abstract base for news collectors."""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if "collect" in cls.__dict__:
            raise TypeError(
                f"{cls.__name__} must override _collect(); "
                "BaseCollector.collect() handles stamping."
            )
        if "_collect" not in cls.__dict__:
            raise TypeError(f"{cls.__name__} must override _collect().")

    def __init__(self, source_id: str, language: str, **kwargs: Any):
        self.source_id = source_id
        self.language = language

    async def collect(self, *args: Any, **kwargs: Any) -> list[RawArticle]:
        """Fetch raw articles and stamp required provenance, lineage, and vintage fields."""

        rows = await self._collect_rows(*args, **kwargs)
        return self._stamp_rows(rows)

    def _collect(self, *args: Any, **kwargs: Any) -> CollectResult:
        raise NotImplementedError("Collectors must implement _collect().")

    async def _collect_rows(self, *args: Any, **kwargs: Any) -> list[RawArticle]:
        rows_result = self._collect(*args, **kwargs)
        if inspect.isawaitable(rows_result):
            rows = await rows_result
        else:
            rows = rows_result
        return list(rows or [])

    def _stamp_rows(self, rows: list[RawArticle]) -> list[RawArticle]:
        fetched_at = _utc_now()
        ingested_at = _utc_now()
        computed_at = ingested_at
        code_sha = _code_sha()
        run_id = _run_id(self.source_id, ingested_at)

        for row in rows:
            if not isinstance(row, RawArticle):
                raise TypeError("BaseCollector.collect() must return RawArticle rows.")

            if not row.source_id:
                row.source_id = self.source_id
            if not row.language:
                row.language = self.language

            row.source = row.source or self.source_id
            row.source_fetched_at = row.source_fetched_at or fetched_at
            row.ingested_at = row.ingested_at or ingested_at
            row.content_hash = row.content_hash or self._content_hash(row)
            row.run_id = row.run_id or run_id
            row.code_sha = row.code_sha or code_sha
            row.as_of_date = row.as_of_date or _as_of_date(row, ingested_at)
            row.computed_at = row.computed_at or computed_at
            row.vintage = row.vintage or ingested_at
            row.status = row.status or "OK"
            row.revision_count = 0 if row.revision_count is None else row.revision_count

        inputs_hash = _inputs_hash(rows)
        for row in rows:
            row.inputs_hash = row.inputs_hash or inputs_hash

        return rows

    def _content_hash(self, row: RawArticle) -> str:
        payload = {
            "source": row.source or self.source_id,
            "source_id": row.source_id or self.source_id,
            "language": row.language or self.language,
            "title": row.title,
            "url": row.url,
            "summary": row.summary,
            "published_at": row.published_at,
            "extra": row.extra,
        }
        return _hash_json(payload)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(source={self.source_id})"


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _as_of_date(row: RawArticle, fallback: datetime) -> date:
    if row.published_at is not None:
        return row.published_at.date()
    return fallback.date()


def _run_id(source_id: str, when: datetime) -> str:
    return f"{source_id}:{when.strftime('%Y%m%dT%H%M%S%f')}"


def _code_sha() -> str:
    try:
        repo_root = Path(__file__).resolve().parents[3]
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        env_sha = os.getenv("HT_CODE_SHA", "").strip()
        if env_sha:
            return env_sha

        raise RuntimeError(
            "code_sha unavailable; refusing to write parquet — set HT_CODE_SHA env var "
            "or run from git checkout"
        )

    sha = result.stdout.strip()
    if len(sha) == 40 and all(char in "0123456789abcdef" for char in sha):
        return sha
    raise RuntimeError(f"git rev-parse HEAD returned an invalid code SHA: {sha!r}")


def _inputs_hash(rows: list[RawArticle]) -> str:
    return _hash_json([row.content_hash for row in rows])


def _hash_json(value: Any) -> str:
    payload = json.dumps(
        value,
        default=_json_default,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return repr(value)
