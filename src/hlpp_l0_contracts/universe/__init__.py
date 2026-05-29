"""HLPP-UNIVERSE — versioned ticker universe config.

Versions:
- v1_130 — legacy 130 tickers (VN30+HOSE50+HNX30+UPCOM20), pre-v0.5 rebrand
- v2_120 — current 120 tickers (VN30+HOSE50+HNX30+UPCOM10), Elon first-principles

≥85% Mcap + Mvolume coverage of VN market.
"""
from __future__ import annotations

from importlib.resources import files
from typing import Any, cast

import yaml


def load(version: str = "v2_120") -> dict[str, Any]:
    """Load universe config by version string.

    Args:
        version: e.g. "v2_120" (current), "v1_130" (legacy).

    Returns:
        dict with keys: version, total, composition (sub-pool → ticker list),
                        tickers (flat list), source_notes.

    Raises:
        FileNotFoundError: if version yaml not bundled.
    """
    pkg = files("hlpp_l0_contracts.universe")
    yaml_path = pkg / f"{version}.yaml"
    with yaml_path.open("r", encoding="utf-8") as f:
        return cast(dict[str, Any], yaml.safe_load(f))


def tickers(version: str = "v2_120") -> list[str]:
    """Convenience: flat list of tickers for the given universe version."""
    return cast(list[str], load(version)["tickers"])


__all__ = ["load", "tickers"]
