# Session API and Contracts

## Backend Routes
File: `backend/app/api/routes.py`

All paths are served under `/api`.

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/health` | Public | Sidecar readiness probe |
| POST | `/auth/issue-token` | Public + operator secret | Mint operator JWT |
| POST | `/sessions` | Operator only | Create session and return candidate JWT |
| GET | `/sessions/{id}` | Verified | Full session snapshot |
| GET | `/sessions/{id}/candidate` | Verified | EEOC-safe candidate snapshot |
| POST | `/sessions/{id}/events` | Verified | Ingest candidate event or telemetry |
| POST | `/sessions/{id}/live-response` | Verified | Live Gemini response |
| POST | `/sessions/{id}/consent` | Verified | Record candidate consent |
| GET | `/sessions/{id}/overlay` | Operator only | Full telemetry overlay |
| GET | `/sessions/{id}/glass-box` | Operator only | Glass-box report |
| POST | `/sessions/{id}/finalize` | Operator only | Lock technical plane and synthesize report |
| POST | `/sessions/{id}/human-review` | Operator only | Record human adjudication |
| GET | `/sessions/{id}/audit-export` | Operator only | Full audit export |
| WS | `/sessions/{id}/ws?token=...` | Verified | Session event stream |

## Desktop Frontend Contract
Next.js API route proxies are removed for the desktop build.

| Frontend path | Backend call |
|---------------|--------------|
| `/candidate?session=<id>` | `GET /api/sessions/{id}/candidate` |
| `/operator?session=<id>` | `GET /api/sessions/{id}` |
| `BiometricSentinel` | `POST /api/sessions/{id}/events` |
| `BackendGate` | `GET /api/health` |

Tokens are read from:

- Candidate: `localStorage("zt_candidate_token")`
- Operator: `localStorage("zt_operator_token")`

## Key Contracts
File: `backend/app/contracts.py`

| Contract | Purpose |
|----------|---------|
| `CandidateEvent` | Inbound event with `TelemetryPacket` |
| `EventIngestRequest` | API body for event ingestion |
| `L0RouteDecision` | Deterministic ADK routing output |
| `InterviewSessionSnapshot` | Full session state |
| `TechnicalScorePlane` | Objective technical scoring state |
| `TelemetryOverlayPlane` | Biometric overlay, excluded from automated scoring |
| `GlassBoxReport` | Final audit report |
| `LiveConversationRequest` / `LiveConversationResponse` | Candidate live response API |
| `SessionCreateResponse` | Session snapshot plus candidate JWT |

## Candidate Sanitization
`sanitize_for_candidate(snapshot)` returns a deep-copied snapshot with biometric
overlay fields zeroed:

- `overlay_enabled=false`
- `collection_mode=disabled`
- telemetry timelines and review segments cleared
- latest stress and heart-rate values set to null
- `excluded_from_automated_scoring=true`

Candidate tokens are JWT-bound to a specific session through
`https://zt-ate.com/session_id`; cross-session candidate access returns HTTP 403.
Operator tokens bypass the session binding check.

## Strict Contracts
All contracts extend `StrictBaseModel`:

```python
model_config = ConfigDict(extra="forbid", validate_assignment=True, str_strip_whitespace=True)
```

Unknown fields are rejected and assignment validation prevents silent corruption.

## EEOC Guardrail
`TechnicalScoringInput` rejects biometric fields before technical scoring:

- `heart_rate_bpm`
- `stress_index`
- `rppg_confidence`
- `raw_vector_hash`
- `telemetry`
- `biometric_vector`
- `biometric_signal`

## Linked Notes
- [[02 - Architecture/JWT Auth and Security Model]]
- [[02 - Architecture/Zero-Trust Planes and Data Boundaries]]
- [[05 - Decisions/ADR-0004 Tauri 2 Desktop Conversion]]
