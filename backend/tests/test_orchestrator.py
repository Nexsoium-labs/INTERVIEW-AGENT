from __future__ import annotations

import pytest

from app.config import Settings
from app.contracts import (
    A2AHandshakeRequest,
    ConsentCaptureRequest,
    EventIngestRequest,
    EventType,
    FinalizeInterviewRequest,
    HumanDecision,
    HumanReviewDecisionRequest,
    InterviewSessionCreate,
    LiveConversationRequest,
    SessionStatus,
    TelemetryPacket,
)
from app.graph import InterviewGraphEngine
from app.orchestrator import InterviewOrchestrator
from app.services.a2a import A2AService
from app.services.adk_router import GoogleADKService
from app.services.agent_registry import AgentRegistryService
from app.services.agno_tools import AgnoToolService
from app.services.crewai_orchestrator import CrewDebateOrchestrator
from app.services.guardrails import GuardrailService
from app.services.live_interface import LiveInterfaceService
from app.services.memory import MemoryBank
from app.services.observability import ObservabilityService
from app.services.reporting import ReportService
from app.services.storage import Storage
from app.services.stream_hub import StreamHub
from app.services.technical_scoring import TechnicalScoringService
from app.services.telemetry_overlay import TelemetryOverlayService


async def _build_orchestrator(tmp_path) -> InterviewOrchestrator:
    storage = Storage(tmp_path / "ivt.db")
    await storage.initialize()

    cfg = Settings(data_dir=tmp_path, sqlite_path=tmp_path / "ivt.db")
    agno_tools = AgnoToolService()
    technical_scoring_service = TechnicalScoringService()
    telemetry_overlay_service = TelemetryOverlayService()
    graph_engine = InterviewGraphEngine(
        adk_service=GoogleADKService(cfg),
        crew_orchestrator=CrewDebateOrchestrator(),
        agno_tools=agno_tools,
        memory_bank=MemoryBank(),
        technical_scoring_service=technical_scoring_service,
        telemetry_overlay_service=telemetry_overlay_service,
    )
    guardrail_service = GuardrailService()
    agent_registry = AgentRegistryService(owner_system="ZT-ATE Test")
    return InterviewOrchestrator(
        storage=storage,
        graph_engine=graph_engine,
        agno_tools=agno_tools,
        report_service=ReportService(
            agno_tools=agno_tools,
            guardrail_service=guardrail_service,
            telemetry_overlay_service=telemetry_overlay_service,
        ),
        observability_service=ObservabilityService(),
        technical_scoring_service=technical_scoring_service,
        agent_registry=agent_registry,
        live_interface_service=LiveInterfaceService(guardrail_service=guardrail_service),
        a2a_service=A2AService(agent_registry=agent_registry),
        stream_hub=StreamHub(),
    )


async def _seed_session(orchestrator: InterviewOrchestrator) -> str:
    session = await orchestrator.create_session(
        request=InterviewSessionCreate(
            candidate_id="candidate-1",
            candidate_role="Platform Engineer",
            language="en",
        )
    )
    await orchestrator.capture_consent(
        session_id=session.session_id,
        request=ConsentCaptureRequest(
            telemetry_collection_allowed=True,
            biometric_processing_allowed=True,
            disclosure_text="Telemetry is collected for operator review only and excluded from automated scoring.",
        ),
    )
    await orchestrator.ingest_event(
        session_id=session.session_id,
        request=EventIngestRequest(
            event_type=EventType.CANDIDATE_MESSAGE,
            telemetry=TelemetryPacket(
                candidate_message="I would isolate queues, check health endpoints, and rollback safely.",
                stress_index=0.21,
                raw_vector_hash="6f1f4dc566f90f5ecf98ee4f710a9f8c",
            ),
            raw_payload={
                "technical_evidence": {
                    "command_log": ["kubectl get pods", "kubectl rollout undo deploy/api"],
                    "hidden_tests": [
                        {
                            "test_name": "recovery-check",
                            "passed": True,
                            "duration_ms": 125,
                            "detail": "primary path recovered",
                        }
                    ],
                    "health_checks": [
                        {
                            "check_name": "api-health",
                            "healthy": True,
                            "detail": "200 OK",
                        }
                    ],
                    "final_system_state": {"api": "healthy", "queue_depth": "stable"},
                },
                "evidence_complete": True,
            },
        ),
    )
    return session.session_id


@pytest.mark.asyncio
async def test_finalize_session_creates_review_pending_report(tmp_path) -> None:
    orchestrator = await _build_orchestrator(tmp_path)
    session_id = await _seed_session(orchestrator)

    report = await orchestrator.finalize_session(
        session_id=session_id,
        request=FinalizeInterviewRequest(summary_note="Interview completed."),
    )
    snapshot = await orchestrator.get_session(session_id)

    assert report.session_id == session_id
    assert report.locked_technical_verdict.locked is True
    assert snapshot.session_status == SessionStatus.REVIEW_PENDING
    assert snapshot.report_available is True
    assert snapshot.technical.technical_verdict is not None


@pytest.mark.asyncio
async def test_human_review_updates_session_and_report(tmp_path) -> None:
    orchestrator = await _build_orchestrator(tmp_path)
    session_id = await _seed_session(orchestrator)
    await orchestrator.finalize_session(
        session_id=session_id,
        request=FinalizeInterviewRequest(summary_note="Ready for governance review."),
    )

    review = await orchestrator.record_human_review(
        session_id=session_id,
        request=HumanReviewDecisionRequest(
            reviewer_id="reviewer-007",
            decision=HumanDecision.APPROVE,
            rationale="Evidence package is consistent and human-validated.",
        ),
    )
    snapshot = await orchestrator.get_session(session_id)
    report = await orchestrator.get_final_report(session_id)

    assert review.decision == HumanDecision.APPROVE
    assert snapshot.session_status == SessionStatus.APPROVED
    assert snapshot.human_decision == HumanDecision.APPROVE
    assert report.human_approval_required is False


