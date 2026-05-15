"""End-to-end CLI integration tests for iw next-id --idempotency-key (CR-00053).

Tests the Click command surface (AC2 end-to-end) for the idempotent replay
behaviour. Uses the same testcontainer PostgreSQL fixture as the rest of
tests/integration/ — no sqlite, no live DB.

Tests:
- test_cli_repeat_with_same_key_returns_same_id  — AC2: two calls, same key,
    same ID, one id_allocations row, counter advanced by 1
- test_cli_no_key_still_works                    — backwards-compatibility: no key,
    distinct IDs, no id_allocations rows, counter advanced by 2
- test_cli_repeat_with_same_key_json_output    — JSON output mode also idempotent
"""

from __future__ import annotations

import json
from typing import Any

from click.testing import CliRunner
from sqlalchemy import select

from orch.cli.main import cli
from orch.db.models import IdAllocation, IdSequence, Project


def _invoke(runner: CliRunner, args: list[str], get_session: callable):
    """Invoke the CLI with an injected session factory."""
    return runner.invoke(
        cli,
        ["--project", "test-proj", *args],
        obj={"get_session": get_session},
        catch_exceptions=False,
    )


def test_cli_repeat_with_same_key_returns_same_id(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    """AC2: two CLI invocations with the same idempotency-key return the same ID.

    Verifies:
    - Both invocations exit 0
    - Both stdout lines contain the same formatted ID (e.g. R-00001)
    - Exactly one row exists in id_allocations after both calls
    - id_sequences.next_number for prefix 'R' advanced by exactly 1 (not 2)
    """
    runner = CliRunner()
    key = "abc-CR00053"

    result1 = _invoke(
        runner, ["next-id", "--type", "research", "--idempotency-key", key], cli_get_session
    )
    assert result1.exit_code == 0, f"first call failed: {result1.output}"
    first_id = result1.output.strip()
    assert first_id.startswith("R-"), f"expected R- prefix, got: {first_id}"

    result2 = _invoke(
        runner, ["next-id", "--type", "research", "--idempotency-key", key], cli_get_session
    )
    assert result2.exit_code == 0, f"second call failed: {result2.output}"
    second_id = result2.output.strip()
    assert second_id == first_id, (
        f"idempotency violation: first call returned {first_id}, second call returned {second_id}"
    )

    rows = (
        db_session.execute(
            select(IdAllocation).where(
                IdAllocation.prefix == "R",
                IdAllocation.idempotency_key == key,
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1, f"expected 1 id_allocations row, got {len(rows)}"
    assert rows[0].number == int(first_id.split("-")[1])

    seq_row = db_session.execute(select(IdSequence).where(IdSequence.prefix == "R")).scalar_one()
    expected_next = int(first_id.split("-")[1]) + 1
    assert seq_row.next_number == expected_next, (
        f"id_sequences.next_number for R is {seq_row.next_number}, "
        f"expected {expected_next} (first_id={first_id})"
    )


def test_cli_no_key_still_works(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    """Backwards-compatibility: no --idempotency-key flag produces distinct IDs.

    Verifies:
    - Both invocations exit 0
    - The two stdout IDs are different (sequential)
    - id_allocations is empty (no-key path never writes to it)
    - id_sequences.next_number advanced by 2
    """
    runner = CliRunner()

    result1 = _invoke(runner, ["next-id", "--type", "research"], cli_get_session)
    assert result1.exit_code == 0, f"first call failed: {result1.output}"
    first_id = result1.output.strip()

    result2 = _invoke(runner, ["next-id", "--type", "research"], cli_get_session)
    assert result2.exit_code == 0, f"second call failed: {result2.output}"
    second_id = result2.output.strip()

    assert second_id != first_id, "two no-key calls must produce distinct IDs"

    first_num = int(first_id.split("-")[1])
    second_num = int(second_id.split("-")[1])
    assert second_num == first_num + 1, (
        f"expected sequential IDs, got {first_num} then {second_num}"
    )

    all_rows = db_session.execute(select(IdAllocation)).scalars().all()
    assert len(all_rows) == 0, (
        f"no-key path must not write to id_allocations, got {len(all_rows)} rows"
    )

    seq_row = db_session.execute(select(IdSequence).where(IdSequence.prefix == "R")).scalar_one()
    assert seq_row.next_number == second_num + 1, (
        f"id_sequences.next_number for R is {seq_row.next_number}, expected {second_num + 1}"
    )


def test_cli_repeat_with_same_key_json_output(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    """JSON output mode is also idempotent: two calls with same key return identical JSON.

    Verifies:
    - Both invocations exit 0
    - Both stdout lines are valid JSON when parsed
    - Both parsed payloads contain identical 'id' field
    - Both parsed payloads contain the correct 'prefix' = 'R'
    """
    runner = CliRunner()
    key = "abc-json-test"

    result1 = _invoke(
        runner,
        ["--json", "next-id", "--type", "research", "--idempotency-key", key],
        cli_get_session,
    )
    assert result1.exit_code == 0, f"first JSON call failed: {result1.output}"

    result2 = _invoke(
        runner,
        ["--json", "next-id", "--type", "research", "--idempotency-key", key],
        cli_get_session,
    )
    assert result2.exit_code == 0, f"second JSON call failed: {result2.output}"

    data1 = json.loads(result1.output)
    data2 = json.loads(result2.output)

    assert data1["id"] == data2["id"], (
        f"JSON output idempotency violated: first id={data1['id']}, second id={data2['id']}"
    )
    assert data1["id"].startswith("R-")
    assert data1["prefix"] == "R"
    assert data2["prefix"] == "R"
    assert isinstance(data1["number"], int)
    assert data1["number"] == data2["number"]

    rows = (
        db_session.execute(
            select(IdAllocation).where(
                IdAllocation.prefix == "R",
                IdAllocation.idempotency_key == key,
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1, f"expected 1 id_allocations row, got {len(rows)}"
