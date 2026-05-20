import asyncio
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import hlpp_l0_contracts.collector.base as base_module
from hlpp_l0_contracts.collector.base import BaseCollector, RawArticle


class OneRowCollector(BaseCollector):
    async def _collect(self) -> list[RawArticle]:
        return [RawArticle(title="Central bank holds rates")]


def test_collect_auto_stamps_required_provenance_lineage_and_vintage_columns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HT_CODE_SHA", "a" * 40)

    rows = asyncio.run(OneRowCollector(source_id="unit-test", language="en").collect())

    assert len(rows) == 1
    row = rows[0]

    auto_stamp_columns = [
        "source",
        "source_fetched_at",
        "ingested_at",
        "content_hash",
        "run_id",
        "code_sha",
        "inputs_hash",
        "computed_at",
        "vintage",
        "as_of_date",
        "status",
        "revision_count",
    ]

    assert all(getattr(row, column) is not None for column in auto_stamp_columns)

def test_collector_subclass_cannot_override_collect_directly() -> None:
    with pytest.raises(TypeError, match="_collect"):

        class BadCollector(BaseCollector):
            async def collect(self) -> list[RawArticle]:
                return [RawArticle(title="wrong hook")]

def test_collector_subclass_must_override_collect_hook() -> None:
    with pytest.raises(TypeError, match="_collect"):

        class MissingCollectHook(BaseCollector):
            pass

def test_code_sha_uses_explicit_env_fallback_when_git_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        base_module.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("git unavailable")),
    )
    monkeypatch.setenv("HT_CODE_SHA", "b" * 40)

    assert base_module._code_sha() == "b" * 40

def test_code_sha_raises_when_git_and_env_are_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        base_module.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("git unavailable")),
    )
    monkeypatch.delenv("HT_CODE_SHA", raising=False)

    message = (
        "code_sha unavailable; refusing to write parquet — set HT_CODE_SHA env var "
        "or run from git checkout"
    )
    with pytest.raises(RuntimeError, match=message):
        base_module._code_sha()
