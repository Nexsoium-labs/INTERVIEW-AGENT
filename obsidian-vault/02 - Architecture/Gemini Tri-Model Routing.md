# Gemini Tri-Model Routing

## Model Tier Map
| Tier | Model ID (config default) | Service | Temperature | Purpose |
|------|--------------------------|---------|-------------|---------|
| Flash Lite | `gemini-2.5-flash-lite` | `adk_router.py` | 0.05 | L0 intent classification — O(1) vs O(n) |
| Flash | `gemini-2.5-flash` | `live_interface.py` | 0.70 | Live empathetic conversational interface |
| Pro | `gemini-2.5-pro` | `evaluator.py` | 0.15 | Glass-Box report synthesis (on finalize only) |

> All model IDs are overridable via `.env` (`FLASH_MODEL`, `LIVE_MODEL`, `PRO_MODEL`).

## SDK Initialization
- Single source of truth: `backend/app/services/genai_config.py`
- `ensure_configured()` called at FastAPI lifespan startup — fail-fast if `GEMINI_API_KEY` missing
- Each model factory uses `@lru_cache(maxsize=1)` — one model object per process
- Safety settings: `BLOCK_ONLY_HIGH` for harassment/hate/dangerous; `BLOCK_MEDIUM_AND_ABOVE` for sexually explicit

## L0 Triage Pipeline (GoogleADKService)
```
route_event(event)
  1. _check_silence()        → drop if silence_ms ≥ 10 000ms and no semantic text
  2. _check_injection()      → escalate to PRO if prompt injection detected
  3. _route_event_remote()   → optional external ADK router (if ADK_ROUTER_URL set)
  4. _classify_with_flash_lite()  → Flash Lite JSON: {complexity, intent, confidence}
       O(1) + confidence ≥ 0.60  → FLASH_LITE lane ("candidate_safe")
       O(n) or CODE_DELTA        → PRO lane ("deep_analysis")
       ambiguous                 → FLASH_LITE lane (cheaper/safer default)
  5. _deterministic_fallback()   → rule-based (used when Flash Lite fails)
```

## Live Interface Sliding Window
- `ConversationBuffer` class — FIFO eviction by character count
- Budget: `settings.live_context_max_chars = 80_000` chars (~20k tokens)
- Each call: rehydrates chat from rolling history buffer; `model.start_chat(history=buf.history)`
- Timeout: `asyncio.wait_for(timeout=12.0)` hard ceiling
- On failure: returns `_DEGRADATION_RESPONSE`, fires `_retry_in_background()` (5s backoff)

## Glass-Box Evaluator (Pro)
- Triggered exclusively on session finalization (`POST /finalize`)
- Step 1: Deterministic `ReportService.build_report()` — always succeeds
- Step 2: Gemini Pro enriches `consensus_summary` with neuro-symbolic narrative
- Step 3: On Pro failure → returns deterministic base report unchanged
- Pro timeout: 45 seconds
- EEOC: Pro prompt includes overlay aggregate (operator-only) but explicitly states biometrics ≠ technical verdict

## Graceful Degradation Chain
```
Flash Lite fails → deterministic fallback routing
Flash (live) fails → "Temporary Cognitive Sync Delay" + background retry
Pro fails → deterministic consensus_summary preserved
```

## Environment Variables
```
GEMINI_API_KEY=<required>
FLASH_MODEL=gemini-2.5-flash-lite
LIVE_MODEL=gemini-2.5-flash
PRO_MODEL=gemini-2.5-pro
LIVE_CONTEXT_MAX_CHARS=80000
ADK_TIMEOUT_SECONDS=8.0
ADK_ROUTER_URL=          # optional external router
ADK_API_KEY=             # optional
```

## Linked Notes
- [[02 - Architecture/ZT-ATE System Architecture]]
- [[03 - Workstreams/Glass-Box Evaluator]]
- [[05 - Decisions/ADR-0003 Gemini Model Tier Routing]]
