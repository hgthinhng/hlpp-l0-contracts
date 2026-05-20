"""LLM usage telemetry with SQLAlchemy-backed persistence and cost estimation.

Exports ``AIUsage`` (queue, flush, and summarize usage records), ``UsageRecord``
(row type), and ``ai_usage_table`` (SQLAlchemy table definition). Supports SQLite
and PostgreSQL via environment-driven configuration.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Mapping

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    func,
    insert,
    select,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session


metadata = MetaData()

ai_usage_table = Table(
    "ai_usage",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("provider", String(30), nullable=False),
    Column("model", String(60), nullable=False),
    Column("task", String(30), nullable=False),
    Column("input_tokens", Integer, nullable=False, default=0),
    Column("output_tokens", Integer, nullable=False, default=0),
    Column("estimated_cost_usd", Float, nullable=False, default=0.0),
    Column("sweep_id", String, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Index("ix_ai_usage_created_task", "created_at", "task"),
    Index("ix_ai_usage_sweep_id", "sweep_id"),
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime:
    if value is None:
        return _utcnow()
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _day_bounds(day: date | datetime | None = None) -> tuple[date, datetime, datetime]:
    if day is None:
        target_day = _utcnow().date()
    elif isinstance(day, datetime):
        target_day = _as_utc(day).date()
    else:
        target_day = day

    start = datetime.combine(target_day, time.min, tzinfo=timezone.utc)
    return target_day, start, start + timedelta(days=1)


@dataclass(frozen=True)
class UsageRecord:
    provider: str
    model: str
    task: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    sweep_id: str | None = None
    created_at: datetime = field(default_factory=_utcnow)


@dataclass
class AIUsage:
    """Queue, cost, flush, and summarize AI provider usage records."""

    task: str = ""
    cost_rates: Mapping[str, Mapping[str, Mapping[str, float]]] = field(
        default_factory=dict
    )
    engine: Engine | None = None
    database_url: str | None = None
    create_tables: bool = True
    echo: bool = False
    _pending_usage: list[UsageRecord] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        if self.engine is None and self.database_url:
            self.engine = create_engine(self.database_url, echo=self.echo)
        if self.engine is not None and self.create_tables:
            self.create_schema()

    @classmethod
    def database_url_from_env(
        cls, env: Mapping[str, str] | None = None, default_sqlite_url: str = "sqlite:///ai_usage.db"
    ) -> str:
        env = os.environ if env is None else env
        engine_name = env.get("ENGINE", "sqlite").strip().lower()

        if engine_name == "sqlite":
            return (
                env.get("AI_USAGE_DATABASE_URL")
                or env.get("SQLITE_URL")
                or env.get("DATABASE_URL")
                or default_sqlite_url
            )

        if engine_name in {"postgres", "postgresql"}:
            url = (
                env.get("AI_USAGE_DATABASE_URL")
                or env.get("POSTGRES_URL")
                or env.get("DATABASE_URL")
            )
            if not url:
                raise ValueError("ENGINE=postgres requires DATABASE_URL or POSTGRES_URL")
            if url.startswith("postgres://"):
                return f"postgresql://{url.removeprefix('postgres://')}"
            return url

        raise ValueError(f"Unsupported ENGINE={engine_name!r}; expected sqlite or postgres")

    @classmethod
    def from_env(
        cls,
        *,
        task: str = "",
        cost_rates: Mapping[str, Mapping[str, Mapping[str, float]]] | None = None,
        env: Mapping[str, str] | None = None,
        create_tables: bool = True,
        echo: bool = False,
    ) -> "AIUsage":
        return cls(
            task=task,
            cost_rates=cost_rates or {},
            database_url=cls.database_url_from_env(env),
            create_tables=create_tables,
            echo=echo,
        )

    @property
    def pending_count(self) -> int:
        return len(self._pending_usage)

    def create_schema(self) -> None:
        if self.engine is None:
            raise ValueError("AIUsage requires an engine or database_url to create tables")
        metadata.create_all(self.engine)

    def calculate_cost(
        self,
        *,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        provider_rates = self.cost_rates.get(provider, {})
        model_rates = provider_rates.get(model, {})
        input_rate = float(model_rates.get("input", 0.0)) / 1_000_000
        output_rate = float(model_rates.get("output", 0.0)) / 1_000_000
        return (int(input_tokens or 0) * input_rate) + (
            int(output_tokens or 0) * output_rate
        )

    def log_response(
        self,
        response: Any,
        *,
        task: str | None = None,
        sweep_id: str | None = None,
        created_at: datetime | None = None,
    ) -> UsageRecord:
        return self.log_usage(
            provider=getattr(response, "provider", ""),
            model=getattr(response, "model", ""),
            task=task,
            input_tokens=getattr(response, "input_tokens", 0),
            output_tokens=getattr(response, "output_tokens", 0),
            sweep_id=sweep_id,
            created_at=created_at,
        )

    def _log_usage(self, response: Any) -> UsageRecord:
        return self.log_response(response)

    def log_usage(
        self,
        *,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        task: str | None = None,
        cost_usd: float | None = None,
        sweep_id: str | None = None,
        created_at: datetime | None = None,
    ) -> UsageRecord:
        usage_task = task or self.task
        if not usage_task:
            raise ValueError("task is required to log AI usage")

        record = UsageRecord(
            provider=provider,
            model=model,
            task=usage_task,
            input_tokens=int(input_tokens or 0),
            output_tokens=int(output_tokens or 0),
            cost_usd=float(
                cost_usd
                if cost_usd is not None
                else self.calculate_cost(
                    provider=provider,
                    model=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )
            ),
            sweep_id=sweep_id,
            created_at=_as_utc(created_at),
        )
        self._pending_usage.append(record)
        return record

    def flush_usage(self, bind: Any | None = None) -> int:
        if not self._pending_usage:
            return 0

        rows = [
            {
                "provider": record.provider,
                "model": record.model,
                "task": record.task,
                "input_tokens": record.input_tokens,
                "output_tokens": record.output_tokens,
                "estimated_cost_usd": record.cost_usd,
                "sweep_id": record.sweep_id,
                "created_at": record.created_at,
            }
            for record in self._pending_usage
        ]

        executor, owned = self._executor(bind)
        try:
            executor.execute(insert(ai_usage_table), rows)
            if hasattr(executor, "flush"):
                executor.flush()
            if owned and hasattr(executor, "commit"):
                executor.commit()
        finally:
            if owned:
                executor.close()

        count = len(rows)
        self._pending_usage.clear()
        return count

    def _flush_usage(self, bind: Any | None = None) -> int:
        return self.flush_usage(bind)

    def daily_budget_summary(
        self,
        *,
        daily_budget_usd: float,
        day: date | datetime | None = None,
        bind: Any | None = None,
    ) -> dict[str, Any]:
        target_day, start, end = _day_bounds(day)
        stmt = select(
            func.coalesce(func.sum(ai_usage_table.c.estimated_cost_usd), 0.0).label(
                "cost"
            ),
            func.count(ai_usage_table.c.id).label("calls"),
            func.coalesce(func.sum(ai_usage_table.c.input_tokens), 0).label(
                "input_tokens"
            ),
            func.coalesce(func.sum(ai_usage_table.c.output_tokens), 0).label(
                "output_tokens"
            ),
        ).where(
            ai_usage_table.c.created_at >= start,
            ai_usage_table.c.created_at < end,
        )

        executor, owned = self._executor(bind)
        try:
            row = executor.execute(stmt).one()._mapping
        finally:
            if owned:
                executor.close()

        spent = round(float(row["cost"] or 0.0), 4)
        budget = float(daily_budget_usd or 0.0)
        remaining = round(max(0.0, budget - spent), 4)
        utilization = round((spent / budget * 100), 1) if budget > 0 else 0.0

        return {
            "date": target_day.isoformat(),
            "daily_limit_usd": budget,
            "spent_today_usd": spent,
            "remaining_today_usd": remaining,
            "utilization_pct": utilization,
            "over_budget": budget > 0 and spent >= budget,
            "calls_today": int(row["calls"] or 0),
            "input_tokens_today": int(row["input_tokens"] or 0),
            "output_tokens_today": int(row["output_tokens"] or 0),
        }

    def _executor(self, bind: Any | None = None) -> tuple[Any, bool]:
        if bind is not None:
            return bind, False
        if self.engine is None:
            raise ValueError("AIUsage requires an engine, database_url, or explicit bind")
        return Session(self.engine), True
