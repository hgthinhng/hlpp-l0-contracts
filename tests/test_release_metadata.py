from __future__ import annotations

from pathlib import Path
import tomllib


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_pyproject_version_is_0_2_0() -> None:
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text())

    assert pyproject["project"]["version"] == "0.2.0"


def test_changelog_records_0_1_5_protocol_release() -> None:
    changelog = (PROJECT_ROOT / "CHANGELOG.md").read_text()

    assert "## 0.1.5 - 2026-05-07" in changelog
    assert "Backfillable" in changelog
    assert "TierAStreamConsumer" in changelog
    assert "ADR-016" in changelog


def test_adr_016_document_locks_tiered_trigger_matrix() -> None:
    adr = (PROJECT_ROOT / "docs" / "adr" / "ADR-016-tiered-l1-l2-trigger.md").read_text()

    assert "ADR-016 LOCK" in adr
    assert "HTAP L1→L2 trigger transport is partitioned into 5 tiers" in adr
    assert "m12-fqx-trading-stream-v1" in adr
    assert "SQLite ring at `~/.local/share/htap/hot-buffer.db`" in adr
    assert "Backfillable" in adr
    assert "TierAStreamConsumer" in adr
