from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from orch.db.models import Project

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


PROJECT_ID = "iw-ai-core"


def seed(db: Session) -> None:
    project = db.get(Project, PROJECT_ID)
    if project is None:
        return

    iw_orch_path = Path("/app/.iw-orch.json")
    if not iw_orch_path.exists():
        return

    iw_orch = json.loads(iw_orch_path.read_text())
    test_config = iw_orch.get("test_config")
    quality_config = iw_orch.get("quality_config")

    updated = dict(project.config or {})
    if isinstance(test_config, dict):
        updated["test_config"] = test_config
    if isinstance(quality_config, dict):
        updated["quality_config"] = quality_config

    project.config = updated
    db.flush()
