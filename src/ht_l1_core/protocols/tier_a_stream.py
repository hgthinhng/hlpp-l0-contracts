"""Tier-A L1 stream protocol contracts."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, TypeAlias, runtime_checkable


@dataclass(frozen=True)
class BarData:
    """One Tier-A trading observation delivered to a stream callback.

    ``observed_at`` must be timezone-aware.
    """

    ticker: str
    observed_at: datetime
    price: float
    volume: int
    raw: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")


BarCallback: TypeAlias = Callable[[BarData], None]


@runtime_checkable
class TierAStreamSession(Protocol):
    """Start/stop lifecycle for an active Tier-A stream session."""

    def start(self) -> None:
        """Start or resume the stream session idempotently.

        A session returned by ``TierAStreamConsumer.start`` is already active; callers use this
        method only to resume a paused/stopped session when an implementation supports resume.
        """
        ...

    def stop(self) -> None:
        """Stop the stream session and release its transport resources idempotently."""
        ...


@runtime_checkable
class TierAStreamConsumer(Protocol):
    """Consumer capable of starting a Tier-A trading stream."""

    def start(self, tickers: Sequence[str], callback: BarCallback) -> TierAStreamSession:
        """Create and start a session for tickers, delivering each observation to callback.

        This is a factory-plus-auto-start contract: the returned ``TierAStreamSession`` is
        active before the method returns, so callers must not call ``session.start`` as part of
        normal setup.
        """
        ...

    def stop(self) -> None:
        """Stop the current session, if any, and release consumer resources idempotently."""
        ...
