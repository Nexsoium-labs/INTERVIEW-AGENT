# Desktop Packaging and Verification

## Scope
This runbook covers ZT-ATE Sentinel Node: the Tauri 2 desktop shell, static
Next.js frontend export, and PyInstaller FastAPI backend sidecar.

## Required Local Toolchain
Windows desktop builds require:

- Rust via `rustup`
- `cargo` and `rustc` on PATH
- Visual Studio Build Tools with MSVC and Windows SDK components
- Node.js and npm
- Python virtual environment under `backend/.venv`

Current local status from Tauri CLI environment detection:

- WebView2: present
- Node/npm: present
- Rust/Cargo: missing
- MSVC Build Tools/Windows SDK: missing

## Backend Sidecar Build
```powershell
cd "C:\Users\BHARATH ANTONY\Documents\AI AGENT\INTERVIEW AGENT\backend"
.\build_backend.bat
```

Expected output:

- PyInstaller creates `dist\zt-backend-sidecar.exe`
- Build script copies it to `..\src-tauri\binaries\zt-backend-sidecar-<rust-target-triple>.exe`

The Tauri sidecar runtime sets:

- `GEMINI_API_KEY`
- `JWT_SECRET_KEY`
- `OPERATOR_MASTER_SECRET`
- `CORS_ORIGINS=["tauri://localhost", "http://localhost:1420", "http://127.0.0.1:1420"]`
- `ENFORCE_SECRET_SCAN=false`

`CORS_ORIGINS` must remain a strict JSON array string. Do not regress it to a
comma-separated list; Pydantic settings will treat the malformed value as JSON
and fail during backend import.

## Frontend Static Export
```powershell
cd "C:\Users\BHARATH ANTONY\Documents\AI AGENT\INTERVIEW AGENT\frontend"
npm install
npx tsc --noEmit
npm run build
```

Expected static routes:

- `frontend/out/candidate/index.html`
- `frontend/out/operator/index.html`
- `frontend/out/setup/index.html`

## Tauri Verification
After installing Rust and MSVC Build Tools:

```powershell
cd "C:\Users\BHARATH ANTONY\Documents\AI AGENT\INTERVIEW AGENT\src-tauri"
cargo check
```

Then:

```powershell
cd "C:\Users\BHARATH ANTONY\Documents\AI AGENT\INTERVIEW AGENT"
.\frontend\node_modules\.bin\tauri.cmd dev
```

Expected behavior:

- Frameless Tauri window opens
- `/setup` is shown on first run
- Stronghold stores the Gemini key plus generated JWT/operator secrets
- First-run setup starts the backend with `spawn_backend_sidecar`
- Returning users start the backend with `spawn_returning_sidecar`, which reads
  secrets directly from Stronghold before `BackendGate` begins polling
- Backend sidecar answers `GET http://127.0.0.1:8000/api/health`
- Main app renders after `BackendGate` completes

## Production Bundle
```powershell
cd "C:\Users\BHARATH ANTONY\Documents\AI AGENT\INTERVIEW AGENT"
.\frontend\node_modules\.bin\tauri.cmd build
```

Expected bundle location:

- `src-tauri/target/release/bundle/`

## Verification Already Completed
| Check | Result |
|-------|--------|
| Backend focused tests | Passed: `tests/test_health.py`, `tests/test_candidate_session.py` |
| Backend targeted lint | Passed |
| Backend `run.py` smoke | Passed with `ENFORCE_SECRET_SCAN=false` |
| Frontend TypeScript | Passed |
| Frontend static export | Passed |
| Frontend static export after returning-sidecar lifecycle patch | Passed on 2026-04-27 |
| Tauri environment detection | Blocked by missing Rust/Cargo and MSVC Build Tools |
| Rust compile check for `spawn_returning_sidecar` | Blocked locally: `cargo` and `rustup` unavailable on PATH |

## Linked Notes
- [[05 - Decisions/ADR-0004 Tauri 2 Desktop Conversion]]
- [[03 - Workstreams/Session API and Contracts]]
- [[03 - Workstreams/Candidate Plane UI]]
- [[03 - Workstreams/Operator Plane Console]]
