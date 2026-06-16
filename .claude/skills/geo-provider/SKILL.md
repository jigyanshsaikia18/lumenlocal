---
name: geo-provider
description: How to add a new AI-search visibility provider to LumenLocal's GEO abstraction layer (backend/app/geo/ai) — the AiSearchProvider adapter, the normalized AiVisibilityRecord output, and the always-mockable rule. Use when adding a surface like ChatGPT, Perplexity, Gemini, Grok, AI Mode/Overviews.
---

# Adding an AI-search provider
Every AI surface (PRD Module 3 / GEO) gets one adapter in `backend/app/geo/ai/` that collapses its native answer into one common record. Don't leak a provider's response shape past `normalize`.

1. **Register the surface** — add one `Provider` member (`records.py`); its value MUST equal the `geo_ai_scans.provider` enum string in `/docs/04_Database_Schema.md`. Don't invent values.
2. **Adapter** — subclass `AiSearchProvider` (`base.py`), set `provider`, implement the pure `normalize`. You get `query(prompt, *, business_name)` for free.

## Input — what we pass a provider
Only the **public prompt** (e.g. "best plumber near me"), exactly as a user would ask — never the tracked business. `business_name` is used locally in `normalize` to detect mentions.

## Output — the normalized record (don't change the shape)
`normalize(raw, *, business_name) -> AiVisibilityRecord{provider, mentioned, prominence, cited_sources}`:
- `provider` — the `Provider` enum for this surface.
- `mentioned` — did the business appear at all (GEO-1).
- `prominence` — 1-based rank (1 = most prominent); `None` when not `mentioned` or the mention is buried/unranked (GEO-4).
- `cited_sources` — ordered, deduped source URLs; captured **even when not mentioned** (GEO-5).

## Rule — always mockable, no live calls in tests
`normalize` is pure and tested directly on canned payloads (no I/O). The live call lives only in `fetch`; the base raises `NotImplementedError`, so nothing reaches a real surface before P2C-2 (wired under the Policy Compliance Engine + scanning-ToS caveat, `/docs/01_PRD.md §11.1`). Tests use `MockAiSearchProvider` (`mock.py`) or a `canned_response` — never a live call. Put `normalize` cases in `backend/tests/geo/ai/`; run `pytest`.
