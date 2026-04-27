from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

_BIOMETRIC_INPUT_KEYS = {
    "heart_rate_bpm",
    "stress_index",
    "rppg_confidence",
    "raw_vector_hash",
    "telemetry",
    "biometric_vector",
    "biometric_signal",
}


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True, str_strip_whitespace=True)


class EventType(StrEnum):
    AUDIO_CHUNK = "audio_chunk"
    WEBCAM_FRAME = "webcam_frame"
    CODE_DELTA = "code_delta"
    CANDIDATE_MESSAGE = "candidate_message"
    SYSTEM_SIGNAL = "system_signal"
    INTEGRITY_FLAG = "INTEGRITY_FLAG"


class ModelTier(StrEnum):
    FLASH_LITE = "gemini-3.1-flash-lite"
    LIVE = "gemini-live"
    PRO = "gemini-3.1-pro"


class SessionStatus(StrEnum):
    IDLE = "idle"
    ACTIVE = "active"
    REVIEW_PENDING = "review_pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class HumanDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"


class CandidateRecommendation(StrEnum):
    ADVANCE = "advance"
    HOLD = "hold"
    REJECT = "reject"


class ScenarioId(StrEnum):
    KUBERNETES_OUTAGE_RECOVERY = "kubernetes_outage_recovery"
    ALGORITHM_CODING_TASK = "algorithm_coding_task"
    PR_CRISIS_RESOLUTION = "pr_crisis_resolution"
    ARCHITECTURE_DEBUGGING = "architecture_debugging"


class ArtifactType(StrEnum):
    COMMAND_LOG = "command_log"
    DIFF_PATCH = "diff_patch"
    HIDDEN_TEST_RESULTS = "hidden_test_results"
    HEALTH_CHECK = "health_check"
    SANDBOX_EVENT_STREAM = "sandbox_event_stream"
    FINAL_SYSTEM_STATE = "final_system_state"


class TechnicalOutcomeStatus(StrEnum):
    PASSED = "passed"
    PARTIAL = "partial"
    FAILED = "failed"


class ConsentSource(StrEnum):
    SYSTEM_DEFAULT = "system_default"
    CANDIDATE_UI = "candidate_ui"
    OPERATOR_OVERRIDE = "operator_override"


class OverlayCollectionMode(StrEnum):
    DISABLED = "disabled"
    ACTIVE = "active"


class TelemetryPacket(StrictBaseModel):
    timestamp_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))
    audio_text: str | None = Field(default=None, max_length=12_000)
    code_delta: str | None = Field(default=None, max_length=40_000)
    candidate_message: str | None = Field(default=None, max_length=6_000)
    heart_rate_bpm: int | None = Field(default=None, ge=30, le=220)
    stress_index: float | None = Field(default=None, ge=0.0, le=1.0)
    silence_ms: int = Field(default=0, ge=0, le=60_000)
    rppg_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    raw_vector_hash: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{32,128}$")

    @model_validator(mode="after")
    def ensure_semantic_content(self) -> TelemetryPacket:
        has_content = any(
            [
                self.audio_text,
                self.code_delta,
                self.candidate_message,
                self.heart_rate_bpm is not None,
                self.stress_index is not None,
                self.rppg_confidence is not None,
                self.raw_vector_hash,
                self.silence_ms > 0,
            ]
        )
        if not has_content:
            raise ValueError("telemetry packet must include at least one semantic signal")
        return self


