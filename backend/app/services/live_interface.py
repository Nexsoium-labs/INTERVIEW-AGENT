"""
ZT-ATE Live Interface — Gemini Flash Conversational Layer
==========================================================
Implements the empathetic interviewer avatar using Gemini Flash.

EEOC Firewall
─────────────
The system instruction baked into get_live_model() (see genai_config.py)
contains ZERO reference to biometric signals. This service is additionally
forbidden from reading snapshot.overlay.* — biometric fields must never
enter the prompt construction path. This is enforced structurally: the
only snapshot fields used below are from .technical and .session metadata.

Sliding Window Context
──────────────────────
A per-session ConversationBuffer maintains rolling conversation history.
When the accumulated character count exceeds `settings.live_context_max_chars`,
oldest exchanges are evicted (oldest-first FIFO), ensuring:
  - Long 45-minute interviews stay within the model's context window
  - Recent context is always preserved
  - System prompt is never evicted (it lives in model initialization)

Graceful Degradation
────────────────────
If the Gemini API call fails (rate limit, safety block, network error),
the service returns a "Temporary Cognitive Sync Delay" acknowledgment to
the candidate and schedules a background retry. The event loop is never
blocked and the interview continues uninterrupted.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict

from app.config import settings
from app.contracts import (
    InterviewSessionSnapshot,
    LiveConversationRequest,
    LiveConversationResponse,
)
from app.services.guardrails import GuardrailService

_log = logging.getLogger(__name__)

# Candidate-facing message when the API is temporarily unavailable.
# Deliberately neutral — does not reveal system internals.
_DEGRADATION_RESPONSE = (
    "I'm experiencing a temporary cognitive sync delay. "
    "Please continue working through your approach — "
    "I'm still actively listening and will reconnect momentarily."
)


# ---------------------------------------------------------------------------
# Sliding-window conversation buffer
# ---------------------------------------------------------------------------

class ConversationBuffer:
    """
    FIFO rolling window of conversation turns, bounded by character count.
    Thread-safe for single-session async access (protected by session lock in orchestrator).
    """

    def __init__(self, max_chars: int) -> None:
        self._max_chars = max_chars
        # google-generativeai chat history format: list of {"role": ..., "parts": [...]}
        self._history: list[dict] = []
        self._total_chars: int = 0

    def push(self, role: str, text: str) -> None:
        """Append a turn and evict oldest entries if the window is full."""
        entry = {"role": role, "parts": [text]}
        self._history.append(entry)
        self._total_chars += len(text)
        self._evict()

    def _evict(self) -> None:
        """Drop the oldest turn pairs until we are within the character budget."""
        # Evict in pairs (user + model) to keep history coherent
        while self._total_chars > self._max_chars and len(self._history) >= 2:
            evicted = self._history.pop(0)
            self._total_chars -= len(evicted["parts"][0])

    @property
    def history(self) -> list[dict]:
        return list(self._history)

    @property
    def turn_count(self) -> int:
        return len(self._history)


# ---------------------------------------------------------------------------
# Live Interface Service
# ---------------------------------------------------------------------------

class LiveInterfaceService:
    def __init__(self, guardrail_service: GuardrailService) -> None:
        self.guardrail_service = guardrail_service
        # Per-session conversation buffers — keyed by session_id
        self._buffers: dict[str, ConversationBuffer] = defaultdict(
            lambda: ConversationBuffer(max_chars=settings.live_context_max_chars)
        )

    async def respond(
        self,
        snapshot: InterviewSessionSnapshot,
        request: LiveConversationRequest,
    ) -> LiveConversationResponse:
        """
        Generate an empathetic interviewer response via Gemini Flash.
        Falls back to graceful degradation on any API failure.
        """
        # EEOC FIREWALL: Only technical performance data enters the prompt.
        # snapshot.overlay.* is intentionally never read here.
        hints: list[str] = []

        if snapshot.technical.technical_score < 50:
            coaching_context = (
                "The candidate appears to be working through a difficult section. "
                "Offer structured guidance: start with the failure domain."
            )
            hints.append("structured-guidance")
        else:
            coaching_context = (
                "The candidate is performing well. "
                "Encourage momentum and prompt for deeper tradeoff analysis."
            )
            hints.append("momentum-preservation")

        # Attempt live Gemini Flash response
        response_text = await self._call_gemini_flash(
            session_id=snapshot.session_id,
            candidate_role=snapshot.candidate_role,
            coaching_context=coaching_context,
            candidate_prompt=request.prompt,
        )

        # Run through guardrails before returning to candidate
        envelope = self.guardrail_service.sanitize_candidate_facing_text(response_text)

        return LiveConversationResponse(
            session_id=snapshot.session_id,
            channel=request.channel,
            response_text=envelope.sanitized_text,
            safe_for_candidate=not envelope.blocked,
            hints_used=hints,
        )

    async def _call_gemini_flash(
        self,
        session_id: str,
        candidate_role: str,
        coaching_context: str,
        candidate_prompt: str,
    ) -> str:
        """
        Maintain a sliding-window chat session per interview and send the
        next candidate message. Returns the model's text response.

        On failure: logs the error, schedules a background retry attempt,
        and returns the graceful degradation string immediately.
        """
        try:
            from app.services.genai_config import get_live_model
        except ImportError:
            _log.error("google-generativeai not installed — returning degradation response.")
            return _DEGRADATION_RESPONSE

        buf = self._buffers[session_id]
        model = get_live_model()

        # Build the enriched user turn: coaching context + candidate input.
        # The system prompt (EEOC-hardened interviewer persona) is already
        # baked into the model object — it is never passed here.
        user_turn = (
            f"[Role: {candidate_role}] "
            f"[Context: {coaching_context}] "
            f"Candidate: {candidate_prompt[:1_000]}"
        )

        try:
            # Re-hydrate a chat session from the rolling history buffer.
            # Each call creates a fresh chat object but seeds it with the
            # preserved history — this is the sliding window mechanism.
            chat = model.start_chat(history=buf.history)

            response = await asyncio.wait_for(
                chat.send_message_async(user_turn),
                timeout=12.0,  # hard ceiling: candidate gets degradation before 12s
            )
            model_text: str = response.text.strip()

            # Persist both turns into the rolling buffer
            buf.push("user", user_turn)
            buf.push("model", model_text)

            _log.debug(
                "Live response generated. session_id=%s turns=%d chars_in_buffer=%d",
                session_id,
                buf.turn_count,
                buf._total_chars,
            )
            return model_text

        except asyncio.TimeoutError:
            _log.warning(
                "Gemini Flash timed out for live response. session_id=%s", session_id
            )
            asyncio.create_task(self._retry_in_background(session_id, user_turn))
            return _DEGRADATION_RESPONSE

        except Exception as exc:
            # Catches: ResourceExhausted (rate limit), StopCandidateException (safety),
            # ServiceUnavailable, and any unexpected SDK errors.
            _log.warning(
                "Gemini Flash live call failed: %s. session_id=%s",
                exc,
                session_id,
            )
            asyncio.create_task(self._retry_in_background(session_id, user_turn))
            return _DEGRADATION_RESPONSE

    async def _retry_in_background(self, session_id: str, user_turn: str) -> None:
        """
        Fire-and-forget background retry after a 5-second back-off.
        On success, the response is stored in the session buffer so the
        next turn has coherent history. The candidate is not notified —
        they already received the degradation acknowledgment.
        """
        await asyncio.sleep(5.0)
        try:
            from app.services.genai_config import get_live_model

            buf = self._buffers[session_id]
            model = get_live_model()
            chat = model.start_chat(history=buf.history)
            response = await asyncio.wait_for(
                chat.send_message_async(user_turn),
                timeout=20.0,
            )
            model_text = response.text.strip()
            buf.push("user", user_turn)
            buf.push("model", model_text)
            _log.info(
                "Background retry succeeded. session_id=%s turns=%d",
                session_id,
                buf.turn_count,
            )
        except Exception as exc:
            _log.warning(
                "Background retry also failed: %s. session_id=%s", exc, session_id
            )

    def clear_session(self, session_id: str) -> None:
        """Release conversation buffer when a session is finalized."""
        self._buffers.pop(session_id, None)
