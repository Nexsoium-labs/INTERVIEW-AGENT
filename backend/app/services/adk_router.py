"""
ZT-ATE L0 Triage Router — Gemini Flash Lite Integration
=========================================================
Routing pipeline (in priority order):

  1. Silence gate        — deterministic drop, zero LLM cost
  2. Injection gate      — deterministic escalation to PRO, zero LLM cost
  3. Flash Lite classify — live API call: extracts intent, determines O(1) vs O(n)
     a. O(1) intent      → stays on Flash Lite lane (no escalation)
     b. O(n) / code      → escalated to PRO
  4. Deterministic fallback — used when Flash Lite call fails (rate limit, timeout)

Async contract: every public method is a coroutine. The FastAPI event loop
is never blocked.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import aiohttp

from app.contracts import CandidateEvent, EventType, L0RouteDecision, ModelTier
from app.config import Settings
from app.security.validators import contains_prompt_injection, sanitize_candidate_text

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Flash Lite classification prompt — compact for minimal token spend
# ---------------------------------------------------------------------------
_L0_CLASSIFY_PROMPT = """You are an interview event classifier. Classify the complexity of this candidate event for routing.

Event type: {event_type}
Content preview (first 600 chars):
{content}

Rules:
- O(1): Simple acknowledgment, yes/no answer, brief factual question, system ping, empty message.
- O(n): Code analysis, multi-step debugging, architecture explanation, security review, algorithm design.

