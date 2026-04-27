from __future__ import annotations

from app.contracts import GlassBoxReport, HumanReviewRecord, InterviewSessionSnapshot, TraceEvent
from app.services.agno_tools import AgnoToolService
from app.services.guardrails import GuardrailService
from app.services.telemetry_overlay import TelemetryOverlayService


class ReportService:
    def __init__(
        self,
        agno_tools: AgnoToolService,
        guardrail_service: GuardrailService,
        telemetry_overlay_service: TelemetryOverlayService,
    ) -> None:
        self.agno_tools = agno_tools
        self.guardrail_service = guardrail_service
        self.telemetry_overlay_service = telemetry_overlay_service

    async def build_report(
        self,
        snapshot: InterviewSessionSnapshot,
        traces: list[TraceEvent],
        summary_note: str | None = None,
        latest_review: HumanReviewRecord | None = None,
    ) -> GlassBoxReport:
        verdict = snapshot.technical.technical_verdict
        if verdict is None:
            raise ValueError("cannot build report without a technical verdict")

        reasoning_trace = [trace.reasoning_path for trace in traces]
        reasoning_map = await self.agno_tools.execute_neuro_symbolic_map(reasoning_trace)
        overlay_summary = self.telemetry_overlay_service.build_summary(snapshot.overlay)

        evidence_refs = [
            f"{artifact.artifact_type}:{artifact.label}"
            for artifact in snapshot.technical.evidence_bundle
        ]
        if summary_note:
            evidence_refs.append(f"operator_note:{summary_note}")
        if latest_review is not None:
            evidence_refs.append(f"human_decision:{latest_review.decision}")

        consensus_summary = (
            f"Technical recommendation={verdict.recommendation}; "
            f"locked={verdict.locked}; "
            f"technical_score={snapshot.technical.technical_score:.2f}; "
            f"overlay_points={len(snapshot.overlay.telemetry_timeline)}."
        )
        candidate_summary = (
            "Interview evidence has been packaged for human review. Automated scoring used only "
            "objective task artifacts. Telemetry, when collected, remained an operator-only "
            "overlay and did not determine the technical verdict."
        )
        envelope = self.guardrail_service.sanitize_candidate_facing_text(candidate_summary)

        return GlassBoxReport(
            session_id=snapshot.session_id,
            locked_technical_verdict=verdict,
            technical_rubric_scores=snapshot.technical.rubric_scores,
            technical_task_outcomes=snapshot.technical.task_outcomes,
            evidence_references=evidence_refs,
            telemetry_overlay_summary=overlay_summary,
            operator_review_segments=snapshot.overlay.review_segments,
            explicit_biometric_exclusion_statement=(
                "Biometric and telemetry overlay signals were excluded from automated technical "
                "scoring and from the locked technical verdict."
            ),
            consensus_summary=consensus_summary,
            reasoning_map=reasoning_map,
            candidate_safe_summary=envelope.sanitized_text,
            trace_count=len(traces),
            human_approval_required=latest_review is None,
        )
