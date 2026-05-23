"""E2E fixtures — session-scoped base URL and per-test PlaywrightWrapper.

Fixture-scoped skip: when ``IW_BROWSER_BASE_URL`` is not set the
``base_url`` / ``pw`` fixtures skip rather than connecting to the live DB
or a phantom host.  The unmarked harness self-check unit tests in
``test_harness_selfcheck.py`` (which request neither fixture) still run.
"""

from __future__ import annotations

import os
from contextlib import suppress
from pathlib import Path

import pytest

from tests.e2e.playwright_wrapper import PlaywrightWrapper

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def base_url() -> str:
    """URL of the isolated E2E stack's dashboard; set via ``IW_BROWSER_BASE_URL``."""
    url = os.environ.get("IW_BROWSER_BASE_URL", "").strip()
    if not url:
        pytest.skip("E2E_STACK_MISSING: IW_BROWSER_BASE_URL is not set")
    return url.rstrip("/")


@pytest.fixture
def pw(base_url: str) -> PlaywrightWrapper:
    """Per-test PlaywrightWrapper instance with a clean browser session.

    ``kill-all`` runs before and after the test so each journey starts and
    ends with no browser state.
    """
    wrapper = PlaywrightWrapper(base_url)
    wrapper.kill_all()

    # Wipe stale screenshots and console logs so each test sees only its own.
    _wipe_playwright_artifacts()

    yield wrapper

    # Teardown: kill the session so it doesn't bleed into the next test.
    wrapper.kill_all()


@pytest.fixture(scope="session")
def evidence_dir() -> Path:
    """Directory for journey-screenshot artefacts (gitignored ``tests/e2e/_artifacts/``).

    The caller may override this via ``IW_E2E_EVIDENCE_DIR`` (used by qv-browser
    at S14 to place screenshots next to the item's ``evidences/post/`` dir).
    """
    path = Path(os.environ.get("IW_E2E_EVIDENCE_DIR", "tests/e2e/_artifacts/"))
    path.mkdir(parents=True, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _wipe_playwright_artifacts() -> None:
    """Remove stale page screenshots and console logs from the playwright-cli dir.

    Called at the start of every journey so no test accidentally reads a
    screenshot or log written by a previous test.
    """
    playwright_dir = Path(".playwright-cli")
    if not playwright_dir.exists():
        return
    for pattern in ("page-*.png", "console-*.log"):
        for f in playwright_dir.glob(pattern):
            with suppress(OSError):
                f.unlink(missing_ok=True)
