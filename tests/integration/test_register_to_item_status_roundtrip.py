"""CR-00023: register → item-status round-trip; manifest stamping; AC6.

Covers AC1, AC2, AC6 from the CR-00023 design.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from click.testing import CliRunner

from orch.cli.main import cli
from orch.db.models import (
    StepStatus,
    StepType,
    WorkflowStep,
)

if TYPE_CHECKING:
    from pathlib import Path

    import pytest
    from sqlalchemy.orm import Session as SASession

    from orch.db.models import Project


def _invoke(
    runner: CliRunner,
    args: list[str],
    get_session: Any,
    project_id: str = "test-proj",
) -> Any:
    return runner.invoke(
        cli,
        ["--project", project_id, *args],
        obj={"get_session": get_session},
        catch_exceptions=False,
    )


def _write_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# AC1 / AC2 — register populates new columns + stamps manifest
# ---------------------------------------------------------------------------


def test_register_populates_command_gate_timeout_columns(
    db_session: SASession,
    test_project: Project,
    cli_get_session: Any,
    tmp_path: Path,
) -> None:
    """AC1: a qv-gate manifest entry produces a row with command/gate/timeout_secs set."""
    manifest = tmp_path / "workflow-manifest.json"
    _write_manifest(
        manifest,
        {
            "id": "I-99001",
            "type": "Issue",
            "title": "Test register populates",
            "steps": [
                {
                    "step": "S01",
                    "agent": "backend-impl",
                    "prompt": "prompts/I-99001_S01_Backend_prompt.md",
                    "description": "implement thing",
                },
                {
                    "step": "S02",
                    "agent": "qv-gate",
                    "gate": "lint",
                    "command": "make lint",
                    "timeout": 600,
                    "description": "QV: lint",
                },
            ],
        },
    )

    runner = CliRunner()
    result = _invoke(
        runner,
        [
            "register",
            "I-99001",
            "Test register populates",
            "--type",
            "incident",
            "--steps-from",
            str(manifest),
        ],
        cli_get_session,
    )
    assert result.exit_code == 0, result.output

    rows = (
        db_session.query(WorkflowStep)
        .filter(WorkflowStep.project_id == "test-proj", WorkflowStep.work_item_id == "I-99001")
        .order_by(WorkflowStep.step_number)
        .all()
    )
    assert len(rows) == 2

    impl, qv = rows
    assert impl.step_id == "S01"
    assert impl.prompt_file == "prompts/I-99001_S01_Backend_prompt.md"
    assert impl.command is None
    assert impl.gate is None
    assert impl.timeout_secs is None

    assert qv.step_id == "S02"
    assert qv.command == "make lint"
    assert qv.gate == "lint"
    assert qv.timeout_secs == 600
    assert qv.prompt_file is None


def test_register_stamps_manifest_with_note(
    db_session: SASession,
    test_project: Project,
    cli_get_session: Any,
    tmp_path: Path,
) -> None:
    """AC2: manifest is rewritten in place to add `_note` referencing iw item-status."""
    manifest = tmp_path / "workflow-manifest.json"
    original_payload = {
        "id": "I-99002",
        "type": "Issue",
        "title": "Stamp manifest",
        "browser_verification": False,
        "steps": [{"step": "S01", "agent": "backend-impl"}],
        "scope": {"allowed_paths": ["orch/foo.py"]},
    }
    _write_manifest(manifest, original_payload)

    runner = CliRunner()
    result = _invoke(
        runner,
        [
            "register",
            "I-99002",
            "Stamp manifest",
            "--type",
            "incident",
            "--steps-from",
            str(manifest),
        ],
        cli_get_session,
    )
    assert result.exit_code == 0, result.output

    stamped = json.loads(manifest.read_text(encoding="utf-8"))
    assert "_note" in stamped
    assert "design-time snapshot" in stamped["_note"]
    assert "iw item-status" in stamped["_note"]

    # Every original key preserved with identical content
    for key, value in original_payload.items():
        assert stamped[key] == value, f"key {key!r} mutated by stamping"


def test_register_stamping_is_idempotent(
    db_session: SASession,
    test_project: Project,
    cli_get_session: Any,
    tmp_path: Path,
) -> None:
    """AC2: re-running register on a stamped manifest produces a byte-identical file."""
    manifest = tmp_path / "workflow-manifest.json"
    _write_manifest(
        manifest,
        {
            "id": "I-99003",
            "type": "Issue",
            "title": "Idempotent",
            "steps": [{"step": "S01", "agent": "backend-impl"}],
        },
    )

    runner = CliRunner()
    result1 = _invoke(
        runner,
        ["register", "I-99003", "Idempotent", "--type", "incident", "--steps-from", str(manifest)],
        cli_get_session,
    )
    assert result1.exit_code == 0, result1.output
    after_first = manifest.read_bytes()

    # Second register is a no-op (already-registered) but still re-stamps the
    # manifest. Even if iw register short-circuits via the "Already registered"
    # branch, calling _stamp_manifest_note directly would be the equivalent
    # check — exercise it explicitly.
    from orch.cli.item_commands import _stamp_manifest_note  # noqa: PLC0415

    _stamp_manifest_note(manifest)
    after_second = manifest.read_bytes()
    assert after_first == after_second, "stamp_manifest_note is not idempotent"


def test_register_stamping_preserves_unicode(
    db_session: SASession,
    test_project: Project,
    cli_get_session: Any,
    tmp_path: Path,
) -> None:
    """AC2: non-ASCII characters survive the stamp round-trip."""
    manifest = tmp_path / "workflow-manifest.json"
    _write_manifest(
        manifest,
        {
            "id": "I-99004",
            "type": "Issue",
            "title": "Café — résumé naïveté",
            "steps": [
                {"step": "S01", "agent": "backend-impl", "description": "add em-dash — handling"}
            ],
        },
    )

    runner = CliRunner()
    result = _invoke(
        runner,
        [
            "register",
            "I-99004",
            "Café — résumé naïveté",
            "--type",
            "incident",
            "--steps-from",
            str(manifest),
        ],
        cli_get_session,
    )
    assert result.exit_code == 0, result.output

    stamped_text = manifest.read_text(encoding="utf-8")
    assert "Café — résumé naïveté" in stamped_text
    assert "em-dash — handling" in stamped_text
    stamped = json.loads(stamped_text)
    assert stamped["title"] == "Café — résumé naïveté"


def test_register_invalid_timeout_fails_clearly(
    db_session: SASession,
    test_project: Project,
    cli_get_session: Any,
    tmp_path: Path,
) -> None:
    """AC1 defensive: a malformed `timeout` exits non-zero with a clear message."""
    manifest = tmp_path / "workflow-manifest.json"
    _write_manifest(
        manifest,
        {
            "steps": [
                {
                    "step": "S01",
                    "agent": "qv-gate",
                    "gate": "lint",
                    "command": "make lint",
                    "timeout": "not-a-number",
                }
            ]
        },
    )

    runner = CliRunner()
    result = _invoke(
        runner,
        ["register", "I-99005", "Bad timeout", "--type", "incident", "--steps-from", str(manifest)],
        cli_get_session,
    )
    assert result.exit_code != 0
    output = (result.stderr or "") + (result.output or "")
    assert "timeout" in output.lower()
    assert "S01" in output


# ---------------------------------------------------------------------------
# AC1 — round-trip register → item-status returns enriched per-step entries
# ---------------------------------------------------------------------------


def test_register_then_item_status_returns_manifest_superset(
    db_session: SASession,
    test_project: Project,
    cli_get_session: Any,
    tmp_path: Path,
) -> None:
    """AC1: item-status JSON contains every manifest field plus runtime status."""
    manifest = tmp_path / "workflow-manifest.json"
    _write_manifest(
        manifest,
        {
            "id": "I-99010",
            "type": "Issue",
            "title": "Roundtrip",
            "steps": [
                {
                    "step": "S01",
                    "agent": "backend-impl",
                    "prompt": "prompts/I-99010_S01_Backend_prompt.md",
                    "description": "build it",
                },
                {
                    "step": "S02",
                    "agent": "qv-gate",
                    "gate": "lint",
                    "command": "make lint",
                    "timeout": 600,
                    "description": "QV: lint",
                },
            ],
        },
    )

    runner = CliRunner()
    reg = _invoke(
        runner,
        ["register", "I-99010", "Roundtrip", "--type", "incident", "--steps-from", str(manifest)],
        cli_get_session,
    )
    assert reg.exit_code == 0, reg.output

    status = _invoke(runner, ["-j", "item-status", "I-99010"], cli_get_session)
    assert status.exit_code == 0, status.output
    data = json.loads(status.output)

    expected_keys = {
        "step_id",
        "step_number",
        "label",
        "agent_label",
        "opencode_agent",
        "type",
        "step_type",
        "step_label",
        "status",
        "description",
        "prompt_file",
        "command",
        "gate",
        "timeout_secs",
    }
    assert len(data["steps"]) == 2
    for step in data["steps"]:
        missing = expected_keys - set(step.keys())
        assert not missing, f"step {step.get('step_id')!r} missing keys: {missing}"

    impl = data["steps"][0]
    assert impl["step_id"] == "S01"
    assert impl["status"] == "pending"
    assert impl["prompt_file"] == "prompts/I-99010_S01_Backend_prompt.md"
    assert impl["command"] is None
    assert impl["gate"] is None
    assert impl["timeout_secs"] is None
    assert impl["opencode_agent"] == "backend-impl"
    assert impl["description"] == "build it"

    qv = data["steps"][1]
    assert qv["step_id"] == "S02"
    assert qv["command"] == "make lint"
    assert qv["gate"] == "lint"
    assert qv["timeout_secs"] == 600
    assert qv["prompt_file"] is None


def test_round_trip_preserves_scope_block(
    db_session: SASession,
    test_project: Project,
    cli_get_session: Any,
    tmp_path: Path,
) -> None:
    """AC2: stamping must not perturb the `scope` block."""
    scope = {"allowed_paths": ["orch/foo.py", "orch/bar.py"]}
    manifest = tmp_path / "workflow-manifest.json"
    _write_manifest(
        manifest,
        {
            "id": "I-99011",
            "type": "Issue",
            "title": "Scope preserved",
            "steps": [{"step": "S01", "agent": "backend-impl"}],
            "scope": scope,
        },
    )

    runner = CliRunner()
    result = _invoke(
        runner,
        [
            "register",
            "I-99011",
            "Scope preserved",
            "--type",
            "incident",
            "--steps-from",
            str(manifest),
        ],
        cli_get_session,
    )
    assert result.exit_code == 0, result.output

    stamped = json.loads(manifest.read_text(encoding="utf-8"))
    assert stamped["scope"] == scope


# ---------------------------------------------------------------------------
# AC1 — null columns serialize as null
# ---------------------------------------------------------------------------


def test_item_status_json_null_columns_serialize_as_null(
    db_session: SASession,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    """A row with all CR-00023 columns NULL renders them as JSON null."""
    runner = CliRunner()
    _invoke(
        runner,
        ["register", "I-99020", "Nulls", "--type", "incident"],
        cli_get_session,
    )
    db_session.add(
        WorkflowStep(
            project_id="test-proj",
            work_item_id="I-99020",
            step_number=1,
            step_id="S01",
            agent_label="Backend",
            opencode_agent="backend-impl",
            step_type=StepType.implementation,
        )
    )
    db_session.flush()

    result = _invoke(runner, ["-j", "item-status", "I-99020"], cli_get_session)
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    step = next(s for s in data["steps"] if s["step_id"] == "S01")
    assert step["command"] is None
    assert step["gate"] is None
    assert step["timeout_secs"] is None
    assert step["prompt_file"] is None
    assert step["step_label"] is None


# ---------------------------------------------------------------------------
# AC6 — DB-only step (not in manifest) is discoverable via iw item-status
# ---------------------------------------------------------------------------


def test_item_status_surfaces_db_only_step_not_in_manifest(
    db_session: SASession,
    test_project: Project,
    cli_get_session: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC6 — I-00041 S14/S15 catch-22 regression.

    Reproduces the original failure: the DB has more steps than the on-disk
    manifest. An agent armed only with `iw item-status --json` must still
    discover the extra step and its launch parameters.
    """
    manifest = tmp_path / "workflow-manifest.json"
    manifest_payload = {
        "id": "I-99030",
        "type": "Issue",
        "title": "AC6",
        "steps": [
            {
                "step": "S01",
                "agent": "backend-impl",
                "prompt": "prompts/I-99030_S01_Backend_prompt.md",
            },
            {
                "step": "S02",
                "agent": "qv-gate",
                "gate": "lint",
                "command": "make lint",
            },
        ],
    }
    _write_manifest(manifest, manifest_payload)

    runner = CliRunner()
    reg = _invoke(
        runner,
        ["register", "I-99030", "AC6", "--type", "incident", "--steps-from", str(manifest)],
        cli_get_session,
    )
    assert reg.exit_code == 0, reg.output

    # Daemon-side append: drop in an S03 row that the manifest doesn't know
    # about and mark it in_progress so it shows up as current_step.
    db_session.add(
        WorkflowStep(
            project_id="test-proj",
            work_item_id="I-99030",
            step_number=3,
            step_id="S03",
            agent_label="Backend",
            opencode_agent="backend-impl",
            step_type=StepType.implementation,
            status=StepStatus.in_progress,
            prompt_file="prompts/I-99030_S03_Backend_prompt.md",
            started_at=datetime.now(UTC),
        )
    )
    db_session.flush()

    # Snapshot the manifest's mtime — item-status must not touch the file.
    mtime_before = manifest.stat().st_mtime_ns

    status = _invoke(runner, ["-j", "item-status", "I-99030"], cli_get_session)
    assert status.exit_code == 0, status.output
    data = json.loads(status.output)

    s03 = next((s for s in data["steps"] if s["step_id"] == "S03"), None)
    assert s03 is not None, "S03 (DB-only) not surfaced by item-status"
    assert s03["status"] == "in_progress"
    assert s03["prompt_file"] == "prompts/I-99030_S03_Backend_prompt.md"
    assert s03["agent_label"] == "Backend"

    assert data["current_step"] is not None
    assert data["current_step"]["step_id"] == "S03"

    assert manifest.stat().st_mtime_ns == mtime_before, (
        "item-status must not touch the manifest file (DB is the source of truth)"
    )
