"""Backfillable Protocol decorator and anti-reestamp guard (L1-W6.JB6.a).

Re-exports the ``Backfillable`` protocol from ``ht_l1_core.protocols`` and
provides ``@backfillable_check`` — a decorator that wraps a collector method
and asserts non-restamped behaviour on invocation.

The guard calls the wrapped method with the supplied ``target_year``, collects
the returned rows, and raises ``RuntimeError`` if *all* returned rows have a
date component that matches *today's* date rather than ``target_year``.  This
catches the classic "fake backfill" pattern where a collector ignores
``target_year`` and just re-stamps the latest snapshot.

Design notes
------------
- The check is **opt-in** and wraps individual collector methods.  It is NOT
  applied automatically to every ``Backfillable`` implementer.
- A ``RuntimeError`` is raised, not an ``AssertionError``, so the loud-fail
  discipline is respected even in optimised Python builds (``-O``).
- The check is skipped when there are zero rows (empty result is a separate
  concern handled by ``emit_skipped_row`` / SKIPPED vintage status).
- Date introspection checks ``as_of_date`` key first, then ``date`` key, then
  falls back to any ``datetime.date``-typed value in the row dict.
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable, Iterable
from datetime import date, datetime
from typing import Any, TypeVar

from ht_l1_core.protocols import Backfillable, BackfillResult, BackfillTargetYearUnavailable

__all__ = [
    "Backfillable",
    "BackfillResult",
    "BackfillTargetYearUnavailable",
    "BackfillRow",
    "backfillable_check",
]

logger = logging.getLogger(__name__)

# A BackfillRow is a plain dict of column-name → value, matching the m12 row shape.
BackfillRow = dict[str, Any]

_F = TypeVar("_F", bound=Callable[..., Iterable[BackfillRow]])


def _extract_year(row: BackfillRow) -> int | None:
    """Return the year from a row dict.  Priority: as_of_date > date > first date value."""
    for key in ("as_of_date", "date"):
        val = row.get(key)
        if isinstance(val, (date, datetime)):
            return val.year
        if isinstance(val, str):
            try:
                return date.fromisoformat(val[:10]).year
            except ValueError:
                pass
    # Fallback: scan all values for a date/datetime
    for val in row.values():
        if isinstance(val, (date, datetime)):
            return val.year
    return None


def backfillable_check(method: _F) -> _F:
    """Decorator asserting that the wrapped method produces target-year data.

    Wraps a collector method with the signature::

        def backfill(self, target_year: int, ...) -> Iterable[BackfillRow]

    On each call the decorator:

    1. Calls the underlying method and materialises the result into a list.
    2. Skips the check if the list is empty (zero rows → separate concern).
    3. Inspects every row's date column (``as_of_date`` or ``date``).
    4. Raises ``RuntimeError`` if **all** datable rows have a year matching
       *today* rather than ``target_year``.  This catches re-stamp-only fakes.

    Usage::

        class MyCollector:
            @backfillable_check
            def backfill(self, target_year: int) -> Iterable[BackfillRow]:
                ...

    The decorator is transparent to type-checkers via ``functools.wraps``.
    """

    @functools.wraps(method)
    def wrapper(*args: Any, **kwargs: Any) -> list[BackfillRow]:
        # Resolve target_year from positional or keyword args.
        target_year: int | None = None
        if len(args) > 1 and isinstance(args[1], int):
            target_year = args[1]
        elif "target_year" in kwargs and isinstance(kwargs["target_year"], int):
            target_year = kwargs["target_year"]

        rows: list[BackfillRow] = list(method(*args, **kwargs))

        if target_year is None or not rows:
            return rows

        today = date.today()
        datable_rows = [r for r in rows if _extract_year(r) is not None]

        if not datable_rows:
            # No date columns to check — pass through.
            return rows

        today_count = sum(1 for r in datable_rows if _extract_year(r) == today.year)
        target_count = sum(1 for r in datable_rows if _extract_year(r) == target_year)

        if today_count == len(datable_rows) and target_year != today.year:
            raise RuntimeError(
                f"backfillable_check: all {len(datable_rows)} row(s) have year "
                f"{today.year} (today) but target_year={target_year}.  "
                "This looks like a fake backfill that re-stamps the latest snapshot.  "
                "Ensure the collector queries data FOR target_year, not today."
            )

        if target_count == 0 and target_year != today.year:
            logger.warning(
                "backfillable_check: 0 of %d datable row(s) matched target_year=%d "
                "(years seen: %s).  Check collector date filtering.",
                len(datable_rows),
                target_year,
                sorted(y for y in {_extract_year(r) for r in datable_rows} if y is not None),
            )

        return rows

    return wrapper  # type: ignore[return-value]
