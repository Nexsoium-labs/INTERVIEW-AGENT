# ADR-0004 Tauri 2 Desktop Conversion

## Status
Implemented with returning-user sidecar lifecycle patch; local Tauri compile
verification pending Rust/Cargo and MSVC Build Tools installation.

## Context
ZT-ATE is moving from a cloud-hosted SaaS shape to a local-first desktop product:
ZT-ATE Sentinel Node. The existing Next.js and FastAPI topology needs to run as a
standalone app while preserving zero-trust data boundaries, candidate/operator
plane separation, and audited backend contracts.

## Decision
Use Tauri 2 as the desktop shell, a statically exported Next.js frontend, and a
PyInstaller-built FastAPI sidecar.

Secrets are provisioned on first run through Tauri Stronghold. The user supplies
`GEMINI_API_KEY`; JWT and operator secrets are generated locally and passed to
the sidecar as environment variables. The backend remains bound to
`127.0.0.1:8000`.

Returning users do not revisit `/setup`. `frontend/app/layout.tsx` must invoke
`spawn_returning_sidecar` after `check_first_run=false` and before rendering
`BackendGate`. The Rust command opens Stronghold, reads the stored credentials,
and starts the sidecar without reflecting secrets through frontend state.

The sidecar CORS allowlist is injected as a strict JSON array string:

```text
["tauri://localhost", "http://localhost:1420", "http://127.0.0.1:1420"]
```

This is required because Pydantic settings parse list environment values as
JSON. Comma-separated CORS strings are invalid for this field.

Dynamic Next.js routes are flattened to static export-compatible routes:

- `/candidate?session=<id>`
- `/operator?session=<id>`

Candidate snapshots use `/api/sessions/{session_id}/candidate`, which strips the
biometric overlay server-side before data reaches the candidate plane.

## Consequences
- No production `.env` file is required for desktop operation.
- Next.js API route proxies are removed from the desktop path.
- Tauri Shell owns sidecar lifecycle and injects runtime secrets.
- Returning-user desktop launch is deterministic: sidecar ignition runs before
  health polling.
- Sidecar spawn logs confirm successful boot without printing secret values.
- Rust/MSVC toolchain installation is required before local Tauri compile and
  bundle verification can run on Windows.

## Implementation Evidence
- Backend focused tests passed: `tests/test_health.py` and
  `tests/test_candidate_session.py`.
- Backend targeted Ruff check passed.
- Backend `run.py` smoke passed with `ENFORCE_SECRET_SCAN=false`.
- Frontend TypeScript check passed.
- Frontend static export produced `/candidate`, `/operator`, and `/setup`.
- Frontend static export passed again on 2026-04-27 after adding
  `spawn_returning_sidecar` boot sequencing.
- Tauri environment detection found WebView2, Node, and npm, but Rust/Cargo and
  MSVC Build Tools were missing locally.
- Rust compile check for the new command remains blocked locally because
  `cargo` and `rustup` are unavailable on PATH.
