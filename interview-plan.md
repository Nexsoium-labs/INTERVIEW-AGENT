# ZT-ATE Sentinel Node — Tauri Desktop Conversion Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the ZT-ATE Next.js + FastAPI web app into a standalone cross-platform desktop app ("ZT-ATE Sentinel Node") using Tauri 2, a statically-exported Next.js frontend, and a PyInstaller-compiled Python sidecar.

**Architecture:** The Tauri 2 shell serves a statically-exported Next.js frontend from `frontend/out/` via its built-in asset protocol. A `zt-backend-sidecar` binary (PyInstaller-compiled FastAPI) is spawned as a child process on launch with secrets passed as environment variables. Secrets are stored in Tauri Stronghold; on first run the user enters their GEMINI_API_KEY and JWT/operator secrets are auto-generated. Dynamic routes `[sessionId]` are flattened to query params (`?session=...`) — all page fetches become client-side calls to `http://127.0.0.1:8000`.

**Tech Stack:** Tauri 2, Rust (`tauri-plugin-shell`, `tauri-plugin-stronghold`), Next.js 15 static export, PyInstaller 6, React 19 Client Components, `@tauri-apps/api` v2, `@tauri-apps/plugin-stronghold` v2

---

## Context

The project is pivoting from cloud SaaS to a local-first desktop product targeting education and mid-market tech (ZT-ATE Sentinel Node). This eliminates the cloud hosting dependency and allows zero-configuration deployment. The existing Next.js + FastAPI stack must be adapted: the Next.js BFF proxy layer (API routes) must be removed, dynamic routes flattened, all Server Components converted to Client Components, and the Python backend compiled into a sidecar binary managed by Tauri's shell plugin.

## Critical Findings from Codebase Exploration

1. `GET /health` **already exists** in `routes.py` — no need to add it
2. `GET /sessions/{id}` is currently `verify_token` (not operator-only) — need a `/candidate` sub-endpoint for EEOC-safe access
3. `config.py` line 8 uses `Path(__file__).resolve().parents[1]` at module level — **will break under PyInstaller** (fix required in Task 1)
4. `typedRoutes: true` in `next.config.ts` is **incompatible with `output: 'export'`** — must be removed
5. `BiometricSentinel.tsx` POSTs to `/api/telemetry/ingest` (relative, Next.js proxy) — must become direct backend call
6. No `src-tauri/` exists anywhere — Tauri has not been initialized

---

## File Map

### Create (new)
| Path | Purpose |
|------|---------|
| `backend/run.py` | PyInstaller entry point (`uvicorn.run`) |
| `backend/zt_ate_backend.spec` | PyInstaller spec (hidden imports, datas, one-file EXE) |
| `backend/build_backend.sh` | Unix build script (PyInstaller → `src-tauri/binaries/`) |
| `backend/build_backend.bat` | Windows build script |
| `src-tauri/tauri.conf.json` | Tauri 2 app config (externalBin, frameless window, CSP) |
| `src-tauri/Cargo.toml` | Rust workspace manifest (tauri-plugin-shell, stronghold) |
| `src-tauri/build.rs` | Tauri codegen build script |
| `src-tauri/src/main.rs` | Thin wrapper calling `lib::run()` |
| `src-tauri/src/lib.rs` | Tauri app builder (setup, sidecar spawn, plugin init) |
| `src-tauri/src/commands.rs` | `generate_secrets`, `spawn_backend_sidecar`, `check_first_run` |
| `src-tauri/capabilities/default.json` | Tauri 2 capability permissions |
| `src-tauri/binaries/.gitkeep` | Placeholder for compiled sidecar binaries |
| `frontend/app/(interview)/candidate/page.tsx` | Flattened candidate page (Client Component, `?session=`) |
| `frontend/app/(interview)/operator/page.tsx` | Flattened operator page (Client Component, `?session=`) |
| `frontend/app/setup/page.tsx` | First-run setup: GEMINI_API_KEY entry + Stronghold provisioning |
| `frontend/lib/hooks/useBackendReady.ts` | Polls `GET /api/health` every 500ms until 200 OK |
| `frontend/components/BackendGate.tsx` | Startup splash — wraps app, shows spinner until backend ready |
| `frontend/components/TitleBar.tsx` | Frameless window controls (drag region + minimize/maximize/close) |

### Modify
| Path | Change |
|------|--------|
| `backend/app/config.py` | Fix `_BACKEND_DIR` for PyInstaller frozen mode; update `cors_origins` defaults to Tauri origins |
| `backend/app/api/routes.py` | Add `GET /sessions/{id}/candidate` endpoint (`verify_token`, EEOC-safe) |
| `backend/app/contracts.py` | Add `sanitize_for_candidate(snapshot)` function |
| `backend/app/main.py` | Gate `SecretScannerService` behind `not sys.frozen` |
| `frontend/next.config.ts` | Add `output: 'export'`, `trailingSlash: true`, `distDir: 'out'`, `images.unoptimized: true`; remove `typedRoutes` |
| `frontend/package.json` | Add `@tauri-apps/api`, `@tauri-apps/plugin-stronghold`, `@tauri-apps/plugin-shell`; add `@tauri-apps/cli` dev dep; add tauri scripts |
| `frontend/lib/api.ts` | Hardcode `BACKEND_BASE = "http://127.0.0.1:8000"`, add `getCandidateSession()`, add `ingestTelemetry()` |
| `frontend/app/(interview)/candidate/_components/BiometricSentinel.tsx` | Replace `/api/telemetry/ingest` proxy call with `ingestTelemetry()` from `lib/api.ts` |
| `frontend/app/layout.tsx` | Convert to Client Component; add `BackendGate`, `TitleBar`, first-run routing |

### Delete
| Path | Reason |
|------|--------|
| `frontend/app/api/sessions/[sessionId]/route.ts` | BFF proxy replaced by `/sessions/{id}/candidate` backend endpoint |
| `frontend/app/api/telemetry/ingest/route.ts` | BiometricSentinel now calls backend directly |
| `frontend/app/(interview)/candidate/[sessionId]/page.tsx` | Replaced by flat `candidate/page.tsx` |
| `frontend/app/(interview)/operator/[sessionId]/page.tsx` | Replaced by flat `operator/page.tsx` |

---

## Task 1: Backend — Fix `config.py` for PyInstaller + Add EEOC Candidate Endpoint

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/contracts.py`
- Modify: `backend/app/api/routes.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_health.py`
- Create: `backend/tests/test_candidate_session.py`

- [ ] **Step 1: Write failing tests**

`backend/tests/test_health.py`:
```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_health_returns_200():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

@pytest.mark.asyncio
async def test_health_no_auth_required():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/health", headers={})
    assert r.status_code == 200
```

`backend/tests/test_candidate_session.py`:
```python
import pytest
from unittest.mock import AsyncMock
from httpx import AsyncClient, ASGITransport
from app.main import app

FAKE_SID = "00000000-0000-0000-0000-000000000001"
OTHER_SID = "00000000-0000-0000-0000-000000000002"

@pytest.mark.asyncio
async def test_candidate_endpoint_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(f"/api/sessions/{FAKE_SID}/candidate")
    assert r.status_code in (401, 403)

