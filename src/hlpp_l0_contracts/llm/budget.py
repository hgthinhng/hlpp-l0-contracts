"""Simple in-memory LLM cost budget guard with per-call and daily caps.

Exports ``BudgetExceeded`` (exception) and ``CostBudgetGuard`` (tracks spend, raises
when caps are breached). Caps can be set via constructor or environment variables.
"""

from __future__ import annotations

import math
import os


class BudgetExceeded(RuntimeError):
    """Raised when an estimated LLM call would exceed a configured budget."""


def _read_cap(value: float | None, env_name: str) -> float:
    if value is not None:
        return float(value)

    raw_value = os.getenv(env_name)
    if raw_value is None or raw_value.strip() == "":
        return math.inf
    return float(raw_value)


class CostBudgetGuard:
    def __init__(
        self,
        daily_cap_usd: float | None = None,
        per_call_cap_usd: float | None = None,
    ) -> None:
        self.daily_cap_usd = _read_cap(daily_cap_usd, "LLM_DAILY_BUDGET_USD")
        self.per_call_cap_usd = _read_cap(
            per_call_cap_usd,
            "LLM_PER_CALL_BUDGET_USD",
        )
        self._daily_total_usd = 0.0

    @property
    def daily_total_usd(self) -> float:
        return self._daily_total_usd

    def check_call(self, estimated_usd: float) -> None:
        estimated = float(estimated_usd)
        if estimated > self.per_call_cap_usd:
            raise BudgetExceeded(
                f"Estimated call cost ${estimated:.6f} exceeds per-call cap "
                f"${self.per_call_cap_usd:.6f}"
            )

        next_total = self._daily_total_usd + estimated
        if next_total > self.daily_cap_usd:
            raise BudgetExceeded(
                f"Estimated daily cost ${next_total:.6f} exceeds daily cap "
                f"${self.daily_cap_usd:.6f}"
            )

        self._daily_total_usd = next_total

    def reset_day(self) -> None:
        self._daily_total_usd = 0.0
