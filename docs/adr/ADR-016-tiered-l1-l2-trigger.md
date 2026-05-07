## §4 ADR-016 LOCK — Tiered L1→L2 Trigger (LOAD-BEARING)

**Decision**: HTAP L1→L2 trigger transport is partitioned into 5 tiers. ht-l1-core 0.1.4 ships the protocol contracts; per-repo collectors implement the tier they belong to.

**Tier matrix** (canonical — copy into `ht-l1-core/docs/adr/ADR-016-tiered-l1-l2-trigger.md`):

| Tier | Routes (Wave-5 in scope) | Transport | Latency target |
|---|---|---|---|
| **A** | `m12-fqx-trading-stream-v1` (NEW Wave 5.0); `m12-fqx-bidask-stream-v1` (post-MVP) | `FiinSession.Trading_Data_Stream(tickers, callback)` → SQLite ring at `~/.local/share/htap/hot-buffer.db`; L2 polls 3–5s OR registers callback | ≤10s end-to-end (op bar), 3–5s ideal |
| **B** | derived 1m/5m bars (post-MVP) | aggregate window from tier-A buffer | ≤1 min |
| **C** | `m12-fqx-ohlcv-raw-v1`, `m12-fqx-ohlcv-adjusted-v1`, `m12-fqx-foreign-flow-v1`, `m12-fqx-market-breadth-v1`, `m12-fqx-money-flow-contribution-v1`, `m12-fqx-limit-band-v1`, `m12-fqx-freefloat-v1`, `m12-vnstock-vn30-membership-snapshot-v1`, `m12-vnstock-corp-actions-calendar-v1`, `m12-vnstock-foreign-flow-v1`, `m12-vnstock-index-ohlcv-v1`, `m12-vnstock-ohlcv-raw-v1` | watermark-pull cron 5–15 min during VN trading session, EOD final | 5–15 min in session |
| **D** | `m12-bctcshallow-financials-{general,bank,securities,insurance,fund}-v1`, `m12-vnstock-fundamental-{statements,ratios}-v1`, `m12-vnstock-macro-{cpi,gdp,fx,policy-rate}-v1`, `m12-vnstock-listing-snapshot-v1`, `m12-cross-market-yf-quotes-v1`, `m12-cross-market-yf-vix-v1`, `m12-macrodata-timeseries-v1` | watermark-pull cron daily | daily-fresh OK |
| **E** | `m12-vnstock-news-v1`, `m12-vnstock-company-news-v1`, future earnings-event feed | event bus (Redis stream / Postgres LISTEN / WebSocket) | sub-minute |

**Drivers**: P1, D1.

**Alternatives considered**: universal cron 1h (rejected — D1); push-everything WebSocket (rejected — overkill for D); naive file-tail (rejected — no resume on consumer restart).

**Why chosen**: tiered transport matches data cadence; reuses existing `last_consumed_at` (FX-1, Wave 1) for C/D resume; tier A is the only new daemon (single-purpose); SQLite ring gives free durability + multi-process safety for dev/MVP.

**Consequences**:

- ht-l1-core 0.1.4 ships 2 new protocols: `Backfillable` (codifies F12-A target_year honor) and `TierAStreamConsumer` (callback signature + start/stop lifecycle).
- bctc-shallow-crawlers / vnstock-adapters / cross-market-adapters / MacroDataCrawlers all stay tier C or D. No streaming collectors needed in Wave 5.0.
- fqx-adapters gains 1 streaming collector (`realtime.py`) + 7 batch collectors stay tier C.
- L2 silver-builders in future Wave 5.x must declare which tier they consume (impacts m12 read pattern: file-tail vs hot-buffer-poll).
- ResearchCrawlers' D9 router stays as-is (already tier D — research reports daily-fresh).

**Follow-ups (post-Wave-5)**:

- Tier-A buffer migration to Redis stream when multi-process consumers needed.
- Tier-E event bus implementation (deferred — NewsCrawlers FROZEN).
- Tier-B 1m/5m derived collector (downsample tier-A).

---
