"""Contract tests for `iw next-id` against a real PostgreSQL testcontainer.

Tests the full contract: exit codes, stdout shape, DB row effects, and
atomicity under concurrent calls (no duplicate IDs).

All tests use the testcontainer db_session fixture — never the live DB.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner
from sqlalchemy import select
from sqlalchemy.orm import Session as SASession

from orch.cli.id_commands import allocate_next_id
from orch.cli.main import cli
from orch.db.models import IdSequence

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from orch.db.models import Project as ProjectModel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def invoke(
    runner: CliRunner,
    args: list[str],
    get_session: object,
    project_id: str = "test-proj",
) -> pytest.ClickResult:
    """Invoke the CLI with a pre-injected session factory."""
    return runner.invoke(
        cli,
        ["--project", project_id, *args],
        obj={"get_session": get_session},
        catch_exceptions=False,
    )


# ---------------------------------------------------------------------------
# Success paths
# ---------------------------------------------------------------------------


def test_next_id_allocates_id_exit_0(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """Exit 0: next-id returns a formatted ID string."""
    runner = CliRunner()
    result = invoke(runner, ["next-id", "--type", "incident"], cli_get_session)

    assert result.exit_code == 0, f"stderr: {result.stderr}\nstdout: {result.output}"
    assert result.output.strip().startswith("I-"), f"Expected I- prefix, got: {result.output}"


def test_next_id_sequential_allocations_are_gapless(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """Exit 0: multiple sequential allocations produce gapless ascending IDs."""
    runner = CliRunner()
    ids = []
    for _ in range(3):
        res = invoke(runner, ["next-id", "--type", "incident"], cli_get_session)
        assert res.exit_code == 0
        ids.append(res.output.strip())

    numbers = [int(i.split("-")[1]) for i in ids]
    assert numbers == [numbers[0], numbers[0] + 1, numbers[0] + 2], (
        f"IDs should be sequential and gapless: {ids}"
    )


def test_next_id_all_types_success(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """Exit 0: all documented type values produce the expected prefix."""
    expected_prefixes = {
        "feature": "F-",
        "incident": "I-",
        "cr": "CR-",
        "batch": "BATCH-",
    }
    runner = CliRunner()
    for item_type, prefix in expected_prefixes.items():
        result = invoke(runner, ["next-id", "--type", item_type], cli_get_session)
        assert result.exit_code == 0, f"{item_type}: {result.stderr}"
        assert result.output.strip().startswith(prefix), (
            f"Expected prefix {prefix} for type {item_type}, got: {result.output}"
        )


def test_next_id_json_output_shape(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """Exit 0 with --json: stdout is valid JSON with documented fields."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--project", test_project.id, "--json", "next-id", "--type", "incident"],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )

    assert result.exit_code == 0, f"stderr: {result.stderr}"
    data = json.loads(result.output)
    assert data["id"].startswith("I-")
    assert data["project_id"] == test_project.id
    assert data["prefix"] == "I"
    assert isinstance(data["number"], int)
    assert data["number"] > 0


def test_next_id_increments_sequence_row(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """Exit 0: each next-id call advances the id_sequences row's next_number by exactly 1.

    ``next_number`` holds the *next* number to hand out, so its absolute value
    after the first-ever allocation depends on the DB's seed state. The invariant
    the contract guarantees — and what this asserts — is that one allocation
    advances the counter by exactly one.
    """
    runner = CliRunner()

    first = invoke(runner, ["next-id", "--type", "incident"], cli_get_session)
    assert first.exit_code == 0, f"stderr: {first.stderr}"
    num_after_first = (
        db_session.execute(select(IdSequence).where(IdSequence.prefix == "I"))
        .scalar_one()
        .next_number
    )

    second = invoke(runner, ["next-id", "--type", "incident"], cli_get_session)
    assert second.exit_code == 0, f"stderr: {second.stderr}"
    num_after_second = (
        db_session.execute(select(IdSequence).where(IdSequence.prefix == "I"))
        .scalar_one()
        .next_number
    )

    assert num_after_second == num_after_first + 1, (
        f"next-id must advance next_number by exactly 1 per call: "
        f"{num_after_first} → {num_after_second}"
    )


# ---------------------------------------------------------------------------
# Atomicity / concurrency
# ---------------------------------------------------------------------------


def test_next_id_concurrent_allocations_no_duplicates(
    db_engine: Session,
    test_project: ProjectModel,
) -> None:
    """Concurrent next-id allocations must produce unique IDs (no lost-update bug).

    Uses ThreadPoolExecutor + real DB sessions to simulate concurrent callers.
    Follows the pattern from test_iw_next_id_atomicity_properties.py.
    """
    project_id = test_project.id

    def _session() -> SASession:
        return SASession(db_engine)

    # Clean state for this test
    with _session() as s, s.begin():
        seq = s.get(IdSequence, "I")
        if seq:
            s.delete(seq)

    def allocate() -> str:
        with _session() as s, s.begin():
            _, formatted = allocate_next_id(s, project_id, "I")
            return formatted

    n = 10
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(lambda _: allocate(), range(n)))

    # Cleanup
    with _session() as s, s.begin():
        seq = s.get(IdSequence, "I")
        if seq:
            s.delete(seq)

    # All IDs must be unique
    assert len(set(results)) == n, (
        f"Duplicate IDs detected under {n} concurrent allocations: {results}"
    )

    # IDs must be gapless from the first allocated number
    numbers = sorted(int(r.split("-")[1]) for r in results)
    assert numbers == list(range(numbers[0], numbers[0] + n)), f"IDs are not gapless: {results}"


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_next_id_unknown_type_exit_2(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """Exit 2: --type value not in the allowed set."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--project", test_project.id, "next-id", "--type", "not-a-type"],
        obj={"get_session": cli_get_session},
        catch_exceptions=True,
    )
    assert result.exit_code == 2
