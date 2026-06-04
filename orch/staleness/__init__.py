"""orch.staleness — Stale Process & Migration Detector (F-00063).

Live-computed staleness for managed project services and Alembic migrations.
No DB schema changes; all state is computed at render time.
"""

from __future__ import annotations

__all__ = [
    "compute_project_staleness",
    "parse_project_staleness",
]

from orch.staleness.config import parse_project_staleness
from orch.staleness.service import compute_project_staleness
