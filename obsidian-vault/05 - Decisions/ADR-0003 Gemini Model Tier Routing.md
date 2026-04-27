# ADR-0003: Gemini Model Tier Routing

## Status
Accepted

## Context
The system required three distinct AI call patterns with very different latency, cost, and reasoning-depth requirements. A single model would either be too slow/expensive for high-frequency triage or too shallow for final report synthesis.

## Decision
Three-tier Gemini routing — each tier maps to one service:

| Tier | Model | Service | Call Frequency | Timeout |
|------|-------|---------|---------------|---------|
| Flash Lite | `gemini-2.5-flash-lite` | `adk_router.py` | Every event (high) | 8s |
| Flash | `gemini-2.5-flash` | `live_interface.py` | Every candidate message | 12s |
| Pro | `gemini-2.5-pro` | `evaluator.py` | Once per session finalization | 45s |

## Rationale

**Flash Lite for L0 triage:** O(1) vs O(n) classification is a simple JSON output task. Temperature 0.05 for near-deterministic routing. Falls back to rule-based routing if Flash Lite fails — session never blocked.

**Flash for live conversation:** Empathetic dialogue requires higher temperature (0.70) and natural response length. Sliding window context (`ConversationBuffer`, 80k char budget) maintains 45-minute interview coherence.

**Pro for Glass-Box synthesis:** Final report needs deep reasoning over full session state. Low temperature (0.15) for analytical consistency. Large output (8192 tokens). One-time cost per session is acceptable.

## Centralized Configuration
- Single SDK init in `genai_config.py` with `ensure_configured()` called at lifespan startup
- `@lru_cache(maxsize=1)` on each model factory — one object per process, no redundant SDK calls
- All model IDs overridable via `.env` — no code change needed to swap model versions
- Safety settings: `BLOCK_ONLY_HIGH` for technical content (security/exploit discussion is a legitimate interview topic)

## Consequences
- Flash Lite failures are cheap (deterministic fallback always available)
- Flash failures return `_DEGRADATION_RESPONSE` + background retry (candidate never blocked)
- Pro failures return deterministic base report (session outcome never blocked by LLM)
- `google-generativeai>=0.8.0` added to `pyproject.toml` core dependencies

## Linked Notes
- [[02 - Architecture/Gemini Tri-Model Routing]]
- [[03 - Workstreams/Glass-Box Evaluator]]
