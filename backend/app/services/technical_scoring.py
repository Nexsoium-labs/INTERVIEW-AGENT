from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.contracts import (
    ActionExecutionResult,
    ArtifactType,
    CandidateRecommendation,
    CandidateEvent,
    HealthCheckResult,
    HiddenTestResult,
    ObservationResult,
    ScenarioId,
    TechnicalOutcomeStatus,
    TechnicalRubricScore,
    TechnicalScorePlane,
    TechnicalScoringInput,
    TechnicalTaskArtifact,
    TechnicalTaskOutcome,
    TechnicalVerdict,
)

_SCENARIO_KEYWORDS: dict[ScenarioId, tuple[str, ...]] = {
    ScenarioId.KUBERNETES_OUTAGE_RECOVERY: (
        "rollback",
        "health",
        "namespace",
        "pod",
        "service",
        "backpressure",
        "isolate",
        "recovery",
    ),
    ScenarioId.ALGORITHM_CODING_TASK: (
        "complexity",
        "test",
        "boundary",
        "correctness",
        "optimize",
        "input",
        "output",
    ),
    ScenarioId.PR_CRISIS_RESOLUTION: (
        "rollback",
        "review",
        "blast radius",
        "regression",
        "mitigation",
        "incident",
    ),
    ScenarioId.ARCHITECTURE_DEBUGGING: (
        "dependency",
        "latency",
        "bottleneck",
        "trace",
        "cache",
        "consistency",
        "boundary",
    ),
}

_SCENARIO_TITLES: dict[ScenarioId, str] = {
    ScenarioId.KUBERNETES_OUTAGE_RECOVERY: "Kubernetes outage recovery",
    ScenarioId.ALGORITHM_CODING_TASK: "Algorithm and coding task",
    ScenarioId.PR_CRISIS_RESOLUTION: "Pull request crisis resolution",
    ScenarioId.ARCHITECTURE_DEBUGGING: "Architecture debugging",
}

_BLOCKED_TECHNICAL_KEYS = {
    "heart_rate_bpm",
    "stress_index",
    "rppg_confidence",
    "raw_vector_hash",
    "telemetry",
    "biometric_vector",
    "biometric_signal",
}


