"""
ZT-ATE API Routes
==================
Zero-Trust route layer. Every endpoint is classified into one of three tiers:

  PUBLIC           — No token required (health, auth/issue-token).
  VERIFIED         — Any valid JWT accepted (candidate or operator).
  OPERATOR_ONLY    — Requires operator role in token; 403 otherwise.

The plane-segregation guarantee is now cryptographic:
  Operator-plane data (overlay, glass-box, review-segments, audit-export)
  is gated by `require_operator` which validates the signed role claim —
  not a client-controllable header.
"""

from __future__ import annotations

import hmac
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from pydantic import BaseModel

from app.contracts import (
    A2AHandshakeRequest,
    A2AHandshakeResponse,
    AgentCard,
    ConsentCaptureRequest,
    ConsentRecord,
    EventIngestRequest,
    FinalizeInterviewRequest,
    GlassBoxReport,
    HumanReviewDecisionRequest,
    HumanReviewRecord,
    InterviewMilestoneSnapshot,
    InterviewSessionCreate,
    InterviewSessionSnapshot,
    LatticeVerificationRequest,
    LatticeVerificationResponse,
    LiveConversationRequest,
    LiveConversationResponse,
    NeuroSymbolicMapRequest,
    ObservabilitySnapshot,
    OperatorReviewSegment,
    PhaseDefinition,
    PhaseRevision,
    PhaseRevisionRequest,
    RPPGExtractionRequest,
    RPPGExtractionResponse,
    SandboxDeploymentRequest,
    SandboxDeploymentResponse,
    SessionAuditExport,
    TechnicalTaskArtifact,
    TelemetryOverlayPlane,
    TraceEvent,
    sanitize_for_candidate,
)
from app.security.auth import (
    SessionCreateResponse,
    TokenResponse,
    mint_candidate_token,
    mint_operator_token,
    require_operator,
    verify_token,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Auth request model (lives here to avoid a separate file for one model)
# ---------------------------------------------------------------------------

class OperatorTokenRequest(BaseModel):
    operator_secret: str


# ---------------------------------------------------------------------------
# PUBLIC — no authentication required
# ---------------------------------------------------------------------------

@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post(
    "/auth/issue-token",
    response_model=TokenResponse,
    summary="Mint an operator-tier JWT. Requires the OPERATOR_MASTER_SECRET.",
)
async def issue_operator_token(
    request: Request,
    payload: OperatorTokenRequest,
) -> TokenResponse:
    """
    Validates the submitted operator_secret against the configured
    OPERATOR_MASTER_SECRET using a constant-time comparison to prevent
    timing-based secret enumeration.
    """
    from app.config import settings  # local import: avoids circular at module init

    secret_matches = hmac.compare_digest(
        payload.operator_secret.encode(),
        settings.operator_master_secret.encode(),
    )
    if not secret_matches:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid operator secret.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return mint_operator_token()


# ---------------------------------------------------------------------------
# WebSocket — token passed as ?token= query param (Bearer header not
# supported by the WS protocol).  Full JWT validation applied.
# ---------------------------------------------------------------------------

@router.websocket("/sessions/{session_id}/ws")
async def session_stream(websocket: WebSocket, session_id: str) -> None:
    from app.security.auth import _decode  # intentionally internal

    token = websocket.query_params.get("token", "")
    try:
        _decode(token)  # raises → websocket.close() not strictly needed; connection drops
    except HTTPException:
        await websocket.close(code=4001)
        return

    orchestrator = websocket.app.state.orchestrator
    await orchestrator.stream_hub.connect(session_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        orchestrator.stream_hub.disconnect(session_id, websocket)


# ---------------------------------------------------------------------------
# OPERATOR_ONLY — Session lifecycle (operators create/finalize/review)
# ---------------------------------------------------------------------------

@router.post(
    "/sessions",
    response_model=SessionCreateResponse,
    summary="Create a new interview session. Returns session snapshot + candidate JWT.",
)
async def create_session(
    request: Request,
    payload: InterviewSessionCreate,
    _claims: Annotated[dict, Depends(require_operator)],
) -> SessionCreateResponse:
    """
    Operator creates the session; the response includes a candidate_token
    cryptographically bound to the new session_id. The operator forwards
    this token to the interviewee — no second round-trip needed.
    """
    orchestrator = request.app.state.orchestrator
    session: InterviewSessionSnapshot = await orchestrator.create_session(payload)
    return SessionCreateResponse(
        session=session,
        candidate_token=mint_candidate_token(session.session_id),
    )


@router.post(
    "/sessions/{session_id}/finalize",
    response_model=GlassBoxReport,
)
async def finalize_session(
    request: Request,
    session_id: str,
    payload: FinalizeInterviewRequest,
    _claims: Annotated[dict, Depends(require_operator)],
) -> GlassBoxReport:
    orchestrator = request.app.state.orchestrator
    try:
        return await orchestrator.finalize_session(session_id=session_id, request=payload)
    except KeyError as err:
        raise HTTPException(status_code=404, detail="session not found") from err
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.post(
    "/sessions/{session_id}/human-review",
    response_model=HumanReviewRecord,
)
async def human_review(
    request: Request,
    session_id: str,
    payload: HumanReviewDecisionRequest,
    _claims: Annotated[dict, Depends(require_operator)],
) -> HumanReviewRecord:
    orchestrator = request.app.state.orchestrator
    try:
        return await orchestrator.record_human_review(session_id=session_id, request=payload)
    except KeyError as err:
        raise HTTPException(status_code=404, detail="session not found") from err
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


# ---------------------------------------------------------------------------
# OPERATOR_ONLY — Biometric / telemetry plane (the three critical vectors)
# ---------------------------------------------------------------------------

@router.get(
    "/sessions/{session_id}/overlay",
    response_model=TelemetryOverlayPlane,
    summary="[OPERATOR] Full rPPG biometric overlay. 403 for non-operator tokens.",
)
async def telemetry_overlay(
    request: Request,
    session_id: str,
    _claims: Annotated[dict, Depends(require_operator)],
) -> TelemetryOverlayPlane:
    orchestrator = request.app.state.orchestrator
    try:
        return await orchestrator.get_overlay(session_id)
    except KeyError as err:
        raise HTTPException(status_code=404, detail="session not found") from err


@router.get(
    "/sessions/{session_id}/review-segments",
    response_model=list[OperatorReviewSegment],
    summary="[OPERATOR] Flagged review segments with biometric annotations.",
)
async def review_segments(
    request: Request,
    session_id: str,
    _claims: Annotated[dict, Depends(require_operator)],
) -> list[OperatorReviewSegment]:
    orchestrator = request.app.state.orchestrator
    try:
        return await orchestrator.get_review_segments(session_id)
    except KeyError as err:
        raise HTTPException(status_code=404, detail="session not found") from err


@router.get(
    "/sessions/{session_id}/glass-box",
    response_model=GlassBoxReport,
    summary="[OPERATOR] Neuro-Symbolic Glass-Box final report.",
)
async def glass_box_report(
    request: Request,
    session_id: str,
    _claims: Annotated[dict, Depends(require_operator)],
) -> GlassBoxReport:
    orchestrator = request.app.state.orchestrator
    try:
        return await orchestrator.get_final_report(session_id)
    except KeyError as err:
        raise HTTPException(status_code=404, detail="session not found") from err
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.get(
    "/sessions/{session_id}/audit-export",
    response_model=SessionAuditExport,
    summary="[OPERATOR] Full audit export including ConsentRecord.",
)
async def audit_export(
    request: Request,
    session_id: str,
    _claims: Annotated[dict, Depends(require_operator)],
) -> SessionAuditExport:
    orchestrator = request.app.state.orchestrator
    try:
        return await orchestrator.get_audit_export(session_id)
    except KeyError as err:
        raise HTTPException(status_code=404, detail="session not found") from err


# ---------------------------------------------------------------------------
# OPERATOR_ONLY — Observability, trace, artifacts, phases, agents, tools
# ---------------------------------------------------------------------------

@router.get("/sessions/{session_id}/trace", response_model=list[TraceEvent])
async def list_trace(
    request: Request,
    session_id: str,
    _claims: Annotated[dict, Depends(require_operator)],
    limit: int = 200,
) -> list[TraceEvent]:
    orchestrator = request.app.state.orchestrator
    try:
        return await orchestrator.list_trace_events(session_id=session_id, limit=limit)
    except KeyError as err:
        raise HTTPException(status_code=404, detail="session not found") from err


@router.get("/sessions/{session_id}/artifacts", response_model=list[TechnicalTaskArtifact])
async def technical_artifacts(
    request: Request,
    session_id: str,
    _claims: Annotated[dict, Depends(require_operator)],
) -> list[TechnicalTaskArtifact]:
    orchestrator = request.app.state.orchestrator
    try:
        return await orchestrator.get_technical_artifacts(session_id)
    except KeyError as err:
        raise HTTPException(status_code=404, detail="session not found") from err


@router.get("/sessions/{session_id}/observability", response_model=ObservabilitySnapshot)
async def session_observability(
    request: Request,
    session_id: str,
    _claims: Annotated[dict, Depends(require_operator)],
) -> ObservabilitySnapshot:
    orchestrator = request.app.state.orchestrator
    try:
        return await orchestrator.get_observability(session_id=session_id)
    except KeyError as err:
        raise HTTPException(status_code=404, detail="session not found") from err


@router.get("/phases", response_model=list[PhaseDefinition])
async def list_phases(
    request: Request,
    _claims: Annotated[dict, Depends(require_operator)],
) -> list[PhaseDefinition]:
    storage = request.app.state.storage
    return await storage.list_phases()


@router.post("/phases/{phase_id}/revisions", response_model=PhaseRevision)
async def revise_phase(
    request: Request,
    phase_id: int,
    payload: PhaseRevisionRequest,
    _claims: Annotated[dict, Depends(require_operator)],
) -> PhaseRevision:
    storage = request.app.state.storage
    try:
        return await storage.revise_phase(phase_id=phase_id, request=payload)
    except KeyError as err:
        raise HTTPException(status_code=404, detail="phase not found") from err


@router.get("/agent-cards", response_model=list[AgentCard])
async def agent_cards(
    request: Request,
    _claims: Annotated[dict, Depends(require_operator)],
) -> list[AgentCard]:
    orchestrator = request.app.state.orchestrator
    return orchestrator.get_agent_cards()


@router.post("/a2a/handshake", response_model=A2AHandshakeResponse)
async def a2a_handshake(
    request: Request,
    payload: A2AHandshakeRequest,
    _claims: Annotated[dict, Depends(require_operator)],
) -> A2AHandshakeResponse:
    orchestrator = request.app.state.orchestrator
    return orchestrator.perform_a2a_handshake(payload)


@router.post("/tools/extract-rppg", response_model=RPPGExtractionResponse)
async def extract_rppg(
    request: Request,
    payload: RPPGExtractionRequest,
    _claims: Annotated[dict, Depends(require_operator)],
) -> RPPGExtractionResponse:
    orchestrator = request.app.state.orchestrator
    result = await orchestrator.agno_tools.extract_rppg_pulse(payload.video_frame)
    return RPPGExtractionResponse.model_validate(result)


@router.post("/tools/verify-lattice", response_model=LatticeVerificationResponse)
async def verify_lattice(
    request: Request,
    payload: LatticeVerificationRequest,
    _claims: Annotated[dict, Depends(require_operator)],
) -> LatticeVerificationResponse:
    orchestrator = request.app.state.orchestrator
    result = await orchestrator.agno_tools.verify_lattice_signature(payload.wallet_address)
    return LatticeVerificationResponse.model_validate(result)


@router.post("/tools/deploy-sandbox", response_model=SandboxDeploymentResponse)
async def deploy_sandbox(
    request: Request,
    payload: SandboxDeploymentRequest,
    _claims: Annotated[dict, Depends(require_operator)],
) -> SandboxDeploymentResponse:
    orchestrator = request.app.state.orchestrator
    result = await orchestrator.agno_tools.deploy_ephemeral_kubernetes(
        scenario_id=payload.scenario_id,
        manifest=payload.manifest,
    )
    return SandboxDeploymentResponse.model_validate(result)


@router.post("/tools/neuro-symbolic-map")
async def neuro_symbolic_map(
    request: Request,
    payload: NeuroSymbolicMapRequest,
    _claims: Annotated[dict, Depends(require_operator)],
) -> dict[str, Any]:
    orchestrator = request.app.state.orchestrator
    return await orchestrator.agno_tools.execute_neuro_symbolic_map(payload.reasoning_trace)


# ---------------------------------------------------------------------------
# VERIFIED — any valid JWT (candidate or operator)
# ---------------------------------------------------------------------------

@router.get("/sessions/{session_id}", response_model=InterviewSessionSnapshot)
async def get_session(
    request: Request,
    session_id: str,
    _claims: Annotated[dict, Depends(verify_token)],
) -> InterviewSessionSnapshot:
    orchestrator = request.app.state.orchestrator
    try:
        return await orchestrator.get_session(session_id)
    except KeyError as err:
        raise HTTPException(status_code=404, detail="session not found") from err


@router.get(
    "/sessions/{session_id}/candidate",
    response_model=InterviewSessionSnapshot,
    summary="[CANDIDATE] EEOC-safe session snapshot.",
)
async def get_candidate_session(
    request: Request,
    session_id: str,
    claims: Annotated[dict, Depends(verify_token)],
) -> InterviewSessionSnapshot:
    """Return a candidate-safe snapshot with biometric overlay fields zeroed."""
    from app.security.auth import SESSION_CLAIM

    roles = claims.get("https://zt-ate.com/roles", [])
    is_operator = "operator" in roles

    if not is_operator:
        token_session_id = claims.get(SESSION_CLAIM)
        if token_session_id != session_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Candidate token is not bound to this session.",
            )

    orchestrator = request.app.state.orchestrator
    try:
        snapshot = await orchestrator.get_session(session_id)
    except KeyError as err:
        raise HTTPException(status_code=404, detail="session not found") from err

    return sanitize_for_candidate(snapshot)


@router.post("/sessions/{session_id}/consent", response_model=ConsentRecord)
async def capture_consent(
    request: Request,
    session_id: str,
    payload: ConsentCaptureRequest,
    _claims: Annotated[dict, Depends(verify_token)],
) -> ConsentRecord:
    orchestrator = request.app.state.orchestrator
    try:
        return await orchestrator.capture_consent(session_id=session_id, request=payload)
    except KeyError as err:
        raise HTTPException(status_code=404, detail="session not found") from err


@router.post("/sessions/{session_id}/events", response_model=InterviewSessionSnapshot)
async def ingest_event(
    request: Request,
    session_id: str,
    payload: EventIngestRequest,
    _claims: Annotated[dict, Depends(verify_token)],
) -> InterviewSessionSnapshot:
    orchestrator = request.app.state.orchestrator
    try:
        return await orchestrator.ingest_event(session_id=session_id, request=payload)
    except KeyError as err:
        raise HTTPException(status_code=404, detail="session not found") from err
    except RuntimeError as err:
        raise HTTPException(status_code=409, detail=str(err)) from err
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.get("/sessions/{session_id}/milestones", response_model=list[InterviewMilestoneSnapshot])
async def milestones(
    request: Request,
    session_id: str,
    _claims: Annotated[dict, Depends(verify_token)],
    limit: int = 200,
) -> list[InterviewMilestoneSnapshot]:
    orchestrator = request.app.state.orchestrator
    try:
        return await orchestrator.list_milestones(session_id=session_id, limit=limit)
    except KeyError as err:
        raise HTTPException(status_code=404, detail="session not found") from err


@router.post(
    "/sessions/{session_id}/live-response",
    response_model=LiveConversationResponse,
)
async def live_response(
    request: Request,
    session_id: str,
    payload: LiveConversationRequest,
    _claims: Annotated[dict, Depends(verify_token)],
) -> LiveConversationResponse:
    orchestrator = request.app.state.orchestrator
    try:
        return await orchestrator.generate_live_response(session_id=session_id, request=payload)
    except KeyError as err:
        raise HTTPException(status_code=404, detail="session not found") from err
