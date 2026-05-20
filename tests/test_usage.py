from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hlpp_l0_contracts.llm.usage import AIUsage


def test_log_response_calculates_cost_and_flushes_to_sqlite() -> None:
    engine = create_engine("sqlite:///:memory:")
    usage = AIUsage(
        task="translation",
        cost_rates={"openai": {"gpt-4o-mini": {"input": 0.15, "output": 0.60}}},
        engine=engine,
    )
    response = SimpleNamespace(
        provider="openai",
        model="gpt-4o-mini",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
    )

    record = usage.log_response(response, sweep_id="sweep-1")
    assert record.cost_usd == pytest.approx(0.75)
    assert usage.pending_count == 1

    assert usage.flush_usage() == 1
    assert usage.pending_count == 0

    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT provider, model, task, input_tokens, output_tokens,
                       estimated_cost_usd, sweep_id
                FROM ai_usage
                """
            )
        ).mappings().one()

    assert row["provider"] == "openai"
    assert row["model"] == "gpt-4o-mini"
    assert row["task"] == "translation"
    assert row["input_tokens"] == 1_000_000
    assert row["output_tokens"] == 1_000_000
    assert row["estimated_cost_usd"] == pytest.approx(0.75)
    assert row["sweep_id"] == "sweep-1"


def test_daily_budget_summary_counts_only_requested_day() -> None:
    engine = create_engine("sqlite:///:memory:")
    usage = AIUsage(
        task="classification",
        cost_rates={"anthropic": {"claude-sonnet": {"input": 3.00, "output": 15.00}}},
        engine=engine,
    )
    now = datetime.now(timezone.utc)

    usage.log_usage(
        provider="anthropic",
        model="claude-sonnet",
        input_tokens=100_000,
        output_tokens=10_000,
        created_at=now - timedelta(days=2),
    )
    usage.log_usage(
        provider="anthropic",
        model="claude-sonnet",
        input_tokens=100_000,
        output_tokens=10_000,
        created_at=now,
    )
    usage.flush_usage()

    summary = usage.daily_budget_summary(daily_budget_usd=1.00, day=now.date())

    assert summary == {
        "date": now.date().isoformat(),
        "daily_limit_usd": 1.0,
        "spent_today_usd": 0.45,
        "remaining_today_usd": 0.55,
        "utilization_pct": 45.0,
        "over_budget": False,
        "calls_today": 1,
        "input_tokens_today": 100_000,
        "output_tokens_today": 10_000,
    }


def test_from_env_supports_sqlite_memory_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENGINE", "sqlite")
    monkeypatch.setenv("SQLITE_URL", "sqlite:///:memory:")

    usage = AIUsage.from_env(
        task="briefing",
        cost_rates={"local": {"test-model": {"input": 1.00, "output": 1.00}}},
    )

    usage.log_usage(
        provider="local",
        model="test-model",
        input_tokens=500_000,
        output_tokens=250_000,
    )
    usage.flush_usage()

    assert usage.engine.url.get_backend_name() == "sqlite"
    assert usage.daily_budget_summary(daily_budget_usd=1.00)["spent_today_usd"] == 0.75
