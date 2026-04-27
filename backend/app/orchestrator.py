from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import UTC, datetime
from uuid import uuid4

from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError

_log = logging.getLogger(__name__)

from app.contracts import (
    A2AHandshakeRequest,
    A2AHandshakeResponse,
    AgentCard,
    CandidateEvent,
    ConsentCaptureRequest,
    ConsentRecord,
    EventIngestRequest,
    EventType,
    FinalizeInterviewRequest,
    GlassBoxReport,
    HumanDecision,
    HumanReviewDecisionRequest,
    HumanReviewRecord,
    InterviewMilestoneSnapshot,
    InterviewSessionCreate,
    InterviewSessionSnapshot,
    LiveConversationRequest,
    LiveConversationResponse,
    ModelTier,
    ObservabilitySnapshot,
    SessionAuditExport,
    SessionStatus,
    TechnicalTaskArtifact,
    TelemetryOverlayPlane,
    TraceEvent,
)
from app.graph import InterviewGraphEngine
from app.services.a2a import A2AService
from app.services.agent_registry import AgentRegistryService
from app.services.agno_tools import AgnoToolService
from app.services.live_interface import LiveInterfaceService
from app.services.observability import ObservabilityService
from app.services.reporting import ReportService
from app.services.storage import Storage
from app.services.stream_hub import StreamHub
from app.services.technical_scoring import TechnicalScoringService
from app.state import base_state


