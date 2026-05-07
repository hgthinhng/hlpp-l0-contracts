"""Tier-A L1 stream protocol contracts."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, TypeAlias, runtime_checkable


@dataclass(frozen=True)
class BarData:
    """One Tier-A trading observation delivered to a stream callback."""

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
        """Start or resume the stream session."""
        ...

    def stop(self) -> None:
        """Stop the stream session and release transport resources."""
        ...


@runtime_checkable
class TierAStreamConsumer(Protocol):
    """Consumer capable of starting a Tier-A trading stream."""

    def start(self, tickers: Sequence[str], callback: BarCallback) -> TierAStreamSession:
        """Start streaming tickers and deliver each observation to callback."""
        ...

    def stop(self) -> None:
        """Stop the current stream session."""
        ...
