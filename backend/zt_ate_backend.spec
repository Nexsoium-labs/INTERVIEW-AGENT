# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for zt-backend-sidecar.
# Usage: cd backend && pyinstaller zt_ate_backend.spec
# Output: dist/zt-backend-sidecar[.exe]

from PyInstaller.utils.hooks import collect_all

(ga_d, ga_b, ga_h) = collect_all("google.generativeai")
(fa_d, fa_b, fa_h) = collect_all("fastapi")
(pd_d, pd_b, pd_h) = collect_all("pydantic")
(ps_d, ps_b, ps_h) = collect_all("pydantic_settings")
(lg_d, lg_b, lg_h) = collect_all("langgraph")
(db_d, db_b, db_h) = collect_all("aiosqlite")

HIDDEN = [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    "google.generativeai",
    "google.generativeai.types",
    "google.generativeai.types.content_types",
    "google.generativeai.types.generation_types",
    "google.auth",
    "google.auth.credentials",
    "google.auth.transport.requests",
    "google.api_core",
    "google.api_core.exceptions",
    "langgraph.graph",
    "langgraph.checkpoint",
    "langgraph.checkpoint.memory",
    "pydantic.v1",
    "cryptography",
    "cryptography.hazmat.primitives.asymmetric",
    "starlette.routing",
    "starlette.middleware",
    "starlette.middleware.cors",
    "starlette.responses",
    "starlette.websockets",
    "orjson",
    "aiofiles",
    "httpx",
    "httpx._transports.default",
    "httpx._transports.asgi",
    "httpx._transports.wsgi",
    "app",
    "app.main",
    "app.config",
    "app.contracts",
    "app.orchestrator",
    "app.graph",
    "app.security",
    "app.security.auth",
    "app.api",
    "app.api.routes",
    "app.services",
    "app.services.genai_config",
    "app.services.adk_router",
    "app.services.live_interface",
    "app.services.evaluator",
    "app.services.storage",
    "app.services.telemetry_overlay",
    "app.services.technical_scoring",
    "app.services.memory",
    "app.services.guardrails",
    "app.services.observability",
    "app.services.reporting",
    "app.services.stream_hub",
    "app.services.a2a",
    "app.services.agent_registry",
    "app.services.agno_tools",
    "app.services.crewai_orchestrator",
    "app.services.secret_scanner",
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
    excludes=[
        "torch",
        "tensorflow",
        "numpy",
        "scipy",
        "matplotlib",
        "PIL",
        "cv2",
        "pytest",
        "pytest_asyncio",
        "IPython",
        "jupyter",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="zt-backend-sidecar",
    debug=False,
    strip=False,
    upx=False,
    console=True,
    runtime_tmpdir=None,
)
