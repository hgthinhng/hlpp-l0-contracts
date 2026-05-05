"""Pydantic schema and loader for ``sources.yaml`` configuration files.

Exports ``SourceEntry`` (individual source definition), ``SourcesYaml`` (top-level
model), and ``load_sources_yaml`` (parse a YAML file into a list of validated entries).
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict


class SourceStatus(str, Enum):
    active = "active"
    disabled = "disabled"
    deprecated = "deprecated"


class SourceOps(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: SourceStatus


class SourceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    url: str
    ops: SourceOps
    disabled_reason: str | None
    last_verified_at: datetime


class SourcesYaml(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sources: list[SourceEntry]


def validate_source(entry_dict: dict[str, Any]) -> SourceEntry:
    return SourceEntry.model_validate(entry_dict)


def load_sources_yaml(path: Path) -> list[SourceEntry]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return SourcesYaml.model_validate(data).sources
