from __future__ import annotations

import math

from app.contracts import (
    ConsensusResult,
    DebatePosition,
    TechnicalRubricScore,
    TechnicalTaskOutcome,
)

try:
    from crewai import Agent, Crew, Task  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    Agent = Crew = Task = None


class CrewDebateOrchestrator:
    """
    Deterministic technical-evidence debate synthesizer.

    The debate consumes only objective rubric and outcome inputs. No overlay or biometric signal
    is accepted on this path.
    """

    async def evaluate(
        self,
        rubric_scores: list[TechnicalRubricScore],
        task_outcomes: list[TechnicalTaskOutcome],
    ) -> ConsensusResult:
        if rubric_scores:
            normalized = [
                0.0 if score.max_score <= 0 else score.score / score.max_score
                for score in rubric_scores
            ]
            quality = sum(normalized) / len(normalized)
        else:
            quality = 0.0

        outcome_penalty = 0.0
        if task_outcomes and any(item.status.value == "failed" for item in task_outcomes):
            outcome_penalty = 0.22
        elif task_outcomes and any(item.status.value == "partial" for item in task_outcomes):
            outcome_penalty = 0.08

        synthesizer_conf = _clamp(quality)
        forensics_conf = _clamp((1.0 - quality) * 0.55 + outcome_penalty)

        assessor_position = DebatePosition(
            agent_name="Technical Synthesizer",
            position="Objective evidence bundle indicates the candidate's work quality.",
            confidence=synthesizer_conf,
        )
        red_team_position = DebatePosition(
            agent_name="Technical Forensics",
            position="Objective evidence bundle was checked for regressions, failures, and gaps.",
            confidence=forensics_conf,
        )

        unified = round(_clamp(synthesizer_conf * 0.68 + (1.0 - forensics_conf) * 0.32) * 100.0, 2)

        return ConsensusResult(
            positions=[assessor_position, red_team_position],
            unified_score=unified,
            rationale=(
                "Consensus computed from rubric-normalized evidence quality and objective outcome "
                "penalties. Telemetry overlay is excluded."
            ),
        )


def _clamp(value: float) -> float:
    if math.isnan(value):
        return 0.0
    return max(0.0, min(1.0, value))
