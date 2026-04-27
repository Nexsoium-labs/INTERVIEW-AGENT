# ZT-ATE Interview Agent Backend

Deterministic FastAPI orchestration backend for the interview agent web app.

## What Changed

- Technical scoring and telemetry overlay now run as two explicit evaluation planes.
- Automated technical verdicts are produced only from objective evidence artifacts.
- Biometrics and operator telemetry remain visible as a separate overlay and are explicitly excluded from automated scoring.
- Consent capture, replayable milestone snapshots, overlay retrieval, artifact retrieval, and audit export endpoints are available.
- The legacy static dashboard has been retired in favor of a separate Next.js frontend in `../frontend`.

## Deterministic Lifecycle

Each event traverses this LangGraph lifecycle:

`session_init -> consent_and_disclosure_gate -> l0_router -> identity_gate -> scenario_selection -> simulation_execution -> technical_assessment -> telemetry_overlay_generation -> operator_review_queue -> memory -> snapshot_milestone`

## Evidence And Verdict Policy

Technical scoring uses only:

- command log
- diff or patch
- hidden test results
- health checks
- sandbox event stream
- final system state

Every glass-box report declares that telemetry overlay signals were excluded from automated technical scoring.

## Core API Endpoints

- `POST /api/sessions`
- `GET /api/sessions/{session_id}`
- `POST /api/sessions/{session_id}/consent`
- `POST /api/sessions/{session_id}/events`
- `GET /api/sessions/{session_id}/artifacts`
- `GET /api/sessions/{session_id}/overlay`
- `GET /api/sessions/{session_id}/review-segments`
- `GET /api/sessions/{session_id}/milestones`
- `GET /api/sessions/{session_id}/audit-export`
- `POST /api/sessions/{session_id}/finalize`
- `POST /api/sessions/{session_id}/human-review`
- `GET /api/sessions/{session_id}/glass-box`
- `GET /api/sessions/{session_id}/observability`

## Run

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

The backend root now returns a simple status payload. Start the Next.js client from `../frontend` separately.