@pytest.mark.asyncio
async def test_finalized_session_blocks_further_events(tmp_path) -> None:
    orchestrator = await _build_orchestrator(tmp_path)
    session_id = await _seed_session(orchestrator)
    await orchestrator.finalize_session(
        session_id=session_id,
        request=FinalizeInterviewRequest(summary_note="Freeze interview state."),
    )

    with pytest.raises(RuntimeError):
        await orchestrator.ingest_event(
            session_id=session_id,
            request=EventIngestRequest(
                event_type=EventType.CANDIDATE_MESSAGE,
                telemetry=TelemetryPacket(
                    candidate_message="This event should be rejected.",
                    raw_vector_hash="6f1f4dc566f90f5ecf98ee4f710a9f8c",
                ),
            ),
        )


@pytest.mark.asyncio
async def test_observability_and_agent_cards_available(tmp_path) -> None:
    orchestrator = await _build_orchestrator(tmp_path)
    session_id = await _seed_session(orchestrator)

    observability = await orchestrator.get_observability(session_id)
    cards = orchestrator.get_agent_cards()

    assert observability.total_traces == 11
    assert observability.latest_technical_score > 0
    assert len(cards) == 4


@pytest.mark.asyncio
async def test_missing_webcam_consent_disables_overlay_without_blocking_interview(tmp_path) -> None:
    orchestrator = await _build_orchestrator(tmp_path)
    session = await orchestrator.create_session(
        request=InterviewSessionCreate(
            candidate_id="candidate-2",
            candidate_role="Site Reliability Engineer",
            language="en",
        )
    )

    snapshot = await orchestrator.ingest_event(
        session_id=session.session_id,
        request=EventIngestRequest(
            event_type=EventType.WEBCAM_FRAME,
            telemetry=TelemetryPacket(
                raw_vector_hash="6f1f4dc566f90f5ecf98ee4f710a9f8c",
            ),
            raw_payload={"video_frame": "data:image/jpeg;base64,abc123"},
        ),
    )
    live = await orchestrator.generate_live_response(
        session_id=session.session_id,
        request=LiveConversationRequest(prompt="Give me a neutral hint.", locale="en"),
    )

    assert snapshot.event_count == 1
    assert snapshot.last_route_target is not None
    assert snapshot.overlay.overlay_enabled is False
    assert live.safe_for_candidate is True
    assert "neutral hint" in live.response_text.lower()


@pytest.mark.asyncio
async def test_audit_export_contains_separate_planes(tmp_path) -> None:
    orchestrator = await _build_orchestrator(tmp_path)
    session_id = await _seed_session(orchestrator)

    audit = await orchestrator.get_audit_export(session_id)

    assert audit.snapshot.technical.contamination_check_passed is True
    assert audit.snapshot.overlay.excluded_from_automated_scoring is True
    assert len(audit.milestones) >= 1


@pytest.mark.asyncio
async def test_legacy_session_state_is_normalized_on_read(tmp_path) -> None:
    orchestrator = await _build_orchestrator(tmp_path)
    session_id = "legacy-session-1"
    await orchestrator.storage.upsert_session_state(
        session_id=session_id,
        candidate_id="candidate-legacy",
        candidate_role="Platform Engineer",
        state={
            "session_id": session_id,
            "candidate_id": "candidate-legacy",
            "candidate_role": "Platform Engineer",
            "language": "en",
            "candidate_score": "88.5",
            "latest_recommendation": "advance",
            "current_stress_level": "0.62",
            "session_status": "active",
            "simulation_status": "legacy_runtime",
            "event_count": 3,
        },
    )

    snapshot = await orchestrator.get_session(session_id)
    overlay = await orchestrator.get_overlay(session_id)

    assert snapshot.technical.technical_score == 88.5
    assert snapshot.technical.technical_verdict is not None
    assert snapshot.technical.technical_verdict.recommendation.value == "advance"
    assert overlay.latest_stress_index == 0.62
    assert overlay.excluded_from_automated_scoring is True


@pytest.mark.asyncio
async def test_contaminated_technical_evidence_is_rejected(tmp_path) -> None:
    orchestrator = await _build_orchestrator(tmp_path)
    session = await orchestrator.create_session(
        request=InterviewSessionCreate(
            candidate_id="candidate-3",
            candidate_role="Platform Engineer",
            language="en",
        )
    )

    with pytest.raises(ValueError):
        await orchestrator.ingest_event(
            session_id=session.session_id,
            request=EventIngestRequest(
                event_type=EventType.CANDIDATE_MESSAGE,
                telemetry=TelemetryPacket(
                    candidate_message="Rollback and restore health checks.",
                    raw_vector_hash="6f1f4dc566f90f5ecf98ee4f710a9f8c",
                ),
                raw_payload={
                    "technical_evidence": {
                        "heart_rate_bpm": 150,
                    }
                },
            ),
        )


@pytest.mark.asyncio
async def test_a2a_handshake_returns_least_privilege_capabilities(tmp_path) -> None:
    orchestrator = await _build_orchestrator(tmp_path)
    response = orchestrator.perform_a2a_handshake(
        A2AHandshakeRequest(
            requester_agent_id="orchestrator",
            target_agent_id="forensics",
            requested_capabilities=[
                "identity-verification",
                "nonexistent-capability",
            ],
            nonce="nonce-12345678",
        )
    )

    assert response.accepted is True
    assert response.approved_capabilities == ["identity-verification"]
    assert response.handshake_token
