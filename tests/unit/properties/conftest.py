"""Hypothesis profile registration + marker auto-apply for tests/unit/properties/.

Three profiles: ci (merge-gate, fast, derandomized), dev (local default), deep (on-demand).
Profile is selected via $IW_HYPOTHESIS_PROFILE, defaulting to "ci".

The db_session fixture comes from tests.integration.conftest (loaded globally via
tests/conftest.py's pytest_plugins), so no extra configuration is needed here.
"""

from __future__ import annotations

import os

import pytest
from hypothesis import HealthCheck, settings

settings.register_profile(
    "ci",
    max_examples=20,
    deadline=2000,
    derandomize=True,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.register_profile(
    "dev",
    max_examples=200,
    deadline=5000,
)
settings.register_profile(
    "deep",
    max_examples=1000,
    deadline=None,
    derandomize=False,
)
settings.load_profile(os.environ.get("IW_HYPOTHESIS_PROFILE", "ci"))


def pytest_collection_modifyitems(config, items):  # noqa: ARG001
    """Auto-apply the `properties` marker to every test in this dir."""
    for item in items:
        if "/tests/unit/properties/" in str(item.fspath):
            item.add_marker(pytest.mark.properties)