class TechnicalScoringService:
    def build_scoring_input(
        self,
        *,
        session_id: str,
        event: CandidateEvent,
        scenario_id: ScenarioId,
        action_result: ActionExecutionResult,
        observation: ObservationResult,
        event_count: int,
    ) -> TechnicalScoringInput:
        technical_payload = event.raw_payload.get("technical_evidence", {})
        if technical_payload is None:
            technical_payload = {}
        if technical_payload and not isinstance(technical_payload, dict):
            raise ValueError("technical_evidence payload must be an object")
        blocked_fields = sorted(_BLOCKED_TECHNICAL_KEYS.intersection(technical_payload.keys()))
        if blocked_fields:
            raise ValueError(
                "technical_evidence payload cannot contain biometric fields: "
                + ", ".join(blocked_fields)
            )

        command_log = self._coerce_string_list(
            technical_payload.get("command_log"),
            fallback=self._default_command_log(event=event, action_result=action_result),
        )
        hidden_tests = self._coerce_hidden_tests(
            technical_payload.get("hidden_tests"),
            fallback=self._default_hidden_tests(event=event),
        )
        health_checks = self._coerce_health_checks(
            technical_payload.get("health_checks"),
            fallback=self._default_health_checks(action_result=action_result, observation=observation),
        )
        sandbox_stream = self._coerce_string_list(
            technical_payload.get("sandbox_event_stream"),
            fallback=self._default_sandbox_stream(action_result=action_result, observation=observation),
        )
        final_system_state = self._coerce_dict(
            technical_payload.get("final_system_state"),
            fallback={
                "action_status": action_result.status,
                "observation": observation.outcome_label,
                "event_count": event_count,
            },
        )
        time_to_resolution_ms = int(
            technical_payload.get("time_to_resolution_ms", max(45_000, event_count * 60_000))
        )
        failed_action_count = int(
            technical_payload.get(
                "failed_action_count",
                1 if action_result.status in {"blocked", "failed"} else 0,
            )
        )
        regression_impact = float(
            technical_payload.get(
                "regression_impact",
                0.35 if any(not check.healthy for check in health_checks) else 0.0,
            )
        )

        return TechnicalScoringInput.model_validate(
            {
                "session_id": session_id,
                "event_id": event.event_id,
                "scenario_id": scenario_id,
                "event_type": event.event_type,
                "candidate_message": event.telemetry.candidate_message,
                "code_delta": event.telemetry.code_delta,
                "command_log": command_log,
                "diff_patch": technical_payload.get("diff_patch") or event.telemetry.code_delta,
                "hidden_tests": [item.model_dump(mode="json") for item in hidden_tests],
                "health_checks": [item.model_dump(mode="json") for item in health_checks],
                "sandbox_event_stream": sandbox_stream,
                "final_system_state": final_system_state,
                "time_to_resolution_ms": time_to_resolution_ms,
                "failed_action_count": failed_action_count,
                "regression_impact": min(max(regression_impact, 0.0), 1.0),
            }
        )

    def evaluate(
        self,
        scoring_input: TechnicalScoringInput,
        *,
        evidence_complete: bool = False,
    ) -> TechnicalScorePlane:
        artifacts = self._build_artifacts(scoring_input)

        rubric_scores = [
            self._score_correctness(scoring_input),
            self._score_completeness(artifacts),
            self._score_recovery_path(scoring_input),
            self._score_safety(scoring_input),
            self._score_time_to_resolution(scoring_input),
            self._score_failed_actions(scoring_input),
            self._score_regression_impact(scoring_input),
        ]

        total_score = round(sum(item.score for item in rubric_scores), 2)
        max_score = round(sum(item.max_score for item in rubric_scores), 2)
        normalized = round((total_score / max_score) * 100.0, 2) if max_score else 0.0
        recommendation = self._recommendation_from_score(normalized)
        passed = recommendation == CandidateRecommendation.ADVANCE
        outcome_status = (
            TechnicalOutcomeStatus.PASSED
            if normalized >= 75.0
            else TechnicalOutcomeStatus.PARTIAL
            if normalized >= 50.0
            else TechnicalOutcomeStatus.FAILED
        )

        outcome = TechnicalTaskOutcome(
            scenario_id=scoring_input.scenario_id,
            title=_SCENARIO_TITLES[scoring_input.scenario_id],
            status=outcome_status,
            summary=(
                f"Deterministic rubric scored {normalized:.2f}/100 from artifacts only. "
                f"Failed actions={scoring_input.failed_action_count}; "
                f"regression impact={scoring_input.regression_impact:.2f}."
            ),
            duration_ms=scoring_input.time_to_resolution_ms,
            failed_action_count=scoring_input.failed_action_count,
            regression_impact=scoring_input.regression_impact,
        )

        verdict = TechnicalVerdict(
            recommendation=recommendation,
            score=total_score,
            max_score=max_score,
            normalized_score=normalized,
            passed=passed,
            rationale=(
                "Technical verdict derived from objective artifacts: commands, diff, hidden tests, "
                "health checks, sandbox stream, and final state. Biometrics excluded."
            ),
            locked=evidence_complete,
            locked_at_utc=datetime.now(UTC),
            contamination_check_passed=True,
        )

        return TechnicalScorePlane(
            scenario_id=scoring_input.scenario_id,
            technical_score=normalized,
            technical_verdict=verdict,
            task_outcomes=[outcome],
            rubric_scores=rubric_scores,
            evidence_bundle=artifacts,
            locked=evidence_complete,
            contamination_check_passed=True,
        )

    def lock_plane(self, plane: TechnicalScorePlane) -> TechnicalScorePlane:
        verdict = plane.technical_verdict
        if verdict is None:
            raise ValueError("technical plane cannot be locked without a verdict")

        if verdict.locked and plane.locked:
            return plane

        locked_verdict = verdict.model_copy(
            update={
                "locked": True,
                "locked_at_utc": datetime.now(UTC),
            }
        )
        return plane.model_copy(
            update={
                "locked": True,
                "technical_verdict": locked_verdict,
            }
        )

    def evidence_references(self, plane: TechnicalScorePlane) -> list[str]:
        return [
            f"{artifact.artifact_type}:{artifact.label}"
            for artifact in plane.evidence_bundle
        ]

    def _build_artifacts(self, scoring_input: TechnicalScoringInput) -> list[TechnicalTaskArtifact]:
        hidden_test_lines = [
            f"{test.test_name}: {'passed' if test.passed else 'failed'} ({test.duration_ms}ms)"
            for test in scoring_input.hidden_tests
        ]
        health_lines = [
            f"{check.check_name}: {'healthy' if check.healthy else 'unhealthy'}"
            for check in scoring_input.health_checks
        ]
        return [
            TechnicalTaskArtifact(
                artifact_type=ArtifactType.COMMAND_LOG,
                label="command-log",
                content="\n".join(scoring_input.command_log) or "no commands recorded",
            ),
            TechnicalTaskArtifact(
                artifact_type=ArtifactType.DIFF_PATCH,
                label="diff-patch",
                content=scoring_input.diff_patch or "no diff submitted",
                content_type="text/x-diff",
            ),
            TechnicalTaskArtifact(
                artifact_type=ArtifactType.HIDDEN_TEST_RESULTS,
                label="hidden-tests",
                content="\n".join(hidden_test_lines) or "no hidden tests supplied",
            ),
            TechnicalTaskArtifact(
                artifact_type=ArtifactType.HEALTH_CHECK,
                label="health-checks",
                content="\n".join(health_lines) or "no health checks supplied",
            ),
            TechnicalTaskArtifact(
                artifact_type=ArtifactType.SANDBOX_EVENT_STREAM,
                label="sandbox-stream",
                content="\n".join(scoring_input.sandbox_event_stream) or "no sandbox events supplied",
            ),
            TechnicalTaskArtifact(
                artifact_type=ArtifactType.FINAL_SYSTEM_STATE,
                label="final-state",
                content=str(scoring_input.final_system_state),
                content_type="application/json",
            ),
        ]

    def _score_correctness(self, scoring_input: TechnicalScoringInput) -> TechnicalRubricScore:
        if scoring_input.hidden_tests:
            passed = sum(1 for test in scoring_input.hidden_tests if test.passed)
            ratio = passed / len(scoring_input.hidden_tests)
        else:
            ratio = 0.45 if scoring_input.code_delta or scoring_input.candidate_message else 0.0
        score = round(ratio * 25.0, 2)
        return TechnicalRubricScore(
            rubric_id="correctness",
            label="Correctness",
            score=score,
            max_score=25.0,
            rationale="Computed from hidden test pass ratio with deterministic fallback.",
        )

    def _score_completeness(
        self, artifacts: list[TechnicalTaskArtifact]
    ) -> TechnicalRubricScore:
        present_types = {artifact.artifact_type for artifact in artifacts if artifact.content}
        score = round((len(present_types) / len(ArtifactType)) * 15.0, 2)
        return TechnicalRubricScore(
            rubric_id="completeness",
            label="Completeness",
            score=score,
            max_score=15.0,
            rationale="Rewards full evidence bundle coverage across all artifact classes.",
        )

    def _score_recovery_path(self, scoring_input: TechnicalScoringInput) -> TechnicalRubricScore:
        text = " ".join(
            [
                scoring_input.candidate_message or "",
                scoring_input.code_delta or "",
                " ".join(scoring_input.command_log),
                str(scoring_input.final_system_state),
            ]
        ).lower()
        keywords = _SCENARIO_KEYWORDS[scoring_input.scenario_id]
        hits = sum(1 for keyword in keywords if keyword in text)
        ratio = hits / max(len(keywords), 1)
        score = round(min(1.0, ratio * 1.35) * 20.0, 2)
        return TechnicalRubricScore(
            rubric_id="recovery_path_quality",
            label="Recovery Path Quality",
            score=score,
            max_score=20.0,
            rationale="Matches scenario-specific remediation and debugging signals.",
        )

    def _score_safety(self, scoring_input: TechnicalScoringInput) -> TechnicalRubricScore:
        unhealthy_checks = sum(1 for check in scoring_input.health_checks if not check.healthy)
        safety_penalty = min(15.0, unhealthy_checks * 3.0 + scoring_input.failed_action_count * 2.5)
        score = round(max(0.0, 15.0 - safety_penalty), 2)
        return TechnicalRubricScore(
            rubric_id="safety_of_actions",
            label="Safety Of Actions",
            score=score,
            max_score=15.0,
            rationale="Penalizes unhealthy state and unsafe or blocked actions.",
        )

    def _score_time_to_resolution(
        self, scoring_input: TechnicalScoringInput
    ) -> TechnicalRubricScore:
        elapsed = scoring_input.time_to_resolution_ms
        if elapsed <= 90_000:
            score = 10.0
        elif elapsed <= 180_000:
            score = 7.5
        elif elapsed <= 300_000:
            score = 4.5
        else:
            score = 1.0
        return TechnicalRubricScore(
            rubric_id="time_to_resolution",
            label="Time To Resolution",
            score=score,
            max_score=10.0,
            rationale="Bounded by deterministic latency buckets.",
        )

    def _score_failed_actions(
        self, scoring_input: TechnicalScoringInput
    ) -> TechnicalRubricScore:
        failures = scoring_input.failed_action_count
        if failures <= 0:
            score = 5.0
        elif failures == 1:
            score = 3.0
        elif failures == 2:
            score = 1.0
        else:
            score = 0.0
        return TechnicalRubricScore(
            rubric_id="failed_action_count",
            label="Failed Action Count",
            score=score,
            max_score=5.0,
            rationale="Rewards clean execution paths with fewer failed actions.",
        )

    def _score_regression_impact(
        self, scoring_input: TechnicalScoringInput
    ) -> TechnicalRubricScore:
        score = round(max(0.0, (1.0 - scoring_input.regression_impact) * 10.0), 2)
        return TechnicalRubricScore(
            rubric_id="regression_impact",
            label="Regression Impact",
            score=score,
            max_score=10.0,
            rationale="Higher regression impact reduces score linearly.",
        )

    def _default_command_log(
        self,
        *,
        event: CandidateEvent,
        action_result: ActionExecutionResult,
    ) -> list[str]:
        lines = [f"event:{event.event_type.value}"]
        if event.telemetry.code_delta:
            lines.append("apply_patch candidate submission")
        if event.telemetry.candidate_message:
            lines.append("summarize candidate remediation plan")
        if action_result.action.action_type.value != "noop":
            lines.append(f"tool:{action_result.action.action_type.value}")
        return lines

    def _default_hidden_tests(self, *, event: CandidateEvent) -> list[HiddenTestResult]:
        text = " ".join(
            filter(
                None,
                [
                    event.telemetry.candidate_message,
                    event.telemetry.code_delta,
                ],
            )
        ).lower()
        passed = any(keyword in text for keyword in ("health", "rollback", "complexity", "test"))
        return [
            HiddenTestResult(
                test_name="hidden-primary",
                passed=passed,
                duration_ms=280,
                detail="Synthesized deterministic hidden check.",
            )
        ]

    def _default_health_checks(
        self,
        *,
        action_result: ActionExecutionResult,
        observation: ObservationResult,
    ) -> list[HealthCheckResult]:
        healthy = action_result.status == "completed"
        return [
            HealthCheckResult(
                check_name="system-readiness",
                healthy=healthy,
                detail="Derived from action completion when explicit health checks are absent.",
            )
        ]

    def _default_sandbox_stream(
        self,
        *,
        action_result: ActionExecutionResult,
        observation: ObservationResult,
    ) -> list[str]:
        return [
            f"action_status={action_result.status}",
            f"observation={observation.outcome_label}",
        ]

    def _coerce_string_list(self, value: Any, *, fallback: list[str]) -> list[str]:
        if value is None:
            return fallback
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError("expected a list of strings in technical evidence")
        return value

    def _coerce_hidden_tests(
        self,
        value: Any,
        *,
        fallback: list[HiddenTestResult],
    ) -> list[HiddenTestResult]:
        if value is None:
            return fallback
        if not isinstance(value, list):
            raise ValueError("hidden_tests must be a list")
        return [HiddenTestResult.model_validate(item) for item in value]

    def _coerce_health_checks(
        self,
        value: Any,
        *,
        fallback: list[HealthCheckResult],
    ) -> list[HealthCheckResult]:
        if value is None:
            return fallback
        if not isinstance(value, list):
            raise ValueError("health_checks must be a list")
        return [HealthCheckResult.model_validate(item) for item in value]

    def _coerce_dict(self, value: Any, *, fallback: dict[str, Any]) -> dict[str, Any]:
        if value is None:
            return fallback
        if not isinstance(value, dict):
            raise ValueError("final_system_state must be an object")
        return value

    def _recommendation_from_score(self, score: float) -> CandidateRecommendation:
        if score >= 75.0:
            return CandidateRecommendation.ADVANCE
        if score >= 50.0:
            return CandidateRecommendation.HOLD
        return CandidateRecommendation.REJECT