@pytest.mark.asyncio
async def test_candidate_token_bound_to_wrong_session_rejected():
    from app.security.auth import mint_candidate_token
    token = mint_candidate_token(FAKE_SID)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(
            f"/api/sessions/{OTHER_SID}/candidate",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 403
    assert "not bound to this session" in r.json()["detail"].lower()

@pytest.mark.asyncio
async def test_overlay_zeroed_for_candidate(monkeypatch):
    from app.security.auth import mint_candidate_token
    from app.contracts import InterviewSessionSnapshot, TelemetryOverlayPlane, TechnicalScorePlane
    overlay = TelemetryOverlayPlane(
        overlay_enabled=True, collection_mode="active",
        telemetry_timeline=[], stress_markers=[], overlay_segments=[],
        operator_review_flags=["spike"], review_segments=[],
        latest_stress_index=0.9, latest_heart_rate_bpm=110,
        overlay_processing_lag_ms=50, excluded_from_automated_scoring=False,
    )
    technical = TechnicalScorePlane(
        scenario_id="s", technical_score=80, technical_verdict=None,
        task_outcomes=[], rubric_scores=[], evidence_bundle=[],
        contamination_check_passed=True, locked=False,
    )
    snap = InterviewSessionSnapshot(
        session_id=FAKE_SID, candidate_id="c", candidate_role="Eng",
        language="en", scenario_id="s", technical=technical, overlay=overlay,
        session_status="active", simulation_status="assessment_live",
        event_count=0, last_route_target=None, report_available=False,
        human_decision=None, consent_record=None, completed_at_utc=None,
        last_updated_utc="2024-01-01T00:00:00Z", trace_events=[], milestone_count=0,
    )
    app.state.orchestrator = AsyncMock()
    app.state.orchestrator.get_session = AsyncMock(return_value=snap)
    token = mint_candidate_token(FAKE_SID)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(
            f"/api/sessions/{FAKE_SID}/candidate",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["overlay"]["overlay_enabled"] is False
    assert body["overlay"]["latest_heart_rate_bpm"] is None
    assert body["overlay"]["operator_review_flags"] == []
    assert body["overlay"]["excluded_from_automated_scoring"] is True
```

- [ ] **Step 2: Run tests — verify they FAIL**
```bash
cd "C:\Users\BHARATH ANTONY\Documents\AI AGENT\INTERVIEW AGENT\backend"
pytest tests/test_health.py tests/test_candidate_session.py -v
# Expected: test_health passes (endpoint exists), candidate tests FAIL (endpoint missing)
```

- [ ] **Step 3: Fix `config.py` for frozen mode**

Replace lines 8–9 and the `_BACKEND_DIR`/`_REPO_DIR` block in `backend/app/config.py`:
```python
from __future__ import annotations
import sys
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

if getattr(sys, "frozen", False):
    _BACKEND_DIR = Path(sys.executable).parent
    _BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", str(_BACKEND_DIR)))
    if str(_BUNDLE_DIR) not in sys.path:
        sys.path.insert(0, str(_BUNDLE_DIR))
else:
    _BACKEND_DIR = Path(__file__).resolve().parents[1]
    _BUNDLE_DIR = _BACKEND_DIR

_REPO_DIR = _BACKEND_DIR.parent
```

Also update the `cors_origins` default:
```python
cors_origins: list[str] = Field(
    default_factory=lambda: [
        "tauri://localhost",
        "http://localhost:1420",
        "http://127.0.0.1:1420",
        "http://localhost:3000",   # kept for dev server compatibility
    ]
)
```

- [ ] **Step 4: Gate `SecretScannerService` in `main.py`**

In `backend/app/main.py`, wrap the secret scan in lifespan:
```python
if settings.enforce_secret_scan and not getattr(sys, "frozen", False):
    SecretScannerService(Path(__file__).resolve().parents[1]).enforce_clean_startup()
```
Add `import sys` at the top of `main.py` if not already present.

- [ ] **Step 5: Add `sanitize_for_candidate()` to `contracts.py`**

Append to the bottom of `backend/app/contracts.py`:
```python
def sanitize_for_candidate(snapshot: "InterviewSessionSnapshot") -> "InterviewSessionSnapshot":
    """
    EEOC firewall — strips all biometric overlay fields before the snapshot
    is returned to the candidate plane.
    Python equivalent of sanitizeForCandidate() that previously lived in
    the deleted Next.js BFF proxy (app/api/sessions/[sessionId]/route.ts).
    """
    from copy import deepcopy
    safe = deepcopy(snapshot)
    safe.overlay.overlay_enabled = False
    safe.overlay.collection_mode = "disabled"
    safe.overlay.telemetry_timeline = []
    safe.overlay.stress_markers = []
    safe.overlay.overlay_segments = []
    safe.overlay.operator_review_flags = []
    safe.overlay.review_segments = []
    safe.overlay.latest_stress_index = None
    safe.overlay.latest_heart_rate_bpm = None
    safe.overlay.overlay_processing_lag_ms = 0
    safe.overlay.excluded_from_automated_scoring = True
    return safe
```

- [ ] **Step 6: Add candidate endpoint to `routes.py`**

In `backend/app/api/routes.py`, add this endpoint after the existing `get_session` handler:
```python
from app.contracts import sanitize_for_candidate

@router.get(
    "/sessions/{session_id}/candidate",
    response_model=InterviewSessionSnapshot,
    summary="[CANDIDATE] EEOC-safe session snapshot.",
)
async def get_candidate_session(
    request: Request,
    session_id: str,
    claims: Annotated[dict, Depends(verify_token)],
) -> InterviewSessionSnapshot:
    """Returns sanitized InterviewSessionSnapshot. Biometric overlay fields zeroed.

    Candidate tokens are JWT-bound to a specific session_id.
    Cross-session access is rejected with HTTP 403.
    Operator tokens bypass the session_id check.
    """
    from app.security.auth import SESSION_CLAIM
    roles = claims.get("https://zt-ate.com/roles", [])
    is_operator = "operator" in roles

    if not is_operator:
        token_session_id = claims.get(SESSION_CLAIM)
        if token_session_id != session_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Candidate token is not bound to this session.",
            )

    orchestrator = request.app.state.orchestrator
    try:
        snapshot = await orchestrator.get_session(session_id)
    except KeyError as err:
        raise HTTPException(status_code=404, detail="session not found") from err

    return sanitize_for_candidate(snapshot)
```

- [ ] **Step 7: Run tests — verify all pass**
```bash
cd "C:\Users\BHARATH ANTONY\Documents\AI AGENT\INTERVIEW AGENT\backend"
pytest tests/test_health.py tests/test_candidate_session.py -v
# Expected:
# test_health_returns_200 PASSED
# test_health_no_auth_required PASSED
# test_candidate_endpoint_requires_auth PASSED
# test_candidate_token_bound_to_wrong_session_rejected PASSED
# test_overlay_zeroed_for_candidate PASSED
```

- [ ] **Step 8: Commit**
```bash
git add backend/app/config.py backend/app/contracts.py backend/app/api/routes.py backend/app/main.py backend/tests/test_health.py backend/tests/test_candidate_session.py
git commit -m "feat(backend): frozen-mode path fix, candidate-safe session endpoint, EEOC sanitize_for_candidate, gate secret scanner"
```

---

## Task 2: Backend — PyInstaller Entry Point and Build Scripts

**Files:**
- Create: `backend/run.py`
- Create: `backend/zt_ate_backend.spec`
- Create: `backend/build_backend.sh`
- Create: `backend/build_backend.bat`

- [ ] **Step 1: Create `backend/run.py`**

```python
"""
ZT-ATE Backend — PyInstaller entry point.
Run as: python run.py  (dev) or as compiled zt-backend-sidecar (Tauri)
"""
import os
import sys

if getattr(sys, "frozen", False):
    _bundle_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    if _bundle_dir not in sys.path:
        sys.path.insert(0, _bundle_dir)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        log_level="info",
        access_log=False,
        loop="asyncio",   # avoids uvloop/winloop dep issues on Windows
    )
```

- [ ] **Step 2: Verify entry point works**
```bash
cd "C:\Users\BHARATH ANTONY\Documents\AI AGENT\INTERVIEW AGENT\backend"
python run.py &
sleep 2
curl http://127.0.0.1:8000/api/health
# Expected: {"status": "ok", ...}
kill %1
```

- [ ] **Step 3: Create `backend/zt_ate_backend.spec`**

```python
# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for zt-backend-sidecar.
# Usage: cd backend && pyinstaller zt_ate_backend.spec
# Output: dist/zt-backend-sidecar[.exe]
# After building: copy to src-tauri/binaries/zt-backend-sidecar-<triple>[.exe]
#   Get triple: rustc -Vv | grep host | cut -f2 -d' '

from PyInstaller.utils.hooks import collect_all

(ga_d, ga_b, ga_h) = collect_all("google.generativeai")
(fa_d, fa_b, fa_h) = collect_all("fastapi")
(pd_d, pd_b, pd_h) = collect_all("pydantic")
(ps_d, ps_b, ps_h) = collect_all("pydantic_settings")
(lg_d, lg_b, lg_h) = collect_all("langgraph")
(db_d, db_b, db_h) = collect_all("aiosqlite")

