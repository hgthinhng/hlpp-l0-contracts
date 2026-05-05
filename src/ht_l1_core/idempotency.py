"""Database-agnostic idempotent insert helpers for SQLite and PostgreSQL.

Exports ``sha256_url`` (deterministic URL hashing) and ``idempotent_insert`` (uses
``INSERT OR IGNORE`` for SQLite and ``ON CONFLICT DO NOTHING`` for PostgreSQL).
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert


INSERT_OR_NOTHING_SQL = {
    "sqlite": "INSERT OR IGNORE",
    "postgres": "ON CONFLICT DO NOTHING",
}


def sha256_url(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def idempotent_insert(session: Any, model: Any, record_dict: Mapping[str, Any]) -> Any:
    dialect_name = session.get_bind().dialect.name

    if dialect_name == "sqlite":
        sqlite_statement = sqlite_insert(model).values(record_dict).prefix_with("OR IGNORE")
        return session.execute(sqlite_statement)
    elif dialect_name in {"postgres", "postgresql"}:
        postgres_statement = postgres_insert(model).values(record_dict).on_conflict_do_nothing()
        return session.execute(postgres_statement)
    else:
        raise ValueError(f"Unsupported dialect for idempotent insert: {dialect_name}")