class CandidateEvent(StrictBaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str
    event_type: EventType
    telemetry: TelemetryPacket
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    requested_scenario: ScenarioId | None = None


class EventIngestRequest(StrictBaseModel):
    event_type: EventType
    telemetry: TelemetryPacket
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    scenario_id: ScenarioId | None = None


class L0RouteDecision(StrictBaseModel):
    pass_through: bool
    reason: str
    target_tier: ModelTier = ModelTier.FLASH_LITE
    tokens_saved_estimate: int = Field(default=0, ge=0)
    fallback_used: bool = False
    routed_lane: Literal["candidate_safe", "security_escalation", "tool_recovery"] = (
        "candidate_safe"
    )


class PerceptionResult(StrictBaseModel):
    intent_label: str
    complexity_score: float = Field(ge=0.0, le=1.0)
    risk_flags: list[str] = Field(default_factory=list)
    normalized_payload: dict[str, Any] = Field(default_factory=dict)


class ReasoningResult(StrictBaseModel):
    reasoning_summary: str
    confidence: float = Field(ge=0.0, le=1.0)
    vulnerability_signals: list[str] = Field(default_factory=list)
    intervention_required: bool


class DebatePosition(StrictBaseModel):
    agent_name: str
    position: str
    confidence: float = Field(ge=0.0, le=1.0)


class ConsensusResult(StrictBaseModel):
    positions: list[DebatePosition] = Field(default_factory=list)
    unified_score: float = Field(ge=0.0, le=100.0)
    rationale: str


class DecisionStep(StrictBaseModel):
    order: Literal[1, 2, 3]
    instruction: str
    objective: str


class PlanningResult(StrictBaseModel):
    decision_tree: list[DecisionStep] = Field(min_length=3, max_length=3)
    selected_action: str
    requires_human_gate: bool


class ActionType(StrEnum):
    NOOP = "noop"
    INJECT_HINT = "inject_hint"
    DEPLOY_EPHEMERAL_KUBERNETES = "deploy_ephemeral_kubernetes"
    VERIFY_LATTICE_SIGNATURE = "verify_lattice_signature"
    EXECUTE_NEURO_SYMBOLIC_MAP = "execute_neuro_symbolic_map"


class ToolAction(StrictBaseModel):
    action_type: ActionType
    parameters: dict[str, Any] = Field(default_factory=dict)
    approved_by_zero_trust: bool
    guardrail_reason: str


class ActionExecutionResult(StrictBaseModel):
    status: Literal["completed", "skipped", "blocked", "failed"]
    action: ToolAction
    output: dict[str, Any] = Field(default_factory=dict)


class ObservationResult(StrictBaseModel):
    outcome_label: str
    candidate_reaction_ms: int = Field(ge=0, le=30_000)
    observed_stress_shift: float = Field(ge=-1.0, le=1.0)


class MemoryUpdate(StrictBaseModel):
    short_term_notes: str
    vector_embedding_key: str
    vector_payload: dict[str, Any] = Field(default_factory=dict)


class TraceEvent(StrictBaseModel):
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str
    node: str
    reasoning_path: str
    input_contract: str
    output_contract: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    started_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))
    latency_ms: int = Field(ge=0)


class InterviewSessionCreate(StrictBaseModel):
    candidate_id: str = Field(min_length=2, max_length=128)
    candidate_role: str = Field(min_length=2, max_length=128)
    language: str = Field(default="en")
    scenario_id: ScenarioId | None = None


class HiddenTestResult(StrictBaseModel):
    test_name: str
    passed: bool
    duration_ms: int = Field(default=0, ge=0)
    detail: str = Field(default="", max_length=2_000)


class HealthCheckResult(StrictBaseModel):
    check_name: str
    healthy: bool
    detail: str = Field(default="", max_length=2_000)


class TechnicalScoringInput(StrictBaseModel):
    session_id: str
    event_id: str
    scenario_id: ScenarioId
    event_type: EventType
    candidate_message: str | None = Field(default=None, max_length=6_000)
    code_delta: str | None = Field(default=None, max_length=40_000)
    command_log: list[str] = Field(default_factory=list)
    diff_patch: str | None = Field(default=None, max_length=40_000)
    hidden_tests: list[HiddenTestResult] = Field(default_factory=list)
    health_checks: list[HealthCheckResult] = Field(default_factory=list)
    sandbox_event_stream: list[str] = Field(default_factory=list)
    final_system_state: dict[str, Any] = Field(default_factory=dict)
    time_to_resolution_ms: int = Field(default=0, ge=0)
    failed_action_count: int = Field(default=0, ge=0)
    regression_impact: float = Field(default=0.0, ge=0.0, le=1.0)

    @model_validator(mode="before")
    @classmethod
    def reject_biometric_inputs(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        blocked = sorted(_BIOMETRIC_INPUT_KEYS.intersection(data.keys()))
        if blocked:
            raise ValueError(
                "technical scoring input cannot contain biometric or telemetry fields: "
                + ", ".join(blocked)
            )
        return data


class TechnicalTaskArtifact(StrictBaseModel):
    artifact_id: str = Field(default_factory=lambda: str(uuid4()))
    artifact_type: ArtifactType
    label: str
    content: str
    content_type: str = "text/plain"
    metadata: dict[str, Any] = Field(default_factory=dict)
    captured_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TechnicalRubricScore(StrictBaseModel):
    rubric_id: str
    label: str
    score: float = Field(ge=0.0)
    max_score: float = Field(gt=0.0)
    rationale: str


class TechnicalTaskOutcome(StrictBaseModel):
    outcome_id: str = Field(default_factory=lambda: str(uuid4()))
    scenario_id: ScenarioId
    title: str
    status: TechnicalOutcomeStatus
    summary: str
    duration_ms: int = Field(default=0, ge=0)
    failed_action_count: int = Field(default=0, ge=0)
    regression_impact: float = Field(default=0.0, ge=0.0, le=1.0)
    created_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TechnicalVerdict(StrictBaseModel):
    recommendation: CandidateRecommendation
    score: float = Field(ge=0.0)
    max_score: float = Field(gt=0.0)
    normalized_score: float = Field(ge=0.0, le=100.0)
    passed: bool
    rationale: str
    locked: bool = True
    locked_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))
    contamination_check_passed: bool = True


