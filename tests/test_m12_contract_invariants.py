"""Cross-repo m12 crawler contract invariants."""

from __future__ import annotations

import ast
from dataclasses import dataclass
import importlib
from pathlib import Path
import sys
from types import ModuleType
from typing import Any

import pandera.pandas as pa
import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_HOME = Path.home()
_DEPENDENT_REPOS = (
    _HOME / "NewsCrawlers",
    _HOME / "MacroDataCrawlers",
    _HOME / "vnstock-adapters",
    _HOME / "fqx-adapters",
    _HOME / "cross-market-adapters",
)

if not any(repo.exists() for repo in _DEPENDENT_REPOS):
    pytest.skip(
        "cross-repo m12 contract invariant test requires sibling L1 repos",
        allow_module_level=True,
    )

for src_path in reversed(
    (_PROJECT_ROOT / "src",)
    + tuple(repo / "src" for repo in _DEPENDENT_REPOS if (repo / "src").exists())
):
    sys.path.insert(0, str(src_path))

from hlpp_l0_contracts.schema.crawler_base import CRAWLER_BASE_COLUMNS, CrawlerBaseSchema  # noqa: E402

_SPEC_PAYLOAD_FIELDS = {
    "m12-newscrawlers-articles-v1": (
        "title",
        "url",
        "published_at",
        "source_name",
        "summary",
        "language",
    ),
    "m12-macrodata-timeseries-v1": (
        "indicator",
        "period",
        "value",
        "frequency",
        "region",
        "policy_event_type",
    ),
    "m12-vnbond-timeseries-v1": (
        "dataset",
        "metric",
        "period",
        "value",
        "frequency",
        "market",
        "tenor",
        "bond_code",
        "unit",
    ),
}


@dataclass(frozen=True)
class M12ContractModule:
    contract_id: str
    module_name: str
    source_path: Path


def _literal_contract_id(path: Path) -> str | None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        value: ast.expr | None = None
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            value = node.value
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            value = node.value
            targets = [node.target]
        if value is None or not isinstance(value, ast.Constant):
            continue
        if not isinstance(value.value, str) or not value.value.startswith("m12-"):
            continue
        if any(isinstance(target, ast.Name) and target.id == "CONTRACT_ID" for target in targets):
            return value.value
    return None


def _module_name_from_path(src_root: Path, path: Path) -> str:
    relative = path.relative_to(src_root).with_suffix("")
    return ".".join(relative.parts)


def _discover_m12_contract_modules() -> tuple[M12ContractModule, ...]:
    discovered: list[M12ContractModule] = []
    missing = [repo for repo in _DEPENDENT_REPOS if not repo.exists()]
    assert not missing, f"missing dependent repo roots: {missing}"

    for repo in _DEPENDENT_REPOS:
        src_root = repo / "src"
        if not src_root.exists():
            continue
        for path in sorted(src_root.rglob("*.py")):
            source = path.read_text(encoding="utf-8")
            if "CONTRACT_ID" not in source or "CrawlerBaseSchema" not in source:
                continue
            contract_id = _literal_contract_id(path)
            if contract_id is None:
                continue
            discovered.append(
                M12ContractModule(
                    contract_id=contract_id,
                    module_name=_module_name_from_path(src_root, path),
                    source_path=path,
                )
            )
    return tuple(sorted(discovered, key=lambda module: module.contract_id))


_M12_CONTRACT_MODULES = _discover_m12_contract_modules()


def _contract_schema(module: ModuleType) -> tuple[str, pa.DataFrameSchema]:
    base_columns = set(CRAWLER_BASE_COLUMNS)
    schemas = [
        (name, value)
        for name, value in vars(module).items()
        if isinstance(value, pa.DataFrameSchema)
        and value is not CrawlerBaseSchema
        and base_columns.issubset(value.columns)
    ]
    assert len(schemas) == 1, (
        f"{module.__name__} must expose exactly one m12 DataFrameSchema "
        f"extending CrawlerBaseSchema, found {[name for name, _ in schemas]}"
    )
    return schemas[0]


def _field_names(value: Any) -> tuple[str, ...]:
    if isinstance(value, pa.DataFrameSchema):
        return tuple(value.columns)
    if isinstance(value, dict):
        return tuple(str(name) for name in value)
    if isinstance(value, (list, tuple)):
        return tuple(str(name) for name in value)
    raise TypeError(f"unsupported payload constant type: {type(value).__name__}")


def _payload_columns_constant(module: ModuleType) -> tuple[str, tuple[str, ...]]:
    candidates: list[tuple[str, tuple[str, ...]]] = []
    for name, value in vars(module).items():
        if name.upper().endswith("_PAYLOAD_COLUMNS"):
            candidates.append((name, _field_names(value)))
    assert len(candidates) == 1, (
        f"{module.__name__} must expose exactly one *_PAYLOAD_COLUMNS constant, "
        f"found {[name for name, _ in candidates]}"
    )
    return candidates[0]


def test_all_spec_payload_contracts_are_discovered() -> None:
    assert {module.contract_id for module in _M12_CONTRACT_MODULES} == set(
        _SPEC_PAYLOAD_FIELDS
    )


@pytest.mark.parametrize(
    "contract_module",
    _M12_CONTRACT_MODULES,
    ids=lambda module: module.contract_id,
)
def test_m12_contract_extends_crawler_base_and_matches_spec_payload(
    contract_module: M12ContractModule,
) -> None:
    module = importlib.import_module(contract_module.module_name)
    expected_payload = _SPEC_PAYLOAD_FIELDS[contract_module.contract_id]

    assert len(CRAWLER_BASE_COLUMNS) == 20
    assert tuple(CrawlerBaseSchema.columns) == tuple(CRAWLER_BASE_COLUMNS)

    payload_constant_name, payload_fields = _payload_columns_constant(module)
    assert payload_fields == expected_payload, (
        f"{contract_module.contract_id} {payload_constant_name} drifted from spec"
    )

    schema_name, schema = _contract_schema(module)
    schema_columns = tuple(schema.columns)
    assert schema_columns[:20] == tuple(CRAWLER_BASE_COLUMNS), (
        f"{contract_module.contract_id} {schema_name} does not inherit the "
        "CrawlerBaseSchema columns first"
    )
    assert schema_columns[20:] == expected_payload
