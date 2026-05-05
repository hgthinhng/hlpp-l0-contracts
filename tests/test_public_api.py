import ht_l1_core

from ht_l1_core.collector.base import BaseCollector, RawArticle
from ht_l1_core.http import HttpClient
from ht_l1_core.idempotency import idempotent_insert, sha256_url
from ht_l1_core.llm.budget import BudgetExceeded, CostBudgetGuard
from ht_l1_core.llm.provider import AIProvider, AIResponse, ProviderChain
from ht_l1_core.llm.usage import AIUsage, UsageRecord
from ht_l1_core.schema.lineage import LineageSchema, _LineageMixin
from ht_l1_core.schema.provenance import BronzeProvenanceSchema, _BronzeProvenanceMixin
from ht_l1_core.schema.vintage import VintageSchema, _VintageMixin
from ht_l1_core.sources_config import SourceEntry, load_sources_yaml


def test_top_level_package_reexports_public_api() -> None:
    expected_exports = {
        "BaseCollector": BaseCollector,
        "RawArticle": RawArticle,
        "ProviderChain": ProviderChain,
        "AIProvider": AIProvider,
        "AIResponse": AIResponse,
        "AIUsage": AIUsage,
        "UsageRecord": UsageRecord,
        "CostBudgetGuard": CostBudgetGuard,
        "BudgetExceeded": BudgetExceeded,
        "HttpClient": HttpClient,
        "_BronzeProvenanceMixin": _BronzeProvenanceMixin,
        "BronzeProvenanceSchema": BronzeProvenanceSchema,
        "_LineageMixin": _LineageMixin,
        "LineageSchema": LineageSchema,
        "_VintageMixin": _VintageMixin,
        "VintageSchema": VintageSchema,
        "load_sources_yaml": load_sources_yaml,
        "SourceEntry": SourceEntry,
        "sha256_url": sha256_url,
        "idempotent_insert": idempotent_insert,
    }

    assert ht_l1_core.__all__ == list(expected_exports)
    for name, value in expected_exports.items():
        assert getattr(ht_l1_core, name) is value
