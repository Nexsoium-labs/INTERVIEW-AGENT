from __future__ import annotations

from collections import Counter

from app.contracts import InterviewSessionSnapshot, ObservabilitySnapshot, TraceEvent


class ObservabilityService:
    def summarize(
        self,
        snapshot: InterviewSessionSnapshot,
        traces: list[TraceEvent],
    ) -> ObservabilitySnapshot:
        node_breakdown = Counter(trace.node for trace in traces)
        average_latency = (
            round(sum(trace.latency_ms for trace in traces) / len(traces), 2) if traces else 0.0
        )
        estimated_tokens_saved = sum(
            int(trace.attributes.get("tokens_saved_estimate", 0)) for trace in traces
        )
        fallback_count = sum(
            1 for trace in traces if bool(trace.attributes.get("fallback_used", False))
        )

        drift_flags: list[str] = []
        if average_latency > 250:
            drift_flags.append("latency-regression")
        if snapshot.overlay.overlay_enabled and snapshot.overlay.overlay_processing_lag_ms > 2_000:
            drift_flags.append("overlay-processing-lag")
        if snapshot.event_count >= 5 and snapshot.technical.technical_score < 45:
            drift_flags.append("technical-score-collapse")
        if not snapshot.technical.contamination_check_passed:
            drift_flags.append("score-contamination-risk")

        if estimated_tokens_saved <= 0:
            cost_governor = "No routing savings detected. Review L0 thresholds and fallback coverage."
        elif average_latency > 150:
            cost_governor = "Latency elevated. Keep Flash Lite on high-volume parsing paths."
        else:
            cost_governor = "Routing profile is healthy. Current tier split is acceptable."

        reproducible = len(snapshot.technical.evidence_bundle) == 6

        return ObservabilitySnapshot(
            session_id=snapshot.session_id,
            session_status=snapshot.session_status,
            total_traces=len(traces),
            average_latency_ms=average_latency,
            node_breakdown=dict(node_breakdown),
            estimated_tokens_saved=estimated_tokens_saved,
            drift_flags=drift_flags,
            cost_governor_recommendation=cost_governor,
            latest_technical_score=snapshot.technical.technical_score,
            overlay_processing_lag_ms=snapshot.overlay.overlay_processing_lag_ms,
            model_fallback_count=fallback_count,
            contamination_check_passed=snapshot.technical.contamination_check_passed,
            reproducible_from_artifacts=reproducible,
        )
