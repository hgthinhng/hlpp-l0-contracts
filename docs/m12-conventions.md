# M12 Cross-Contract Conventions

This document records the universal rules every `m12-*` contract must follow,
extracted from the M12 Brain Layer A survey across the HTAP repositories on
2026-05-06. Use it as a checklist when designing a new M12 contract.

## Inventory Snapshot

Layer A inventoried 32 hosted M12 contract identifiers:

| Repository | Hosted contracts | Base surface observed |
|---|---:|---|
| `fqx-adapters` | 7 | `stamp_for_bronze()` bronze/vintage columns plus vendor payload passthrough |
| `vnstock-adapters` | 14 | `stamp_for_bronze()` bronze/vintage columns plus vendor payload passthrough |
| `cross-market-adapters` | 2 | `stamp_for_bronze()` bronze/vintage columns plus yfinance payload passthrough |
| `NewsCrawlers` | 2 | one `CrawlerBaseSchema` Pandera contract, one Arrow catalyst contract |
| `MacroDataCrawlers` | 1 | `CrawlerBaseSchema` Pandera contract |
| `ResearchCrawlers` | 1 | `CrawlerBaseSchema` Pandera contract |
| `bctc-shallow-crawlers` | 5 | `CrawlerBaseSchema` Pandera contracts |

The survey also found consumed external M12 IDs in readers and source registries.
Those are not counted as hosted contracts unless the repository owns the schema
or producer source for the identifier.

## Naming Convention

M12 contract IDs follow ADR-005:

```text
m12-{vendor_slug}-{capability}-v{N}
```

- `vendor_slug`: lowercase, hyphens allowed, no underscores. Examples:
  `researchcrawlers`, `bctcshallow`, `fqx`, `cross-market`.
- `capability`: short noun phrase describing the data shape. Examples:
  `reports`, `timeseries`, `financials-bank`, `ohlcv-raw`.
- `version`: integer starting at `1`; increment on breaking schema changes.

## Base Columns

`CrawlerBaseSchema` contributes these 20 columns. New CrawlerBase-backed
contracts must keep these names, order, dtypes, and nullability byte-identical
unless ht-l1-core intentionally releases a breaking schema change.

| # | Name | Type | Nullable | Semantics |
|---|---|---|---|---|
| 1 | `source` | string | no | Static contract source identifier written with the row. |
| 2 | `source_fetched_at` | datetime | no | UTC timestamp when the upstream source was fetched. |
| 3 | `ingested_at` | datetime | no | UTC timestamp when the row entered bronze. |
| 4 | `content_hash` | string | no | SHA-256 digest of the source payload row. |
| 5 | `vintage` | datetime | no | Revision vintage used by point-in-time consumers. |
| 6 | `as_of_date` | date | no | Data's point-in-time as-of date, not fetch time by default. |
| 7 | `status` | string | no | One of `OK`, `DEGRADED`, or `SKIPPED`. |
| 8 | `skip_reason` | string | yes | Reason a row was skipped. |
| 9 | `error_category` | string | yes | Machine-readable degradation or skip class. |
| 10 | `revision_count` | integer | no | Number of known revisions for this logical row. |
| 11 | `last_consumed_at` | datetime | yes | Downstream consumption marker for FX-1 style tracking. |
| 12 | `run_id` | string | no | Collector or writer run identifier. |
| 13 | `code_sha` | string | no | 40-character lowercase git SHA for producing code. |
| 14 | `inputs_hash` | string | no | Hash of source inputs used by the run. |
| 15 | `computed_at` | datetime | no | UTC timestamp when derived fields were computed. |
| 16 | `tos_status` | string | yes | Terms-of-service status at collection time. |
| 17 | `robots_status` | string | yes | robots.txt or crawl-permission status. |
| 18 | `tos_citation_required` | string | yes | Attribution or citation requirement from source policy. |
| 19 | `disabled_reason` | string | yes | Reason collection is disabled, if any. |
| 20 | `llm_extraction_risk` | string | yes | Risk marker for LLM-assisted extraction or summarization. |

