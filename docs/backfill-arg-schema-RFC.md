# RFC — Backfill Arg-Schema Unification

**Status:** PROPOSED — pending operator ratification
**Date:** 2026-05-06
**Author:** HTAP Wave 3 Phase A close-out (Lane C C2)
**Related:**
- Wave 2 SHIPPED memo (`project_htap_wave2_shipped_2026-05-05.md`) — flagged Wave 3 ticket: "backfill arg-schema unification"
- L1 plan §3 / §3.5 / §3.7 — Workstreams B / V / X backfill harnesses (B9 / V17 / X-no-backfill-yet)
- `vnstock-adapters/src/vnstock_adapters/backfill.py` docstring — names this RFC ticket
- `fqx-adapters/src/fqx_adapters/backfill.py`

---

## 1. Problem

Each adapter repo ships its own `backfill.py` CLI. The CLI surface is identical for date-range-only contracts:

```
<repo>/backfill <contract> --start YYYY-MM-DD --end YYYY-MM-DD [--delay 0.5]
```

But this CLI **cannot** drive contracts that require additional per-call arguments. Every adapter ships a `collect()` method exposed through an `AdapterModule` Protocol with **zero arguments** — the date-range CLI has no way to thread per-contract args (e.g. `symbol`, `period`, `universe`) through `collect()`.

### Current coverage gap (vnstock-adapters)

`DEFAULT_ADAPTERS` registers 7 contracts (V4 / V5 / V6 / V10–V13). The remaining 7 contracts cannot be backfilled via the CLI:

| Contract | Required args |
|---|---|
| `m12-vnstock-ohlcv-raw-v1` (V2) | `symbol, start, end` |
| `m12-vnstock-index-ohlcv-v1` (V3) | `start, end` (iterate 4 indices internally) |
| `m12-vnstock-foreign-flow-v1` (V7) | `symbol, start, end` |
| `m12-vnstock-news-v1` (V8) | snapshot — fits, but not registered |
| `m12-vnstock-company-news-v1` (V9) | `symbol` |
| `m12-vnstock-fundamental-statements-v1` (V14) | `symbol, period` |
| `m12-vnstock-fundamental-ratios-v1` (V15) | `symbol, period` |

### Same gap in fqx-adapters

`CONTRACT_MODULES` registers 4 contracts (ohlcv-raw, ohlcv-adjusted, money-flow, freefloat). Per-symbol contracts (B5 foreign-flow, B6 market-breadth, B8 freefloat) and contracts requiring a universe (`['VN30','VN100','HOSE']`) cannot be threaded through the no-arg CLI.

### Cross-market-adapters

No `backfill.py` shipped yet. Need to design before X4 lands.

### Symptom

Operator wanting to backfill a date-range OHLCV pull for VIC has to write an ad-hoc script importing `vnstock_adapters.v2.ohlcv_raw` directly. Per-contract scripts proliferate, each with its own argv shape and its own date-iteration loop. No telemetry / cost / outage handling unification.

---

## 2. Goal

A single canonical contract — implementable by every m12 adapter — that lets ONE shared CLI driver back-fill ANY contract over ANY date range with the right per-contract args, while preserving:

- Hard Rule 28 boundary (vendor calls only inside the adapter module)
- ADR-003 vintage NOT NULL discipline
- ADR-005 m12 contract naming
- Per-adapter cost / rate-limit / vendor-outage policy

---

## 3. Proposed design

### 3.1 `Backfillable` Protocol (lands in `hlpp-l0-contracts`)

```python
# hlpp_l0_contracts/backfill/protocol.py
from collections.abc import Iterable
from datetime import date
from typing import Protocol, runtime_checkable

import pandas as pd
from pydantic import BaseModel


class BackfillArgSchema(BaseModel):
    """Per-contract arg shape. Each adapter declares its required + optional fields."""
    start: date
    end: date
    # subclasses add fields: symbol: str, period: Literal["quarter","year"], universe: list[str], ...


@runtime_checkable
class Backfillable(Protocol):
    """Adapter module-level surface for date-range driven backfill."""

    arg_schema: type[BackfillArgSchema]
    """Pydantic class declaring this contract's required args."""

    contract_id: str
    """Canonical m12 contract id, e.g. 'm12-vnstock-ohlcv-raw-v1'."""

    def iter_runs(self, args: BackfillArgSchema) -> Iterable[BackfillArgSchema]:
        """Decompose user-supplied args into per-run arg sets.
        Default: yield args once (single snapshot). Override to fan out by symbol / date."""
        ...

    def collect(self, args: BackfillArgSchema) -> pd.DataFrame:
        """Execute one collection run with the supplied args. Returns vintage-stamped frame."""
        ...
```

### 3.2 Per-contract arg subclasses

```python
class DateRangeArgs(BackfillArgSchema):
    """For snapshot-style contracts that just need a date window."""
    pass


class TickerDateRangeArgs(BackfillArgSchema):
    """For per-symbol OHLCV / foreign-flow / company-news."""
    symbols: list[str] = Field(default_factory=list, description="Empty = use universe")
    universe: Literal["VN30", "VN100", "HOSE", "CUSTOM"] | None = None


class TickerPeriodArgs(BackfillArgSchema):
    """For fundamental statements / ratios."""
    symbols: list[str]
    period: Literal["quarter", "year"]
```

