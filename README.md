# hlpp-l0-contracts

HLPP L0 Contracts (formerly `ht-l1-core`) is the foundational Python library for the
HLPP v1.0 pipeline — Hierarchical Lens & Performance Protocol. It provides the shared
contracts that every L1a/L1b/L2 builder, the L3a API service, and the L3b Telegram bot
import: HLPP-NORMALIZED + HLPP-COMPUTED Pydantic schemas, the versioned ticker universe,
pre-write parquet validators, git metadata helpers, plus the legacy collector / HTTP /
LLM / idempotency primitives inherited from the v0.1.x era.

> **Rename note (v0.2.0):** This package was renamed from `ht-l1-core` →
> `hlpp-l0-contracts`. The backward-compat shim (`ht_l1_core`) has been removed.

## Installation

```bash
pip install -e .
```

## Public API

### HLPP v1.0 contracts (NEW in 0.2.0)

| Module | Summary |
|---|---|
| `hlpp_l0_contracts.schemas.base` | `HlppNormalizedBase` (L1b mandatory cols) + `HlppComputedBase` (L2{a..f} lineage cols). Frozen Pydantic models, `extra="forbid"`. |
| `hlpp_l0_contracts.schemas.normalized` | Per-dataset L1b payload classes — `PriceIntraday30s`, `PriceDaily`, `ForeignFlowDaily`, `FundamentalsQuarterly`, `Ticker360` (+ TODO 6). |
| `hlpp_l0_contracts.schemas.computed` | Per-analysis L2 payload classes — `FactorSize`, `FactorMomentum_12_1m`, `FactorQuality`, `CapmBeta`, `TaIndicator`, `FaDupont3Way`, `FactorResidualMomentum`, `Peg`, `RegimeMarkovVnindex`, `SignalBlend`. |
| `hlpp_l0_contracts.universe` | `load(version)` + `tickers(version)` — versioned YAML universe loader (current `v2_120`, legacy `v1_130`). |
| `hlpp_l0_contracts.validators` | `validate_normalized(df, dataset_id=...)` + `validate_computed(df, dataset_id=..., chain_depth=..., domain=...)` — gate parquet writes; raise `SchemaValidationError`. |
| `hlpp_l0_contracts.git_meta` | `git_commit_hash()` + `git_dirty()` — auto-inject `builder_version` / `analysis_version` (avoid manual semver bumps). |

### Legacy primitives (from hlpp-l0-contracts 0.1.x)

| Module | Summary |
|---|---|
| `hlpp_l0_contracts.browser_fetch` | `BrowserFetchClient` — sync typed client for the hlpp-l0-browser L0 rendering service. Exposes `render()`, `health()`, `render_html()`, `render_json()`. Loud-fail error hierarchy; built-in 429 retry. |
| `hlpp_l0_contracts.collector.base` | `BaseCollector` abstract base with `RawArticle` rows and auto-stamped provenance/lineage/vintage fields. |
| `hlpp_l0_contracts.http` | `HttpClient` wrapper with retry on 429/5xx and `Retry-After` support. |
| `hlpp_l0_contracts.idempotency` | `sha256_url` and `idempotent_insert` for SQLite/PostgreSQL. |
| `hlpp_l0_contracts.llm.budget` | `CostBudgetGuard` with per-call and daily USD caps. |
| `hlpp_l0_contracts.llm.provider` | `AIProvider`, `AIResponse`, `AnthropicProvider`, `OpenAICompatibleProvider`, `LocalProvider`, `ProviderChain`. |
| `hlpp_l0_contracts.llm.usage` | `AIUsage` telemetry with cost estimation and SQLAlchemy persistence. |
| `hlpp_l0_contracts.schema.lineage` | `_LineageMixin` and `LineageSchema` for silver-builder lineage columns. |
| `hlpp_l0_contracts.schema.provenance` | `_BronzeProvenanceMixin` and `BronzeProvenanceSchema` for bronze ingestion provenance. |
| `hlpp_l0_contracts.schema.vintage` | `_VintageMixin` and `VintageSchema` for vintage status tracking. |
| `hlpp_l0_contracts.sources_config` | `SourceEntry`, `SourcesYaml`, and `load_sources_yaml` for `sources.yaml` validation. |

## Usage

```python
import asyncio
from hlpp_l0_contracts.collector.base import BaseCollector, RawArticle

class MyCollector(BaseCollector):
    async def _collect(self):
        return [RawArticle(title="News headline")]

rows = asyncio.run(MyCollector("my-source", "en").collect())
print(rows[0].title, rows[0].content_hash)
```
