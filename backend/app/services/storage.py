from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite
import orjson

from app.contracts import (
    ConsentRecord,
    GlassBoxReport,
    HumanReviewRecord,
    InterviewMilestoneSnapshot,
    PhaseDefinition,
    PhaseRevision,
    PhaseRevisionRequest,
    TechnicalScorePlane,
    TelemetryOverlayPlane,
)


class Storage:
    def __init__(self, sqlite_path: Path):
        self.sqlite_path = sqlite_path

    async def initialize(self) -> None:
        async with aiosqlite.connect(self.sqlite_path) as db:
            await db.executescript(
                """
                PRAGMA journal_mode=WAL;

                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    candidate_id TEXT NOT NULL,
                    candidate_role TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS technical_planes (
                    session_id TEXT PRIMARY KEY,
                    plane_json TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS overlay_planes (
                    session_id TEXT PRIMARY KEY,
                    plane_json TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS consent_records (
                    session_id TEXT PRIMARY KEY,
                    consent_json TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS milestone_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    milestone_json TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS trace_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    trace_json TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS phases (
                    phase_id INTEGER PRIMARY KEY,
                    phase_json TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS phase_revisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    phase_id INTEGER NOT NULL,
                    revision_json TEXT NOT NULL,
                    revised_at_utc TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS final_reports (
                    session_id TEXT PRIMARY KEY,
                    report_json TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS human_reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    review_json TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL
                );
                """
            )
            await db.commit()

    async def seed_phases(self, phases: list[PhaseDefinition]) -> None:
        existing = await self.list_phases()
        if existing:
            return

        now = datetime.now(UTC).isoformat()
        async with aiosqlite.connect(self.sqlite_path) as db:
            await db.executemany(
                """
                INSERT INTO phases (phase_id, phase_json, updated_at_utc)
                VALUES (?, ?, ?)
                """,
                [
                    (
                        phase.phase_id,
                        _dumps(phase.model_dump(mode="json")),
                        now,
                    )
                    for phase in phases
                ],
            )
            await db.commit()

    async def list_phases(self) -> list[PhaseDefinition]:
        async with aiosqlite.connect(self.sqlite_path) as db:
            cursor = await db.execute("SELECT phase_json FROM phases ORDER BY phase_id ASC")
            rows = await cursor.fetchall()
        return [PhaseDefinition.model_validate(_loads(row[0])) for row in rows]

    async def revise_phase(self, phase_id: int, request: PhaseRevisionRequest) -> PhaseRevision:
        phases = await self.list_phases()
        target = next((phase for phase in phases if phase.phase_id == phase_id), None)
        if target is None:
            raise KeyError(f"phase {phase_id} not found")

        target.status = request.status
        now = datetime.now(UTC)
        revision = PhaseRevision(
            phase_id=phase_id,
            summary=request.summary,
            rationale=request.rationale,
            status=request.status,
            revised_at_utc=now,
        )

        async with aiosqlite.connect(self.sqlite_path) as db:
            await db.execute(
                """
                UPDATE phases
                SET phase_json = ?, updated_at_utc = ?
                WHERE phase_id = ?
                """,
                (
                    _dumps(target.model_dump(mode="json")),
                    now.isoformat(),
                    phase_id,
                ),
            )
            await db.execute(
                """
                INSERT INTO phase_revisions (phase_id, revision_json, revised_at_utc)
                VALUES (?, ?, ?)
                """,
                (
                    phase_id,
                    _dumps(revision.model_dump(mode="json")),
                    now.isoformat(),
                ),
            )
            await db.commit()

        return revision

    async def upsert_session_state(
        self,
        session_id: str,
        candidate_id: str,
        candidate_role: str,
        state: dict[str, Any],
    ) -> None:
        now = datetime.now(UTC).isoformat()
        payload = _dumps(state)
        async with aiosqlite.connect(self.sqlite_path) as db:
            await db.execute(
                """
                INSERT INTO sessions (
                    session_id,
                    candidate_id,
                    candidate_role,
                    state_json,
                    created_at_utc,
                    updated_at_utc
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id)
                DO UPDATE SET
                    candidate_id = excluded.candidate_id,
                    candidate_role = excluded.candidate_role,
                    state_json = excluded.state_json,
                    updated_at_utc = excluded.updated_at_utc
                """,
                (
                    session_id,
                    candidate_id,
                    candidate_role,
                    payload,
                    now,
                    now,
                ),
            )
            await db.commit()

    async def load_session_state(self, session_id: str) -> dict[str, Any] | None:
        async with aiosqlite.connect(self.sqlite_path) as db:
            cursor = await db.execute(
                "SELECT state_json FROM sessions WHERE session_id = ?",
                (session_id,),
            )
            row = await cursor.fetchone()

        if row is None:
            return None
        return _loads(row[0])

    async def save_technical_plane(self, session_id: str, plane: TechnicalScorePlane) -> None:
        await self._upsert_plane("technical_planes", session_id, plane.model_dump(mode="json"))

    async def load_technical_plane(self, session_id: str) -> TechnicalScorePlane | None:
        payload = await self._load_plane("technical_planes", session_id)
        if payload is None:
            return None
        try:
            return TechnicalScorePlane.model_validate(payload)
        except Exception:
            return None

    async def save_overlay_plane(self, session_id: str, plane: TelemetryOverlayPlane) -> None:
        await self._upsert_plane("overlay_planes", session_id, plane.model_dump(mode="json"))

    async def load_overlay_plane(self, session_id: str) -> TelemetryOverlayPlane | None:
        payload = await self._load_plane("overlay_planes", session_id)
        if payload is None:
            return None
        try:
            return TelemetryOverlayPlane.model_validate(payload)
        except Exception:
            return None

    async def save_consent_record(self, record: ConsentRecord) -> ConsentRecord:
        now = datetime.now(UTC).isoformat()
        async with aiosqlite.connect(self.sqlite_path) as db:
            await db.execute(
                """
                INSERT INTO consent_records (session_id, consent_json, created_at_utc, updated_at_utc)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id)
                DO UPDATE SET
                    consent_json = excluded.consent_json,
                    updated_at_utc = excluded.updated_at_utc
                """,
                (
                    record.session_id,
                    _dumps(record.model_dump(mode="json")),
                    now,
                    now,
                ),
            )
            await db.commit()
        return record

    async def load_consent_record(self, session_id: str) -> ConsentRecord | None:
        async with aiosqlite.connect(self.sqlite_path) as db:
            cursor = await db.execute(
                "SELECT consent_json FROM consent_records WHERE session_id = ?",
                (session_id,),
            )
            row = await cursor.fetchone()

        if row is None:
            return None
        try:
            return ConsentRecord.model_validate(_loads(row[0]))
        except Exception:
            return None

    async def append_milestone_snapshot(
        self,
        milestone: InterviewMilestoneSnapshot,
    ) -> InterviewMilestoneSnapshot:
        async with aiosqlite.connect(self.sqlite_path) as db:
            await db.execute(
                """
                INSERT INTO milestone_snapshots (session_id, milestone_json, created_at_utc)
                VALUES (?, ?, ?)
                """,
                (
                    milestone.session_id,
                    _dumps(milestone.model_dump(mode="json")),
                    milestone.captured_at_utc.isoformat(),
                ),
            )
            await db.commit()
        return milestone

    async def fetch_milestones(self, session_id: str, limit: int = 200) -> list[InterviewMilestoneSnapshot]:
        bounded_limit = max(1, min(limit, 2_000))
        async with aiosqlite.connect(self.sqlite_path) as db:
            cursor = await db.execute(
                """
                SELECT milestone_json
                FROM milestone_snapshots
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, bounded_limit),
            )
            rows = await cursor.fetchall()

        return [
            InterviewMilestoneSnapshot.model_validate(_loads(row[0]))
            for row in reversed(rows)
        ]

    async def append_trace_event(self, session_id: str, trace_event: dict[str, Any]) -> None:
        now = datetime.now(UTC).isoformat()
        async with aiosqlite.connect(self.sqlite_path) as db:
            await db.execute(
                """
                INSERT INTO trace_events (session_id, trace_json, created_at_utc)
                VALUES (?, ?, ?)
                """,
                (
                    session_id,
                    _dumps(trace_event),
                    now,
                ),
            )
            await db.commit()

    async def fetch_trace_events(self, session_id: str, limit: int = 200) -> list[dict[str, Any]]:
        bounded_limit = max(1, min(limit, 2_000))
        async with aiosqlite.connect(self.sqlite_path) as db:
            cursor = await db.execute(
                """
                SELECT trace_json
                FROM trace_events
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, bounded_limit),
            )
            rows = await cursor.fetchall()

        return [_loads(row[0]) for row in reversed(rows)]

    async def save_final_report(self, report: GlassBoxReport) -> None:
        now = datetime.now(UTC).isoformat()
        async with aiosqlite.connect(self.sqlite_path) as db:
            await db.execute(
                """
                INSERT INTO final_reports (
                    session_id,
                    report_json,
                    created_at_utc,
                    updated_at_utc
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id)
                DO UPDATE SET
                    report_json = excluded.report_json,
                    updated_at_utc = excluded.updated_at_utc
                """,
                (
                    report.session_id,
                    _dumps(report.model_dump(mode="json")),
                    now,
                    now,
                ),
            )
            await db.commit()

    async def load_final_report(self, session_id: str) -> GlassBoxReport | None:
        async with aiosqlite.connect(self.sqlite_path) as db:
            cursor = await db.execute(
                "SELECT report_json FROM final_reports WHERE session_id = ?",
                (session_id,),
            )
            row = await cursor.fetchone()

        if row is None:
            return None
        try:
            return GlassBoxReport.model_validate(_loads(row[0]))
        except Exception:
            return None

    async def append_human_review(self, review: HumanReviewRecord) -> HumanReviewRecord:
        async with aiosqlite.connect(self.sqlite_path) as db:
            await db.execute(
                """
                INSERT INTO human_reviews (session_id, review_json, created_at_utc)
                VALUES (?, ?, ?)
                """,
                (
                    review.session_id,
                    _dumps(review.model_dump(mode="json")),
                    review.decided_at_utc.isoformat(),
                ),
            )
            await db.commit()
        return review

    async def fetch_latest_human_review(self, session_id: str) -> HumanReviewRecord | None:
        async with aiosqlite.connect(self.sqlite_path) as db:
            cursor = await db.execute(
                """
                SELECT review_json
                FROM human_reviews
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (session_id,),
            )
            row = await cursor.fetchone()

        if row is None:
            return None
        try:
            return HumanReviewRecord.model_validate(_loads(row[0]))
        except Exception:
            return None

    # Strict allowlist for plane table names.
    # f-string interpolation of caller-supplied table names is prohibited.
    # Any new plane table MUST be added here explicitly.
    _PLANE_TABLE_ALLOWLIST: frozenset[str] = frozenset(
        {"technical_planes", "overlay_planes"}
    )

    async def _upsert_plane(self, table: str, session_id: str, plane_payload: dict[str, Any]) -> None:
        if table not in self._PLANE_TABLE_ALLOWLIST:
            raise ValueError(f"Unknown plane table: {table!r}")
        # Table name is now safe — it came from a frozenset of hardcoded literals,
        # not from user input. SQLite does not support parameterised table names,
        # so allowlist + format is the correct mitigation (not f-string on raw input).
        sql_upsert = (
            f"INSERT INTO {table} (session_id, plane_json, created_at_utc, updated_at_utc) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(session_id) "
            "DO UPDATE SET plane_json = excluded.plane_json, updated_at_utc = excluded.updated_at_utc"
        )
        now = datetime.now(UTC).isoformat()
        async with aiosqlite.connect(self.sqlite_path) as db:
            await db.execute(sql_upsert, (session_id, _dumps(plane_payload), now, now))
            await db.commit()

    async def _load_plane(self, table: str, session_id: str) -> dict[str, Any] | None:
        if table not in self._PLANE_TABLE_ALLOWLIST:
            raise ValueError(f"Unknown plane table: {table!r}")
        sql_select = f"SELECT plane_json FROM {table} WHERE session_id = ?"
        async with aiosqlite.connect(self.sqlite_path) as db:
            cursor = await db.execute(sql_select, (session_id,))
            row = await cursor.fetchone()
        if row is None:
            return None
        return _loads(row[0])


def _dumps(payload: Any) -> str:
    return orjson.dumps(payload).decode("utf-8")


def _loads(payload: str) -> Any:
    return orjson.loads(payload)