class InterviewOrchestrator:
    def __init__(
        self,
        storage: Storage,
        graph_engine: InterviewGraphEngine,
        agno_tools: AgnoToolService,
        report_service: ReportService,
        observability_service: ObservabilityService,
        technical_scoring_service: TechnicalScoringService,
        agent_registry: AgentRegistryService,
        live_interface_service: LiveInterfaceService,
        a2a_service: A2AService,
        stream_hub: StreamHub,
        trace_history_limit: int = 400,
    ) -> None:
        self.storage = storage
        self.graph_engine = graph_engine
        self.agno_tools = agno_tools
        self.report_service = report_service
        self.observability_service = observability_service
        self.technical_scoring_service = technical_scoring_service
        self.agent_registry = agent_registry
        self.live_interface_service = live_interface_service
        self.a2a_service = a2a_service
        self.stream_hub = stream_hub
        self.trace_history_limit = trace_history_limit
        self._session_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def create_session(self, request: InterviewSessionCreate) -> InterviewSessionSnapshot:
        session_id = str(uuid4())
        state = base_state(
            session_id=session_id,
            candidate_id=request.candidate_id,
            candidate_role=request.candidate_role,
            language=request.language,
            scenario_id=request.scenario_id,
        )
        state["session_status"] = SessionStatus.ACTIVE
        await self.storage.upsert_session_state(
            session_id=session_id,
            candidate_id=request.candidate_id,
            candidate_role=request.candidate_role,
            state=jsonable_encoder(state),
        )
        await self.storage.save_technical_plane(session_id, state["technical_plane"])
        await self.storage.save_overlay_plane(session_id, state["overlay_plane"])
        snapshot = _snapshot_from_state(state, [], [], None)
        await self.stream_hub.publish(
            session_id,
            {"type": "session_created", "snapshot": snapshot.model_dump(mode="json")},
        )
        return snapshot

    async def get_session(self, session_id: str) -> InterviewSessionSnapshot:
        snapshot, _, _ = await self._load_session_context(session_id)
        return snapshot

    async def capture_consent(
        self,
        session_id: str,
        request: ConsentCaptureRequest,
    ) -> ConsentRecord:
        lock = self._session_locks[session_id]
        async with lock:
            state = await self.storage.load_session_state(session_id)
            if state is None:
                raise KeyError(session_id)

            record = ConsentRecord(
                session_id=session_id,
                telemetry_collection_allowed=request.telemetry_collection_allowed,
                biometric_processing_allowed=request.biometric_processing_allowed,
                jurisdiction=request.jurisdiction,
                disclosure_text=request.disclosure_text,
                source=request.source,
                recorded_by=request.recorded_by,
            )
            await self.storage.save_consent_record(record)
            state["consent_record"] = record.model_dump(mode="json")
            state["updated_at_utc"] = datetime.now(UTC)
            await self.storage.upsert_session_state(
                session_id=session_id,
                candidate_id=str(state["candidate_id"]),
                candidate_role=str(state["candidate_role"]),
                state=jsonable_encoder(state),
            )

            snapshot, _, _ = await self._load_session_context(session_id)
            await self.stream_hub.publish(
                session_id,
                {"type": "consent_captured", "snapshot": snapshot.model_dump(mode="json")},
            )
            return record

    async def ingest_event(
        self,
        session_id: str,
        request: EventIngestRequest,
    ) -> InterviewSessionSnapshot:
        lock = self._session_locks[session_id]
        async with lock:
            state = await self.storage.load_session_state(session_id)
            if state is None:
                raise KeyError(session_id)
            if state.get("session_status") in {
                SessionStatus.REVIEW_PENDING,
                SessionStatus.APPROVED,
                SessionStatus.REJECTED,
                SessionStatus.REVIEW_PENDING.value,
                SessionStatus.APPROVED.value,
                SessionStatus.REJECTED.value,
            }:
                raise RuntimeError("session is finalized and no longer accepts interview events")

            consent = await self.storage.load_consent_record(session_id)
            technical_plane = await self.storage.load_technical_plane(session_id)
            overlay_plane = await self.storage.load_overlay_plane(session_id)
            state = self._normalize_runtime_state(
                state=state,
                technical_plane=technical_plane,
                overlay_plane=overlay_plane,
                consent_record=consent,
            )

            event = CandidateEvent(
                session_id=session_id,
                event_type=request.event_type,
                telemetry=request.telemetry,
                raw_payload=request.raw_payload,
                requested_scenario=request.scenario_id,
            )
            event = await self._enrich_event(event, consent)

            state["current_event"] = event
            state["event_count"] = int(state.get("event_count", 0)) + 1
            state["session_status"] = SessionStatus.ACTIVE
            state["updated_at_utc"] = datetime.now(UTC)
            state["trace_events"] = []
            state["milestones"] = []
            if event.requested_scenario is not None:
                state["scenario_id"] = event.requested_scenario

            updated_state = await self.graph_engine.run(state)
            trace_events = [
                trace if isinstance(trace, TraceEvent) else TraceEvent.model_validate(trace)
                for trace in updated_state.get("trace_events", [])
            ]
            milestone_records = [
                item
                if isinstance(item, InterviewMilestoneSnapshot)
                else InterviewMilestoneSnapshot.model_validate(item)
                for item in updated_state.get("milestones", [])
            ]

            for trace in trace_events:
                await self.storage.append_trace_event(
                    session_id=session_id,
                    trace_event=trace.model_dump(mode="json"),
                )
            for milestone in milestone_records:
                await self.storage.append_milestone_snapshot(milestone)

            route_decision = updated_state.get("route_decision")
            if route_decision is not None:
                target_tier = getattr(route_decision, "target_tier", None)
                if target_tier is None and isinstance(route_decision, dict):
                    target_tier = route_decision.get("target_tier")
                updated_state["last_route_target"] = target_tier

            if "technical_plane" in updated_state:
                await self.storage.save_technical_plane(
                    session_id,
                    updated_state["technical_plane"],
                )
            if "overlay_plane" in updated_state:
                await self.storage.save_overlay_plane(
                    session_id,
                    updated_state["overlay_plane"],
                )

            state_to_save = jsonable_encoder(updated_state)
            state_to_save.pop("trace_events", None)
            state_to_save.pop("milestones", None)
            await self.storage.upsert_session_state(
                session_id=session_id,
                candidate_id=str(state_to_save.get("candidate_id", "")),
                candidate_role=str(state_to_save.get("candidate_role", "")),
                state=state_to_save,
            )

            snapshot, _, _ = await self._load_session_context(session_id)
            await self.stream_hub.publish(
                session_id,
                {"type": "event_processed", "snapshot": snapshot.model_dump(mode="json")},
            )
            return snapshot

    async def list_trace_events(self, session_id: str, limit: int = 200) -> list[TraceEvent]:
        state = await self.storage.load_session_state(session_id)
        if state is None:
            raise KeyError(session_id)
        rows = await self.storage.fetch_trace_events(session_id=session_id, limit=limit)
        return [TraceEvent.model_validate(row) for row in rows]

    async def list_milestones(
        self,
        session_id: str,
        limit: int = 200,
    ) -> list[InterviewMilestoneSnapshot]:
        state = await self.storage.load_session_state(session_id)
        if state is None:
            raise KeyError(session_id)
        return await self.storage.fetch_milestones(session_id=session_id, limit=limit)

    async def get_technical_artifacts(self, session_id: str) -> list[TechnicalTaskArtifact]:
        snapshot = await self.get_session(session_id)
        return snapshot.technical.evidence_bundle

    async def get_overlay(self, session_id: str) -> TelemetryOverlayPlane:
        state = await self.storage.load_session_state(session_id)
        if state is None:
            raise KeyError(session_id)
        plane = await self.storage.load_overlay_plane(session_id)
        if plane is None:
            plane = type_hint_overlay(state.get("overlay_plane"), state)
            await self.storage.save_overlay_plane(session_id, plane)
        return plane

    async def get_review_segments(self, session_id: str):
        overlay = await self.get_overlay(session_id)
        return overlay.review_segments

    async def build_glass_box_report(
        self,
        session_id: str,
        summary_note: str | None = None,
    ) -> GlassBoxReport:
        snapshot, traces, _ = await self._load_session_context(session_id)
        latest_review = await self.storage.fetch_latest_human_review(session_id)
        report = await self.report_service.build_report(
            snapshot=snapshot,
            traces=traces,
            summary_note=summary_note,
            latest_review=latest_review,
        )
        return report

    async def finalize_session(
        self,
        session_id: str,
        request: FinalizeInterviewRequest,
    ) -> GlassBoxReport:
        lock = self._session_locks[session_id]
        async with lock:
            state = await self.storage.load_session_state(session_id)
            if state is None:
                raise KeyError(session_id)

            trace_count = len(
                await self.storage.fetch_trace_events(
                    session_id=session_id,
                    limit=max(self.trace_history_limit, 1),
                )
            )
            if trace_count == 0 and not request.force:
                raise ValueError("cannot finalize a session with no trace evidence")

            technical_plane = await self.storage.load_technical_plane(session_id)
            if technical_plane is None:
                technical_plane = type_hint_technical(state.get("technical_plane"), state)
                await self.storage.save_technical_plane(session_id, technical_plane)
            if technical_plane.technical_verdict is None:
                raise ValueError("cannot finalize a session without technical scoring evidence")
            technical_plane = self.technical_scoring_service.lock_plane(technical_plane)
            await self.storage.save_technical_plane(session_id, technical_plane)

            state["technical_plane"] = technical_plane.model_dump(mode="json")
            state["session_status"] = SessionStatus.REVIEW_PENDING
            state["simulation_status"] = "final_report_export"
            state["completed_at_utc"] = datetime.now(UTC)
            state["updated_at_utc"] = datetime.now(UTC)

            await self.storage.upsert_session_state(
                session_id=session_id,
                candidate_id=str(state["candidate_id"]),
                candidate_role=str(state["candidate_role"]),
                state=jsonable_encoder(state),
            )

            report = await self.build_glass_box_report(
                session_id=session_id,
                summary_note=request.summary_note,
            )
            await self.storage.save_final_report(report)

            state["report_available"] = True
            state["technical_plane"] = technical_plane.model_dump(mode="json")
            await self.storage.upsert_session_state(
                session_id=session_id,
                candidate_id=str(state["candidate_id"]),
                candidate_role=str(state["candidate_role"]),
                state=jsonable_encoder(state),
            )

            overlay_plane = await self.storage.load_overlay_plane(session_id)
            review_segments = overlay_plane.review_segments if overlay_plane is not None else []
            milestone = InterviewMilestoneSnapshot(
                session_id=session_id,
                stage="final_report_export",
                event_count=int(state.get("event_count", 0)),
                trace_count=trace_count,
                technical_score=technical_plane.technical_score,
                technical_recommendation=technical_plane.technical_verdict.recommendation,
                overlay_enabled=overlay_plane.overlay_enabled if overlay_plane is not None else False,
                overlay_segment_count=len(review_segments),
                simulation_status="final_report_export",
                note="Technical verdict locked and report exported for human review.",
            )
            await self.storage.append_milestone_snapshot(milestone)

            await self.stream_hub.publish(
                session_id,
                {"type": "session_finalized", "report": report.model_dump(mode="json")},
            )
            return report

    async def record_human_review(
        self,
        session_id: str,
        request: HumanReviewDecisionRequest,
    ) -> HumanReviewRecord:
        lock = self._session_locks[session_id]
        async with lock:
            state = await self.storage.load_session_state(session_id)
            if state is None:
                raise KeyError(session_id)

            report = await self.storage.load_final_report(session_id)
            if report is None:
                raise ValueError("session must be finalized before human review")

            review = HumanReviewRecord(
                session_id=session_id,
                reviewer_id=request.reviewer_id,
                decision=request.decision,
                rationale=request.rationale,
                cryptographic_acknowledgement=request.cryptographic_acknowledgement,
            )
            await self.storage.append_human_review(review)

            state["human_decision"] = request.decision
            state["session_status"] = (
                SessionStatus.APPROVED
                if request.decision == HumanDecision.APPROVE
                else SessionStatus.REJECTED
            )
            state["simulation_status"] = "human_signoff"
            state["updated_at_utc"] = datetime.now(UTC)
            await self.storage.upsert_session_state(
                session_id=session_id,
                candidate_id=str(state["candidate_id"]),
                candidate_role=str(state["candidate_role"]),
                state=jsonable_encoder(state),
            )

            refreshed_report = await self.build_glass_box_report(session_id=session_id)
            await self.storage.save_final_report(refreshed_report)
            snapshot = await self.get_session(session_id)
            await self.stream_hub.publish(
                session_id,
                {
                    "type": "human_review_recorded",
                    "review": review.model_dump(mode="json"),
                    "snapshot": snapshot.model_dump(mode="json"),
                },
            )
            return review

    async def get_final_report(self, session_id: str) -> GlassBoxReport:
        report = await self.storage.load_final_report(session_id)
        if report is not None:
            return report
        return await self.build_glass_box_report(session_id)

    async def get_observability(self, session_id: str) -> ObservabilitySnapshot:
        snapshot, traces, _ = await self._load_session_context(session_id)
        return self.observability_service.summarize(snapshot=snapshot, traces=traces)

    async def get_audit_export(self, session_id: str) -> SessionAuditExport:
        snapshot, traces, milestones = await self._load_session_context(session_id)
        return SessionAuditExport(
            snapshot=snapshot,
            report=await self.storage.load_final_report(session_id),
            consent_record=await self.storage.load_consent_record(session_id),
            milestones=milestones,
            trace_events=traces,
        )

    def get_agent_cards(self) -> list[AgentCard]:
        return self.agent_registry.issue_default_cards()

    async def generate_live_response(
        self,
        session_id: str,
        request: LiveConversationRequest,
    ) -> LiveConversationResponse:
        snapshot = await self.get_session(session_id)
        return await self.live_interface_service.respond(snapshot=snapshot, request=request)

    def perform_a2a_handshake(
        self,
        request: A2AHandshakeRequest,
    ) -> A2AHandshakeResponse:
        return self.a2a_service.handshake(request)

    async def _load_session_context(
        self,
        session_id: str,
    ) -> tuple[InterviewSessionSnapshot, list[TraceEvent], list[InterviewMilestoneSnapshot]]:
        state = await self.storage.load_session_state(session_id)
        if state is None:
            raise KeyError(session_id)

        trace_rows = await self.storage.fetch_trace_events(
            session_id=session_id,
            limit=min(self.trace_history_limit, 500),
        )
        traces = [TraceEvent.model_validate(row) for row in trace_rows]
        milestones = await self.storage.fetch_milestones(
            session_id=session_id,
            limit=min(self.trace_history_limit, 500),
        )
        report = await self.storage.load_final_report(session_id)
        latest_review = await self.storage.fetch_latest_human_review(session_id)
        technical_plane = await self.storage.load_technical_plane(session_id)
        overlay_plane = await self.storage.load_overlay_plane(session_id)
        consent_record = await self.storage.load_consent_record(session_id)

        enriched_state = dict(state)
        enriched_state["report_available"] = report is not None
        if latest_review is not None:
            enriched_state["human_decision"] = latest_review.decision
        enriched_state = self._normalize_runtime_state(
            state=enriched_state,
            technical_plane=technical_plane,
            overlay_plane=overlay_plane,
            consent_record=consent_record,
        )

        return _snapshot_from_state(enriched_state, traces, milestones, consent_record), traces, milestones

    async def _enrich_event(
        self,
        event: CandidateEvent,
        consent: ConsentRecord | None,
    ) -> CandidateEvent:
        overlay_allowed = bool(
            consent
            and consent.telemetry_collection_allowed
            and consent.biometric_processing_allowed
        )
        if (
            overlay_allowed
            and event.event_type == EventType.WEBCAM_FRAME
            and event.raw_payload.get("video_frame")
            and event.telemetry.heart_rate_bpm is None
        ):
            rppg = await self.agno_tools.extract_rppg_pulse(
                str(event.raw_payload["video_frame"])
            )
            try:
                event.telemetry.heart_rate_bpm = int(rppg["pulse_bpm"])
                event.telemetry.rppg_confidence = float(rppg["confidence"])
            except ValidationError as exc:
                # ANOMALY_WARNING: rPPG values are outside physiological bounds
                # (heart_rate_bpm must be 30–220 bpm; confidence must be 0.0–1.0).
                # The biometric fields are intentionally left as None so the
                # LangGraph state can proceed without a 500 crash or data loss.
                # This warning is operator-visible in structured server logs.
                _log.warning(
                    "ANOMALY_WARNING | rPPG enrichment discarded — out-of-range biometric "
                    "payload. session_id=%s pulse_bpm=%s confidence=%s validation_error=%s",
                    event.session_id,
                    rppg.get("pulse_bpm"),
                    rppg.get("confidence"),
                    exc,
                )
        return event

    def _normalize_runtime_state(
        self,
        *,
        state: dict,
        technical_plane,
        overlay_plane,
        consent_record: ConsentRecord | None,
    ) -> dict:
        normalized = dict(state)
        technical = type_hint_technical(
            technical_plane if technical_plane is not None else normalized.get("technical_plane"),
            normalized,
        )
        overlay = type_hint_overlay(
            overlay_plane if overlay_plane is not None else normalized.get("overlay_plane"),
            normalized,
        )
        normalized["scenario_id"] = normalized.get("scenario_id") or technical.scenario_id
        normalized["technical_plane"] = technical
        normalized["overlay_plane"] = overlay
        if consent_record is not None:
            normalized["consent_record"] = consent_record
        return normalized