class TechnicalScorePlane(StrictBaseModel):
    scenario_id: ScenarioId
    technical_score: float = Field(default=0.0, ge=0.0, le=100.0)
    technical_verdict: TechnicalVerdict | None = None
    task_outcomes: list[TechnicalTaskOutcome] = Field(default_factory=list)
    rubric_scores: list[TechnicalRubricScore] = Field(default_factory=list)
    evidence_bundle: list[TechnicalTaskArtifact] = Field(default_factory=list)
    locked: bool = False
    contamination_check_passed: bool = True


class TelemetryOverlayPoint(StrictBaseModel):
    point_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))
    correlated_event_id: str | None = None
    stress_index: float | None = Field(default=None, ge=0.0, le=1.0)
    heart_rate_bpm: int | None = Field(default=None, ge=30, le=220)
    speech_cadence_wpm: float | None = Field(default=None, ge=0.0, le=400.0)
    keystroke_irregularity: float | None = Field(default=None, ge=0.0, le=1.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class TelemetryOverlaySegment(StrictBaseModel):
    segment_id: str = Field(default_factory=lambda: str(uuid4()))
    start_timestamp_utc: datetime
    end_timestamp_utc: datetime
    correlated_event_id: str | None = None
    stress_delta: float = Field(ge=-1.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str


class OperatorReviewSegment(StrictBaseModel):
    segment_id: str = Field(default_factory=lambda: str(uuid4()))
    start_timestamp_utc: datetime
    end_timestamp_utc: datetime
    correlated_simulation_event: str | None = None
    stress_delta: float = Field(ge=-1.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    review_rationale: str
    priority: Literal["low", "medium", "high"] = "medium"


class TelemetryOverlayPlane(StrictBaseModel):
    overlay_enabled: bool = False
    collection_mode: OverlayCollectionMode = OverlayCollectionMode.DISABLED
    telemetry_timeline: list[TelemetryOverlayPoint] = Field(default_factory=list)
    stress_markers: list[TelemetryOverlaySegment] = Field(default_factory=list)
    overlay_segments: list[TelemetryOverlaySegment] = Field(default_factory=list)
    operator_review_flags: list[str] = Field(default_factory=list)
    review_segments: list[OperatorReviewSegment] = Field(default_factory=list)
    latest_stress_index: float | None = Field(default=None, ge=0.0, le=1.0)
    latest_heart_rate_bpm: int | None = Field(default=None, ge=30, le=220)
    overlay_processing_lag_ms: int = Field(default=0, ge=0)
    excluded_from_automated_scoring: bool = True


class ConsentRecord(StrictBaseModel):
    session_id: str
    telemetry_collection_allowed: bool = False
    biometric_processing_allowed: bool = False
    jurisdiction: str = Field(default="unspecified", max_length=128)
    disclosure_text: str = Field(max_length=2_000)
    source: ConsentSource = ConsentSource.SYSTEM_DEFAULT
    recorded_by: str = Field(default="system", min_length=2, max_length=128)
    recorded_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ConsentCaptureRequest(StrictBaseModel):
    telemetry_collection_allowed: bool
    biometric_processing_allowed: bool
    jurisdiction: str = Field(default="unspecified", max_length=128)
    disclosure_text: str = Field(min_length=20, max_length=2_000)
    source: ConsentSource = ConsentSource.CANDIDATE_UI
    recorded_by: str = Field(default="candidate", min_length=2, max_length=128)


class InterviewMilestoneSnapshot(StrictBaseModel):
    milestone_id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str
    stage: str
    captured_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))
    event_count: int = Field(default=0, ge=0)
    trace_count: int = Field(default=0, ge=0)
    technical_score: float = Field(default=0.0, ge=0.0, le=100.0)
    technical_recommendation: CandidateRecommendation | None = None
    overlay_enabled: bool = False
    overlay_segment_count: int = Field(default=0, ge=0)
    simulation_status: str
    note: str = ""


class InterviewSessionSnapshot(StrictBaseModel):
    session_id: str
    candidate_id: str
    candidate_role: str
    language: str = "en"
    scenario_id: ScenarioId
    technical: TechnicalScorePlane
    overlay: TelemetryOverlayPlane
    session_status: SessionStatus = SessionStatus.IDLE
    simulation_status: str = "idle"
    event_count: int = Field(default=0, ge=0)
    last_route_target: ModelTier | None = None
    report_available: bool = False
    human_decision: HumanDecision | None = None
    consent_record: ConsentRecord | None = None
    completed_at_utc: datetime | None = None
    last_updated_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))
    trace_events: list[TraceEvent] = Field(default_factory=list)
    milestone_count: int = Field(default=0, ge=0)


