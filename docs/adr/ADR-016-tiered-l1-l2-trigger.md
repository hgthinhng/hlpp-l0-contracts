## §4 ADR-016 LOCK — Tiered L1→L2 Trigger (LOAD-BEARING)

**Decision**: HTAP L1→L2 trigger transport is partitioned into 5 tiers. ht-l1-core 0.1.5 ships the protocol contracts; per-repo collectors implement the tier they belong to.

**Notation**: §4 is the Wave 5 plan section that locks the trigger-transport doctrine. P1 means operator pushback on hourly-latency polling; D1 means data-cadence diversity requires tier-specific transports. F12-A is the Wave 1 target-year backfill contract; D9 is the research-report daily-fresh route.

**Tier matrix** (canonical — copy into `ht-l1-core/docs/adr/ADR-016-tiered-l1-l2-trigger.md`):

| Tier | Routes (Wave-5 in scope) | Transport | Latency target |
|---|---|---|---|
| **A** | `m12-fqx-trading-stream-v1` (NEW Wave 5.0); `m12-fqx-bidask-stream-v1` (post-MVP) | `FiinSession.Trading_Data_Stream(tickers, callback)` → SQLite ring at `~/.local/share/htap/hot-buffer.db`; L2 polls 3–5s OR registers callback | ≤10s end-to-end (op bar), 3–5s ideal |
| **B** | derived 1m/5m bars (post-MVP) | aggregate window from tier-A buffer | ≤1 min |
| **C** | `m12-fqx-ohlcv-raw-v1`, `m12-fqx-ohlcv-adjusted-v1`, `m12-fqx-foreign-flow-v1`, `m12-fqx-market-breadth-v1`, `m12-fqx-money-flow-contribution-v1`, `m12-fqx-limit-band-v1`, `m12-fqx-freefloat-v1`, `m12-vnstock-vn30-membership-snapshot-v1`, `m12-vnstock-corp-actions-calendar-v1`, `m12-vnstock-foreign-flow-v1`, `m12-vnstock-index-ohlcv-v1`, `m12-vnstock-ohlcv-raw-v1` | watermark-pull cron 5–15 min during VN trading session, EOD final | 5–15 min in session |
| **D** | `m12-bctcshallow-financials-{general,bank,securities,insurance,fund}-v1`, `m12-vnstock-fundamental-{statements,ratios}-v1`, `m12-vnstock-macro-{cpi,gdp,fx,policy-rate}-v1`, `m12-vnstock-listing-snapshot-v1`, `m12-cross-market-yf-quotes-v1`, `m12-cross-market-yf-vix-v1`, `m12-macrodata-timeseries-v1` | watermark-pull cron daily | daily-fresh OK |
| **E** | `m12-vnstock-news-v1`, `m12-vnstock-company-news-v1`, future earnings-event feed | event bus (Redis stream / Postgres LISTEN / WebSocket) | sub-minute |

**Drivers**: P1 (operator pushback on hourly-latency polling), D1 (data-cadence diversity requires tier-specific transports).

**Alternatives considered**: universal cron 1h (rejected — D1); push-everything WebSocket (rejected — overkill for D); naive file-tail (rejected — no resume on consumer restart).

**Why chosen**:

- Tiered transport matches each source's data cadence.
- Existing `last_consumed_at` (FX-1, Wave 1) covers C/D resume without a new mechanism.
- Tier A is the only new daemon and stays single-purpose.
- SQLite ring storage gives free durability and multi-process safety for dev/MVP.

**Consequences**:

- ht-l1-core 0.1.5 ships 2 protocol families: `Backfillable` (codifies F12-A target_year honor) and `TierAStreamConsumer` + `TierAStreamSession` + `BarData` (callback payload + start/stop lifecycle).
- bctc-shallow-crawlers / vnstock-adapters / cross-market-adapters / MacroDataCrawlers all stay tier C or D. No streaming collectors needed in Wave 5.0.
- fqx-adapters gains 1 streaming collector (`realtime.py`) + 7 batch collectors stay tier C.
- L2 silver-builders in future Wave 5.x must declare which tier they consume. Tier A uses hot-buffer poll/callback; tiers C/D use watermark-pull via `last_consumed_at`. Legacy file-tail is rejected for trigger transport.
- ResearchCrawlers' D9 router stays as-is (D9 = research-report daily-fresh route; already tier D).

**Follow-ups (post-Wave-5)**:

- Tier-A buffer migration to Redis stream when multi-process consumers needed.
- Tier-E event bus implementation (deferred — NewsCrawlers FROZEN).
- Tier-B 1m/5m derived collector (downsample tier-A).

---
