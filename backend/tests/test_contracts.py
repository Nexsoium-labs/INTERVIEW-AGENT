from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.contracts import CandidateEvent, EventType, ScenarioId, TechnicalScoringInput, TelemetryPacket


def test_telemetry_rejects_non_numeric_heart_rate() -> None:
    with pytest.raises(ValidationError):
        TelemetryPacket(
            candidate_message="hello",
            heart_rate_bpm="fast",  # type: ignore[arg-type]
            raw_vector_hash="6f1f4dc566f90f5ecf98ee4f710a9f8c",
        )


def test_telemetry_requires_semantic_signal() -> None:
    with pytest.raises(ValidationError):
        TelemetryPacket()


def test_telemetry_accepts_silence_only_packet() -> None:
    packet = TelemetryPacket(silence_ms=1200)

    assert packet.silence_ms == 1200


def test_candidate_event_valid_contract() -> None:
    packet = TelemetryPacket(
        candidate_message="I can explain my architecture choices.",
        heart_rate_bpm=92,
        stress_index=0.31,
        raw_vector_hash="6f1f4dc566f90f5ecf98ee4f710a9f8c",
    )

    event = CandidateEvent(
        session_id="session-1",
        event_type=EventType.CANDIDATE_MESSAGE,
        telemetry=packet,
    )

    assert event.telemetry.heart_rate_bpm == 92


def test_technical_scoring_input_rejects_biometric_fields() -> None:
    with pytest.raises(ValidationError):
        TechnicalScoringInput(
            session_id="session-1",
            event_id="event-1",
            scenario_id=ScenarioId.KUBERNETES_OUTAGE_RECOVERY,
            event_type=EventType.CANDIDATE_MESSAGE,
            candidate_message="restore service",
            heart_rate_bpm=144,  # type: ignore[call-arg]
        )