### 3.3 Shared CLI (lands in `hlpp-l0-contracts`)

```python
# hlpp_l0_contracts/backfill/cli.py
def main(argv: list[str] | None = None) -> int:
    """Universal backfill driver. Discovers Backfillable adapters via entry points."""
    parser = build_parser()
    args = parser.parse_args(argv)
    adapter = load_adapter(args.contract)  # entry-point lookup
    typed_args = adapter.arg_schema.model_validate(args.__dict__)
    for run_args in adapter.iter_runs(typed_args):
        frame = adapter.collect(run_args)
        # write parquet, log telemetry, sleep delay, handle outage policy
```

CLI surface stays minimal at the top level (`contract, --start, --end, --delay`) and uses argparse subparsers OR Pydantic's `model_validate` to accept per-contract extras (`--symbol VIC --period quarter`).

### 3.4 Adapter package entry-points

Each adapter declares its modules in `pyproject.toml`:

```toml
[project.entry-points."hlpp_l0_contracts.backfill"]
"m12-vnstock-ohlcv-raw-v1" = "vnstock_adapters.v2.ohlcv_raw"
"m12-fqx-ohlcv-raw-v1" = "fqx_adapters.ohlcv_raw"
```

The shared CLI walks `importlib.metadata.entry_points(group="hlpp_l0_contracts.backfill")` to discover Backfillable modules — no per-repo registry duplication.

### 3.5 Vendor-outage policy unification

The shared CLI also enforces the `OK_EMPTY` / `SKIPPED` row policy (per ADR-003) so each adapter doesn't re-implement it. Adapter raises `VendorOutage(category=...)`; CLI catches + writes the SKIPPED row + sets manifest flag.

---

## 4. Migration

| Repo | Action |
|---|---|
| `hlpp-l0-contracts` | Add `backfill/` package (Protocol, ArgSchema, CLI, outage helper). Bump 0.1.3 with new module |
| `fqx-adapters` | Replace local `backfill.py` with `hlpp_l0_contracts.backfill.cli`. Each module gains `arg_schema`, `contract_id`, `iter_runs`, refactor `collect()` to take args |
| `vnstock-adapters` | Same — drop the no-arg CLI, retire `DEFAULT_ADAPTERS` registry, add entry-points. The 7 currently-uncovered contracts gain backfill support automatically |
| `cross-market-adapters` | Implement `Backfillable` for V8 / V9 / VIX. No legacy CLI to remove |

Migration order: hlpp-l0-contracts 0.1.3 first (additive — old CLI keeps working), then per-repo migration in any order. No big-bang.

### Compatibility

- Old `<repo>/backfill <contract> --start --end --delay` invocations keep working during migration: the `hlpp_l0_contracts.backfill.cli` accepts the same minimal arg set for snapshot contracts, just with `arg_schema = DateRangeArgs`.
- Tests don't break — `run_backfill(contract, start=, end=)` keyword API can be preserved as a thin wrapper.

---

## 5. Why not …

| Alternative | Rejected because |
|---|---|
| **Status quo**: per-repo CLI + ad-hoc scripts for non-trivial contracts | 7 contracts uncovered today, growing as Wave 3 lands. Each ad-hoc script reimplements date iter + outage handling |
| **Click / Typer** instead of argparse + Pydantic | One more dep; Pydantic is already pulled in via `hlpp-l0-contracts/sources_config.py` validators. argparse + Pydantic gives the same ergonomics |
| **Thrift-style schema-first** | Overkill for an internal CLI. Pydantic ArgSchema gives type-checking + JSON-schema export for free |
| **Per-adapter CLI module** (just write `backfill.py` in each repo with full per-contract args) | Bloats every repo; outage policy + telemetry diverges across repos. The point of this RFC is to centralize that |

---

## 6. Open questions for operator

1. **Q1** — entry-point discovery vs explicit registry: prefer entry-points (auto-discovery, no central list) OR keep an explicit `CONTRACT_MODULES` per adapter repo for clarity?
2. **Q2** — should `iter_runs` decomposition (1 user-run → N adapter-runs) live in the adapter or in the CLI? RFC says adapter (closer to vendor knowledge), but CLI is also viable.
3. **Q3** — backwards-compat shim window: keep the legacy `vnstock_adapters.backfill:main` in place for one minor version, OR cut over directly?
4. **Q4** — naming: `Backfillable` (this RFC) vs `BackfillAdapter` (more explicit) vs `M12BackfillProtocol` (verbose, self-documenting)?

---

## 7. Acceptance for "RFC accepted"

- Operator answers Q1–Q4 (or accepts defaults)
- This file moves to `hlpp-l0-contracts/docs/backfill-arg-schema-DESIGN.md` (status: ACCEPTED)
- Implementation ticket lands as hlpp-l0-contracts 0.1.3 milestone
- Then per-repo migrations dispatch in Wave 4 (or parallel with Wave 3 close-out if priority bumps)

---

## 8. Out of scope for this RFC

- Wave 4 silver-builder consumption of m12 parquets — separate workstream
- Vendor cost-budget guard tuning — already in `hlpp_l0_contracts.llm.budget`, integration left to CLI implementation phase
- Backfill scheduling (cron / Airflow integration) — separate handoff doc
