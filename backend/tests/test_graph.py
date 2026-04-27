from __future__ import annotations

import pytest

pytest.importorskip("langgraph")

from app.config import Settings
from app.contracts import CandidateEvent, ConsentRecord, EventType, TelemetryPacket
from app.graph import InterviewGraphEngine
from app.services.adk_router import GoogleADKService
from app.services.agno_tools import AgnoToolService
from app.services.crewai_orchestrator import CrewDebateOrchestrator
from app.services.memory import MemoryBank
from app.services.technical_scoring import TechnicalScoringService
from app.services.telemetry_overlay import TelemetryOverlayService
from app.state import base_state


@pytest.mark.asyncio
async def test_graph_executes_lifecycle_sequence(tmp_path) -> None:
    cfg = Settings(data_dir=tmp_path, sqlite_path=tmp_path / "test.db")
    engine = InterviewGraphEngine(
        adk_service=GoogleADKService(cfg),
        crew_orchestrator=CrewDebateOrchestrator(),
        agno_tools=AgnoToolService(),
        memory_bank=MemoryBank(),
        technical_scoring_service=TechnicalScoringService(),
        telemetry_overlay_service=TelemetryOverlayService(),
    )

    state = base_state("sess-1", "candidate-1", "Platform Engineer")
    state["consent_record"] = ConsentRecord(
        session_id="sess-1",
        telemetry_collection_allowed=True,
        biometric_processing_allowed=True,
        disclosure_text="Telemetry is collected for operator review only and excluded from automated scoring.",
    )
    state["current_event"] = CandidateEvent(
        session_id="sess-1",
        event_type=EventType.CANDIDATE_MESSAGE,
        telemetry=TelemetryPacket(
            candidate_message="I would isolate failure domains and deploy immutable pods.",
            stress_index=0.22,
            raw_vector_hash="6f1f4dc566f90f5ecf98ee4f710a9f8c",
        ),
    )

    result = await engine.run(state)
    nodes = [trace.node for trace in result["trace_events"]]

    assert nodes == [
        "session_init",
        "consent_and_disclosure_gate",
        "l0_router",
        "identity_gate",
        "scenario_selection",
        "simulation_execution",
        "technical_assessment",
        "telemetry_overlay_generation",
        "operator_review_queue",
        "memory",
        "snapshot_milestone",
    ]
    assert 0.0 <= result["technical_plane"].technical_score <= 100.0
    assert result["overlay_plane"].excluded_from_automated_scoring is True


@pytest.mark.asyncio
async def test_graph_drops_silent_event_at_l0(tmp_path) -> None:
    cfg = Settings(data_dir=tmp_path, sqlite_path=tmp_path / "test.db", l0_silence_cutoff_ms=1000)
    engine = InterviewGraphEngine(
        adk_service=GoogleADKService(cfg),
        crew_orchestrator=CrewDebateOrchestrator(),
        agno_tools=AgnoToolService(),
        memory_bank=MemoryBank(),
        technical_scoring_service=TechnicalScoringService(),
        telemetry_overlay_service=TelemetryOverlayService(),
    )

    state = base_state("sess-2", "candidate-2", "SRE")
    state["current_event"] = CandidateEvent(
        session_id="sess-2",
        event_type=EventType.AUDIO_CHUNK,
        telemetry=TelemetryPacket(
            audio_text="",
            silence_ms=2000,
            raw_vector_hash="6f1f4dc566f90f5ecf98ee4f710a9f8c",
        ),
    )

    result = await engine.run(state)
    nodes = [trace.node for trace in result["trace_events"]]

    assert nodes == ["session_init", "consent_and_disclosure_gate", "l0_router"]
