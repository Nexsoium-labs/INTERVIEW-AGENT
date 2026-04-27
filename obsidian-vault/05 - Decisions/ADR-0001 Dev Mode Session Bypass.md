# ADR-0001: Dev Mode Session Bypass

## Status
Accepted

## Context
UI development required stable, deterministic session payloads before the real backend (JWT auth, SQLite persistence, Gemini API) was fully wired end-to-end.

## Decision
Introduce a tightly bounded bypass in `frontend/app/api/sessions/[sessionId]/route.ts`:
- Active ONLY when `NODE_ENV === "development"`
- Active ONLY for `sessionId === "demo-session-777"`
- Returns mock `InterviewSessionSnapshot` from `buildMockSessionSnapshot()`

## Consequences
- Enables deterministic local UI testing without a running backend
- Preserves zero-trust data plane separation (candidate gets sanitized mock, operator gets full mock)
- Adds maintenance obligation: bypass must never be broadened or promoted to production

## Current Scope (verified)
- Homepage nav links correctly point to `/candidate/demo-session-777` and `/operator/demo-session-777` (fixed in Sprint 3, C-01)
- UUID validation (`SessionIdSchema`) still enforced for all non-bypass traffic
- `X-ZT-Plane` still validated even in bypass mode (`SessionPlaneSchema`)

## Risks
- Accidental shipping of bypass to production (mitigated by `NODE_ENV` guard)
- Mock data becoming stale vs real contracts (mitigated by using exact `InterviewSessionSnapshot` type)

## Verification
- `GET /api/sessions/demo-session-777` with `X-ZT-Plane: Candidate` → `telemetry_timeline: []`
- `GET /api/sessions/demo-session-777` with `X-ZT-Plane: Operator` → full 8-point timeline
- `GET /api/sessions/not-demo-session-777` → 400 (UUID validation failure)

## Linked Notes
- [[04 - Runbooks/Dev Mode Session Testing]]
- [[03 - Workstreams/Session API and Contracts]]