def _snapshot_from_state(
    state: dict,
    trace_events: list[TraceEvent],
    milestones: list[InterviewMilestoneSnapshot],
    consent_record: ConsentRecord | None,
) -> InterviewSessionSnapshot:
    technical = type_hint_technical(state.get("technical_plane"), state)
    overlay = type_hint_overlay(state.get("overlay_plane"), state)
    return InterviewSessionSnapshot(
        session_id=str(state["session_id"]),
        candidate_id=str(state["candidate_id"]),
        candidate_role=str(state["candidate_role"]),
        language=str(state.get("language", "en")),
        scenario_id=state.get("scenario_id") or technical.scenario_id,
        technical=technical,
        overlay=overlay,
        session_status=SessionStatus(state.get("session_status", SessionStatus.IDLE)),
        simulation_status=str(state.get("simulation_status", "idle")),
        event_count=int(state.get("event_count", 0)),
        last_route_target=_as_optional_enum(ModelTier, state.get("last_route_target")),
        report_available=bool(state.get("report_available", False)),
        human_decision=_as_optional_enum(HumanDecision, state.get("human_decision")),
        consent_record=consent_record,
        completed_at_utc=_as_optional_datetime(state.get("completed_at_utc")),
        last_updated_utc=_as_datetime(state.get("updated_at_utc")),
        trace_events=trace_events,
        milestone_count=len(milestones),
    )


