from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

FAKE_SID = "00000000-0000-0000-0000-000000000001"
OTHER_SID = "00000000-0000-0000-0000-000000000002"


@pytest.mark.asyncio
async def test_candidate_endpoint_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(f"/api/sessions/{FAKE_SID}/candidate")
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_candidate_token_bound_to_wrong_session_rejected():
    from app.security.auth import mint_candidate_token

    token = mint_candidate_token(FAKE_SID)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(
            f"/api/sessions/{OTHER_SID}/candidate",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 403
    assert "not bound to this session" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_overlay_zeroed_for_candidate():
    from app.contracts import (
        InterviewSessionSnapshot,
        ScenarioId,
        TechnicalScorePlane,
        TelemetryOverlayPlane,
    )
    from app.security.auth import mint_candidate_token

    overlay = TelemetryOverlayPlane(
        overlay_enabled=True,
        collection_mode="active",
        telemetry_timeline=[],
        stress_markers=[],
        overlay_segments=[],
        operator_review_flags=["spike"],
        review_segments=[],
        latest_stress_index=0.9,
        latest_heart_rate_bpm=110,
        overlay_processing_lag_ms=50,
        excluded_from_automated_scoring=False,
    )
    technical = TechnicalScorePlane(
        scenario_id=ScenarioId.ALGORITHM_CODING_TASK,
        technical_score=80,
        technical_verdict=None,
        task_outcomes=[],
        rubric_scores=[],
        evidence_bundle=[],
        contamination_check_passed=True,
        locked=False,
    )
    snap = InterviewSessionSnapshot(
        session_id=FAKE_SID,
        candidate_id="c",
        candidate_role="Eng",
        language="en",
        scenario_id=ScenarioId.ALGORITHM_CODING_TASK,
        technical=technical,
        overlay=overlay,
        session_status="active",
        simulation_status="assessment_live",
        event_count=0,
        last_route_target=None,
        report_available=False,
        human_decision=None,
        consent_record=None,
        completed_at_utc=None,
        last_updated_utc="2024-01-01T00:00:00Z",
        trace_events=[],
        milestone_count=0,
    )
    app.state.orchestrator = AsyncMock()
    app.state.orchestrator.get_session = AsyncMock(return_value=snap)
    token = mint_candidate_token(FAKE_SID)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(
            f"/api/sessions/{FAKE_SID}/candidate",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["overlay"]["overlay_enabled"] is False
    assert body["overlay"]["latest_heart_rate_bpm"] is None
    assert body["overlay"]["operator_review_flags"] == []
    assert body["overlay"]["excluded_from_automated_scoring"] is True
