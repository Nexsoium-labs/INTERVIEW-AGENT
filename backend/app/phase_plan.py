from __future__ import annotations

from app.contracts import PhaseDefinition, PhaseStatus


def default_phase_plan() -> list[PhaseDefinition]:
    return [
        PhaseDefinition(
            phase_id=1,
            title="Multi-Framework Topological Mapping",
            owner_framework="Google ADK + LangGraph + Pydantic AI + CrewAI + Agno",
            objective="Assign mathematically optimized ownership of each system layer.",
            status=PhaseStatus.ACTIVE,
        ),
        PhaseDefinition(
            phase_id=2,
            title="Enhanced ReAct Cognitive Engine",
            owner_framework="LangGraph",
            objective="Run deterministic 6-stage async loop with explicit transitions.",
        ),
        PhaseDefinition(
            phase_id=3,
            title="Agent Skill Acquisition",
            owner_framework="Agno",
            objective="Expose external effectors as typed native agent skills.",
        ),
        PhaseDefinition(
            phase_id=4,
            title="Data Contracts and Zero-Trust Ingestion",
            owner_framework="Pydantic AI",
            objective="Reject schema drift and enforce self-correction before state mutation.",
        ),
        PhaseDefinition(
            phase_id=5,
            title="State Machine and Workflow Routing",
            owner_framework="LangGraph",
            objective="Maintain one source of truth for interview graph continuity.",
        ),
        PhaseDefinition(
            phase_id=6,
            title="Multi-Agent Swarm Orchestration",
            owner_framework="CrewAI",
            objective="Run adversarial agent debate and return unified confidence score.",
        ),
        PhaseDefinition(
            phase_id=7,
            title="Memory Architectures",
            owner_framework="LangGraph + Vector DB",
            objective="Separate ephemeral, working, and long-term retrieval memory planes.",
        ),
        PhaseDefinition(
            phase_id=8,
            title="Flash Lite Interceptor",
            owner_framework="Google ADK",
            objective="Filter low-value packets and gate expensive model escalation.",
        ),
        PhaseDefinition(
            phase_id=9,
            title="Gemini Live Synthesizer",
            owner_framework="Google ADK",
            objective="Provide low-latency multilingual interface detached from scoring logic.",
        ),
        PhaseDefinition(
            phase_id=10,
            title="Deep Core Glass-Box Export",
            owner_framework="Gemini 3.1 Pro",
            objective="Produce immutable, auditable decision report and final score.",
        ),
        PhaseDefinition(
            phase_id=11,
            title="Observability and Continuous Evaluation",
            owner_framework="DeepEval or Phoenix",
            objective="Track faithfulness, relevance, drift, and cost-aware rerouting.",
        ),
        PhaseDefinition(
            phase_id=12,
            title="A2A Protocol Integration",
            owner_framework="A2A v1.2",
            objective="Secure agent handoff using signed cryptographic agent cards.",
        ),
        PhaseDefinition(
            phase_id=13,
            title="Security Hardening and Runtime Protection",
            owner_framework="Guardrails + gVisor",
            objective="Block prompt injection and enforce least-privilege sandbox execution.",
        ),
        PhaseDefinition(
            phase_id=14,
            title="Hardware Abstraction and Deployment",
            owner_framework="Docker + Cloud Run",
            objective="Local high-bandwidth prototyping and cloud autoscaling deployment.",
        ),
        PhaseDefinition(
            phase_id=15,
            title="Human-in-the-Loop Governance",
            owner_framework="EEOC/GDPR Governance",
            objective="Require human cryptographic approval for final legal hiring decision.",
        ),
    ]
