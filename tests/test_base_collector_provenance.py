import asyncio
from importlib import metadata as importlib_metadata
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import ht_l1_core.collector.base as base_module
from ht_l1_core.collector.base import BaseCollector, RawArticle


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
        "as_of_date",
        "computed_at",
        "vintage",
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

def test_code_sha_uses_package_version_when_git_and_env_are_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        base_module.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("git unavailable")),
    )
    monkeypatch.delenv("HT_CODE_SHA", raising=False)
    monkeypatch.setattr(importlib_metadata, "version", lambda package: "0.0.1+local")

    assert base_module._code_sha() == "0.0.1+local"

def test_code_sha_raises_when_no_code_identity_is_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        base_module.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("git unavailable")),
    )
    monkeypatch.delenv("HT_CODE_SHA", raising=False)

    def raise_missing_package(package: str) -> str:
        raise importlib_metadata.PackageNotFoundError(package)

    monkeypatch.setattr(importlib_metadata, "version", raise_missing_package)

    with pytest.raises(RuntimeError, match="Unable to determine code SHA"):
        base_module._code_sha()
