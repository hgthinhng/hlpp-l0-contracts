# ht-l1-core

HT L1 Core is the foundational Python library for HTAP pipeline stage 1. It provides
resilient data collectors with automatic bronze provenance stamping, LLM provider
abstractions with budget guards and usage telemetry, idempotent database helpers,
and reusable SQLAlchemy/Pandera schema mixins for lineage and vintage tracking.

## Installation

```bash
pip install -e .
```

## Public API

| Module | Summary |
|---|---|
| `ht_l1_core.browser_fetch` | `BrowserFetchClient` — sync typed client for the ht-browser-fetch L0 rendering service. Exposes `render()`, `health()`, `render_html()`, `render_json()`. Loud-fail error hierarchy; built-in 429 retry. |
| `ht_l1_core.collector.base` | `BaseCollector` abstract base with `RawArticle` rows and auto-stamped provenance/lineage/vintage fields. |
| `ht_l1_core.http` | `HttpClient` wrapper with retry on 429/5xx and `Retry-After` support. |
| `ht_l1_core.idempotency` | `sha256_url` and `idempotent_insert` for SQLite/PostgreSQL. |
| `ht_l1_core.llm.budget` | `CostBudgetGuard` with per-call and daily USD caps. |
| `ht_l1_core.llm.provider` | `AIProvider`, `AIResponse`, `AnthropicProvider`, `OpenAICompatibleProvider`, `LocalProvider`, `ProviderChain`. |
| `ht_l1_core.llm.usage` | `AIUsage` telemetry with cost estimation and SQLAlchemy persistence. |
| `ht_l1_core.schema.lineage` | `_LineageMixin` and `LineageSchema` for silver-builder lineage columns. |
| `ht_l1_core.schema.provenance` | `_BronzeProvenanceMixin` and `BronzeProvenanceSchema` for bronze ingestion provenance. |
| `ht_l1_core.schema.vintage` | `_VintageMixin` and `VintageSchema` for vintage status tracking. |
| `ht_l1_core.sources_config` | `SourceEntry`, `SourcesYaml`, and `load_sources_yaml` for `sources.yaml` validation. |

## Usage

```python
import asyncio
from ht_l1_core.collector.base import BaseCollector, RawArticle

class MyCollector(BaseCollector):
    async def _collect(self):
        return [RawArticle(title="News headline")]

rows = asyncio.run(MyCollector("my-source", "en").collect())
print(rows[0].title, rows[0].content_hash)
```
