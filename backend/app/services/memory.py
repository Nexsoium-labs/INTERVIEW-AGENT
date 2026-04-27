from __future__ import annotations

import hashlib
from typing import Any


class MemoryBank:
    """
    Lightweight namespaced memory adapter.
    Technical evidence and telemetry overlay are intentionally isolated.
    """

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}
        self._session_index: dict[str, dict[str, list[str]]] = {}

    async def write(self, namespace: str, session_id: str, payload: dict[str, Any]) -> str:
        key_material = f"{namespace}:{session_id}:{payload}"
        key = hashlib.sha256(key_material.encode("utf-8")).hexdigest()
        self._store[key] = {
            "namespace": namespace,
            "session_id": session_id,
            "payload": payload,
        }
        self._session_index.setdefault(session_id, {}).setdefault(namespace, []).append(key)
        return key

    async def read(self, key: str) -> dict[str, Any] | None:
        record = self._store.get(key)
        if record is None:
            return None
        return dict(record)

    async def read_session(self, session_id: str, namespace: str) -> list[dict[str, Any]]:
        keys = self._session_index.get(session_id, {}).get(namespace, [])
        return [self._store[key] for key in keys if key in self._store]
