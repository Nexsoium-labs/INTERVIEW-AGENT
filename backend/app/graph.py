from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.contracts import (
    ActionExecutionResult,
    ActionType,
    CandidateEvent,
    CandidateRecommendation,
    ConsentRecord,
    ConsensusResult,
    DecisionStep,
    InterviewMilestoneSnapshot,
    L0RouteDecision,
    MemoryUpdate,
    ObservationResult,
    PerceptionResult,
    PlanningResult,
    ReasoningResult,
    TechnicalScorePlane,
    TelemetryOverlayPlane,
    ToolAction,
    TraceEvent,
)
from app.services.adk_router import GoogleADKService
from app.services.agno_tools import AgnoToolService
from app.services.crewai_orchestrator import CrewDebateOrchestrator
from app.services.memory import MemoryBank
from app.services.technical_scoring import TechnicalScoringService
from app.services.telemetry_overlay import TelemetryOverlayService
from app.state import InterviewGraphState


class InterviewGraphEngine:
    def __init__(
        self,
        adk_service: GoogleADKService,
        crew_orchestrator: CrewDebateOrchestrator,
        agno_tools: AgnoToolService,
        memory_bank: MemoryBank,
        technical_scoring_service: TechnicalScoringService,
        telemetry_overlay_service: TelemetryOverlayService,
    ) -> None:
        self.adk_service = adk_service
        self.crew_orchestrator = crew_orchestrator
        self.agno_tools = agno_tools
        self.memory_bank = memory_bank
        self.technical_scoring_service = technical_scoring_service
        self.telemetry_overlay_service = telemetry_overlay_service
        self.app = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(InterviewGraphState)

        graph.add_node("session_init", self._session_init_node)
        graph.add_node("consent_and_disclosure_gate", self._consent_gate_node)
        graph.add_node("l0_router", self._l0_router_node)
        graph.add_node("identity_gate", self._identity_gate_node)
        graph.add_node("scenario_selection", self._scenario_selection_node)
        graph.add_node("simulation_execution", self._simulation_execution_node)
        graph.add_node("technical_assessment", self._technical_assessment_node)
        graph.add_node("telemetry_overlay_generation", self._telemetry_overlay_node)
        graph.add_node("operator_review_queue", self._operator_review_queue_node)
        graph.add_node("memory", self._memory_node)
        graph.add_node("snapshot_milestone", self._snapshot_milestone_node)

        graph.add_edge(START, "session_init")
        graph.add_edge("session_init", "consent_and_disclosure_gate")
        graph.add_edge("consent_and_disclosure_gate", "l0_router")
        graph.add_conditional_edges(
            "l0_router",
            self._route_after_l0,
            {
                "drop": END,
                "continue": "identity_gate",
            },
        )
        graph.add_edge("identity_gate", "scenario_selection")
        graph.add_edge("scenario_selection", "simulation_execution")
        graph.add_edge("simulation_execution", "technical_assessment")
        graph.add_edge("technical_assessment", "telemetry_overlay_generation")
        graph.add_edge("telemetry_overlay_generation", "operator_review_queue")
        graph.add_edge("operator_review_queue", "memory")
        graph.add_edge("memory", "snapshot_milestone")
        graph.add_edge("snapshot_milestone", END)

        return graph.compile()

    async def run(self, state: InterviewGraphState) -> InterviewGraphState:
        return await self.app.ainvoke(state)

    @staticmethod
    def _route_after_l0(state: InterviewGraphState) -> str:
        decision = _as_model(L0RouteDecision, state.get("route_decision"))
        return "continue" if decision.pass_through else "drop"

    async def _session_init_node(self, state: InterviewGraphState) -> dict[str, Any]:
        started = perf_counter()
        event = state["current_event"]
        return {
            "simulation_status": "session_init",
            "trace_events": [
                _trace(
                    session_id=state["session_id"],
                    node="session_init",
                    reasoning_path=(
                        f"Initialized deterministic lifecycle for event {event.event_id} "
                        "before any model or tool routing."
                    ),
                    input_contract="CandidateEvent",
                    output_contract="InterviewGraphState",
                    attributes={"event_type": event.event_type},
                    started=started,
                )
            ],
        }

    async def _consent_gate_node(self, state: InterviewGraphState) -> dict[str, Any]:
        started = perf_counter()
        consent = _as_model(ConsentRecord, state.get("consent_record")) if state.get("consent_record") else None
        overlay_allowed = bool(
            consent
            and consent.telemetry_collection_allowed
            and consent.biometric_processing_allowed
        )
        return {
            "simulation_status": "consent_gated",
            "trace_events": [
                _trace(
                    session_id=state["session_id"],
                    node="consent_and_disclosure_gate",
                    reasoning_path=(
                        "Applied consent gate. Telemetry overlay can proceed only with explicit "
                        "telemetry and biometric consent."
                    ),
                    input_contract="ConsentRecord|None",
                    output_contract="OverlayConsentDecision",
                    attributes={
                        "overlay_enabled": overlay_allowed,
                        "consent_present": consent is not None,
                    },
                    started=started,
                )
            ],
        }

    async def _l0_router_node(self, state: InterviewGraphState) -> dict[str, Any]:
        started = perf_counter()
        event = state["current_event"]
        decision = await self.adk_service.route_event(event)
        return {
            "route_decision": decision,
            "last_route_target": decision.target_tier,
            "trace_events": [
                _trace(
                    session_id=state["session_id"],
                    node="l0_router",
                    reasoning_path=decision.reason,
                    input_contract="CandidateEvent",
                    output_contract="L0RouteDecision",
                    attributes={
                        "target_tier": decision.target_tier,
                        "tokens_saved_estimate": decision.tokens_saved_estimate,
                        "pass_through": decision.pass_through,
                        "fallback_used": decision.fallback_used,
                        "routed_lane": decision.routed_lane,
                    },
                    started=started,
                )
            ],
        }

    async def _identity_gate_node(self, state: InterviewGraphState) -> dict[str, Any]:
        started = perf_counter()
        event = state["current_event"]
        message = (event.telemetry.candidate_message or "").lower()
        injection_detected = "ignore all previous instructions" in message
        path = (
            "Prompt injection signature observed. Session remains active but security review "
            "evidence was added."
            if injection_detected
            else "Identity gate cleared for normal technical evaluation."
        )
        return {
            "simulation_status": "identity_gated",
            "trace_events": [
                _trace(
                    session_id=state["session_id"],
                    node="identity_gate",
                    reasoning_path=path,
                    input_contract="CandidateEvent",
                    output_contract="IdentityGateDecision",
                    attributes={"prompt_injection_detected": injection_detected},
                    started=started,
                )
            ],
        }

    async def _scenario_selection_node(self, state: InterviewGraphState) -> dict[str, Any]:
        started = perf_counter()
        event = state["current_event"]
        scenario_id = event.requested_scenario or state["scenario_id"]
        return {
            "scenario_id": scenario_id,
            "simulation_status": "scenario_selected",
            "trace_events": [
                _trace(
                    session_id=state["session_id"],
                    node="scenario_selection",
                    reasoning_path="Selected deterministic scenario rubric for this session.",
                    input_contract="CandidateEvent+InterviewGraphState",
                    output_contract="ScenarioId",
                    attributes={"scenario_id": scenario_id},
                    started=started,
                )
            ],
        }

    async def _simulation_execution_node(self, state: InterviewGraphState) -> dict[str, Any]:
        started = perf_counter()
        event = state["current_event"]

        signal_size = len(event.telemetry.audio_text or "") + len(event.telemetry.code_delta or "")
        signal_size += len(event.telemetry.candidate_message or "")
        complexity = min(1.0, 0.15 + (signal_size / 12_000))

        risk_flags: list[str] = []
        candidate_text = (event.telemetry.candidate_message or "").lower()
        if "ignore all previous instructions" in candidate_text:
            risk_flags.append("prompt_injection_attempt")
        if "clarify" in candidate_text:
            risk_flags.append("candidate_clarification_request")

        perception = PerceptionResult(
            intent_label=event.event_type.value,
            complexity_score=round(complexity, 3),
            risk_flags=risk_flags,
            normalized_payload={
                "audio_text": event.telemetry.audio_text or "",
                "code_delta": event.telemetry.code_delta or "",
                "candidate_message": event.telemetry.candidate_message or "",
            },
        )

        confidence = max(
            0.1,
            min(0.98, 0.92 - (0.35 * len(risk_flags)) - (0.2 * perception.complexity_score)),
        )
        reasoning = ReasoningResult(
            reasoning_summary=(
                f"Intent={perception.intent_label}; complexity={perception.complexity_score:.2f}; "
                f"risk_count={len(risk_flags)}"
            ),
            confidence=round(confidence, 3),
            vulnerability_signals=risk_flags,
            intervention_required=bool(risk_flags) or perception.complexity_score > 0.7,
        )

        selected_action = self._select_action(reasoning=reasoning, event=event)
        plan = PlanningResult(
            decision_tree=[
                DecisionStep(
                    order=1,
                    instruction="Stabilize candidate context and preserve simulation continuity.",
                    objective="Continuity",
                ),
                DecisionStep(
                    order=2,
                    instruction="Select deterministic action branch from objective simulation state.",
                    objective="Safe routing",
                ),
                DecisionStep(
                    order=3,
                    instruction="Emit auditable action payload with zero-trust approval gates.",
                    objective="Safe execution",
                ),
            ],
            selected_action=selected_action,
            requires_human_gate=selected_action == "verify_identity",
        )

        action_result = await self._execute_action(
            plan=plan,
            event=event,
            scenario_id=state["scenario_id"].value,
        )
        observation = self._build_observation(action_result)

        return {
            "perception": perception,
            "reasoning": reasoning,
            "plan": plan,
            "action_result": action_result,
            "observation": observation,
            "simulation_status": "simulation_execution",
            "trace_events": [
                _trace(
                    session_id=state["session_id"],
                    node="simulation_execution",
                    reasoning_path=(
                        "Ran deterministic simulation perception, planning, tool execution, and "
                        "observation without consulting biometric telemetry."
                    ),
                    input_contract="CandidateEvent",
                    output_contract=(
                        "PerceptionResult+ReasoningResult+PlanningResult+"
                        "ActionExecutionResult+ObservationResult"
                    ),
                    attributes={
                        "complexity_score": perception.complexity_score,
                        "selected_action": plan.selected_action,
                        "action_status": action_result.status,
                    },
                    started=started,
                )
            ],
        }

    async def _technical_assessment_node(self, state: InterviewGraphState) -> dict[str, Any]:
        started = perf_counter()
        event = state["current_event"]
        action_result = _as_model(ActionExecutionResult, state.get("action_result"))
        observation = _as_model(ObservationResult, state.get("observation"))

        scoring_input = self.technical_scoring_service.build_scoring_input(
            session_id=state["session_id"],
            event=event,
            scenario_id=state["scenario_id"],
            action_result=action_result,
            observation=observation,
            event_count=int(state.get("event_count", 0)),
        )
        technical_evidence = event.raw_payload.get("technical_evidence", {})
        if technical_evidence is None:
            technical_evidence = {}
        if not isinstance(technical_evidence, dict):
            raise ValueError("technical_evidence payload must be an object")
        evidence_complete = bool(
            event.raw_payload.get("evidence_complete")
            or technical_evidence.get("evidence_complete", False)
        )
        technical_plane = self.technical_scoring_service.evaluate(
            scoring_input,
            evidence_complete=evidence_complete,
        )
        consensus = await self.crew_orchestrator.evaluate(
            rubric_scores=technical_plane.rubric_scores,
            task_outcomes=technical_plane.task_outcomes,
        )

        return {
            "technical_scoring_input": scoring_input,
            "technical_plane": technical_plane,
            "consensus": consensus,
            "simulation_status": "technical_assessment",
            "trace_events": [
                _trace(
                    session_id=state["session_id"],
                    node="technical_assessment",
                    reasoning_path=(
                        "Scored objective evidence bundle and produced a technical verdict. "
                        "Crew debate consumed rubric outputs only."
                    ),
                    input_contract="TechnicalScoringInput",
                    output_contract="TechnicalScorePlane+ConsensusResult",
                    attributes={
                        "technical_score": technical_plane.technical_score,
                        "technical_recommendation": (
                            technical_plane.technical_verdict.recommendation
                            if technical_plane.technical_verdict
                            else CandidateRecommendation.REJECT
                        ),
                        "consensus_score": consensus.unified_score,
                    },
                    started=started,
                )
            ],
        }

    async def _telemetry_overlay_node(self, state: InterviewGraphState) -> dict[str, Any]:
        started = perf_counter()
        event = state["current_event"]
        perception = _as_model(PerceptionResult, state.get("perception"))
        observation = _as_model(ObservationResult, state.get("observation"))
        current_plane = _as_model(TelemetryOverlayPlane, state["overlay_plane"])

        overlay_plane = self.telemetry_overlay_service.update_plane(
            current_plane=current_plane,
            telemetry=event.telemetry,
            consent_record=(
                _as_model(ConsentRecord, state.get("consent_record"))
                if state.get("consent_record")
                else None
            ),
            correlated_event_id=event.event_id,
            correlated_simulation_event=observation.outcome_label,
            risk_flags=perception.risk_flags,
        )

        return {
            "overlay_plane": overlay_plane,
            "simulation_status": "telemetry_overlay_generation",
            "trace_events": [
                _trace(
                    session_id=state["session_id"],
                    node="telemetry_overlay_generation",
                    reasoning_path=(
                        "Built operator-only telemetry overlay aligned to the simulation event. "
                        "Overlay output is excluded from the technical verdict."
                    ),
                    input_contract="TelemetryPacket+ConsentRecord|None",
                    output_contract="TelemetryOverlayPlane",
                    attributes={
                        "overlay_enabled": overlay_plane.overlay_enabled,
                        "review_segment_count": len(overlay_plane.review_segments),
                    },
                    started=started,
                )
            ],
        }

    async def _operator_review_queue_node(self, state: InterviewGraphState) -> dict[str, Any]:
        started = perf_counter()
        overlay_plane = _as_model(TelemetryOverlayPlane, state["overlay_plane"])
        technical_plane = _as_model(TechnicalScorePlane, state.get("technical_plane"))
        requires_queue = bool(overlay_plane.review_segments) or (
            technical_plane.technical_verdict is not None
            and technical_plane.technical_verdict.recommendation != CandidateRecommendation.ADVANCE
        )
        simulation_status = "operator_review_queue" if requires_queue else "candidate_active"
        return {
            "simulation_status": simulation_status,
            "trace_events": [
                _trace(
                    session_id=state["session_id"],
                    node="operator_review_queue",
                    reasoning_path=(
                        "Queued operator attention from overlay review segments and technical "
                        "verdict status without mutating the locked score."
                    ),
                    input_contract="TechnicalScorePlane+TelemetryOverlayPlane",
                    output_contract="OperatorQueueDecision",
                    attributes={
                        "requires_operator_review": requires_queue,
                        "review_segment_count": len(overlay_plane.review_segments),
                    },
                    started=started,
                )
            ],
        }

    async def _memory_node(self, state: InterviewGraphState) -> dict[str, Any]:
        started = perf_counter()
        technical_plane = _as_model(TechnicalScorePlane, state.get("technical_plane"))
        overlay_plane = _as_model(TelemetryOverlayPlane, state["overlay_plane"])
        consensus = _as_model(ConsensusResult, state.get("consensus"))

        technical_key = await self.memory_bank.write(
            "technical",
            state["session_id"],
            {
                "technical_score": technical_plane.technical_score,
                "scenario_id": technical_plane.scenario_id,
                "consensus": consensus.unified_score,
                "verdict": (
                    technical_plane.technical_verdict.recommendation
                    if technical_plane.technical_verdict
                    else None
                ),
            },
        )
        overlay_key = await self.memory_bank.write(
            "overlay",
            state["session_id"],
            {
                "overlay_enabled": overlay_plane.overlay_enabled,
                "review_segments": len(overlay_plane.review_segments),
                "latest_stress_index": overlay_plane.latest_stress_index,
            },
        )

        memory_update = MemoryUpdate(
            short_term_notes=(
                f"technical={technical_plane.technical_score:.2f}; "
                f"overlay_review_segments={len(overlay_plane.review_segments)}"
            ),
            vector_embedding_key=technical_key,
            vector_payload={"technical_key": technical_key, "overlay_key": overlay_key},
        )

        return {
            "memory_update": memory_update,
            "updated_at_utc": datetime.now(UTC),
            "trace_events": [
                _trace(
                    session_id=state["session_id"],
                    node="memory",
                    reasoning_path=(
                        "Persisted technical evidence memory and overlay memory in separate "
                        "namespaces."
                    ),
                    input_contract="TechnicalScorePlane+TelemetryOverlayPlane",
                    output_contract="MemoryUpdate",
                    attributes={
                        "technical_key": technical_key,
                        "overlay_key": overlay_key,
                    },
                    started=started,
                )
            ],
        }

    async def _snapshot_milestone_node(self, state: InterviewGraphState) -> dict[str, Any]:
        started = perf_counter()
        technical_plane = _as_model(TechnicalScorePlane, state.get("technical_plane"))
        overlay_plane = _as_model(TelemetryOverlayPlane, state["overlay_plane"])
        milestone = InterviewMilestoneSnapshot(
            session_id=state["session_id"],
            stage=state.get("simulation_status", "event_processed"),
            event_count=int(state.get("event_count", 0)),
            trace_count=len(state.get("trace_events", [])) + 1,
            technical_score=technical_plane.technical_score,
            technical_recommendation=(
                technical_plane.technical_verdict.recommendation
                if technical_plane.technical_verdict
                else None
            ),
            overlay_enabled=overlay_plane.overlay_enabled,
            overlay_segment_count=len(overlay_plane.review_segments),
            simulation_status=state.get("simulation_status", "event_processed"),
            note="Replayable milestone captured after technical and overlay planes diverged.",
        )
        return {
            "milestones": [milestone],
            "trace_events": [
                _trace(
                    session_id=state["session_id"],
                    node="snapshot_milestone",
                    reasoning_path="Captured replayable milestone snapshot for audit export.",
                    input_contract="InterviewGraphState",
                    output_contract="InterviewMilestoneSnapshot",
                    attributes={"stage": milestone.stage},
                    started=started,
                )
            ],
        }

    def _select_action(self, *, reasoning: ReasoningResult, event: CandidateEvent) -> str:
        if "prompt_injection_attempt" in reasoning.vulnerability_signals:
            return "verify_identity"
        if event.event_type.value in {"code_delta", "candidate_message", "webcam_frame"}:
            return "inject_hint" if reasoning.intervention_required else "noop"
        if event.event_type.value == "system_signal":
            return "stress_test"
        if reasoning.intervention_required:
            return "inject_hint"
        return "noop"

    async def _execute_action(
        self,
        *,
        plan: PlanningResult,
        event: CandidateEvent,
        scenario_id: str,
    ) -> ActionExecutionResult:
        action = ToolAction(
            action_type=ActionType.NOOP,
            parameters={},
            approved_by_zero_trust=True,
            guardrail_reason="No operation required.",
        )
        output: dict[str, Any] = {}
        status = "completed"

        if plan.selected_action == "inject_hint":
            action = ToolAction(
                action_type=ActionType.INJECT_HINT,
                parameters={"difficulty_shift": "down_one_level"},
                approved_by_zero_trust=True,
                guardrail_reason="Pedagogical nudge is safe and reversible.",
            )
            output = {
                "hint": "Focus on objective artifacts: command log, diff, hidden tests, and health checks.",
            }
        elif plan.selected_action == "stress_test":
            manifest = {
                "apiVersion": "v1",
                "kind": "Pod",
                "metadata": {"name": "interview-sim"},
                "spec": {
                    "containers": [
                        {
                            "name": "sim",
                            "image": "ghcr.io/example/interview-sim:v1.0.0",
                        }
                    ]
                },
            }
            action = ToolAction(
                action_type=ActionType.DEPLOY_EPHEMERAL_KUBERNETES,
                parameters={"scenario_id": scenario_id, "manifest": manifest},
                approved_by_zero_trust=True,
                guardrail_reason="Manifest validated with restricted schema and immutable image tags.",
            )
            output = await self.agno_tools.deploy_ephemeral_kubernetes(
                scenario_id=scenario_id,
                manifest=manifest,
            )
            if output.get("status") == "blocked":
                status = "blocked"
        elif plan.selected_action == "verify_identity":
            wallet_address = str(
                event.raw_payload.get("wallet_address", "did:key:z6Mkq1SecureDemoKey")
            )
            action = ToolAction(
                action_type=ActionType.VERIFY_LATTICE_SIGNATURE,
                parameters={"wallet_address": wallet_address},
                approved_by_zero_trust=True,
                guardrail_reason="Escalated due to prompt injection signature.",
            )
            output = await self.agno_tools.verify_lattice_signature(wallet_address=wallet_address)

        return ActionExecutionResult(
            status=status,
            action=action,
            output=output,
        )

    def _build_observation(self, action_result: ActionExecutionResult) -> ObservationResult:
        if action_result.action.action_type == ActionType.INJECT_HINT:
            return ObservationResult(
                outcome_label="candidate_stabilized",
                candidate_reaction_ms=420,
                observed_stress_shift=-0.12,
            )
        if action_result.action.action_type == ActionType.DEPLOY_EPHEMERAL_KUBERNETES:
            return ObservationResult(
                outcome_label="sandbox_recovery_simulated",
                candidate_reaction_ms=180,
                observed_stress_shift=0.18,
            )
        if action_result.action.action_type == ActionType.VERIFY_LATTICE_SIGNATURE:
            return ObservationResult(
                outcome_label="identity_challenge_acknowledged",
                candidate_reaction_ms=260,
                observed_stress_shift=0.04,
            )
        return ObservationResult(
            outcome_label="passive_progress",
            candidate_reaction_ms=500,
            observed_stress_shift=-0.02,
        )


def _trace(
    *,
    session_id: str,
    node: str,
    reasoning_path: str,
    input_contract: str,
    output_contract: str,
    attributes: dict[str, Any] | None = None,
    started: float,
) -> TraceEvent:
    now = datetime.now(UTC)
    latency = max(0, int((perf_counter() - started) * 1000))
    return TraceEvent(
        session_id=session_id,
        node=node,
        reasoning_path=reasoning_path,
        input_contract=input_contract,
        output_contract=output_contract,
        attributes=attributes or {},
        started_at_utc=now,
        completed_at_utc=now,
        latency_ms=latency,
    )


def _as_model(model_cls, payload):
    if isinstance(payload, model_cls):
        return payload
    return model_cls.model_validate(payload)
