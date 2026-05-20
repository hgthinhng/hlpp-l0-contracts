"""Tests for hlpp_l0_contracts.universe loader."""
from __future__ import annotations

import pytest

from hlpp_l0_contracts import universe


def test_load_v2_120_returns_expected_skeleton():
    config = universe.load("v2_120")
    assert config["version"] == "v2_120"
    assert config["total"] == 120
    assert set(config["composition"].keys()) == {
        "vn30",
        "hose_top50_ex_vn30",
        "hnx30",
        "upcom_top10",
    }
    assert config["composition"]["vn30"]["size"] == 30
    assert config["composition"]["hose_top50_ex_vn30"]["size"] == 50
    assert config["composition"]["hnx30"]["size"] == 30
    assert config["composition"]["upcom_top10"]["size"] == 10


def test_load_default_is_v2_120():
    assert universe.load() == universe.load("v2_120")


def test_tickers_returns_list():
    result = universe.tickers("v2_120")
    assert isinstance(result, list)


def test_load_unknown_version_raises():
    with pytest.raises(FileNotFoundError):
        universe.load("v999_bogus")
