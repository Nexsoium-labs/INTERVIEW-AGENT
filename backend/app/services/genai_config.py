"""
ZT-ATE Gemini SDK Configuration
=================================
Single source of truth for:
  - API key initialization (called once at server startup)
  - Safety settings tuned for enterprise technical interviews
  - Model factory functions — one per tier

Tier topology
─────────────
  FLASH_LITE  →  get_flash_lite_model()  →  L0 intent classification (O(1) triage)
  FLASH       →  get_live_model()         →  Live conversational interface
  PRO         →  get_pro_model()          →  Async Glass-Box report synthesis

Migration note
──────────────
All model identifiers are loaded from `settings.*_model` so they can be
overridden via `.env` without touching source code. Swapping to a new
model family requires only an `.env` change.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

_log = logging.getLogger(__name__)

try:
    import google.generativeai as genai
    from google.generativeai import GenerationConfig
    from google.generativeai.types import HarmBlockThreshold, HarmCategory

    _SDK_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SDK_AVAILABLE = False
    _log.warning(
        "google-generativeai not installed. Gemini API calls will be unavailable. "
        "Run: pip install google-generativeai"
    )

# ---------------------------------------------------------------------------
# Safety settings
# ---------------------------------------------------------------------------
# BLOCK_ONLY_HIGH for technical content — security/exploit discussion,
# system debugging, and threat-modeling are legitimate interview topics.
# Tightened to BLOCK_MEDIUM_AND_ABOVE for sexually explicit content only.

def _build_safety_settings() -> list[dict[str, Any]]:
    if not _SDK_AVAILABLE:
        return []
    return [
        {
            "category": HarmCategory.HARM_CATEGORY_HARASSMENT,
            "threshold": HarmBlockThreshold.BLOCK_ONLY_HIGH,
        },
        {
            "category": HarmCategory.HARM_CATEGORY_HATE_SPEECH,
            "threshold": HarmBlockThreshold.BLOCK_ONLY_HIGH,
        },
        {
            "category": HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
            "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        },
        {
            "category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
            "threshold": HarmBlockThreshold.BLOCK_ONLY_HIGH,
        },
    ]

INTERVIEW_SAFETY_SETTINGS: list[dict[str, Any]] = _build_safety_settings()

# ---------------------------------------------------------------------------
# EEOC-compliant system instruction for the Live conversational interface.
# Deliberately contains zero reference to biometric signals.
# ---------------------------------------------------------------------------
LIVE_SYSTEM_INSTRUCTION = (
    "You are a professional and empathetic technical interviewer. "
    "Your sole purpose is to guide the candidate through technical challenges "
    "using clear questions, constructive prompts, and encouraging feedback. "
    "You have ZERO access to — and must NEVER infer, reference, or react to — "
    "any physiological or biometric information about the candidate, including "
    "stress levels, heart rate, vocal stress indicators, or emotional state. "
    "Your responses must be based exclusively on the candidate's spoken or "
    "written technical content. Keep answers concise, supportive, and focused "
    "on the problem domain."
)

# ---------------------------------------------------------------------------
# SDK initialization
# ---------------------------------------------------------------------------

_initialized = False


def ensure_configured() -> None:
    """
    Initialize the Gemini SDK with the API key from settings.
    Safe to call multiple times — only configures once.
    Raises RuntimeError if the key is absent.
    """
    global _initialized
    if _initialized:
        return
    if not _SDK_AVAILABLE:
        raise RuntimeError(
            "google-generativeai package is not installed. "
            "Add it to pyproject.toml and reinstall."
        )

    from app.config import settings  # local import — avoids circular at module init

    if not settings.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. "
            "Add it to backend/.env: GEMINI_API_KEY=<your-key>"
        )

    genai.configure(api_key=settings.gemini_api_key)
    _initialized = True
    _log.info(
        "Gemini SDK configured. flash=%s  live=%s  pro=%s",
        settings.flash_model,
        settings.live_model,
        settings.pro_model,
    )


# ---------------------------------------------------------------------------
# Model factories
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_flash_lite_model() -> "genai.GenerativeModel":
    """
    L0 triage model — lowest cost, fastest response.
    JSON output mode enabled; temperature near-zero for deterministic routing.
    """
    ensure_configured()
    from app.config import settings

    return genai.GenerativeModel(
        model_name=settings.flash_model,
        safety_settings=INTERVIEW_SAFETY_SETTINGS,
        generation_config=GenerationConfig(
            temperature=0.05,
            max_output_tokens=256,
            response_mime_type="application/json",
        ),
    )


@lru_cache(maxsize=1)
def get_live_model() -> "genai.GenerativeModel":
    """
    Live conversational model — EEOC-hardened system instruction baked in.
    Higher temperature for natural, empathetic dialogue.
    """
    ensure_configured()
    from app.config import settings

    return genai.GenerativeModel(
        model_name=settings.live_model,
        safety_settings=INTERVIEW_SAFETY_SETTINGS,
        generation_config=GenerationConfig(
            temperature=0.70,
            max_output_tokens=512,
        ),
        system_instruction=LIVE_SYSTEM_INSTRUCTION,
    )


@lru_cache(maxsize=1)
def get_pro_model() -> "genai.GenerativeModel":
    """
    Deep reasoning model — Glass-Box synthesis only.
    Low temperature for analytical consistency; large output window for full report.
    """
    ensure_configured()
    from app.config import settings

    return genai.GenerativeModel(
        model_name=settings.pro_model,
        safety_settings=INTERVIEW_SAFETY_SETTINGS,
        generation_config=GenerationConfig(
            temperature=0.15,
            max_output_tokens=8192,
        ),
    )
