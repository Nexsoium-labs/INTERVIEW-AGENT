from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.contracts import (
    ConsentRecord,
    ObservationResult,
    OperatorReviewSegment,
    OverlayCollectionMode,
    TelemetryOverlayPlane,
    TelemetryOverlayPoint,
    TelemetryOverlaySegment,
    TelemetryPacket,
)


class TelemetryOverlayService:
    def update_plane(
        self,
        *,
        current_plane: TelemetryOverlayPlane,
        telemetry: TelemetryPacket,
        consent_record: ConsentRecord | None,
        correlated_event_id: str,
        correlated_simulation_event: str,
        risk_flags: list[str],
    ) -> TelemetryOverlayPlane:
        overlay_enabled = bool(
            consent_record
            and consent_record.telemetry_collection_allowed
            and consent_record.biometric_processing_allowed
        )
        if not overlay_enabled:
            return current_plane.model_copy(
                update={
                    "overlay_enabled": False,
                    "collection_mode": OverlayCollectionMode.DISABLED,
                    "excluded_from_automated_scoring": True,
                    "operator_review_flags": self._append_unique(
                        current_plane.operator_review_flags,
                        "telemetry-disabled-or-without-consent",
                    ),
                }
            )

        point = TelemetryOverlayPoint(
            timestamp_utc=telemetry.timestamp_utc,
            correlated_event_id=correlated_event_id,
            stress_index=telemetry.stress_index,
            heart_rate_bpm=telemetry.heart_rate_bpm,
            speech_cadence_wpm=self._speech_cadence(telemetry),
            keystroke_irregularity=self._keystroke_irregularity(telemetry),
            confidence=round(
                max(
                    0.0,
                    min(
                        1.0,
                        (telemetry.rppg_confidence or 0.0)
                        if telemetry.heart_rate_bpm is not None
                        else 0.65,
                    ),
                ),
                3,
            ),
        )
        previous_stress = current_plane.latest_stress_index
        stress_delta = round((point.stress_index or 0.0) - (previous_stress or 0.0), 3)

        stress_markers = list(current_plane.stress_markers)
        overlay_segments = list(current_plane.overlay_segments)
        review_segments = list(current_plane.review_segments)
        operator_review_flags = list(current_plane.operator_review_flags)

        if point.stress_index is not None and abs(stress_delta) >= 0.18:
            marker = TelemetryOverlaySegment(
                start_timestamp_utc=point.timestamp_utc,
                end_timestamp_utc=point.timestamp_utc + timedelta(seconds=8),
                correlated_event_id=correlated_event_id,
                stress_delta=stress_delta,
                confidence=point.confidence,
                rationale="Stress delta exceeded review threshold relative to prior overlay point.",
            )
            stress_markers.append(marker)
            overlay_segments.append(marker)

        if (
            "prompt_injection_attempt" in risk_flags
            or (point.stress_index is not None and point.stress_index >= 0.82)
            or (point.heart_rate_bpm is not None and point.heart_rate_bpm >= 150)
        ):
            review_segments.append(
                OperatorReviewSegment(
                    start_timestamp_utc=point.timestamp_utc,
                    end_timestamp_utc=point.timestamp_utc + timedelta(seconds=15),
                    correlated_simulation_event=correlated_simulation_event,
                    stress_delta=stress_delta,
                    confidence=max(point.confidence, 0.7),
                    review_rationale=(
                        "Operator review requested due to elevated physiological signal or "
                        "security-relevant task correlation."
                    ),
                    priority="high",
                )
            )
            operator_review_flags = self._append_unique(
                operator_review_flags,
                "operator-review-required",
            )

        lag_ms = max(
            0,
            int((datetime.now(UTC) - telemetry.timestamp_utc).total_seconds() * 1000),
        )

        return current_plane.model_copy(
            update={
                "overlay_enabled": True,
                "collection_mode": OverlayCollectionMode.ACTIVE,
                "telemetry_timeline": [*current_plane.telemetry_timeline, point],
                "stress_markers": stress_markers,
                "overlay_segments": overlay_segments,
                "review_segments": review_segments,
                "operator_review_flags": operator_review_flags,
                "latest_stress_index": point.stress_index,
                "latest_heart_rate_bpm": point.heart_rate_bpm,
                "overlay_processing_lag_ms": lag_ms,
                "excluded_from_automated_scoring": True,
            }
        )

    def build_summary(self, plane: TelemetryOverlayPlane):
        from app.contracts import TelemetryOverlaySummary

        return TelemetryOverlaySummary(
            overlay_enabled=plane.overlay_enabled,
            total_points=len(plane.telemetry_timeline),
            total_segments=len(plane.overlay_segments),
            total_review_segments=len(plane.review_segments),
            latest_stress_index=plane.latest_stress_index,
            latest_heart_rate_bpm=plane.latest_heart_rate_bpm,
            excluded_from_automated_scoring=True,
        )

    def _speech_cadence(self, telemetry: TelemetryPacket) -> float | None:
        text = telemetry.audio_text or telemetry.candidate_message
        if not text:
            return None
        word_count = len([word for word in text.split() if word])
        base_seconds = max(15.0, telemetry.silence_ms / 1000.0 + 15.0)
        return round((word_count / base_seconds) * 60.0, 2)

    def _keystroke_irregularity(self, telemetry: TelemetryPacket) -> float | None:
        if not telemetry.code_delta:
            return None
        lines = [line for line in telemetry.code_delta.splitlines() if line.strip()]
        if not lines:
            return 0.0
        lengths = [len(line) for line in lines]
        spread = max(lengths) - min(lengths)
        return round(min(1.0, spread / 80.0), 3)

    def _append_unique(self, items: list[str], item: str) -> list[str]:
        if item in items:
            return items
        return [*items, item]
