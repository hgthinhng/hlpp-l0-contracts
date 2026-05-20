from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hlpp_l0_contracts.llm.budget import BudgetExceeded, CostBudgetGuard


def test_check_call_raises_when_running_daily_total_would_exceed_env_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_DAILY_BUDGET_USD", "0.01")

    guard = CostBudgetGuard()

    guard.check_call(0.006)
    with pytest.raises(BudgetExceeded):
        guard.check_call(0.006)