class PhaseStatus(StrEnum):
    PLANNED = "planned"
    ACTIVE = "active"
    BLOCKED = "blocked"
    COMPLETED = "completed"


class PhaseDefinition(StrictBaseModel):
    phase_id: int = Field(ge=1, le=15)
    title: str
    owner_framework: str
    objective: str
    status: PhaseStatus = PhaseStatus.PLANNED


class PhaseRevisionRequest(StrictBaseModel):
    summary: str = Field(min_length=5, max_length=600)
    rationale: str = Field(min_length=5, max_length=2_000)
    status: PhaseStatus


class PhaseRevision(StrictBaseModel):
    phase_id: int = Field(ge=1, le=15)
    summary: str
    rationale: str
    status: PhaseStatus
    revised_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))


class FinalizeInterviewRequest(StrictBaseModel):
    summary_note: str | None = Field(default=None, max_length=1_500)
    force: bool = False


class HumanReviewDecisionRequest(StrictBaseModel):
    reviewer_id: str = Field(min_length=2, max_length=128)
    decision: HumanDecision
    rationale: str = Field(min_length=5, max_length=2_000)
    cryptographic_acknowledgement: bool = True


class HumanReviewRecord(StrictBaseModel):
    session_id: str
    reviewer_id: str
    decision: HumanDecision
    rationale: str
    cryptographic_acknowledgement: bool = True
    decided_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))


class GuardrailFinding(StrictBaseModel):
    rule_id: str
    severity: Literal["low", "medium", "high"]
    detail: str


class GuardrailEnvelope(StrictBaseModel):
    blocked: bool
    sanitized_text: str
    findings: list[GuardrailFinding] = Field(default_factory=list)


class TelemetryOverlaySummary(StrictBaseModel):
    overlay_enabled: bool
    total_points: int = Field(ge=0)
    total_segments: int = Field(ge=0)
    total_review_segments: int = Field(ge=0)
    latest_stress_index: float | None = Field(default=None, ge=0.0, le=1.0)
    latest_heart_rate_bpm: int | None = Field(default=None, ge=30, le=220)
    excluded_from_automated_scoring: bool = True


