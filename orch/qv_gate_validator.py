"""QV gate phantom-detection validator.

Recognises quality_validation step commands that cannot succeed in a
project's repo_root (missing Makefile target, missing directory, missing
binary). Used at iw approve and iw batch-approve to silently mark such
steps as 'skipped' before the daemon wastes fix-cycle budget on them.

The validator is conservative: when a command shape is unrecognised, it
returns True (assume runnable). This means a future buggy registry entry
cannot skip a real gate — the worst case is failing to catch a new
phantom shape, which degrades to the pre-fix behaviour.
"""

from __future__ import annotations

import logging
import re
import shlex
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session  # noqa: TC002  same pattern as rest of orch package

from orch.db.models import (
    DaemonEvent,
    Project,
    StepStatus,
    StepType,
    WorkflowStep,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pattern-detection helpers (pure — no DB, no I/O beyond filesystem + which)
# ---------------------------------------------------------------------------


def _makefile_target(command: str) -> str | None:
    """Return the Makefile target name if command is 'make <target>'.

    Allows flags between 'make' and the target (e.g. 'make --quiet lint'
    or 'make -C dir target'). Flag arguments are consumed and not returned
    as the target.
    Returns None if the command doesn't match the pattern.
    """
    tokens = shlex.split(command)
    if not tokens:
        return None
    if tokens[0] != "make":
        return None

    # Consume flag tokens and their arguments (e.g. -C <dir>, --file=<f>)
    idx = 1
    while idx < len(tokens):
        token = tokens[idx]
        if not token.startswith("-"):
            # First non-flag token is the target
            break
        # It's a flag — check if it takes a separate argument
        # Short flags: -C <arg>, -f <arg>, -j <arg>
        # Long flags: --file=<arg>, --makefile=<arg>
        if token.startswith("--"):
            # --flag or --flag=<arg>
            if "=" in token:
                # --flag=value — no separate argument consumed
                idx += 1
            else:
                # --flag — no argument consumed
                idx += 1
        elif len(token) == 2:
            # -x — could consume the next token as its argument
            idx += 2  # skip flag and its argument
        else:
            # Multi-char short flag like -abc (no arg)
            idx += 1

    if idx >= len(tokens):
        return None
    return tokens[idx]


def _makefile_has_target(repo_root: Path, target: str) -> bool:
    """Return True if repo_root/Makefile contains a '^<target>:' line."""
    makefile_path = repo_root / "Makefile"
    if not makefile_path.is_file():
        return False
    pattern = re.compile(f"^{re.escape(target)}:", re.MULTILINE)
    try:
        content = makefile_path.read_text()
    except OSError:
        return False
    return bool(pattern.search(content))


def _cd_directory(command: str) -> str | None:
    """Return the directory if command starts with 'cd <dir> && ...'.

    Strips wrapping quotes from the directory name.
    """
    stripped = command.strip()
    if not stripped.startswith("cd "):
        return None
    # Match: cd <dir> && (allowing whitespace around &&)
    m = re.match(r"^cd\s+(\S+)\s*(&&|\b)", stripped)
    if not m:
        return None
    directory = m.group(1)
    # Strip quotes (single or double) if present
    if (directory.startswith('"') and directory.endswith('"')) or (
        directory.startswith("'") and directory.endswith("'")
    ):
        directory = directory[1:-1]
    return directory


def _bare_executable(command: str) -> str | None:
    """Return the first token if it looks like a bare executable.

    Returns None for commands that matched the 'make' or 'cd' patterns,
    or that contain shell metacharacters we can't confidently classify.
    """
    tokens = shlex.split(command)
    if not tokens:
        return None
    first = tokens[0]
    # 'make' and 'cd' are handled by their dedicated patterns
    if first in ("make", "cd"):
        return None
    # Shell operators that make this an unclassifiable multi-token command
    shell_operators = {"|", ";", "&", ">", "<"}
    if any(t in shell_operators for t in tokens):
        return None
    # Only consider it a bare exec if the first token contains no shell
    # metacharacters
    shell_metachars = "|;&><$*?![]{}()~"
    if any(c in first for c in shell_metachars):
        return None
    # Looks like a bare executable
    return first


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GateVerdict:
    """Result of classify_qv_gate.

    Attributes
    ----------
    runnable : bool
        True if the gate command is structurally plausible in repo_root.
        False means it is a phantom gate and should be auto-skipped.
    reason : str | None
        One of the defined phantom-reason strings, or None when runnable.
    """

    runnable: bool
    reason: str | None


_REASON_MISSING_MAKEFILE_TARGET = "missing_makefile_target"
_REASON_MISSING_MAKEFILE_FILE = "missing_makefile_file"
_REASON_MISSING_DIRECTORY = "missing_directory"
_REASON_MISSING_EXECUTABLE = "missing_executable"


def classify_qv_gate(repo_root: Path, gate: str, command: str) -> GateVerdict:  # noqa: ARG001
    """Classify a QV gate command as runnable or phantom.

    Parameters
    ----------
    repo_root : Path
        Absolute or relative path to the project repository root.
    gate : str
        The gate name (step's 'gate' field, may be empty).
    command : str
        The raw command string from the step's 'command' field (may be empty).

    Returns
    -------
    GateVerdict
        ``runnable=True`` when the command is plausibly runnable.
        ``runnable=False`` when it is a known phantom shape, with ``reason``
        set to one of the defined reason constants.
    """
    command = command.strip()

    # ---- Pattern 1: make <target> ----------------------------------------
    target = _makefile_target(command)
    if target is not None:
        # Check if Makefile exists at all
        if not _makefile_has_target(repo_root, target):
            # Distinguish "no Makefile" vs "target not in Makefile"
            makefile_path = repo_root / "Makefile"
            if not makefile_path.is_file():
                return GateVerdict(runnable=False, reason=_REASON_MISSING_MAKEFILE_FILE)
            return GateVerdict(runnable=False, reason=_REASON_MISSING_MAKEFILE_TARGET)
        return GateVerdict(runnable=True, reason=None)

    # ---- Pattern 2: cd <dir> && ... ---------------------------------------
    directory = _cd_directory(command)
    if directory is not None:
        target_dir = repo_root / directory
        if not target_dir.is_dir():
            return GateVerdict(runnable=False, reason=_REASON_MISSING_DIRECTORY)
        return GateVerdict(runnable=True, reason=None)

    # ---- Pattern 3: bare executable --------------------------------------
    executable = _bare_executable(command)
    if executable is not None:
        # Conservative: do NOT check shutil.which() here.  The command may be
        # present in the daemon's environment but absent from the test host's
        # PATH (e.g. tools installed inside the worktree, npx wrappers, pip
        # shims, etc.).  Since we cannot reliably determine availability, we
        # return True (assume runnable) — the worst case is a false negative,
        # which degrades to the pre-fix behaviour.
        return GateVerdict(runnable=True, reason=None)

    # ---- Fallback: unrecognised shape — conservative, assume runnable ----
    return GateVerdict(runnable=True, reason=None)


def validate_qv_gate(repo_root: Path, gate: str, command: str) -> bool:
    """Return True if the command is structurally runnable in repo_root.

    This is a convenience wrapper around :func:`classify_qv_gate`.
    """
    return classify_qv_gate(repo_root, gate, command).runnable


# ---------------------------------------------------------------------------
# DB-mutating orchestrator
# ---------------------------------------------------------------------------


def auto_skip_phantom_qv_gates(
    session: Session,
    project_id: str,
    work_item_id: str,
    *,
    trigger: str = "approve",
) -> list[tuple[str, str, str]]:
    """For each pending QV step on the item, auto-skip phantom gates.

    Queries all ``quality_validation`` steps with status ``pending`` for the
    given work item, classifies each command, and marks phantom gates as
    ``skipped`` with a ``completed_at`` timestamp.  A ``DaemonEvent`` audit
    row is inserted for every skipped step.

    Parameters
    ----------
    session : Session
        SQLAlchemy session (caller manages commit/rollback).
    project_id : str
        The project identifier.
    work_item_id : str
        The work-item identifier.
    trigger : str
        Source that triggered the skip (``approve`` or ``batch_approve``).
        Passed through to the daemon event metadata.

    Returns
    -------
    list[tuple[str, str, str]]
        List of ``(step_id, gate, reason)`` for each step that was skipped.
    """
    # Resolve repo_root once
    project = session.get(Project, project_id)
    if project is None:
        logger.warning("auto_skip_phantom_qv_gates: project %s not found, skipping", project_id)
        return []
    repo_root = Path(project.repo_root) if project.repo_root else Path.cwd()

    # Fetch only pending QV steps — never touch steps the daemon already started
    # or that were manually marked skipped
    steps = (
        session.query(WorkflowStep)
        .filter(
            WorkflowStep.project_id == project_id,
            WorkflowStep.work_item_id == work_item_id,
            WorkflowStep.step_type == StepType.quality_validation,
            WorkflowStep.status == StepStatus.pending,
        )
        .all()
    )

    skipped: list[tuple[str, str, str]] = []

    for step in steps:
        gate = step.gate or ""
        command = step.command or ""
        verdict = classify_qv_gate(repo_root, gate, command)
        if verdict.runnable:
            continue

        # Mark step as skipped
        step.status = StepStatus.skipped
        step.completed_at = datetime.now(UTC)

        # Insert audit event
        entity_id = f"{work_item_id}/{step.step_id}"
        event = DaemonEvent(
            project_id=project_id,
            event_type="step_auto_skipped_phantom_gate",
            entity_id=entity_id,
            entity_type="workflow_step",
            message=f"Auto-skipped phantom QV gate {gate}: {verdict.reason}",
            event_metadata={
                "work_item_id": work_item_id,
                "step_id": step.step_id,
                "gate": gate,
                "command": command,
                "reason": verdict.reason,
                "trigger": trigger,
            },
        )
        session.add(event)
        reason: str = verdict.reason or "unknown"
        skipped.append((step.step_id, gate, reason))
        logger.info("Auto-skipped phantom gate %s (%s): %s", step.step_id, gate, verdict.reason)

    if skipped:
        logger.info(
            "auto_skip_phantom_qv_gates [%s/%s]: %d phantom gate(s) auto-skipped",
            project_id,
            work_item_id,
            len(skipped),
        )

    session.flush()
    return skipped