`stamp_for_bronze()` currently stamps the first 11 bronze/vintage columns only.
Layer A documented existing Wave 2 adapter contracts as observed passthrough
surfaces. New contracts should prefer `CrawlerBaseSchema`; migrating Wave 2
passthrough adapters to 20 columns is a Layer C readiness item.

## Universal Invariants

1. `vintage` is not null on every row.
2. `source` is a static literal at write time and must equal the contract ID.
3. `as_of_date` is the data's point-in-time as-of date; it must not be confused
   with fetch time when the source exposes a real observation date.
4. `code_sha`, when present, is a 40-character lowercase git SHA, not a package
   version string.
5. `ticker` or `symbol`, when present, must use the upstream instrument code
   expected by that vendor and should be normalizable to HoSE/HNX/UPCoM or the
   relevant market namespace.
6. `status` must be one of `OK`, `DEGRADED`, or `SKIPPED`.
7. `content_hash` must hash the source payload before provenance and lineage
   columns are added.
8. Contract IDs are stable. Breaking changes require a version bump to
   `v{N+1}`, not a silent payload change under the same ID.

## Per-Capability Conventions

### OHLCV And Quote Contracts

OHLCV and quote contracts should expose observation time plus open, high, low,
close, and volume when the upstream provides them. Adjusted and raw prices must
use separate contract IDs.

### Flow And Breadth Contracts

Foreign-flow, market-breadth, money-flow, and free-float contracts should keep
vendor metric names unless a normalization layer owns the translation. Units
must be recorded in the per-contract doc because vendors mix shares, values,
ratios, and index contributions.

### News And Catalyst Contracts

Article-like contracts must preserve title, URL, publication timestamp, source
name or source ID, summary, and language. Derived event/catalyst contracts must
document their rule engine and distinguish publication time from event date.

### Macro Timeseries Contracts

Macro contracts must distinguish `period` or `report_time` from fetch time.
`frequency`, `region`, and `indicator` should be explicit whenever the hosted
contract owns a normalized schema.

### Research Report Contracts

Research contracts must separate source classification, content shape,
canonicality, language, report identity, publication time, and URL/PDF location.
Training-corpus flags are intentionally outside
`m12-researchcrawlers-reports-v1` per ResearchCrawlers ADR-006.

### Financial Statement Contracts

Financial statement contracts must include entity identity, period,
`period_end_date`, `report_type`, and `accounting_framework`. Industry-specific
metrics may be nullable to preserve partial disclosure; key identity fields must
not be nullable.

## Cross-Repo Schema Diff Requirement

The 20 base columns from `CrawlerBaseSchema` must be byte-identical across all
CrawlerBase-backed contracts. Drift in name, order, dtype, or nullability is a
Critic-gate blocker.

Layer A also records an observed pre-Layer-C drift: Wave 2 DataFrame adapters in
`fqx-adapters`, `vnstock-adapters`, and `cross-market-adapters` currently expose
only the 11 `stamp_for_bronze()` base columns and pass through vendor payloads
without a static Pandera payload schema. Do not copy this pattern for new
contracts without explicitly documenting the passthrough contract boundary.

## Schema Docstring Format

Every hosted M12 contract must have `docs/schema/{contract_id}.md` in its host
repository. The document must include:

- vendor slug, capability, version, and source-of-truth file;
- overview of the data shape and intended L2 consumers;
- column table with name, type, nullability, description, unit, derivation, and
  cross-reference;
- invariants;
- producer class, function, or writer;
- known consumers;
- schema evolution log;
- related ADRs or `TBD post-MVP`.

This is M12 Layer A: design-time documentation. Runtime deduplication and CI
schema validation are separate Layer B and Layer C work.

## Backlog Items

1. ht-l1-core 0.1.3 should make `_code_sha()` loud-fail instead of falling back
   to package metadata when no git SHA or `HT_CODE_SHA` is available.
2. Layer C should add a CI validator that compares every `CrawlerBaseSchema`
   base-column sequence against ht-l1-core.
3. Wave 2 adapter contracts should either gain explicit payload schemas or keep
   the passthrough boundary documented in their per-contract docs.
4. The NewsCrawlers catalyst Arrow schema should be evaluated for migration to a
   Pandera CrawlerBase-backed M12 contract if it becomes a bronze contract rather
   than a processor output.
