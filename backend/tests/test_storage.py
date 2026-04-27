from __future__ import annotations

import pytest

from app.contracts import PhaseRevisionRequest, PhaseStatus
from app.phase_plan import default_phase_plan
from app.services.storage import Storage


@pytest.mark.asyncio
async def test_phase_seed_and_revision(tmp_path) -> None:
    db_path = tmp_path / "phase.db"
    storage = Storage(db_path)
    await storage.initialize()
    await storage.seed_phases(default_phase_plan())

    phases = await storage.list_phases()
    assert len(phases) == 15

    revision = await storage.revise_phase(
        phase_id=2,
        request=PhaseRevisionRequest(
            summary="Activated enhanced loop",
            rationale="Graph nodes are implemented and instrumented.",
            status=PhaseStatus.ACTIVE,
        ),
    )

    assert revision.phase_id == 2
    assert revision.status == PhaseStatus.ACTIVE

    updated = await storage.list_phases()
    phase2 = next(phase for phase in updated if phase.phase_id == 2)
    assert phase2.status == PhaseStatus.ACTIVE
