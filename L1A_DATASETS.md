# L1a Dataset IDs — FROZEN CONTRACT (do not rename)

**Status: FROZEN as of 2026-05-30.** Decided by 4-LLM round-table (Codex + Kimi + Gemini + grok, unanimous 4/4) after a self-corrupted rename script (`_purge_rename.py`) tried to flat-rename `m12-`→`l1a-` and left the ecosystem half-broken.

## The rule

The L1a raw-vendor **`dataset_id` strings use the `m12-` prefix and are an IMMUTABLE contract.**
They appear ~1700+ times across 6 repos AND as on-disk partition directory names
(`~/hlpp-data/l1a/m12/{vendor}/m12-{vendor}-{name}-v{N}/as_of_date=…/part.parquet`).

- **DO NOT rename `m12-*` dataset ids.** Not to `l1a-`, not to anything. `m12` is an opaque but stable codename for the L1a raw-capture layer. Ugly ≠ harmful.
- Evolve a dataset only by minting a **new version** (`-v2`) or a **new id** — never by in-place rename of an id that already has persisted data.
- `m12` (the dataset-id prefix / on-disk path segment) is SEPARATE from:
  - `l1a` as the **layer name** (dir `src/.../l1a/`, `~/hlpp-data/l1a/`, service `hlpp-l1a-fqx-collector`) — that IS correct, keep it.
  - `l1b_`/`l2_` **dataset names** (the silver→l1b/l2 rename) — that rename is DONE and correct, keep it.
  - `HLPP-NORMALIZED`/`HLPP-COMPUTED` **schema labels** — legit per spec.
- The architecture spec's `~/HLPP-HOT/RAW/{vendor}/{name}/v{N}/` layout (Option C) is a **separate future storage-migration project**, done via path-resolver + dual-write + versioned paths — NOT a dataset-id rename. Do not conflate.

## Source of truth

The canonical `m12-*` ids are the `SOURCE = "m12-…"` constants in the vendor adapter repos:
- `fqx-adapters/src/fqx_adapters/*.py` (e.g. `m12-fqx-ohlcv-adjusted-v1`, `m12-fqx-index-intraday-v1`)
- `vnstock-adapters/src/...` (e.g. `m12-vnstock-ohlcv-raw-v1`, `m12-vnstock-corp-actions-calendar-v1`)
- plus `m12-bctcshallow-*`, `m12-newscrawlers-*`, `m12-macrodata-*`, `m12-researchcrawlers-*`.

## Guardrails (how this stays clean)

- **No global regex rename** of a contract id across repos. Ever.
- **No self-rewriting migration script** (a script must not be in its own sweep path; commit it first).
- A drift-guard test (`tests/.../test_no_l1a_dataset_id_drift.py` in hlpp-pipelines) fails CI if any `l1a-{vendor}-…` dataset-id string reappears.
- If you ever think a rename is needed: it almost never is. Add a logical→physical registry/catalog entry instead, so the name lives in ONE place.
