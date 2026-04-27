from __future__ import annotations

import re

from app.contracts import GuardrailEnvelope, GuardrailFinding

_EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_PATTERN = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?){2}\d{4}\b")
_BIAS_PATTERNS = {
    "bias.age": re.compile(r"\btoo old\b|\btoo young\b", re.IGNORECASE),
    "bias.gender": re.compile(r"\bmale only\b|\bfemale only\b", re.IGNORECASE),
    "bias.ethnicity": re.compile(r"\bethnic\b|\brace\b", re.IGNORECASE),
}


class GuardrailService:
    def sanitize_candidate_facing_text(self, text: str) -> GuardrailEnvelope:
        sanitized = text
        findings: list[GuardrailFinding] = []

        if _EMAIL_PATTERN.search(sanitized):
            findings.append(
                GuardrailFinding(
                    rule_id="pii.email",
                    severity="high",
                    detail="Email address detected in candidate-facing content.",
                )
            )
            sanitized = _EMAIL_PATTERN.sub("[redacted-email]", sanitized)

        if _PHONE_PATTERN.search(sanitized):
            findings.append(
                GuardrailFinding(
                    rule_id="pii.phone",
                    severity="high",
                    detail="Phone number detected in candidate-facing content.",
                )
            )
            sanitized = _PHONE_PATTERN.sub("[redacted-phone]", sanitized)

        for rule_id, pattern in _BIAS_PATTERNS.items():
            if pattern.search(sanitized):
                findings.append(
                    GuardrailFinding(
                        rule_id=rule_id,
                        severity="medium",
                        detail="Potentially biased language detected in candidate-facing content.",
                    )
                )

        blocked = any(finding.severity == "high" for finding in findings)
        return GuardrailEnvelope(
            blocked=blocked,
            sanitized_text=sanitized.strip(),
            findings=findings,
        )
