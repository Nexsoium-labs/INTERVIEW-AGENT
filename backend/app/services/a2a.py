from __future__ import annotations

import hashlib

from app.contracts import A2AHandshakeRequest, A2AHandshakeResponse
from app.services.agent_registry import AgentRegistryService


class A2AService:
    def __init__(self, agent_registry: AgentRegistryService) -> None:
        self.agent_registry = agent_registry

    def handshake(self, request: A2AHandshakeRequest) -> A2AHandshakeResponse:
        cards = {card.agent_id: card for card in self.agent_registry.issue_default_cards()}
        requester = cards.get(request.requester_agent_id)
        target = cards.get(request.target_agent_id)

        if requester is None or target is None:
            return A2AHandshakeResponse(
                accepted=False,
                handshake_token="",
                requester_agent_id=request.requester_agent_id,
                target_agent_id=request.target_agent_id,
                approved_capabilities=[],
                reason="Unknown agent identity in handshake request.",
            )

        approved_capabilities = [
            capability
            for capability in request.requested_capabilities
            if capability in target.capabilities
        ]
        accepted = bool(approved_capabilities)
        reason = (
            "Handshake accepted with least-privilege capability subset."
            if accepted
            else "Requested capabilities are not permitted for the target agent."
        )
        token = ""
        if accepted:
            token = hashlib.sha256(
                (
                    f"{request.requester_agent_id}:{request.target_agent_id}:"
                    f"{approved_capabilities}:{request.nonce}:{request.session_id or ''}"
                ).encode()
            ).hexdigest()

        return A2AHandshakeResponse(
            accepted=accepted,
            handshake_token=token,
            requester_agent_id=request.requester_agent_id,
            target_agent_id=request.target_agent_id,
            approved_capabilities=approved_capabilities,
            reason=reason,
        )
