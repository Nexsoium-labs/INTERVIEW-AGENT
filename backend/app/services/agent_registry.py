from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

from app.contracts import AgentCard, ModelTier


class AgentRegistryService:
    def __init__(self, owner_system: str) -> None:
        self.owner_system = owner_system

    def issue_default_cards(self) -> list[AgentCard]:
        definitions = [
            (
                "l0-router",
                "Flash Lite Interceptor",
                ModelTier.FLASH_LITE,
                ["semantic-firewall", "cost-routing", "packet-filtering"],
            ),
            (
                "live-synth",
                "Gemini Live Synthesizer",
                ModelTier.LIVE,
                ["voice-interface", "multilingual-delivery", "candidate-dialogue"],
            ),
            (
                "forensics",
                "Quantum Forensics Agent",
                ModelTier.PRO,
                ["identity-verification", "lattice-signature-check", "trust-evaluation"],
            ),
            (
                "orchestrator",
                "Final Orchestrator",
                ModelTier.PRO,
                ["graph-routing", "final-reporting", "human-review-gating"],
            ),
        ]
        return [self._issue_card(*definition) for definition in definitions]

    def _issue_card(
        self,
        agent_id: str,
        agent_name: str,
        model_tier: ModelTier,
        capabilities: list[str],
    ) -> AgentCard:
        fingerprint = hashlib.sha256(f"{agent_id}:{self.owner_system}".encode()).hexdigest()[:32]
        signature = hashlib.sha256(
            f"{agent_id}:{agent_name}:{model_tier}:{capabilities}:{fingerprint}".encode()
        ).hexdigest()
        return AgentCard(
            agent_id=agent_id,
            agent_name=agent_name,
            protocol_version="A2A/1.2",
            owner_system=self.owner_system,
            model_tier=model_tier,
            capabilities=capabilities,
            public_key_fingerprint=fingerprint,
            signature=signature,
            valid_until_utc=datetime.now(UTC) + timedelta(days=30),
        )
