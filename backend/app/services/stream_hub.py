from __future__ import annotations

from collections import defaultdict

from fastapi import WebSocket


class StreamHub:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[session_id].add(websocket)

    def disconnect(self, session_id: str, websocket: WebSocket) -> None:
        peers = self._connections.get(session_id)
        if peers is None:
            return
        peers.discard(websocket)
        if not peers:
            self._connections.pop(session_id, None)

    async def publish(self, session_id: str, payload: dict) -> None:
        peers = list(self._connections.get(session_id, set()))
        for websocket in peers:
            try:
                await websocket.send_json(payload)
            except Exception:
                self.disconnect(session_id, websocket)
