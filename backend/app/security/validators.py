from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

INJECTION_PATTERNS = [
    re.compile(r"ignore\s+all\s+previous\s+instructions", re.IGNORECASE),
    re.compile(r"system\s+prompt", re.IGNORECASE),
    re.compile(r"bypass\s+guard", re.IGNORECASE),
]


class RestrictedK8sManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True, populate_by_name=True)

    api_version: str = Field(alias="apiVersion", pattern=r"^v1$")
    kind: str = Field(pattern=r"^Pod$")
    metadata: dict[str, str]
    spec: dict[str, Any]


def contains_prompt_injection(payload: str) -> bool:
    return any(pattern.search(payload) for pattern in INJECTION_PATTERNS)


def sanitize_candidate_text(payload: str) -> str:
    clean = payload.replace("\x00", "").strip()
    return clean[:6000]


def validate_manifest(manifest: dict[str, Any]) -> tuple[bool, str]:
    try:
        parsed = RestrictedK8sManifest.model_validate(manifest)
    except ValidationError as exc:
        return False, f"schema validation failed: {exc.errors()}"

    containers = parsed.spec.get("containers", [])
    if not isinstance(containers, list) or not containers:
        return False, "manifest must declare at least one container"

    for container in containers:
        image = container.get("image", "")
        if "latest" in image:
            return False, "container image tags must be immutable"

    return True, "manifest approved"
