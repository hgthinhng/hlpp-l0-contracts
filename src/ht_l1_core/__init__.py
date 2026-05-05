"""Public API for HT L1 Core."""

from .collector.base import BaseCollector, RawArticle
from .llm.provider import AIProvider, AIResponse, ProviderChain
from .llm.usage import AIUsage, UsageRecord
from .llm.budget import BudgetExceeded, CostBudgetGuard
from .http import HttpClient
from .schema.crawler_base import (
    CRAWLER_BASE_COLUMNS,
    CrawlerBaseSchema,
    _CrawlerBaseMixin,
)
from .schema.lineage import LineageSchema, _LineageMixin
from .schema.provenance import BronzeProvenanceSchema, _BronzeProvenanceMixin
from .schema.vintage import VintageSchema, _VintageMixin
from .sources_config import SourceEntry, load_sources_yaml
from .idempotency import idempotent_insert, sha256_url
from .stamping import stamp_for_bronze

__all__ = [
    "BaseCollector",
    "RawArticle",
    "ProviderChain",
    "AIProvider",
    "AIResponse",
    "AIUsage",
    "UsageRecord",
    "CostBudgetGuard",
    "BudgetExceeded",
    "HttpClient",
    "_BronzeProvenanceMixin",
    "BronzeProvenanceSchema",
    "_LineageMixin",
    "LineageSchema",
    "_VintageMixin",
    "VintageSchema",
    "_CrawlerBaseMixin",
    "CrawlerBaseSchema",
    "CRAWLER_BASE_COLUMNS",
    "load_sources_yaml",
    "SourceEntry",
    "sha256_url",
    "idempotent_insert",
    "stamp_for_bronze",
]