HIDDEN = [
    # uvicorn (runtime protocol discovery)
    "uvicorn.logging", "uvicorn.loops", "uvicorn.loops.auto", "uvicorn.loops.asyncio",
    "uvicorn.protocols.http", "uvicorn.protocols.http.auto", "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets", "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan", "uvicorn.lifespan.on", "uvicorn.lifespan.off",
    # google-generativeai
    "google.generativeai", "google.generativeai.types",
    "google.generativeai.types.content_types", "google.generativeai.types.generation_types",
    "google.auth", "google.auth.credentials", "google.auth.transport.requests",
    "google.api_core", "google.api_core.exceptions",
    # langgraph internals
    "langgraph.graph", "langgraph.checkpoint", "langgraph.checkpoint.memory",
    # pydantic v1 compat shim
    "pydantic.v1",
    # JWT
    "cryptography", "cryptography.hazmat.primitives.asymmetric",
    # starlette
    "starlette.routing", "starlette.middleware", "starlette.middleware.cors",
    "starlette.responses", "starlette.websockets",
    # misc
    "orjson", "aiofiles",
    # app package (all services)
    "app", "app.main", "app.config", "app.contracts", "app.orchestrator", "app.graph",
    "app.security", "app.security.auth", "app.api", "app.api.routes",
    "app.services", "app.services.genai_config", "app.services.adk_router",
    "app.services.live_interface", "app.services.evaluator", "app.services.storage",
    "app.services.telemetry_overlay", "app.services.technical_scoring",
    "app.services.memory", "app.services.guardrails", "app.services.observability",
    "app.services.reporting", "app.services.stream_hub", "app.services.a2a",
    "app.services.agent_registry", "app.services.agno_tools",
    "app.services.crewai_orchestrator", "app.services.secret_scanner",
] + ga_h + fa_h + pd_h + ps_h + lg_h + db_h

DATAS = ga_d + fa_d + pd_d + ps_d + lg_d + db_d + [("app", "app")]
BINARIES = ga_b + fa_b + pd_b + ps_b + lg_b + db_b

a = Analysis(
    ["run.py"],
    pathex=["."],
    binaries=BINARIES,
    datas=DATAS,
    hiddenimports=HIDDEN,
    hookspath=[],
    excludes=["torch", "tensorflow", "numpy", "scipy", "matplotlib", "PIL", "cv2",
               "pytest", "pytest_asyncio", "httpx", "IPython", "jupyter"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name="zt-backend-sidecar",
    debug=False, strip=False, upx=False,
    console=True,   # keep True — Tauri reads stderr for crash diagnostics
    runtime_tmpdir=None,
)
```

- [ ] **Step 4: Create `backend/build_backend.sh`**

```bash
#!/usr/bin/env bash
# Build script for macOS and Linux.
# Usage: cd backend && ./build_backend.sh
set -euo pipefail

echo "==> Detecting Rust target triple..."
TRIPLE=$(rustc -Vv | grep host | cut -f2 -d' ')
echo "    Target: ${TRIPLE}"

echo "==> Cleaning previous artifacts..."
rm -rf dist/ build/

echo "==> Installing PyInstaller and dependencies..."
pip install pyinstaller
pip install -e ".[full]"

echo "==> Building sidecar binary..."
pyinstaller zt_ate_backend.spec

echo "==> Smoke-testing binary..."
./dist/zt-backend-sidecar &
BG_PID=$!
for i in $(seq 1 10); do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/api/health || echo "000")
    [ "$STATUS" = "200" ] && break
    sleep 1
done
kill $BG_PID 2>/dev/null; wait $BG_PID 2>/dev/null || true
[ "$STATUS" != "200" ] && { echo "ERROR: health check failed (HTTP ${STATUS})"; exit 1; }
echo "    Health check passed."

echo "==> Copying to Tauri binaries..."
DEST="../src-tauri/binaries/zt-backend-sidecar-${TRIPLE}"
cp dist/zt-backend-sidecar "${DEST}"
chmod +x "${DEST}"
echo "    Written: ${DEST}"
echo ""
echo "Done. Run 'cargo tauri build' from the project root."
```
```bash
chmod +x backend/build_backend.sh
```

- [ ] **Step 5: Create `backend/build_backend.bat`**

```batch
@echo off
setlocal enabledelayedexpansion

echo =^> Detecting Rust target triple...
for /f "tokens=2" %%i in ('rustc -Vv ^| findstr /c:"host"') do set TRIPLE=%%i
echo     Target: %TRIPLE%

echo =^> Cleaning previous artifacts...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

echo =^> Installing PyInstaller and dependencies...
pip install pyinstaller
pip install -e ".[full]"

echo =^> Building sidecar binary...
pyinstaller zt_ate_backend.spec
if %ERRORLEVEL% neq 0 ( echo ERROR: PyInstaller failed. & exit /b 1 )

echo =^> Copying to Tauri binaries...
set DEST=..\src-tauri\binaries\zt-backend-sidecar-%TRIPLE%.exe
copy dist\zt-backend-sidecar.exe "%DEST%"
if %ERRORLEVEL% neq 0 ( echo ERROR: Copy failed. & exit /b 1 )
echo     Written: %DEST%

echo.
echo Done. Run 'cargo tauri build' from the project root.
```

- [ ] **Step 6: Commit**
```bash
git add backend/run.py backend/zt_ate_backend.spec backend/build_backend.sh backend/build_backend.bat
git commit -m "feat(backend): PyInstaller entry point, spec file, cross-platform build scripts"
```

---

## Task 3: Frontend — Static Export Config and Dependencies

**Files:**
- Modify: `frontend/next.config.ts`
- Modify: `frontend/package.json`

- [ ] **Step 1: Update `next.config.ts`**

```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",        // Tauri static bundle
  trailingSlash: true,     // /candidate/ → candidate/index.html
  distDir: "out",          // Tauri frontendDist points here
  images: {
    unoptimized: true,     // next/image server optimization unavailable in static mode
  },
  // typedRoutes removed — incompatible with output: 'export'
};

export default nextConfig;
```

- [ ] **Step 2: Update `package.json`**

Add deps and tauri scripts:
```json
{
  "name": "zt-ate-frontend",
  "version": "0.2.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "tauri": "tauri",
    "tauri:dev": "tauri dev",
    "tauri:build": "tauri build"
  },
  "dependencies": {
    "@tailwindcss/postcss": "^4.2.4",
    "@tauri-apps/api": "^2.5.0",
    "@tauri-apps/plugin-stronghold": "^2.2.0",
    "@tauri-apps/plugin-shell": "^2.2.0",
    "lucide-react": "^1.9.0",
    "next": "15.1.6",
    "react": "19.0.0",
    "react-dom": "19.0.0",
    "zod": "^4.3.6"
  },
  "devDependencies": {
    "@tauri-apps/cli": "^2.5.0",
    "@types/node": "22.10.5",
    "@types/react": "19.0.2",
    "@types/react-dom": "19.0.2",
    "autoprefixer": "^10.5.0",
    "postcss": "^8.5.10",
    "tailwindcss": "^4.2.4",
    "typescript": "5.7.2"
  }
}
```

- [ ] **Step 3: Install deps**
```bash
cd "C:\Users\BHARATH ANTONY\Documents\AI AGENT\INTERVIEW AGENT\frontend"
npm install
```

- [ ] **Step 4: Commit**
```bash
git add frontend/next.config.ts frontend/package.json frontend/package-lock.json
git commit -m "feat(frontend): enable Next.js static export for Tauri desktop, add Tauri v2 npm deps"
```

---

## Task 4: Frontend — Delete BFF Proxies and Dynamic Routes; Update API Client

**Files:**
- Delete: `frontend/app/api/sessions/[sessionId]/route.ts`
- Delete: `frontend/app/api/telemetry/ingest/route.ts`
- Delete: `frontend/app/(interview)/candidate/[sessionId]/page.tsx`
- Delete: `frontend/app/(interview)/operator/[sessionId]/page.tsx`
- Modify: `frontend/lib/api.ts`

- [ ] **Step 1: Delete the four incompatible files**
```bash
cd "C:\Users\BHARATH ANTONY\Documents\AI AGENT\INTERVIEW AGENT\frontend"
rm app/api/sessions/\[sessionId\]/route.ts
rmdir app/api/sessions/\[sessionId\]
rmdir app/api/sessions
rmdir app/api/telemetry/ingest/route.ts  # remove the route file
rm "app/api/telemetry/ingest/route.ts"
rm "app/(interview)/candidate/[sessionId]/page.tsx"
rmdir "app/(interview)/candidate/[sessionId]"
rm "app/(interview)/operator/[sessionId]/page.tsx"
rmdir "app/(interview)/operator/[sessionId]"
```
Use file manager or PowerShell `Remove-Item -Recurse` if bash path escaping is difficult on Windows.

- [ ] **Step 2: Rewrite `frontend/lib/api.ts`**

```typescript
/**
 * lib/api.ts — Backend API client (Tauri Sentinel Node edition)
 * Hardcoded to http://127.0.0.1:8000 — the sidecar always binds here.
 * NEVER use NEXT_PUBLIC_BACKEND_URL (embeds as undefined in static export).
 */
import type {
  GlassBoxReport,
  InterviewSessionSnapshot,
  TelemetryOverlayPlane,
} from "@/lib/types";

