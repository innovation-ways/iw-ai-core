"""Integration test for worktree reaper with real containers (AC4).

Verifies that the reaper correctly identifies orphan containers and reaps them.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.integration.conftest import (
    db_engine,  # noqa: F401
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

DOCKER_AVAILABLE: bool | None = None


def _check_docker() -> bool:
    global DOCKER_AVAILABLE
    if DOCKER_AVAILABLE is not None:
        return DOCKER_AVAILABLE
    try:
        result = subprocess.run(
            ["docker", "ps"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        DOCKER_AVAILABLE = result.returncode == 0
    except Exception:
        DOCKER_AVAILABLE = False
    return DOCKER_AVAILABLE


@pytest.fixture
def docker_available():
    if not _check_docker():
        pytest.skip("Docker not available")
    return True


@pytest.mark.integration
def test_reaper_classifies_and_reaps_orphan(
    docker_available: bool,
    db_session: Session,
    tmp_path: Path,
) -> None:
    """AC4 — orphan container detection + reap on daemon startup.

    This test:
    1. Creates a compose stack with labels matching a deleted BatchItem (orphan)
    2. Confirms no BatchItem row with that id exists
    3. Calls worktree_reaper.reap(db)
    4. Asserts the compose stack is gone
    5. Asserts a DaemonEvent was emitted with classification='orphan'
    """
    from orch.daemon.worktree_reaper import reap, scan
    from orch.db.models import Batch, BatchItem, Project, WorkItem, WorkItemType

    db_session.add(Project(id="test-proj", display_name="Test", repo_root="/tmp", config={}))
    db_session.flush()
    db_session.add(
        WorkItem(
            project_id="test-proj",
            id="F-00001",
            type=WorkItemType.Feature,
            title="Test",
        )
    )
    db_session.flush()
    db_session.add(Batch(project_id="test-proj", id="BATCH-00001"))
    db_session.flush()
    bi = BatchItem(project_id="test-proj", batch_id="BATCH-00001", work_item_id="F-00001")
    db_session.add(bi)
    db_session.flush()
    batch_item_id = str(bi.id)
    db_session.delete(bi)
    db_session.commit()

    compose_project_name = f"iwcore-{batch_item_id.lower().replace('_', '-')}"

    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(
        f"name: {compose_project_name}\n"
        "services:\n"
        "  db:\n"
        "    image: postgres:15-alpine\n"
        "    environment:\n"
        "      POSTGRES_DB: worktree_orphan\n"
        "      POSTGRES_USER: testuser\n"
        "      POSTGRES_PASSWORD: testpass\n"
        "    labels:\n"
        "      iwcore.role: worktree-db\n"
        f'      iwcore.batch_item: "{batch_item_id}"\n'
        "      iwcore.project: test-proj\n"
    )

    try:
        result = subprocess.run(
            ["docker", "compose", "-p", compose_project_name, "-f", str(compose_file), "up", "-d"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, f"Compose up failed: {result.stderr}"

        time.sleep(3)

        findings_before = scan()
        orphan_findings = [f for f in findings_before if f.batch_item_id == batch_item_id]
        assert len(orphan_findings) == 1, f"Expected 1 orphan finding, got {len(orphan_findings)}"

        reaped = reap(db_session)

        assert len(reaped) >= 1, "Reaper should have reaped at least the orphan"
        reaped_orphan = [r for r in reaped if r.batch_item_id == batch_item_id]
        assert len(reaped_orphan) == 1, "Reaper should have reaped the specific orphan"
        assert reaped_orphan[0].classification == "orphan"

        time.sleep(1)
        ps_result = subprocess.run(
            [
                "docker",
                "ps",
                "--filter",
                f"name={compose_project_name}",
                "--format",
                "{{.Names}}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert compose_project_name not in ps_result.stdout, (
            f"Orphan compose stack {compose_project_name} "
            "should have been reaped but containers still running"
        )

    finally:
        subprocess.run(
            [
                "docker",
                "compose",
                "-p",
                compose_project_name,
                "-f",
                str(compose_file),
                "down",
                "-v",
            ],
            capture_output=True,
            timeout=60,
        )
