# ZT-ATE System Architecture

## Core Principles
- Deterministic orchestration with explicit LangGraph state transitions.
- Strict typed contracts at every boundary through Pydantic v2 models.
- Candidate telemetry isolation by backend-enforced plane policy.
- Observable and auditable decision pathways through glass-box reports.
- Local-first desktop operation through ZT-ATE Sentinel Node.

## Stack
| Layer | Technology |
|-------|------------|
| Desktop shell | Tauri 2 |
| Frontend | Next.js 15 static export, React 19 |
| Backend | FastAPI + uvicorn sidecar |
| Backend packaging | PyInstaller |
| Secret storage | Tauri Stronghold |
| Orchestration | LangGraph |
| Database | aiosqlite / SQLite |
| AI models | Google Gemini Flash Lite / Flash / Pro |
| Auth | PyJWT HS256, with RS256/JWKS migration path reserved |
| Styling | Tailwind CSS |

## Runtime Topology
```text
Tauri 2 shell
  -> serves frontend/out through Tauri asset protocol
  -> opens frameless app window
  -> manages Stronghold vault
  -> spawns zt-backend-sidecar with env-injected secrets
     -> first run: credentials passed from /setup
     -> returning user: credentials loaded from Stronghold by Rust command

Next.js static frontend
  -> /setup
  -> /candidate?session=<id>
  -> /operator?session=<id>
  -> direct calls to http://127.0.0.1:8000/api

FastAPI sidecar
  -> deterministic session API
  -> LangGraph orchestration
  -> telemetry overlay segregation
  -> SQLite persistence
```

## Major Planes
| Plane | Role | Auth |
|-------|------|------|
| Candidate | Assessment workspace, live response, BiometricSentinel | `verify_token`; candidate JWT bound to session |
| Operator | Technical scoring dashboard and telemetry overlay | `require_operator` |
| Session API | Zero-trust gatekeeper, sanitizer, event ingest | JWT on all routes except health and token issue |

## Critical Paths
1. First run: `/setup` captures `GEMINI_API_KEY`, generates JWT/operator secrets, stores secrets in Stronghold.
2. First-run setup invokes `spawn_backend_sidecar` and injects secrets through environment variables.
3. Returning app launch invokes `spawn_returning_sidecar`; Rust reads Stronghold and injects the same sidecar environment without exposing secrets to React state.
4. Rust injects `CORS_ORIGINS` as a JSON array string so Pydantic settings can parse it deterministically.
5. Frontend `BackendGate` polls `GET /api/health` only after sidecar ignition succeeds.
6. Operator mints token through `POST /api/auth/issue-token`.
7. Operator creates a session through `POST /api/sessions`; backend returns a candidate JWT.
8. Candidate route calls `GET /api/sessions/{id}/candidate`; backend strips biometric overlay fields.
9. Operator route calls `GET /api/sessions/{id}`; operator JWT can receive full overlay.
10. BiometricSentinel posts aggregate telemetry to `POST /api/sessions/{id}/events`.
11. Finalization calls `POST /api/sessions/{id}/finalize` and produces a `GlassBoxReport`.

## Gemini Tri-Model Swarm Brain
```text
Event ingest
  -> GoogleADKService.route_event()       Gemini Flash Lite L0 triage
  -> LiveInterfaceService.respond()       Gemini Flash live response
  -> GlassBoxEvaluator.synthesize()       Gemini Pro final report synthesis
```

## Packaging Boundary
Production desktop deployments do not require a plaintext `.env` file. Secrets
flow from Stronghold to Tauri commands to the sidecar environment. The desktop
sidecar CORS allowlist is injected as strict JSON, not as a comma-separated
string.

## Linked Notes
- [[02 - Architecture/Zero-Trust Planes and Data Boundaries]]
- [[02 - Architecture/Gemini Tri-Model Routing]]
- [[02 - Architecture/JWT Auth and Security Model]]
- [[03 - Workstreams/Session API and Contracts]]
- [[04 - Runbooks/Desktop Packaging and Verification]]