export const BACKEND_BASE = "http://127.0.0.1:8000";
const API_BASE = `${BACKEND_BASE}/api`;

async function fetchJson<T>(
  path: string,
  init?: RequestInit & { token?: string | null }
): Promise<T> {
  const { token, ...rest } = init ?? {};
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(rest.headers as Record<string, string> ?? {}),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}${path}`, { ...rest, headers, cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

/** Full snapshot — OPERATOR ONLY */
export async function getSession(sessionId: string, token: string): Promise<InterviewSessionSnapshot> {
  return fetchJson(`/sessions/${sessionId}`, { token });
}

export async function getOverlay(sessionId: string, token: string): Promise<TelemetryOverlayPlane> {
  return fetchJson(`/sessions/${sessionId}/overlay`, { token });
}

export async function getReport(sessionId: string, token: string): Promise<GlassBoxReport | null> {
  try { return await fetchJson(`/sessions/${sessionId}/glass-box`, { token }); }
  catch { return null; }
}

/**
 * EEOC-sanitized snapshot — CANDIDATE PLANE.
 * Uses /sessions/{id}/candidate — biometric overlay fields are zeroed server-side.
 * Never substitute with getSession() in candidate-facing code.
 */
export async function getCandidateSession(
  sessionId: string,
  token: string | null
): Promise<InterviewSessionSnapshot> {
  return fetchJson(`/sessions/${sessionId}/candidate`, { token });
}

/**
 * Direct telemetry ingest — replaces deleted /api/telemetry/ingest proxy.
 * Gracefully swallows errors — telemetry failure never blocks the interview.
 */
export async function ingestTelemetry(
  sessionId: string,
  payload: {
    event_type: string;
    telemetry: { heart_rate_bpm: number; rppg_confidence: number; silence_ms: number };
    raw_payload: Record<string, unknown>;
  },
  token: string | null
): Promise<void> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  try {
    await fetch(`${API_BASE}/sessions/${encodeURIComponent(sessionId)}/events`, {
      method: "POST", headers, body: JSON.stringify(payload),
      keepalive: true, signal: AbortSignal.timeout(4_000),
    });
  } catch { /* graceful degradation */ }
}
```

- [ ] **Step 3: Update `BiometricSentinel.tsx` telemetry call**

Add import at top of `BiometricSentinel.tsx`:
```typescript
import { ingestTelemetry } from "@/lib/api";
```

Replace the `transmitTelemetry` function body (the section that calls `/api/telemetry/ingest`):
```typescript
const transmitTelemetry = useCallback(async () => {
  const jwt = resolveToken();
  const rgb = rgbSignalRef.current;
  const currentBpm = bpmRef.current;
  const rppgConfidence = Math.round((0.5 + Math.min(rgb.variance / 30, 0.45)) * 100) / 100;
  try {
    await ingestTelemetry(
      sessionId,
      {
        event_type: "webcam_frame",
        telemetry: {
          heart_rate_bpm: Math.min(220, Math.max(30, Math.round(currentBpm))),
          rppg_confidence: rppgConfidence,
          silence_ms: 0,
        },
        raw_payload: {
          rgb_variance: { r: rgb.r, g: rgb.g, b: rgb.b, sigma: rgb.variance },
          source: "rppg_sentinel_v1",
          timestamp_utc: new Date().toISOString(),
        },
      },
      jwt
    );
    setTransmitStatus("ok");
    setTxCount((n) => n + 1);
  } catch {
    setTransmitStatus("error");
  }
}, [sessionId, resolveToken]);
```

- [ ] **Step 4: Type-check**
```bash
cd "C:\Users\BHARATH ANTONY\Documents\AI AGENT\INTERVIEW AGENT\frontend"
npx tsc --noEmit
# Expected: 0 errors
```

- [ ] **Step 5: Commit**
```bash
git add frontend/lib/api.ts "frontend/app/(interview)/candidate/_components/BiometricSentinel.tsx"
git commit -m "feat(frontend): replace BFF proxy with direct backend calls, EEOC-safe getCandidateSession, ingestTelemetry direct"
```

---

## Task 5: Frontend — New Client Component Pages (Flattened Routes)

**Files:**
- Create: `frontend/app/(interview)/candidate/page.tsx`
- Create: `frontend/app/(interview)/operator/page.tsx`

- [ ] **Step 1: Create `frontend/app/(interview)/candidate/page.tsx`**

```typescript
"use client";
/**
 * Candidate Session Page — static export / Tauri edition
 * Session ID comes from ?session= query param (not URL segment).
 * Fetches from Python backend directly via getCandidateSession() (EEOC-safe).
 */
import { useSearchParams } from "next/navigation";
import { useEffect, useState, Suspense } from "react";
import type { InterviewSessionSnapshot } from "@/lib/types";
import { getCandidateSession } from "@/lib/api";
import { InteractiveSession } from "./_components/InteractiveSession";

function CandidateSessionInner() {
  const searchParams = useSearchParams();
  const sessionId = searchParams.get("session");
  const [sessionData, setSessionData] = useState<InterviewSessionSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!sessionId) {
      setError("No session ID. Provide ?session=<uuid> in the URL.");
      setLoading(false);
      return;
    }
    const token = typeof window !== "undefined"
      ? localStorage.getItem("zt_candidate_token")
      : null;
    getCandidateSession(sessionId, token)
      .then(setSessionData)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Failed to load session."))
      .finally(() => setLoading(false));
  }, [sessionId]);

  if (loading) return (
    <div className="h-screen w-full flex items-center justify-center bg-[#0a0a0a] text-cyan-300">
      <div className="flex flex-col items-center gap-4">
        <div className="h-8 w-8 rounded-full border-2 border-cyan-400 border-t-transparent animate-spin" />
        <p className="text-sm uppercase tracking-widest text-slate-400">Initializing Workspace</p>
      </div>
    </div>
  );

  if (error || !sessionData) return (
    <div className="h-screen w-full flex items-center justify-center bg-[#0a0a0a]">
      <div className="max-w-md text-center space-y-3 px-6">
        <p className="text-xs uppercase tracking-widest text-rose-400">Session Error</p>
        <p className="text-sm text-slate-300">{error ?? "Session not found or expired."}</p>
      </div>
    </div>
  );

  return (
    <div
      className="h-screen w-full flex flex-col bg-[#0a0a0a] text-slate-100 overflow-hidden font-sans relative"
      style={{ backgroundImage: "url(/bg-quantum.png)", backgroundSize: "cover", backgroundPosition: "center" }}
    >
      <div className="absolute inset-0 bg-slate-950/70 backdrop-blur-[4px] z-0 pointer-events-none" />
      <div className="relative z-10 flex flex-col h-full w-full">
        <InteractiveSession
          sessionId={sessionData.session_id}
          candidateRole={sessionData.candidate_role}
        />
      </div>
    </div>
  );
}

export default function CandidateSessionPage() {
  return (
    <Suspense fallback={<div className="h-screen w-full flex items-center justify-center bg-[#0a0a0a]"><div className="h-8 w-8 rounded-full border-2 border-cyan-400 border-t-transparent animate-spin" /></div>}>
      <CandidateSessionInner />
    </Suspense>
  );
}
```

- [ ] **Step 2: Create `frontend/app/(interview)/operator/page.tsx`**

Copy the complete rendering logic from the **deleted** `[sessionId]/page.tsx` server component into a client component. Key changes: add `"use client"`, replace server-side `fetch` with `useEffect` + `getSession()`, read `?session=` param and `zt_operator_token` from localStorage.