def type_hint_technical(technical_plane, state):
    from app.contracts import CandidateRecommendation, TechnicalScorePlane, TechnicalVerdict
    from app.state import default_scenario

    if technical_plane is not None:
        return TechnicalScorePlane.model_validate(technical_plane)
    scenario_id = state.get("scenario_id") or default_scenario(str(state.get("candidate_role", "")))
    legacy_score = _coerce_percentage(state.get("candidate_score"))
    legacy_recommendation = state.get("latest_recommendation")
    verdict = None
    if legacy_recommendation:
        try:
            recommendation = CandidateRecommendation(str(legacy_recommendation).lower())
        except ValueError:
            recommendation = None
        if recommendation is not None:
            verdict = TechnicalVerdict(
                recommendation=recommendation,
                score=legacy_score,
                max_score=100.0,
                normalized_score=legacy_score,
                passed=recommendation == CandidateRecommendation.ADVANCE,
                rationale="Derived from legacy single-plane session state during compatibility fallback.",
                locked=bool(state.get("report_available", False)),
            )
    return TechnicalScorePlane(
        scenario_id=scenario_id,
        technical_score=legacy_score,
        technical_verdict=verdict,
        locked=bool(state.get("report_available", False)),
        contamination_check_passed=True,
    )


def type_hint_overlay(overlay_plane, state):
    from app.contracts import OverlayCollectionMode, TelemetryOverlayPlane

    if overlay_plane is not None:
        return TelemetryOverlayPlane.model_validate(overlay_plane)
    legacy_stress = _coerce_unit_interval(state.get("current_stress_level"))
    return TelemetryOverlayPlane(
        collection_mode=OverlayCollectionMode.DISABLED,
        latest_stress_index=legacy_stress,
        excluded_from_automated_scoring=True,
    )


def _as_datetime(value) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    return datetime.now(UTC)


def _as_optional_datetime(value) -> datetime | None:
    if value is None:
        return None
    return _as_datetime(value)


def _as_optional_enum(enum_cls, value):
    if value is None or value == "":
        return None
    if isinstance(value, enum_cls):
        return value
    return enum_cls(value)


def _coerce_percentage(value) -> float:
    if value is None:
        return 0.0
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(numeric, 100.0))


def _coerce_unit_interval(value) -> float | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(numeric, 1.0))