class GlassBoxReport(StrictBaseModel):
    session_id: str
    locked_technical_verdict: TechnicalVerdict
    technical_rubric_scores: list[TechnicalRubricScore] = Field(default_factory=list)
    technical_task_outcomes: list[TechnicalTaskOutcome] = Field(default_factory=list)
    evidence_references: list[str] = Field(default_factory=list)
    telemetry_overlay_summary: TelemetryOverlaySummary
    operator_review_segments: list[OperatorReviewSegment] = Field(default_factory=list)
    explicit_biometric_exclusion_statement: str
    consensus_summary: str
    reasoning_map: dict[str, Any] = Field(default_factory=dict)
    candidate_safe_summary: str
    trace_count: int = Field(default=0, ge=0)
    human_approval_required: bool = True
    generated_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ObservabilitySnapshot(StrictBaseModel):
    session_id: str
    session_status: SessionStatus
    total_traces: int = Field(ge=0)
    average_latency_ms: float = Field(ge=0.0)
    node_breakdown: dict[str, int] = Field(default_factory=dict)
    estimated_tokens_saved: int = Field(default=0, ge=0)
    drift_flags: list[str] = Field(default_factory=list)
    cost_governor_recommendation: str
    latest_technical_score: float = Field(ge=0.0, le=100.0)
    overlay_processing_lag_ms: int = Field(default=0, ge=0)
    model_fallback_count: int = Field(default=0, ge=0)
    contamination_check_passed: bool = True
    reproducible_from_artifacts: bool = True


class AgentCard(StrictBaseModel):
    agent_id: str
    agent_name: str
    protocol_version: str
    owner_system: str
    model_tier: ModelTier
    capabilities: list[str] = Field(default_factory=list)
    public_key_fingerprint: str
    signature: str
    valid_until_utc: datetime


class LiveConversationRequest(StrictBaseModel):
    prompt: str = Field(min_length=1, max_length=6_000)
    locale: str = Field(default="en")
    channel: Literal["text", "voice"] = "text"


class LiveConversationResponse(StrictBaseModel):
    session_id: str
    channel: Literal["text", "voice"]
    response_text: str
    safe_for_candidate: bool = True
    target_tier: ModelTier = ModelTier.LIVE
    hints_used: list[str] = Field(default_factory=list)
    generated_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))


class A2AHandshakeRequest(StrictBaseModel):
    requester_agent_id: str = Field(min_length=2, max_length=128)
    target_agent_id: str = Field(min_length=2, max_length=128)
    requested_capabilities: list[str] = Field(default_factory=list)
    nonce: str = Field(min_length=8, max_length=256)
    session_id: str | None = None


class A2AHandshakeResponse(StrictBaseModel):
    accepted: bool
    handshake_token: str
    requester_agent_id: str
    target_agent_id: str
    approved_capabilities: list[str] = Field(default_factory=list)
    reason: str
    issued_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RPPGExtractionRequest(StrictBaseModel):
    video_frame: str = Field(min_length=16, max_length=1_500_000)


class RPPGExtractionResponse(StrictBaseModel):
    pulse_bpm: int = Field(ge=30, le=220)
    confidence: float = Field(ge=0.0, le=1.0)
    source: str
    digest: str


class LatticeVerificationRequest(StrictBaseModel):
    wallet_address: str = Field(min_length=8, max_length=256)


class LatticeVerificationResponse(StrictBaseModel):
    verified: bool
    algorithm: str
    wallet_address: str
    confidence: float = Field(ge=0.0, le=1.0)


class SandboxDeploymentRequest(StrictBaseModel):
    scenario_id: str = Field(min_length=2, max_length=128)
    manifest: dict[str, Any] = Field(default_factory=dict)


class SandboxDeploymentResponse(StrictBaseModel):
    status: str
    scenario_id: str
    reason: str
    sandbox: dict[str, Any] = Field(default_factory=dict)


class NeuroSymbolicMapRequest(StrictBaseModel):
    reasoning_trace: list[str] = Field(default_factory=list)


class SessionAuditExport(StrictBaseModel):
    snapshot: InterviewSessionSnapshot
    report: GlassBoxReport | None = None
    consent_record: ConsentRecord | None = None
    milestones: list[InterviewMilestoneSnapshot] = Field(default_factory=list)
    trace_events: list[TraceEvent] = Field(default_factory=list)
    generated_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))


def sanitize_for_candidate(snapshot: InterviewSessionSnapshot) -> InterviewSessionSnapshot:
    """
    EEOC firewall: strips biometric overlay fields before a session snapshot
    crosses into the candidate plane.
    """
    from copy import deepcopy

    safe = deepcopy(snapshot)
    safe.overlay.overlay_enabled = False
    safe.overlay.collection_mode = OverlayCollectionMode.DISABLED
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
