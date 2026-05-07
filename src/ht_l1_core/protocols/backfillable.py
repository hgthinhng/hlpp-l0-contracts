"""Protocol contract for target-year backfill collectors."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class BackfillResult:
    """Result summary returned by a target-year backfill run."""

    target_year: int
    rows: int
    status: str = "OK"
    message: str = ""


class BackfillTargetYearUnavailable(ValueError):
    """Raised when a source cannot serve the requested target year."""

    target_year: int
    available_years: tuple[int, ...]
    source: str

    def __init__(
        self,
        *,
        target_year: int,
        available_years: Iterable[int] = (),
        source: str = "",
        message: str | None = None,
    ) -> None:
        years = tuple(sorted(set(available_years)))
        self.target_year = target_year
        self.available_years = years
        self.source = source

        if message is None:
            parts = [f"target_year={target_year} unavailable"]
            if source:
                parts.append(f"source={source!r}")
            if years:
                parts.append(f"available_years={years!r}")
            message = "; ".join(parts)

        super().__init__(message)


@runtime_checkable
class Backfillable(Protocol):
    """Collector contract for sources that honor an explicit target year."""

    def backfill(self, *, target_year: int, **kw: object) -> BackfillResult:
        """Backfill the requested year or raise BackfillTargetYearUnavailable."""
        ...