Respond ONLY with valid JSON, no explanation:
{{"complexity": "O(1)" or "O(n)", "intent": "<3-6 word label>", "confidence": 0.0-1.0}}"""


class GoogleADKService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def route_event(self, event: CandidateEvent) -> L0RouteDecision:
        """
        Full L0 triage pipeline. Returns a routing decision that the graph
        uses to select the processing tier.
        """
        # 1. Silence gate — no LLM needed
        silent_decision = self._check_silence(event)
        if silent_decision is not None:
            return silent_decision

        # 2. Injection gate — no LLM needed, escalate immediately
        injection_decision = self._check_injection(event)
        if injection_decision is not None:
            return injection_decision

        # 3. Try the remote ADK router first (if configured)
        if self.settings.adk_router_url:
            remote = await self._route_event_remote(event)
            if remote is not None:
                return remote

        # 4. Flash Lite live classification
        flash_lite_decision = await self._classify_with_flash_lite(event)
        if flash_lite_decision is not None:
            return flash_lite_decision

        # 5. Deterministic fallback (Flash Lite unavailable)
        return self._deterministic_fallback(event)

    # ------------------------------------------------------------------
    # Gate checks (deterministic, zero LLM cost)
    # ------------------------------------------------------------------

    def _check_silence(self, event: CandidateEvent) -> L0RouteDecision | None:
        """Drop silent packets before touching any LLM."""
        semantic_text = _extract_semantic_text(event)
        if (
            event.telemetry.silence_ms >= self.settings.l0_silence_cutoff_ms
            and not semantic_text
            and event.event_type != EventType.WEBCAM_FRAME
        ):
            return L0RouteDecision(
                pass_through=False,
                reason="Dropped silent packet at deterministic L0 gate (pre-LLM).",
                target_tier=ModelTier.FLASH_LITE,
                tokens_saved_estimate=90,
                fallback_used=False,
                routed_lane="dropped",
            )
        return None

    def _check_injection(self, event: CandidateEvent) -> L0RouteDecision | None:
        """Escalate prompt injection attempts immediately to PRO security lane."""
        semantic_text = _extract_semantic_text(event)
        if semantic_text and contains_prompt_injection(semantic_text):
            _log.warning(
                "Prompt injection signature detected. session_id=%s event_type=%s",
                event.session_id,
                event.event_type,
            )
            return L0RouteDecision(
                pass_through=True,
                reason="Prompt injection detected. Escalated to PRO security lane.",
                target_tier=ModelTier.PRO,
                tokens_saved_estimate=0,
                fallback_used=False,
                routed_lane="security_escalation",
            )
        return None

    # ------------------------------------------------------------------
    # Flash Lite — live intent classification
    # ------------------------------------------------------------------

    async def _classify_with_flash_lite(
        self, event: CandidateEvent
    ) -> L0RouteDecision | None:
        """
        Call Gemini Flash Lite to classify the event intent.
        Returns None if the call fails (caller falls through to deterministic fallback).
        """
        try:
            from app.services.genai_config import get_flash_lite_model
        except ImportError:
            return None

        semantic_text = _extract_semantic_text(event)
        content_preview = semantic_text[:600] if semantic_text else "(empty)"

        prompt = _L0_CLASSIFY_PROMPT.format(
            event_type=event.event_type.value,
            content=content_preview,
        )

        try:
            model = get_flash_lite_model()
            # asyncio.wait_for enforces a hard ceiling so one slow call
            # cannot stall the entire event ingest pipeline.
            response = await asyncio.wait_for(
                model.generate_content_async(prompt),
                timeout=self.settings.adk_timeout_seconds,
            )
            return self._parse_flash_lite_response(response.text, event)

        except asyncio.TimeoutError:
            _log.warning(
                "Flash Lite classification timed out (%.1fs). "
                "Falling back to deterministic routing. session_id=%s",
                self.settings.adk_timeout_seconds,
                event.session_id,
            )
            return None

        except Exception as exc:  # rate limit, safety block, network error
            _log.warning(
                "Flash Lite classification failed: %s. "
                "Falling back to deterministic routing. session_id=%s",
                exc,
                event.session_id,
            )
            return None

    def _parse_flash_lite_response(
        self, raw_text: str, event: CandidateEvent
    ) -> L0RouteDecision | None:
        """Parse the JSON classification returned by Flash Lite."""
        try:
            data: dict[str, Any] = json.loads(raw_text.strip())
            complexity: str = data.get("complexity", "O(n)")
            intent: str = data.get("intent", "unclassified")
            confidence: float = float(data.get("confidence", 0.5))
        except (json.JSONDecodeError, ValueError, TypeError):
            _log.warning(
                "Flash Lite returned unparseable JSON: %r", raw_text[:200]
            )
            return None

        # O(1): stays on Flash Lite — no escalation
        if complexity == "O(1)" and confidence >= 0.60:
            return L0RouteDecision(
                pass_through=True,
                reason=f"Flash Lite: O(1) complexity — intent={intent!r} confidence={confidence:.2f}",
                target_tier=ModelTier.FLASH_LITE,
                tokens_saved_estimate=40,
                fallback_used=False,
                routed_lane="candidate_safe",
            )

        # O(n) or low-confidence O(1) — escalate to PRO
        # Code deltas always escalate regardless of Flash Lite opinion
        if event.event_type == EventType.CODE_DELTA or complexity == "O(n)":
            return L0RouteDecision(
                pass_through=True,
                reason=f"Flash Lite: O(n) complexity — intent={intent!r} confidence={confidence:.2f}",
                target_tier=ModelTier.PRO,
                tokens_saved_estimate=0,
                fallback_used=False,
                routed_lane="deep_analysis",
            )

        # Ambiguous classification — default to Flash Lite (safer/cheaper)
        return L0RouteDecision(
            pass_through=True,
            reason=f"Flash Lite: ambiguous classification — intent={intent!r} confidence={confidence:.2f}",
            target_tier=ModelTier.FLASH_LITE,
            tokens_saved_estimate=20,
            fallback_used=False,
            routed_lane="candidate_safe",
        )

    # ------------------------------------------------------------------
    # Remote ADK router (optional external service)
    # ------------------------------------------------------------------

    async def _route_event_remote(self, event: CandidateEvent) -> L0RouteDecision | None:
        headers = {"Content-Type": "application/json"}
        if self.settings.adk_api_key:
            headers["Authorization"] = f"Bearer {self.settings.adk_api_key}"

        timeout = aiohttp.ClientTimeout(total=self.settings.adk_timeout_seconds)
        payload = event.model_dump(mode="json")

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    self.settings.adk_router_url,
                    json=payload,
                    headers=headers,
                ) as response:
                    if response.status >= 400:
                        return None
                    data: dict[str, Any] = await response.json()
                    decision = L0RouteDecision.model_validate(data)
                    return decision.model_copy(update={"fallback_used": False})
        except (TimeoutError, aiohttp.ClientError, ValueError):
            return None

    # ------------------------------------------------------------------
    # Deterministic fallback (no LLM)
    # ------------------------------------------------------------------

    def _deterministic_fallback(self, event: CandidateEvent) -> L0RouteDecision:
        """
        Purely rule-based routing used when Flash Lite is unavailable.
        Identical to the original local router — preserves system availability.
        """
        semantic_text = _extract_semantic_text(event)
        signal_size = len(semantic_text)

        if signal_size > 2_500 or event.event_type == EventType.CODE_DELTA:
            return L0RouteDecision(
                pass_through=True,
                reason="Fallback: high-complexity artifact routed to PRO.",
                target_tier=ModelTier.PRO,
                tokens_saved_estimate=0,
                fallback_used=True,
                routed_lane="deep_analysis",
            )

        if event.event_type == EventType.SYSTEM_SIGNAL:
            return L0RouteDecision(
                pass_through=True,
                reason="Fallback: system signal routed to Flash Lite.",
                target_tier=ModelTier.FLASH_LITE,
                tokens_saved_estimate=20,
                fallback_used=True,
                routed_lane="tool_recovery",
            )

        return L0RouteDecision(
            pass_through=True,
            reason="Fallback: default Flash Lite candidate-safe lane.",
            target_tier=ModelTier.FLASH_LITE,
            tokens_saved_estimate=35,
            fallback_used=True,
            routed_lane="candidate_safe",
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_semantic_text(event: CandidateEvent) -> str:
    return sanitize_candidate_text(
        "\n".join(
            filter(
                None,
                [
                    event.telemetry.audio_text or "",
                    event.telemetry.candidate_message or "",
                    event.telemetry.code_delta or "",
                ],
            )
        )
    )