Full file (preserves all existing rendering logic from the deleted Server Component):
```typescript
"use client";
import { useSearchParams } from "next/navigation";
import { useEffect, useState, Suspense } from "react";
import type { InterviewSessionSnapshot } from "@/lib/types";
import { getSession } from "@/lib/api";
import { Activity, AlertTriangle, Brain, ChartSpline, ClipboardCheck, Gauge, Shield } from "lucide-react";

function OperatorSessionInner() {
  const searchParams = useSearchParams();
  const sessionId = searchParams.get("session");
  const [sessionData, setSessionData] = useState<InterviewSessionSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!sessionId) { setError("No session ID. Provide ?session=<uuid>."); setLoading(false); return; }
    const token = typeof window !== "undefined" ? localStorage.getItem("zt_operator_token") : null;
    if (!token) { setError("Operator token not found. Authenticate first."); setLoading(false); return; }
    getSession(sessionId, token)
      .then(setSessionData)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Failed to load session."))
      .finally(() => setLoading(false));
  }, [sessionId]);

  if (loading) return (
    <div className="h-screen w-full flex items-center justify-center bg-slate-950">
      <div className="flex flex-col items-center gap-4">
        <div className="h-8 w-8 rounded-full border-2 border-cyan-400 border-t-transparent animate-spin" />
        <p className="text-sm uppercase tracking-widest text-slate-400">Loading Telemetry Board</p>
      </div>
    </div>
  );

  if (error || !sessionData) return (
    <div className="h-screen w-full flex items-center justify-center bg-slate-950">
      <div className="max-w-md text-center space-y-3 px-6">
        <p className="text-xs uppercase tracking-widest text-rose-400">Operator Error</p>
        <p className="text-sm text-slate-300">{error ?? "Session not found."}</p>
      </div>
    </div>
  );

  // ── All rendering logic from deleted Server Component is preserved below ──
  const taskOutcomes = sessionData.technical.task_outcomes;
  const failedActionCount = taskOutcomes.reduce((sum, t) => sum + t.failed_action_count, 0);
  const syntaxErrorRate = Math.round((failedActionCount / Math.max(sessionData.event_count, 1)) * 1000) / 10;
  const inFlightTask = taskOutcomes.find((t) => t.status === "partial") ?? taskOutcomes[0];
  const timeline = [...sessionData.overlay.telemetry_timeline].sort(
    (a, b) => new Date(a.timestamp_utc).getTime() - new Date(b.timestamp_utc).getTime()
  );
  const latest = timeline[timeline.length - 1];
  const stressPolyline = timeline.map((p, i) => {
    const x = (i / Math.max(timeline.length - 1, 1)) * 100;
    const y = (1 - (p.stress_index ?? 0)) * 100;
    return `${x},${y}`;
  }).join(" ");
  const pulsePolyline = timeline.map((p, i) => {
    const x = (i / Math.max(timeline.length - 1, 1)) * 100;
    const norm = Math.min(Math.max(((p.heart_rate_bpm ?? 60) - 60) / 80, 0), 1);
    return `${x},${(1 - norm) * 100}`;
  }).join(" ");
  const flags = [
    ...sessionData.overlay.operator_review_flags,
    ...sessionData.overlay.stress_markers.map(
      (m) => `${new Date(m.start_timestamp_utc).toISOString().slice(11, 16)} UTC — ${m.rationale}`
    ),
  ];

  return (
    <div className="h-screen bg-slate-950 text-slate-100 flex flex-col overflow-hidden">
      <div className="flex flex-col flex-1 overflow-hidden w-full max-w-[1440px] mx-auto px-4 sm:px-8 py-6">
        <header className="mb-5 flex flex-wrap items-start justify-between gap-4 border-b border-slate-800 pb-5 shrink-0">
          <div className="space-y-1">
            <p className="text-xs uppercase tracking-[0.18em] text-cyan-300/75">Operator Console</p>
            <h1 className="text-2xl font-semibold text-white">Executive Interview Telemetry Board</h1>
            <p className="text-sm text-slate-400">Session {sessionData.session_id} • {sessionData.candidate_role}</p>
          </div>
          <div className="inline-flex items-center gap-2 rounded-full border border-cyan-400/30 bg-cyan-400/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-cyan-200">
            <Shield className="h-4 w-4" />Plane Operator
          </div>
        </header>
        <main className="flex-1 overflow-hidden grid gap-6 xl:grid-cols-2">
          {/* Intelligence pane */}
          <section className="space-y-5 overflow-y-auto [scrollbar-width:thin] pr-1">
            <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5 shadow-2xl shadow-black/30">
              <h2 className="mb-4 flex items-center gap-2 text-base font-semibold text-white"><Gauge className="h-5 w-5 text-emerald-300" />Technical Plane</h2>
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-xl border border-slate-800 bg-slate-950/80 p-4"><p className="text-xs uppercase tracking-[0.12em] text-slate-500">Score</p><p className="mt-1 text-3xl font-semibold text-emerald-300">{sessionData.technical.technical_score}</p></div>
                <div className="rounded-xl border border-slate-800 bg-slate-950/80 p-4"><p className="text-xs uppercase tracking-[0.12em] text-slate-500">Task Status</p><p className="mt-1 text-sm font-medium text-slate-100">{inFlightTask?.title ?? "No active task"}</p></div>
                <div className="rounded-xl border border-slate-800 bg-slate-950/80 p-4"><p className="text-xs uppercase tracking-[0.12em] text-slate-500">Syntax Error Rate</p><p className="mt-1 text-3xl font-semibold text-amber-300">{syntaxErrorRate}%</p></div>
              </div>
            </div>
            <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
              <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.15em] text-slate-300"><ClipboardCheck className="h-4 w-4 text-cyan-300" />Current Task Outcomes</h3>
              <div className="space-y-3">
                {taskOutcomes.map((t) => (
                  <div key={t.outcome_id} className="rounded-xl border border-slate-800 bg-slate-950/80 p-4">
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-sm font-medium text-white">{t.title}</p>
                      <span className="rounded-full border border-slate-700 bg-slate-900 px-2.5 py-0.5 text-xs uppercase text-slate-300">{t.status}</span>
                    </div>
                    <p className="mt-2 text-sm text-slate-400">{t.summary}</p>
                    <p className="mt-2 text-xs text-slate-500">Failed: {t.failed_action_count} • {Math.round(t.duration_ms / 1000)}s</p>
                  </div>
                ))}
              </div>
            </div>
          </section>
          {/* Telemetry pane */}
          <section className="space-y-5 overflow-y-auto [scrollbar-width:thin] pr-1">
            <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
              <h2 className="mb-4 flex items-center gap-2 text-base font-semibold text-white"><Brain className="h-5 w-5 text-fuchsia-300" />Telemetry Plane</h2>
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-xl border border-slate-800 bg-slate-950/80 p-4"><p className="text-xs uppercase text-slate-500">Latest BPM</p><p className="mt-1 text-2xl font-semibold text-rose-300">{latest?.heart_rate_bpm ?? "--"}</p></div>
                <div className="rounded-xl border border-slate-800 bg-slate-950/80 p-4"><p className="text-xs uppercase text-slate-500">Stress Index</p><p className="mt-1 text-2xl font-semibold text-amber-300">{Math.round((latest?.stress_index ?? 0) * 100)}%</p></div>
                <div className="rounded-xl border border-slate-800 bg-slate-950/80 p-4"><p className="text-xs uppercase text-slate-500">Overlay Lag</p><p className="mt-1 text-2xl font-semibold text-cyan-300">{sessionData.overlay.overlay_processing_lag_ms}ms</p></div>
              </div>
            </div>
            <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
              <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold uppercase text-slate-300"><ChartSpline className="h-4 w-4 text-emerald-300" />Pulse / Stress Correlation</h3>
              <div className="rounded-xl border border-slate-800 bg-slate-950/85 p-4">
                <svg viewBox="0 0 100 100" className="h-44 w-full">
                  <defs>
                    <linearGradient id="sg" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stopColor="#f59e0b" /><stop offset="100%" stopColor="#ef4444" /></linearGradient>
                    <linearGradient id="pg" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stopColor="#22d3ee" /><stop offset="100%" stopColor="#34d399" /></linearGradient>
                  </defs>
                  {[0, 25, 50, 75, 100].map((l) => <line key={l} x1="0" x2="100" y1={l} y2={l} stroke="#1e293b" strokeWidth="0.4" />)}
                  <polyline points={stressPolyline} fill="none" stroke="url(#sg)" strokeWidth="1.8" />
                  <polyline points={pulsePolyline} fill="none" stroke="url(#pg)" strokeWidth="1.8" />
                </svg>
                <div className="mt-2 flex gap-4 text-xs text-slate-400">
                  <span className="inline-flex items-center gap-1.5"><Activity className="h-3.5 w-3.5 text-amber-300" />Stress</span>
                  <span className="inline-flex items-center gap-1.5"><Activity className="h-3.5 w-3.5 text-cyan-300" />Pulse</span>
                </div>
              </div>
            </div>
            <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
              <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold uppercase text-slate-300"><AlertTriangle className="h-4 w-4 text-rose-300" />Flagged Behavioral Timeline</h3>
              <div className="space-y-2">
                {flags.map((f, i) => <div key={i} className="rounded-xl border border-slate-800 bg-slate-950/80 p-3 text-sm text-slate-200">{f}</div>)}
              </div>
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}

export default function OperatorSessionPage() {
  return (
    <Suspense fallback={<div className="h-screen w-full flex items-center justify-center bg-slate-950"><div className="h-8 w-8 rounded-full border-2 border-cyan-400 border-t-transparent animate-spin" /></div>}>
      <OperatorSessionInner />
    </Suspense>
  );
}
```

