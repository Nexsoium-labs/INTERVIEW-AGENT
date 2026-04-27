# Backend Startup Runbook

## Modes
The backend can run in two modes:

| Mode | Command | Secret source |
|------|---------|---------------|
| Development API server | `uvicorn app.main:app --reload --port 8000` | `backend/.env` or shell env |
| Desktop sidecar shape | `python run.py` | Tauri-injected environment variables from setup or Stronghold vault |

## Prerequisites
- Python 3.11+
- Project virtualenv in `backend/.venv`
- `GEMINI_API_KEY` for live Gemini calls
- `JWT_SECRET_KEY` with at least 32 bytes of entropy
- `OPERATOR_MASTER_SECRET`

## First-Time Dev Setup
```powershell
cd "C:\Users\BHARATH ANTONY\Documents\AI AGENT\INTERVIEW AGENT\backend"
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Optional full adapter install:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[full]"
```

Example `.env`:

```text
GEMINI_API_KEY=<your key>
JWT_SECRET_KEY=<32+ byte random secret>
OPERATOR_MASTER_SECRET=<operator token minting secret>
CORS_ORIGINS=["tauri://localhost","http://localhost:1420","http://127.0.0.1:1420","http://localhost:3000"]
```

## Start Backend
Development server:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Desktop sidecar-compatible smoke:

```powershell
$env:ENFORCE_SECRET_SCAN="false"
.\.venv\Scripts\python.exe run.py
```

## Health Check
```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/health
```

Expected response:

```json
{"status":"ok"}
```

## Startup Notes
- Missing `GEMINI_API_KEY` logs a warning and live model calls degrade
  gracefully.
- `ENFORCE_SECRET_SCAN=false` is expected for the PyInstaller/Tauri sidecar.
- Desktop production does not require plaintext `.env`; Tauri Stronghold stores
  secrets and passes them as sidecar environment variables.
- `CORS_ORIGINS` must be a JSON string array. A comma-separated value causes
  Pydantic settings to attempt `json.loads()` on malformed JSON and crash at
  backend initialization.

## Desktop Boot Lifecycle
First run:

1. `/setup` captures `GEMINI_API_KEY`.
2. Tauri generates `JWT_SECRET_KEY` and `OPERATOR_MASTER_SECRET`.
3. Setup stores all three secrets in Stronghold under `vault.hold` and client
   `zt-ate-secrets`.
4. Setup invokes `spawn_backend_sidecar` with in-memory credentials.
5. Rust injects secrets, `CORS_ORIGINS` as a JSON array, and
   `ENFORCE_SECRET_SCAN=false`.

Returning user:

1. `frontend/app/layout.tsx` calls `check_first_run`.
2. If first run is false, layout invokes `spawn_returning_sidecar`.
3. Rust opens Stronghold, reads `gemini_api_key`, `jwt_secret_key`, and
   `operator_master_secret`, and injects them into the sidecar environment.
4. Only after successful spawn does layout set `firstRunChecked=true`.
5. `BackendGate` then polls `GET /api/health`.

Operational log signal:

```text
[zt-backend-sidecar] spawned successfully (returning-user vault boot); credentials injected
```

This log confirms spawn success without printing secret material.

## Key Environment Variables
| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Required for live AI | Gemini API key |
| `JWT_SECRET_KEY` | Required | JWT signing secret |
| `OPERATOR_MASTER_SECRET` | Required | Secret used to mint operator tokens |
| `CORS_ORIGINS` | Recommended | Tauri and dev server origin whitelist |
| `ENFORCE_SECRET_SCAN` | Optional | Set `false` for sidecar smoke/build |
| `FLASH_MODEL` | Optional | Gemini Flash Lite route model |
| `LIVE_MODEL` | Optional | Gemini live response model |
| `PRO_MODEL` | Optional | Gemini final report model |

## Linked Notes
- [[04 - Runbooks/Desktop Packaging and Verification]]
- [[04 - Runbooks/Dev Mode Session Testing]]
- [[02 - Architecture/Gemini Tri-Model Routing]]
- [[02 - Architecture/JWT Auth and Security Model]]
