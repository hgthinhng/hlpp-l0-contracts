# Changelog

## 0.1.7 - 2026-05-10

- **MAJOR fix (Codex):** `BrowserFetchClient` default timeout raised from 30 s → 45 s.
  Aligns with service legal maximum: `QUEUE_TIMEOUT_MS` (10 s) + `MAX_RENDER_MS` (30 s) + 5 s
  network overhead. Prevents false `BrowserFetchTimeoutError` on valid queued renders.
  Module-level constant `DEFAULT_TIMEOUT_S = 45.0` exported for callers that need to
  reference the rationale in their own code.
- **MINOR fix (Gemini):** `BrowserFetchError` base class and all subclasses now accept and
  expose a `fetch_ms: int | None` attribute. `_parse_render_response` plumbs `fetch_ms` from
  the service error envelope (SERVICE_SPEC §3) to the raised exception. Consumers can now
  observe how long the upstream attempted before failing (e.g. 30 001 ms on a 504
  RENDER_TIMEOUT). `None` when the error is transport-level (TCP timeout, connection refused).
  Backwards-compatible additive change.

## 0.1.6 - 2026-05-10

- Added `BrowserFetchClient` — sync typed client for the ht-browser-fetch L0 headless-Chromium
  rendering service (ADR-019). Includes `RenderResult`, `HealthResult`, `Cookie` dataclasses
  and a full loud-fail error hierarchy (`BrowserFetchUnavailable`, `BrowserFetchAuthError`,
  `BrowserFetchTimeoutError`, `BrowserFetchBadRequest`, `BrowserFetchUpstreamFailed`,
  `BrowserFetchPoolTimeout`, `BrowserFetchServerError`). Built-in 429 retry (3 attempts,
  base 1 s, cap 8 s). Sync-only; async client deferred to v0.1.7+.

## 0.1.5 - 2026-05-07

- Clarified ADR-016 notation, rationale, trigger-transport consequences, and Tier-A protocol
  inventory.
- Expanded `TierAStreamConsumer` and `TierAStreamSession` lifecycle docstrings and documented
  `BarData.observed_at` timezone-awareness.
- Documented collector-specific keyword passthrough for `Backfillable.backfill`.

## 0.1.4 - 2026-05-07

- Added `Backfillable`, `BackfillResult`, and `BackfillTargetYearUnavailable` protocol
  contracts for target-year backfill collectors.
- Added `TierAStreamConsumer`, `TierAStreamSession`, and `BarData` protocol contracts for
  Tier-A stream consumers.
- Added ADR-016 documenting the tiered L1→L2 trigger transport matrix.
