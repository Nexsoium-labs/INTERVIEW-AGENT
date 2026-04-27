from __future__ import annotations

import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router as api_router
from app.config import settings
from app.graph import InterviewGraphEngine
from app.orchestrator import InterviewOrchestrator
from app.phase_plan import default_phase_plan
from app.services.a2a import A2AService
from app.services.adk_router import GoogleADKService
from app.services.agent_registry import AgentRegistryService
from app.services.agno_tools import AgnoToolService
from app.services.crewai_orchestrator import CrewDebateOrchestrator
from app.services.evaluator import GlassBoxEvaluator
from app.services.guardrails import GuardrailService
from app.services.live_interface import LiveInterfaceService
from app.services.memory import MemoryBank
from app.services.observability import ObservabilityService
from app.services.reporting import ReportService
from app.services.secret_scanner import SecretScannerService
from app.services.storage import Storage
from app.services.stream_hub import StreamHub
from app.services.technical_scoring import TechnicalScoringService
from app.services.telemetry_overlay import TelemetryOverlayService


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.enforce_secret_scan and not getattr(sys, "frozen", False):
        SecretScannerService(settings.data_dir.parent).enforce_clean_startup()

    # Fail-fast: validate GEMINI_API_KEY before accepting traffic.
    # Skips gracefully if google-generativeai is not installed (optional dep).
    try:
        from app.services.genai_config import ensure_configured
        ensure_configured()
    except RuntimeError as _gemini_err:
        import logging as _logging
        _logging.getLogger(__name__).warning(
            "Gemini SDK not configured (%s). Live model calls will degrade gracefully.", _gemini_err
        )

    storage = Storage(settings.sqlite_path)
    await storage.initialize()
    await storage.seed_phases(default_phase_plan())

    agno_tools = AgnoToolService()
    memory_bank = MemoryBank()
    technical_scoring_service = TechnicalScoringService()
    telemetry_overlay_service = TelemetryOverlayService()
    agent_registry = AgentRegistryService(owner_system=settings.app_name)
    guardrail_service = GuardrailService()
    stream_hub = StreamHub()
    graph_engine = InterviewGraphEngine(
        adk_service=GoogleADKService(settings),
        crew_orchestrator=CrewDebateOrchestrator(),
        agno_tools=agno_tools,
        memory_bank=memory_bank,
        technical_scoring_service=technical_scoring_service,
        telemetry_overlay_service=telemetry_overlay_service,
    )
    orchestrator = InterviewOrchestrator(
        storage=storage,
        graph_engine=graph_engine,
        agno_tools=agno_tools,
        report_service=GlassBoxEvaluator(
            report_service=ReportService(
                agno_tools=agno_tools,
                guardrail_service=guardrail_service,
                telemetry_overlay_service=telemetry_overlay_service,
            )
        ),
        observability_service=ObservabilityService(),
        technical_scoring_service=technical_scoring_service,
        agent_registry=agent_registry,
        live_interface_service=LiveInterfaceService(guardrail_service=guardrail_service),
        a2a_service=A2AService(agent_registry=agent_registry),
        stream_hub=stream_hub,
        trace_history_limit=settings.trace_history_limit,
    )

    app.state.storage = storage
    app.state.orchestrator = orchestrator

    yield


app = FastAPI(title=settings.app_name, version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,   # explicit whitelist — see config.py
    allow_credentials=True,                # required for Authorization header forwarding
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)

app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/")
async def index():
    return JSONResponse(
        {
            "name": settings.app_name,
            "message": (
                "Backend is running. Start the Next.js frontend separately "
                "for the operator console."
            ),
        }
    )
