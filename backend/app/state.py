from __future__ import annotations

import operator
from datetime import UTC, datetime
from typing import Annotated

from typing_extensions import TypedDict

from app.contracts import (
    ActionExecutionResult,
    CandidateEvent,
    ConsentRecord,
    ConsensusResult,
    HumanDecision,
    InterviewMilestoneSnapshot,
    L0RouteDecision,
    MemoryUpdate,
    ModelTier,
    ObservationResult,
    OverlayCollectionMode,
    PerceptionResult,
    PlanningResult,
    ReasoningResult,
    ScenarioId,
    SessionStatus,
    TechnicalScorePlane,
    TechnicalScoringInput,
    TelemetryOverlayPlane,
    TraceEvent,
)


class InterviewGraphState(TypedDict, total=False):
    session_id: str
    candidate_id: str
    candidate_role: str
    language: str
    scenario_id: ScenarioId

    current_event: CandidateEvent
    consent_record: ConsentRecord | None

    route_decision: L0RouteDecision
    perception: PerceptionResult
    reasoning: ReasoningResult
    consensus: ConsensusResult
    plan: PlanningResult
    action_result: ActionExecutionResult
    observation: ObservationResult
    memory_update: MemoryUpdate
    technical_scoring_input: TechnicalScoringInput

    technical_plane: TechnicalScorePlane
    overlay_plane: TelemetryOverlayPlane

    session_status: SessionStatus
    simulation_status: str
    event_count: int
    last_route_target: ModelTier | None
    report_available: bool
    human_decision: HumanDecision | None
    completed_at_utc: datetime | None
    updated_at_utc: datetime

    trace_events: Annotated[list[TraceEvent], operator.add]
    milestones: Annotated[list[InterviewMilestoneSnapshot], operator.add]


def default_scenario(candidate_role: str) -> ScenarioId:
    role = candidate_role.lower()
    if "platform" in role or "site reliability" in role or "sre" in role:
        return ScenarioId.KUBERNETES_OUTAGE_RECOVERY
    if "architect" in role:
        return ScenarioId.ARCHITECTURE_DEBUGGING
    if "algorithm" in role or "backend" in role:
        return ScenarioId.ALGORITHM_CODING_TASK
    return ScenarioId.PR_CRISIS_RESOLUTION


def base_state(
    session_id: str,
    candidate_id: str,
    candidate_role: str,
    language: str = "en",
    scenario_id: ScenarioId | None = None,
) -> InterviewGraphState:
    selected_scenario = scenario_id or default_scenario(candidate_role)
    technical_plane = TechnicalScorePlane(scenario_id=selected_scenario)
    overlay_plane = TelemetryOverlayPlane(
        overlay_enabled=False,
        collection_mode=OverlayCollectionMode.DISABLED,
    )
    return {
        "session_id": session_id,
        "candidate_id": candidate_id,
        "candidate_role": candidate_role,
        "language": language,
        "scenario_id": selected_scenario,
        "consent_record": None,
        "technical_plane": technical_plane,
        "overlay_plane": overlay_plane,
        "session_status": SessionStatus.IDLE,
        "simulation_status": "idle",
        "event_count": 0,
        "last_route_target": None,
        "report_available": False,
        "human_decision": None,
        "completed_at_utc": None,
        "updated_at_utc": datetime.now(UTC),
        "trace_events": [],
        "milestones": [],
    }
