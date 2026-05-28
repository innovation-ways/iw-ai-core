"""Fixture: seed test health snapshot data (CR-00086 S16).

Inserts 30+ historical snapshots per metric for iw-ai-core so the
sparklines render with real trend data. Also leaves innoforge untouched
(v3 empty-state check). Also adds a minimal test_config so the Tests page
renders (it requires `test_config.categories` to be non-empty).

Idempotent: re-running is a no-op.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

from orch.db.models import Project, TestHealthSnapshot
from sqlalchemy import select

PROJECT_ID = "iw-ai-core"

METRICS_CONFIG = [
    # (metric_key, start_value, trend, jitter_range)
    # Mutation score: 60–85%, slight upward trend
    ("mutation_score", 60.0, +0.8, 2.5),
    # Coverage: 70–92%, slow upward
    ("coverage_pct", 70.0, +0.6, 3.0),
    # Flaky tests: 0–7, slight downward trend
    ("flaky_test_count", 7.0, -0.15, 1.5),
    # Assertion baseline: 650→540, downward (CR-00046/81 progress)
    ("assertion_baseline_size", 650.0, -4.0, 15.0),
]


def seed(db) -> None:
    now = datetime.now(UTC)
    base_ts = now.replace(minute=0, second=0, microsecond=0)

    # Ensure iw-ai-core has a test_config (Tests page requires categories)
    project = db.get(Project, PROJECT_ID)
    if project is not None:
        config = dict(project.config) if project.config else {}
        if "test_config" not in config or not config["test_config"].get("categories"):
            config["test_config"] = {
                "categories": {
                    "unit": {
                        "label": "Unit Tests",
                        "command": "make test-unit",
                        "description": "Fast unit tests",
                    },
                    "integration": {
                        "label": "Integration Tests",
                        "command": "make test-integration",
                        "description": "Integration tests",
                    },
                }
            }
            project.config = config
            db.flush()

    for metric_key, start_val, trend_per_hour, jitter in METRICS_CONFIG:
        # Check if we already have snapshots for this metric (idempotent)
        existing = db.scalar(
            select(TestHealthSnapshot).filter(
                TestHealthSnapshot.project_id == PROJECT_ID,
                TestHealthSnapshot.metric == metric_key,
            ).limit(1)
        )

        if existing is not None:
            continue

        hours_back = 29  # 0..29 = 30 points + now
        for h in range(hours_back, -1, -1):
            ts = base_ts - timedelta(hours=h)
            base = start_val + (hours_back - h) * trend_per_hour
            value = round(base + random.uniform(-jitter, jitter), 2)
            if metric_key == "mutation_score":
                value = max(50.0, min(95.0, value))
            elif metric_key == "coverage_pct":
                value = max(55.0, min(98.0, value))
            elif metric_key == "flaky_test_count":
                value = max(0.0, min(15.0, value))
            elif metric_key == "assertion_baseline_size":
                value = max(300, min(800, value))

        # Idempotent per (project_id, metric, ts_minute)
            existing_row = db.scalar(
                select(TestHealthSnapshot).filter(
                    TestHealthSnapshot.project_id == PROJECT_ID,
                    TestHealthSnapshot.metric == metric_key,
                    TestHealthSnapshot.ts == ts,
                )
            )

            if existing_row is None:
                db.add(
                    TestHealthSnapshot(
                        project_id=PROJECT_ID,
                        ts=ts,
                        metric=metric_key,
                        value=value,
                        meta={"fixture": "CR-00086-S16-e2e-fixture"},
                    )
                )

        db.flush()
