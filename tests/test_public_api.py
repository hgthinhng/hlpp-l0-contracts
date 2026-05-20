import hlpp_l0_contracts

from hlpp_l0_contracts.browser_fetch import (
    BrowserFetchAuthError,
    BrowserFetchBadRequest,
    BrowserFetchClient,
    BrowserFetchError,
    BrowserFetchPoolTimeout,
    BrowserFetchServerError,
    BrowserFetchTimeoutError,
    BrowserFetchUnavailable,
    BrowserFetchUpstreamFailed,
    Cookie,
    HealthResult,
    RenderResult,
)
from hlpp_l0_contracts.collector.base import BaseCollector, RawArticle
from hlpp_l0_contracts.http import HttpClient
from hlpp_l0_contracts.idempotency import idempotent_insert, sha256_url
from hlpp_l0_contracts.llm.budget import BudgetExceeded, CostBudgetGuard
from hlpp_l0_contracts.llm.provider import AIProvider, AIResponse, ProviderChain
from hlpp_l0_contracts.llm.usage import AIUsage, UsageRecord
from hlpp_l0_contracts.protocols import (
    Backfillable,
    BackfillResult,
    BackfillTargetYearUnavailable,
    BarData,
    TierAStreamConsumer,
    TierAStreamSession,
)
from hlpp_l0_contracts.schema.crawler_base import (
    CRAWLER_BASE_COLUMNS,
    CrawlerBaseSchema,
    _CrawlerBaseMixin,
)
from hlpp_l0_contracts.schema.lineage import LineageSchema, _LineageMixin
from hlpp_l0_contracts.schema.provenance import BronzeProvenanceSchema, _BronzeProvenanceMixin
from hlpp_l0_contracts.schema.vintage import VintageSchema, _VintageMixin
from hlpp_l0_contracts.sources_config import SourceEntry, load_sources_yaml
from hlpp_l0_contracts.stamping import stamp_for_bronze


def test_top_level_package_reexports_public_api() -> None:
    expected_exports = {
        # browser_fetch (0.1.6)
        "BrowserFetchClient": BrowserFetchClient,
        "Cookie": Cookie,
        "RenderResult": RenderResult,
        "HealthResult": HealthResult,
        "BrowserFetchError": BrowserFetchError,
        "BrowserFetchUnavailable": BrowserFetchUnavailable,
        "BrowserFetchAuthError": BrowserFetchAuthError,
        "BrowserFetchTimeoutError": BrowserFetchTimeoutError,
        "BrowserFetchBadRequest": BrowserFetchBadRequest,
        "BrowserFetchUpstreamFailed": BrowserFetchUpstreamFailed,
        "BrowserFetchPoolTimeout": BrowserFetchPoolTimeout,
        "BrowserFetchServerError": BrowserFetchServerError,
        # collector
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
        "Backfillable": Backfillable,
        "BackfillResult": BackfillResult,
        "BackfillTargetYearUnavailable": BackfillTargetYearUnavailable,
        "BarData": BarData,
        "TierAStreamConsumer": TierAStreamConsumer,
        "TierAStreamSession": TierAStreamSession,
        "_BronzeProvenanceMixin": _BronzeProvenanceMixin,
        "BronzeProvenanceSchema": BronzeProvenanceSchema,
        "_LineageMixin": _LineageMixin,
        "LineageSchema": LineageSchema,
        "_VintageMixin": _VintageMixin,
        "VintageSchema": VintageSchema,
        "_CrawlerBaseMixin": _CrawlerBaseMixin,
        "CrawlerBaseSchema": CrawlerBaseSchema,
        "CRAWLER_BASE_COLUMNS": CRAWLER_BASE_COLUMNS,
        "load_sources_yaml": load_sources_yaml,
        "SourceEntry": SourceEntry,
        "sha256_url": sha256_url,
        "idempotent_insert": idempotent_insert,
        "stamp_for_bronze": stamp_for_bronze,
    }

    assert hlpp_l0_contracts.__all__ == list(expected_exports)
    for name, value in expected_exports.items():
        assert getattr(hlpp_l0_contracts, name) is value
