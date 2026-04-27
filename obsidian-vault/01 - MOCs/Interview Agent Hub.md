# Interview Agent Hub
> Map of Content: start here for every session.

## Mission
Ship and operate the Zero-Trust Autonomous Talent Ecosystem (ZT-ATE) with
deterministic routing, strict contracts, auditable outcomes, and local-first
desktop deployment through ZT-ATE Sentinel Node.

## Current Sprint Status
| Sprint | Topic | Status |
|--------|-------|--------|
| 1 | Security and DB Hardening (JWT, CORS, SQL injection) | Complete |
| 2 | EEOC Compliance and Pydantic Stability | Complete |
| 3 | UI/UX Reactivity and Timer Logic | Complete |
| 4 | Tri-Model Gemini API Integration (Swarm Brain) | Complete |
| 5 | BiometricSentinel WebRTC Component | Complete |
| 6 | Tauri Desktop Conversion | Implemented with returning-user sidecar patch; Rust/MSVC local verification pending |
| 7 | Sentinel Node Production Hardening | Complete |

## Architecture
- [[02 - Architecture/ZT-ATE System Architecture]]
- [[02 - Architecture/Zero-Trust Planes and Data Boundaries]]
- [[02 - Architecture/Gemini Tri-Model Routing]]
- [[02 - Architecture/JWT Auth and Security Model]]

## Workstreams
- [[03 - Workstreams/Candidate Plane UI]]
- [[03 - Workstreams/Operator Plane Console]]
- [[03 - Workstreams/Session API and Contracts]]
- [[03 - Workstreams/Biometric Sentinel]]
- [[03 - Workstreams/Glass-Box Evaluator]]

## Operations
- [[04 - Runbooks/Backend Startup]]
- [[04 - Runbooks/Desktop Packaging and Verification]]
- [[04 - Runbooks/Dev Mode Session Testing]]
- [[05 - Decisions/ADR-0001 Dev Mode Session Bypass]]
- [[05 - Decisions/ADR-0002 JWT Auth Strategy]]
- [[05 - Decisions/ADR-0003 Gemini Model Tier Routing]]
- [[05 - Decisions/ADR-0004 Tauri 2 Desktop Conversion]]

## Templates
- [[06 - Templates/Session Note Template]]
- [[06 - Templates/Decision Template]]

## Key File Paths
| Layer | Path |
|-------|------|
| Backend root | `backend/app/` |
| Backend config | `backend/app/config.py` |
| Backend contracts | `backend/app/contracts.py` |
| Backend auth | `backend/app/security/auth.py` |
| Backend routes | `backend/app/api/routes.py` |
| Backend sidecar entrypoint | `backend/run.py` |
| Backend PyInstaller spec | `backend/zt_ate_backend.spec` |
| Frontend root | `frontend/app/` |
| Candidate page | `frontend/app/(interview)/candidate/page.tsx` |
| Operator page | `frontend/app/(interview)/operator/page.tsx` |
| First-run setup page | `frontend/app/setup/page.tsx` |
| API client | `frontend/lib/api.ts` |
| Tauri shell | `src-tauri/` |
| Tauri commands | `src-tauri/src/commands.rs` |
| Tauri config | `src-tauri/tauri.conf.json` |

## Current Verification Ledger
| Check | Result |
|-------|--------|
| Backend health and candidate endpoint tests | Passed: 5 tests |
| Backend targeted Ruff check | Passed |
| Backend sidecar entrypoint smoke | Passed with `ENFORCE_SECRET_SCAN=false` |
| Frontend TypeScript | Passed |
| Frontend static export | Passed; generated `/candidate`, `/operator`, `/setup` |
| Frontend static export after sidecar lifecycle patch | Passed on 2026-04-27 |
| Tauri compile check | Blocked: Rust/Cargo and MSVC Build Tools missing locally |
