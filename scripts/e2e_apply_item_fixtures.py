"""Apply per-item E2E fixtures for a single work item.

In-container script invoked by the daemon after the E2E stack is healthy.
Discovers and runs every ``seed(db)`` function found in
``ai-dev/active/<item_id>/e2e_fixtures/*.py`` (lexical order).

Usage:
    uv run python scripts/e2e_apply_item_fixtures.py <item_id>

Exit codes:
    0   — success (including no-op when the directory does not exist)
    1   — fixture raised or no seed() callable found
    2   — wrong number of arguments

Environment:
    IW_CORE_DB_*  — per-worktree DB credentials (E2E DB, NOT orch DB 5433)
    IW_E2E_SEED   — must be set to bypass the production guardrail in
                    orch.db.identity; set by docker-compose.e2e.yml as "1"

The production guardrail is NOT enforced here — this script targets the E2E
database exclusively (see IW_E2E_SEED above).  Running it on the production
orchestration DB would only happen if someone pointed IW_CORE_DB_* at 5433
while also setting IW_E2E_SEED=1, which is an operator error, not a scenario
we guard against in every code path.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _repo_root() -> Path:
    """Return the repository root (parent of scripts/)."""
    return Path(__file__).resolve().parent.parent


def main(item_id: str) -> None:
    """Discover and apply fixtures for ``item_id``.

    Silently no-ops when ``ai-dev/active/<item_id>/e2e_fixtures/`` does not
    exist — most work items have no per-item fixtures.
    """
    # Import locally so the module is importable for testing without DB env vars.
    from orch.db.session import get_session  # noqa: PLC0415
    from scripts.e2e_seed import _run_fixture  # noqa: PLC0415

    repo_root = _repo_root()
    fixtures_dir = repo_root / "ai-dev" / "active" / item_id / "e2e_fixtures"

    if not fixtures_dir.exists():
        sys.stdout.write(f"e2e_apply_item_fixtures: no fixtures directory for {item_id} — no-op\n")
        sys.stdout.flush()
        return

    fixture_files = sorted(f for f in fixtures_dir.glob("*.py") if not f.name.startswith("_"))

    if not fixture_files:
        sys.stdout.write(
            f"e2e_apply_item_fixtures: fixtures directory exists but is empty "
            f"for {item_id} — no-op\n"
        )
        sys.stdout.flush()
        return

    with get_session() as db:
        for fixture_path in fixture_files:
            sys.stdout.write(
                f"e2e_apply_item_fixtures: running {fixture_path.relative_to(repo_root)}\n"
            )
            sys.stdout.flush()
            _run_fixture(fixture_path, db)
            db.flush()
        db.commit()

    sys.stdout.write(
        f"e2e_apply_item_fixtures: applied {len(fixture_files)} fixture(s) for {item_id}\n"
    )
    sys.stdout.flush()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.stderr.write(
            f"usage: {Path(__file__).name} <item_id>\n"
            "  item_id: work item identifier, e.g. CR-00036\n"
        )
        sys.stderr.flush()
        sys.exit(2)

    item_id = sys.argv[1]
    try:
        main(item_id)
    except Exception as exc:
        sys.stderr.write(f"e2e_apply_item_fixtures: FAILED for {item_id}: {exc}\n")
        sys.stderr.flush()
        sys.exit(1)
