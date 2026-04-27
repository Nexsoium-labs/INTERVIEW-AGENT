# Glass-Box Evaluator

## File
`backend/app/services/evaluator.py`

## Purpose
Gemini Pro wrapper around `ReportService`. Produces the final `GlassBoxReport` — the operator-only neuro-symbolic audit document. Called exclusively on session finalization.

## Trigger Points
1. `POST /finalize` → `orchestrator.finalize_session()` → `orchestrator.build_glass_box_report()` → `evaluator.synthesize()`
2. `GET /glass-box` → `orchestrator.build_glass_box_report()` → `evaluator.synthesize()`

## Architecture
```
GlassBoxEvaluator.synthesize()
    │
    ├─ Step 1: ReportService.build_report()   ← always runs, always succeeds
    │          (deterministic, no LLM)
    │          → base GlassBoxReport with templated consensus_summary
    │
    └─ Step 2: _call_gemini_pro()             ← best-effort enrichment
               asyncio.wait_for(timeout=45s)
               on success → base_report.model_copy(update={"consensus_summary": pro_narrative})
               on failure → base_report returned unchanged
```

## Duck-Typing Design
`GlassBoxEvaluator.build_report()` is an alias for `synthesize()`. This lets `GlassBoxEvaluator` be passed as `report_service` to `InterviewOrchestrator` with zero orchestrator changes.

## Gemini Pro Prompt Inputs
| Field | Source | EEOC Safe? |
|-------|--------|-----------|
| Technical score, recommendation, verdict | `TechnicalScorePlane` | ✅ |
| Task outcomes (title, status, summary, failed_actions) | `TechnicalTaskOutcome` | ✅ |
| Rubric scores (label, score, rationale) | `TechnicalRubricScore` | ✅ |
| Evidence artifacts (type + label only) | `TechnicalTaskArtifact` | ✅ |
| Overlay aggregate (counts, latest BPM/stress) | `TelemetryOverlayPlane` | ✅ operator-only |
| Operator review flags | `TelemetryOverlayPlane` | ✅ operator-only |
| Trace count | `len(traces)` | ✅ |

> Pro prompt explicitly instructs model: biometric signals DID NOT influence technical verdict.

## GlassBoxReport Contract
Key fields from `contracts.py`:
```python
session_id: str
locked_technical_verdict: TechnicalVerdict
technical_rubric_scores: list[TechnicalRubricScore]
technical_task_outcomes: list[TechnicalTaskOutcome]
evidence_references: list[str]
telemetry_overlay_summary: TelemetryOverlaySummary
operator_review_segments: list[OperatorReviewSegment]
explicit_biometric_exclusion_statement: str   ← always set
consensus_summary: str                         ← enriched by Pro (or deterministic fallback)
reasoning_map: dict                            ← from AgnoToolService.execute_neuro_symbolic_map()
candidate_safe_summary: str                    ← sanitized via GuardrailService
human_approval_required: bool
```

## Graceful Degradation
- Pro timeout (45s): returns deterministic report unchanged
- Pro rate limit / safety block / network error: returns deterministic report unchanged
- `google-generativeai` not installed: logs error, returns deterministic report unchanged

## Current Status
- [x] `evaluator.py` created and wired in `main.py`
- [x] `GlassBoxEvaluator` passed as `report_service` to `InterviewOrchestrator`
- [x] `ensure_configured()` called at lifespan startup
- [x] `google-generativeai>=0.8.0` in `pyproject.toml`

## Linked Notes
- [[02 - Architecture/Gemini Tri-Model Routing]]
- [[03 - Workstreams/Session API and Contracts]]
- [[02 - Architecture/Zero-Trust Planes and Data Boundaries]]