- [ ] **Step 3: Type-check**
```bash
cd "C:\Users\BHARATH ANTONY\Documents\AI AGENT\INTERVIEW AGENT\frontend"
npx tsc --noEmit
# Expected: 0 errors
```

- [ ] **Step 4: Verify static build works**
```bash
npm run build
# Expected: creates frontend/out/ with candidate/index.html, operator/index.html
# Must NOT error with "Server Component cannot be used with output: export"
```

- [ ] **Step 5: Commit**
```bash
git add "frontend/app/(interview)/candidate/page.tsx" "frontend/app/(interview)/operator/page.tsx"
git commit -m "feat(frontend): flatten dynamic routes to query params, convert to Client Components for static export"
```

---

## Task 6: Frontend — Backend Ready Hook, Gate, Title Bar, Setup Page, Root Layout

**Files:**
- Create: `frontend/lib/hooks/useBackendReady.ts`
- Create: `frontend/components/BackendGate.tsx`
- Create: `frontend/components/TitleBar.tsx`
- Create: `frontend/app/setup/page.tsx`
- Modify: `frontend/app/layout.tsx`

- [ ] **Step 1: Create `frontend/lib/hooks/useBackendReady.ts`**

```typescript
"use client";
import { useState, useEffect } from "react";

const BACKEND_URL = "http://127.0.0.1:8000";
const MAX_ATTEMPTS = 40;  // 20 seconds
const POLL_INTERVAL_MS = 500;

export interface BackendReadyState {
  ready: boolean;
  attempts: number;
  error: string | null;
  maxAttempts: number;
}

export function useBackendReady(): BackendReadyState {
  const [ready, setReady] = useState(false);
  const [attempts, setAttempts] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let attempt = 0;
    async function poll() {
      while (!cancelled && attempt < MAX_ATTEMPTS) {
        try {
          const res = await fetch(`${BACKEND_URL}/api/health`, { signal: AbortSignal.timeout(1_000) });
          if (res.ok && !cancelled) { setReady(true); return; }
        } catch { /* not yet up */ }
        attempt++;
        if (!cancelled) setAttempts(attempt);
        await new Promise<void>((r) => setTimeout(r, POLL_INTERVAL_MS));
      }
      if (!cancelled) setError("Sentinel Node failed to initialize. Please restart the application.");
    }
    poll();
    return () => { cancelled = true; };
  }, []);

  return { ready, attempts, error, maxAttempts: MAX_ATTEMPTS };
}
```

- [ ] **Step 2: Create `frontend/components/BackendGate.tsx`**

```typescript
"use client";
import type { ReactNode } from "react";
import { useBackendReady } from "@/lib/hooks/useBackendReady";
import { Shield, AlertCircle } from "lucide-react";

export function BackendGate({ children }: { children: ReactNode }) {
  const { ready, attempts, error, maxAttempts } = useBackendReady();

  if (error) return (
    <div className="h-screen w-full flex items-center justify-center bg-[#0a0a0a]">
      <div className="max-w-sm text-center space-y-4 px-6">
        <AlertCircle className="h-10 w-10 text-rose-400 mx-auto" />
        <h2 className="text-lg font-semibold text-white">Initialization Failed</h2>
        <p className="text-sm text-slate-400">{error}</p>
        <button onClick={() => window.location.reload()} className="mt-2 px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-sm text-slate-200 transition-colors">
          Retry
        </button>
      </div>
    </div>
  );

  if (!ready) return (
    <div className="h-screen w-full flex items-center justify-center bg-[#0a0a0a]">
      <div className="flex flex-col items-center gap-6">
        <div className="rounded-full border border-cyan-400/30 bg-cyan-400/10 p-5">
          <Shield className="h-12 w-12 text-cyan-300" />
        </div>
        <div className="text-center space-y-2">
          <h1 className="text-xl font-semibold text-white">ZT-ATE Sentinel Node</h1>
          <p className="text-xs uppercase tracking-widest text-slate-500">Initializing Secure Backend</p>
        </div>
        <div className="w-48 h-1 rounded-full bg-slate-800 overflow-hidden">
          <div
            className="h-full bg-cyan-500 rounded-full transition-all duration-300"
            style={{ width: `${(attempts / maxAttempts) * 100}%` }}
          />
        </div>
        <p className="text-xs text-slate-600">{attempts}/{maxAttempts} checks</p>
      </div>
    </div>
  );

  return <>{children}</>;
}
```

- [ ] **Step 3: Create `frontend/components/TitleBar.tsx`**

```typescript
"use client";
/**
 * TitleBar — Custom frameless window chrome for Tauri.
 * data-tauri-drag-region makes the element draggable as a window handle.
 * Window control buttons invoke Tauri window commands.
 * Falls back gracefully in browser (window.* calls no-op outside Tauri).
 */
import { Minus, Maximize2, X } from "lucide-react";

async function minimize() {
  try { const { getCurrentWindow } = await import("@tauri-apps/api/window"); await (await getCurrentWindow()).minimize(); } catch {}
}
async function maximize() {
  try { const { getCurrentWindow } = await import("@tauri-apps/api/window"); const w = await getCurrentWindow(); (await w.isMaximized()) ? w.unmaximize() : w.maximize(); } catch {}
}
async function close() {
  try { const { getCurrentWindow } = await import("@tauri-apps/api/window"); await (await getCurrentWindow()).close(); } catch {}
}

export function TitleBar() {
  return (
    <div
      className="h-8 w-full flex items-center justify-between bg-[#050505] border-b border-slate-900 px-3 shrink-0 select-none"
      data-tauri-drag-region
    >
      <div className="flex items-center gap-2 pointer-events-none" data-tauri-drag-region>
        <span className="text-xs text-slate-600 tracking-widest uppercase">ZT-ATE Sentinel Node</span>
      </div>
      <div className="flex items-center gap-0.5">
        {[
          { icon: Minus, action: minimize, label: "Minimize", hover: "hover:bg-slate-800" },
          { icon: Maximize2, action: maximize, label: "Maximize", hover: "hover:bg-slate-800" },
          { icon: X, action: close, label: "Close", hover: "hover:bg-rose-900" },
        ].map(({ icon: Icon, action, label, hover }) => (
          <button
            key={label}
            onClick={action}
            aria-label={label}
            className={`p-1.5 rounded text-slate-500 ${hover} hover:text-slate-200 transition-colors`}
          >
            <Icon className="h-3.5 w-3.5" />
          </button>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create `frontend/app/setup/page.tsx`**

```typescript
"use client";
/**
 * /setup — First-run provisioning: GEMINI_API_KEY entry + Stronghold vault creation.
 * Shown once when vault.hold does not exist.
 * After provisioning: redirects to / (BackendGate polls /health → main app).
 */
import { useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { appDataDir } from "@tauri-apps/api/path";
import { Client } from "@tauri-apps/plugin-stronghold";
import { useRouter } from "next/navigation";
import { Shield, Key, Loader2, CheckCircle2 } from "lucide-react";

const VAULT_PASSPHRASE = "zt-ate-device-passphrase-v1";
const STORE_NAME = "zt-ate-secrets";
const encode = (s: string) => Array.from(new TextEncoder().encode(s));

export default function SetupPage() {
  const router = useRouter();
  const [geminiKey, setGeminiKey] = useState("");
  const [status, setStatus] = useState<"idle" | "provisioning" | "done" | "error">("idle");
  const [errMsg, setErrMsg] = useState("");

  async function handleProvision() {
    if (!geminiKey.trim()) { setErrMsg("GEMINI_API_KEY is required."); return; }
    setStatus("provisioning"); setErrMsg("");
    try {
      // 1. Auto-generate JWT_SECRET_KEY and OPERATOR_MASTER_SECRET in Rust (rand::thread_rng)
      const [jwtKey, opSecret] = await invoke<[string, string]>("generate_secrets");
      // 2. Store all secrets in Stronghold vault
      const vaultPath = `${await appDataDir()}/vault.hold`;
      const vault = await Client.load(vaultPath, VAULT_PASSPHRASE);
      const store = vault.getStore(STORE_NAME);
      await store.insert("gemini_api_key", encode(geminiKey.trim()));
      await store.insert("jwt_secret_key", encode(jwtKey));
      await store.insert("operator_master_secret", encode(opSecret));
      await vault.save();
      // 3. Spawn backend sidecar with secrets as env vars
      await invoke("spawn_backend_sidecar", {
        geminiApiKey: geminiKey.trim(),
        jwtSecretKey: jwtKey,
        operatorMasterSecret: opSecret,
      });
      setStatus("done");
      setTimeout(() => router.push("/"), 1_500);
    } catch (err: unknown) {
      setErrMsg(`Provisioning failed: ${err instanceof Error ? err.message : String(err)}`);
      setStatus("error");
    }
  }

  return (
    <div className="h-screen w-full flex items-center justify-center bg-[#0a0a0a]">
      <div className="w-full max-w-md px-8 py-10 space-y-8">
        <div className="space-y-2 text-center">
          <div className="flex justify-center">
            <div className="rounded-full border border-cyan-400/30 bg-cyan-400/10 p-4">
              <Shield className="h-10 w-10 text-cyan-300" />
            </div>
          </div>
          <h1 className="text-2xl font-semibold text-white">ZT-ATE Sentinel Node</h1>
          <p className="text-xs uppercase tracking-widest text-slate-500">First-Run Security Provisioning</p>
        </div>
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
          <p className="text-xs text-slate-400 leading-relaxed">
            Enter your Gemini API key. JWT signing secrets and the operator master secret
            are auto-generated with cryptographically secure randomness and stored in your
            device vault. They are never written to disk in plaintext.
          </p>
        </div>
        <div className="space-y-2">
          <label className="block text-xs uppercase tracking-widest text-slate-400">Gemini API Key</label>
          <div className="relative">
            <Key className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
            <input
              type="password" value={geminiKey}
              onChange={(e) => setGeminiKey(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && status === "idle" && handleProvision()}
              placeholder="AIza..."
              disabled={status === "provisioning" || status === "done"}
              className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-slate-700 bg-slate-950 text-slate-100 text-sm placeholder-slate-600 focus:outline-none focus:border-cyan-500 disabled:opacity-50"
            />
          </div>
        </div>
        {errMsg && <p className="text-sm text-rose-400 text-center">{errMsg}</p>}
        <button
          onClick={handleProvision}
          disabled={status === "provisioning" || status === "done" || !geminiKey.trim()}
          className="w-full py-3 rounded-xl bg-cyan-600 hover:bg-cyan-500 disabled:opacity-40 text-white text-sm font-semibold uppercase tracking-widest transition-colors flex items-center justify-center gap-2"
        >
          {status === "provisioning" && <Loader2 className="h-4 w-4 animate-spin" />}
          {status === "done" && <CheckCircle2 className="h-4 w-4 text-emerald-300" />}
          {status === "idle" && "Initialize Sentinel Node"}
          {status === "provisioning" && "Provisioning..."}
          {status === "done" && "Provisioned — Starting..."}
          {status === "error" && "Retry Provisioning"}
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Update `frontend/app/layout.tsx`**

The root layout must be a Client Component to use `useBackendReady` and redirect to `/setup` on first run.

```typescript
"use client";
/**
 * Root layout — Tauri Sentinel Node edition.
 * 1. Checks for first-run (stronghold vault missing) → redirects to /setup.
 * 2. Wraps children in BackendGate (polls /health before rendering).
 * 3. Renders TitleBar (frameless window chrome).
 *
 * NOTE: Converting RootLayout to "use client" means metadata must be
 * exported from individual page.tsx files, not here.
 */
import "./globals.css";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { invoke } from "@tauri-apps/api/core";
import { BackendGate } from "@/components/BackendGate";
import { TitleBar } from "@/components/TitleBar";

// Detects if running inside Tauri (window.__TAURI_INTERNALS__ is injected by Tauri)
function isTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

export default function RootLayout({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [firstRunChecked, setFirstRunChecked] = useState(false);

  useEffect(() => {
    if (!isTauri()) { setFirstRunChecked(true); return; }
    if (pathname === "/setup") { setFirstRunChecked(true); return; }

    invoke<boolean>("check_first_run")
      .then((isFirstRun) => {
        if (isFirstRun) router.replace("/setup");
        else setFirstRunChecked(true);
      })
      .catch(() => setFirstRunChecked(true));
  }, [pathname, router]);

  return (
    <html lang="en">
      <body className="bg-[#0a0a0a] text-slate-100">
        {isTauri() && <TitleBar />}
        {firstRunChecked ? (
          pathname === "/setup"
            ? children
            : <BackendGate>{children}</BackendGate>
        ) : (
          <div className="h-screen w-full flex items-center justify-center bg-[#0a0a0a]">
            <div className="h-8 w-8 rounded-full border-2 border-cyan-400 border-t-transparent animate-spin" />
          </div>
        )}
      </body>
    </html>
  );
}
```

- [ ] **Step 6: Final type check and static build**
```bash
cd "C:\Users\BHARATH ANTONY\Documents\AI AGENT\INTERVIEW AGENT\frontend"
npx tsc --noEmit
npm run build
# Expected: frontend/out/ created, no TS errors, no static export errors
```

- [ ] **Step 7: Commit**
```bash
git add frontend/app/layout.tsx frontend/app/setup/page.tsx frontend/components/BackendGate.tsx frontend/components/TitleBar.tsx frontend/lib/hooks/useBackendReady.ts
git commit -m "feat(frontend): BackendGate health-poll, TitleBar frameless chrome, first-run setup page, Stronghold provisioning"
```

---

## Task 7: Tauri — Rust Project Scaffolding

**Files:**
- Create: `src-tauri/Cargo.toml`
- Create: `src-tauri/build.rs`
- Create: `src-tauri/src/main.rs`
- Create: `src-tauri/src/lib.rs`
- Create: `src-tauri/src/commands.rs`
- Create: `src-tauri/capabilities/default.json`
- Create: `src-tauri/tauri.conf.json`
- Create: `src-tauri/binaries/.gitkeep`
- Create: `Cargo.toml` (workspace root)

- [ ] **Step 1: Create workspace `Cargo.toml` at project root**
```toml
[workspace]
members = ["src-tauri"]
resolver = "2"
```

- [ ] **Step 2: Create `src-tauri/Cargo.toml`**
```toml
[package]
name = "zt-ate-sentinel-node"
version = "1.0.0"
edition = "2021"
rust-version = "1.77"

[lib]
name = "zt_ate_sentinel_node_lib"
crate-type = ["staticlib", "cdylib", "rlib"]

[[bin]]
name = "zt-ate-sentinel-node"
path = "src/main.rs"

[build-dependencies]
tauri-build = { version = "2", features = [] }

[dependencies]
tauri = { version = "2", features = ["protocol-asset"] }
tauri-plugin-shell = "2"
tauri-plugin-stronghold = "2"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
rand = "0.8"
hex = "0.4"
argon2 = "0.5"
tokio = { version = "1", features = ["rt", "sync"] }

[profile.release]
opt-level = "z"     # optimize for binary size
lto = true
codegen-units = 1
panic = "abort"
strip = true
```

- [ ] **Step 3: Create `src-tauri/build.rs`**
```rust
fn main() {
    tauri_build::build()
}
```

- [ ] **Step 4: Create `src-tauri/src/main.rs`**
```rust
// Prevents additional console window on Windows in release builds.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    zt_ate_sentinel_node_lib::run();
}
```

- [ ] **Step 5: Create `src-tauri/src/commands.rs`**
```rust
use rand::Rng;
use tauri::AppHandle;
use tauri_plugin_shell::ShellExt;

/// Auto-generates JWT_SECRET_KEY and OPERATOR_MASTER_SECRET.
/// Returns (jwt_secret_key, operator_master_secret) as hex strings.
/// Each is 32 bytes (256 bits) of cryptographically secure random data.
#[tauri::command]
pub fn generate_secrets() -> Result<(String, String), String> {
    let mut rng = rand::thread_rng();
    let jwt_key: String = (0..32)
        .map(|_| format!("{:02x}", rng.gen::<u8>()))
        .collect();
    let op_secret: String = (0..32)
        .map(|_| format!("{:02x}", rng.gen::<u8>()))
        .collect();
    Ok((jwt_key, op_secret))
}

/// Checks if this is the first run (vault.hold does not exist in appDataDir).
#[tauri::command]
pub async fn check_first_run(app: AppHandle) -> Result<bool, String> {
    let app_data = app
        .path()
        .app_data_dir()
        .map_err(|e| e.to_string())?;
    Ok(!app_data.join("vault.hold").exists())
}

/// Spawns the zt-backend-sidecar with secrets injected as environment variables.
/// Called by the frontend after reading secrets from Stronghold.
/// CORS_ORIGINS includes both the Tauri asset protocol origin and the dev server origin.
#[tauri::command]
pub async fn spawn_backend_sidecar(
    app: AppHandle,
    gemini_api_key: String,
    jwt_secret_key: String,
    operator_master_secret: String,
) -> Result<(), String> {
    app.shell()
        .sidecar("zt-backend-sidecar")
        .map_err(|e| e.to_string())?
        .env("GEMINI_API_KEY", gemini_api_key)
        .env("JWT_SECRET_KEY", jwt_secret_key)
        .env("OPERATOR_MASTER_SECRET", operator_master_secret)
        .env(
            "CORS_ORIGINS",
            "tauri://localhost,http://localhost:1420,http://127.0.0.1:1420",
        )
        .env("ENFORCE_SECRET_SCAN", "false") // secrets come from env, not .env file
        .spawn()
        .map_err(|e| e.to_string())?;
    Ok(())
}
```

- [ ] **Step 6: Create `src-tauri/src/lib.rs`**
```rust
mod commands;

use tauri::Manager;

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(
            tauri_plugin_stronghold::Builder::new(|password| {
                // Derive a 256-bit key from the vault passphrase using Argon2id.
                // Salt is fixed for this app — adequate for device-scoped storage.
                use argon2::Argon2;
                let mut key = vec![0u8; 32];
                Argon2::default()
                    .hash_password_into(
                        password.as_bytes(),
                        b"zt-ate-sentinel-node-argon2-salt-v1",
                        &mut key,
                    )
                    .expect("Argon2 key derivation failed");
                key
            })
            .build(),
        )
        .invoke_handler(tauri::generate_handler![
            commands::generate_secrets,
            commands::check_first_run,
            commands::spawn_backend_sidecar,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

- [ ] **Step 7: Create `src-tauri/capabilities/default.json`**
```json
{
  "$schema": "../gen/schemas/desktop-schema.json",
  "identifier": "default",
  "description": "Default capabilities for ZT-ATE Sentinel Node",
  "windows": ["main"],
  "permissions": [
    "core:default",
    "core:window:allow-minimize",
    "core:window:allow-maximize",
    "core:window:allow-unmaximize",
    "core:window:allow-close",
    "core:window:allow-is-maximized",
    "shell:allow-execute",
    "shell:allow-spawn",
    "stronghold:allow-initialize",
    "stronghold:allow-create-client",
    "stronghold:allow-get-store",
    "stronghold:allow-store-insert",
    "stronghold:allow-store-get",
    "stronghold:allow-save"
  ]
}
```

- [ ] **Step 8: Create `src-tauri/binaries/.gitkeep`**
```bash
mkdir -p src-tauri/binaries
touch src-tauri/binaries/.gitkeep
```

- [ ] **Step 9: Compile check**
```bash
cd src-tauri
cargo check
# Expected: Compiling zt-ate-sentinel-node... Finished — 0 errors
```

- [ ] **Step 10: Commit**
```bash
git add Cargo.toml src-tauri/
git commit -m "feat(tauri): initialize Rust sidecar manager with generate_secrets, check_first_run, spawn_backend_sidecar commands + Stronghold + Shell plugins"
```

---

## Task 8: Tauri — `tauri.conf.json`

**Files:**
- Create: `src-tauri/tauri.conf.json`

- [ ] **Step 1: Create `src-tauri/tauri.conf.json`**

```json
{
  "$schema": "https://schema.tauri.app/config/2",
  "productName": "ZT-ATE Sentinel Node",
  "version": "1.0.0",
  "identifier": "com.zt-ate.sentinel-node",
  "build": {
    "frontendDist": "../frontend/out",
    "devUrl": "http://localhost:3000",
    "beforeDevCommand": "cd ../frontend && npm run dev",
    "beforeBuildCommand": "cd ../frontend && npm run build"
  },
  "app": {
    "windows": [
      {
        "label": "main",
        "title": "ZT-ATE Sentinel Node",
        "width": 1440,
        "height": 900,
        "minWidth": 1024,
        "minHeight": 700,
        "resizable": true,
        "fullscreen": false,
        "decorations": false,
        "transparent": false,
        "center": true,
        "visible": true
      }
    ],
    "security": {
      "csp": "default-src 'self' tauri: asset: https://asset.localhost; connect-src 'self' http://127.0.0.1:8000; media-src 'self' blob: mediastream: *; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
    }
  },
  "bundle": {
    "active": true,
    "targets": "all",
    "icon": [
      "icons/32x32.png",
      "icons/128x128.png",
      "icons/128x128@2x.png",
      "icons/icon.icns",
      "icons/icon.ico"
    ],
    "externalBin": [
      "binaries/zt-backend-sidecar"
    ]
  }
}
```

> **Important:** `decorations: false` enables the frameless "Quantum Obsidian" aesthetic. The `TitleBar` component provides custom window chrome with drag region and controls.

> **externalBin:** Tauri 2 expects binaries at `src-tauri/binaries/zt-backend-sidecar-<rust-target-triple>[.exe]`. Get your triple: `rustc -Vv | grep host | cut -f2 -d' '`

- [ ] **Step 2: Generate placeholder icons (required for build)**
```bash
cd src-tauri
# Use Tauri CLI to generate default icons from a 1024x1024 PNG
# Replace app-icon.png with your actual icon first
npx @tauri-apps/cli icon app-icon.png
# Or create minimal placeholder icons to unblock build:
mkdir -p icons
# Download placeholder icons from Tauri's template repo or create 32x32 PNGs
```

- [ ] **Step 3: Run Tauri dev (smoke test — backend sidecar binary must exist)**
```bash
# Ensure binary exists first:
ls src-tauri/binaries/
# Expected: zt-backend-sidecar-x86_64-pc-windows-msvc.exe (or platform triple)

# Then:
cd src-tauri
cargo tauri dev
# Expected: window opens, /setup page shown (first run), TitleBar visible
```

- [ ] **Step 4: Commit**
```bash
git add src-tauri/tauri.conf.json src-tauri/icons/
git commit -m "feat(tauri): configure tauri.conf.json — frameless window, externalBin sidecar, CSP, cross-platform bundle targets"
```

---

## Verification — End-to-End Smoke Test

```bash
# 1. Build the Python sidecar
cd "C:\Users\BHARATH ANTONY\Documents\AI AGENT\INTERVIEW AGENT\backend"
build_backend.bat  # or ./build_backend.sh on Unix

# 2. Verify binary is in place
ls ../src-tauri/binaries/
# Expected: zt-backend-sidecar-<triple>.exe present

# 3. Build the Next.js static export
cd ../frontend
npm run build
# Expected: out/ directory created

# 4. Launch Tauri dev mode
cd ../src-tauri
cargo tauri dev
# Expected:
#   - Frameless window opens (decorations: false)
#   - TitleBar visible with minimize/maximize/close buttons
#   - /setup page shown on first run
#   - Enter GEMINI_API_KEY → "Provisioning..." → redirect to /
#   - BackendGate spinner → sidecar starts → health check passes
#   - Main app renders

# 5. Navigate to candidate page
# In browser address: tauri://localhost/candidate?session=demo-session-777
# Expected: Candidate workspace loads with InteractiveSession

# 6. Navigate to operator page
# tauri://localhost/operator?session=demo-session-777
# Expected: Telemetry board loads with SVG chart

# 7. Build final distributable
cargo tauri build
# Expected: src-tauri/target/release/bundle/ contains:
#   - Windows: .msi installer
#   - macOS: .dmg
#   - Linux: .AppImage / .deb
```

---

## Environment Variables Reference (Desktop App)

| Variable | Source | Purpose |
|----------|--------|---------|
| `GEMINI_API_KEY` | User-entered → Stronghold → env var | Gemini API calls |
| `JWT_SECRET_KEY` | Auto-generated → Stronghold → env var | JWT HS256 signing (32 bytes hex) |
| `OPERATOR_MASTER_SECRET` | Auto-generated → Stronghold → env var | Operator token minting |
| `CORS_ORIGINS` | Hardcoded by Tauri Rust | `tauri://localhost,http://localhost:1420` |
| `ENFORCE_SECRET_SCAN` | `false` (set by Tauri Rust) | Disable file scan in frozen mode |

No `.env` file needed in production — all secrets flow from Stronghold → Tauri Rust → sidecar env vars.

---

## ADR Note (for vault update after implementation)

After completing this plan, add `ADR-0004` to the Obsidian vault:
- **Title:** Tauri 2 Desktop Conversion — ZT-ATE Sentinel Node
- **Decision:** Static Next.js export + PyInstaller sidecar + Tauri Stronghold secrets
- **Status:** Implemented
- Update `Interview Agent Hub.md` sprint table: Sprint 6 — Tauri Desktop Conversion — ✅ Complete
