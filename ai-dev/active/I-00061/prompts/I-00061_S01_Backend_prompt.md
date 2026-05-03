# I-00061_S01_Backend_prompt

**Work Item**: I-00061 — Auto-skip phantom QV gates at item approval
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

(Standard policy. See `ai-dev/templates/Implementation_Prompt_Template.md` for the full text. Testcontainer fixtures spun up by pytest are exempt; nothing else in this step touches Docker.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This step adds NO migrations and NO schema changes — only Python code and CLI hooks. Do not run any alembic command other than `alembic history` for read-only verification.)

## Input Files

- **Runtime step state** — for the current step list, status, and gate commands, prefer `uv run iw item-status I-00061 --json`. The `workflow-manifest.json` file is a design-time snapshot.
- `ai-dev/active/I-00061/I-00061_Issue_Design.md` — Design document (READ FULLY before starting; the validator design and hook points are spelled out)
- `orch/cli/item_commands.py` — contains `approve` (the first hook point; the existing `item.status = WorkItemStatus.approved` + `session.flush()` block is the anchor — re-grep the file at edit time, line numbers may drift)
- `orch/cli/batch_commands.py` — contains `batch_approve` (the second hook point)
- `orch/db/models.py` — `WorkflowStep`, `BatchItem`, `DaemonEvent`, `Project`, `StepType`, `StepStatus` enums
- `orch/CLAUDE.md` — package conventions and DB-layer rules
- `CLAUDE.md` — root project rules

## Output Files

- `orch/qv_gate_validator.py` (NEW) — pure validators + DB-mutating orchestrator
- `orch/cli/item_commands.py` (MODIFIED) — `approve` invokes `auto_skip_phantom_qv_gates` post-flush
- `orch/cli/batch_commands.py` (MODIFIED) — `batch_approve` invokes `auto_skip_phantom_qv_gates` post-flush for every item in the batch
- `ai-dev/active/I-00061/reports/I-00061_S01_Backend_report.md` — Step report

## Context

You are implementing the validator and CLI hooks that prevent phantom QV gates from stalling work items. Read the design doc completely first — `Validator Design`, `Hook Points`, and `Daemon Event Schema` sections give you the contract verbatim.

The validator is split into two functions intentionally:

1. `validate_qv_gate(repo_root, gate, command) -> bool` is **pure** — no DB, no mutation, no logging. Takes a `Path`, the gate name, and the raw command string; returns True if structurally runnable, False if phantom. It is unit-tested in isolation.
2. `auto_skip_phantom_qv_gates(session, project_id, work_item_id) -> list[tuple[str, str, str]]` is the orchestrator — it queries `WorkflowStep` rows, calls the pure validator, mutates rows, inserts `DaemonEvent` audit rows, returns the list of skipped steps. It is integration-tested against a real testcontainer DB.

## Requirements

### 1. Create `orch/qv_gate_validator.py`

Module structure:

```python
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

import re
import shlex
import shutil
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from orch.db.models import (
    DaemonEvent,
    Project,
    StepStatus,
    StepType,
    WorkflowStep,
)
```

Implement (in this order):

1. `_makefile_target(command: str) -> str | None` — returns the target name
   if the command is `make <target>` (allowing `--<flag>` between `make` and
   the target). Returns `None` if it doesn't match. Use `shlex.split` to
   tokenise robustly.
2. `_makefile_has_target(repo_root: Path, target: str) -> bool` — read
   `repo_root / "Makefile"`, return True if any line matches
   `^<target>:` (use `re.escape(target)` to be safe). Return False if the
   Makefile doesn't exist.
3. `_cd_directory(command: str) -> str | None` — returns the directory if
   the command starts with `cd <dir> && …`. Match `^cd\s+(\S+)\s*&&` (or
   parse with shlex if cleaner). Strip wrapping quotes from the dir.
4. `_bare_executable(command: str) -> str | None` — for commands that did
   not match `make` or `cd …`, return the first whitespace-separated token
   if it looks like an executable name (no shell metacharacters like `|`,
   `;`, `>`, `<`, `&` other than the `&&` already handled by `cd`). Return
   `None` for anything multi-token-with-shell-features that we can't
   confidently classify.
5. `validate_qv_gate(repo_root: Path, gate: str, command: str) -> bool` —
   apply the patterns in order and return False on the first phantom hit;
   return True if everything is plausibly runnable or the shape isn't
   recognised. Define a small `@dataclass class PhantomReason` only if it
   makes the next function cleaner; otherwise return raw bool and let the
   caller derive the reason.

A second public helper to expose the *reason* (so the orchestrator can
record it in the daemon event) is useful — define it alongside the bool
function, e.g.:

```python
@dataclass(frozen=True)
class GateVerdict:
    runnable: bool
    reason: str | None  # one of: "missing_makefile_target",
                        # "missing_makefile_file",
                        # "missing_directory",
                        # "missing_executable",
                        # None when runnable

def classify_qv_gate(repo_root: Path, gate: str, command: str) -> GateVerdict:
    ...

def validate_qv_gate(repo_root: Path, gate: str, command: str) -> bool:
    return classify_qv_gate(repo_root, gate, command).runnable
```

Both `classify_qv_gate` and `validate_qv_gate` are public — tests will use
both.

6. `auto_skip_phantom_qv_gates(session: Session, project_id: str,
   work_item_id: str) -> list[tuple[str, str, str]]` — the orchestrator:
   - Look up `Project.repo_root` for `project_id` (single query).
   - Query `WorkflowStep` rows for the item where
     `step_type == StepType.quality_validation` and
     `status == StepStatus.pending` (only pending — never resurrect a step
     the daemon already started or a step that was already manually
     skipped).
   - For each, call `classify_qv_gate(Path(repo_root), step.gate or "",
     step.command or "")`. If `runnable` is False:
     - Set `step.status = StepStatus.skipped`,
       `step.completed_at = datetime.now(UTC)`.
     - Insert a `DaemonEvent` row with the schema from the design doc's
       `Daemon Event Schema` section. Use `event_type =
       "step_auto_skipped_phantom_gate"`. Pass the metadata dict directly
       (the JSONB column accepts dicts).
   - Trigger source: pass it in via a `*, trigger: str` kwarg
     (`"approve"` or `"batch_approve"`). Default to `"approve"` if you
     prefer, but the batch hook MUST pass `trigger="batch_approve"`.
   - Flush the session before returning so the caller sees the writes.
   - Return list of `(step_id, gate, reason)` tuples for skipped rows.
   - Log via the module's logger at INFO level: one line per skip with
     the reason, plus a summary if any were skipped.

### 2. Wire the hook into `iw approve`

Edit `orch/cli/item_commands.py`. Inside the `approve` command, after the
existing `item.status = WorkItemStatus.approved` and `session.flush()`
(re-grep for these — line numbers drift between edits), call:

```python
from orch.qv_gate_validator import auto_skip_phantom_qv_gates  # at top of file
...
session.flush()  # existing line — keep
skipped = auto_skip_phantom_qv_gates(
    session, project_id, item_id, trigger="approve"
)
```

Then enhance the JSON / human output to surface what was skipped (use the
existing `ctx.obj.get("json")` branch):

- JSON mode: include `"auto_skipped_steps": [{"step_id": ..., "gate": ...,
  "reason": ...}, ...]` in the dict you echo.
- Plain mode: if `skipped` is non-empty, print one line per skipped step:
  `Auto-skipped phantom gate <step_id> (<gate>): <reason>`.

The `approve` command itself MUST still exit 0 — phantom gates are not
errors, they are silently routed around.

### 3. Wire the hook into `iw batch-approve`

Edit `orch/cli/batch_commands.py`. Locate the `batch_approve` command
(or whatever Click name it has — confirm via `grep -n "@click.command" orch/cli/batch_commands.py`). After the batch transitions to approved
and is flushed, iterate every `BatchItem` in the batch and call
`auto_skip_phantom_qv_gates(session, project_id, batch_item.work_item_id,
trigger="batch_approve")`. Aggregate the results across all items and
report them in the same JSON / plain-text style as `approve`. Keep the
batch-approve command exit code at 0.

### 4. Conservative-default invariant

The validator MUST default to True (runnable) when it cannot confidently
classify a command. If you find yourself writing `return False` for a
catch-all branch, stop — that is wrong. Only return False from a branch
that has *positively identified* a known-broken pattern.

## Project Conventions

Read `orch/CLAUDE.md` and `CLAUDE.md`. Key constraints:

- SQLAlchemy 2.0 sync style (`Mapped[]`); psycopg v3 driver — do NOT import psycopg2.
- `from __future__ import annotations` at the top of new modules.
- `DaemonEvent.metadata` is `event_metadata` in Python (SQLAlchemy reserves `metadata`). The DB column is still `metadata`.
- The validator is a NEW module under `orch/`. It is NOT a CLI module — do not put Click code in it.
- No new dependencies. Stick to stdlib + existing deps (`sqlalchemy`, etc.).
- Use `datetime.now(UTC)` for timestamps (`from datetime import UTC, datetime`).

## TDD Requirement

Follow TDD (Red-Green-Refactor). The actual test file is delivered in S03, but for your own sanity you should write small inline `python -c` or `pytest -k` checks against your validator as you develop. The S03 step will replace those with the formal test files.

For S01 specifically:

1. **RED**: Sketch the validator API and write 3-4 quick assertions (in a scratch file or `python -c`) that demonstrate each pattern. Confirm they fail against an empty implementation.
2. **GREEN**: Fill in the patterns one at a time, re-running your scratch checks until each passes.
3. **REFACTOR**: Once all patterns work, simplify (collapse dead branches, extract small helpers if duplication appears).

Do NOT write the formal `tests/unit/test_qv_gate_validator.py` or `tests/integration/test_phantom_gate_auto_skip.py` — those are S03's deliverables. Your scratch tests can be deleted before reporting completion.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, you MUST run these in order
and fix any issues they report.

1. **`make format`** — auto-fixes formatting drift. If it reformats files,
   inspect the diff and re-stage; do NOT skip.
2. **`make type-check`** — must report zero errors involving the files you
   touched.
3. **`make lint`** — must report zero errors.

If a tool isn't available in your worktree, STOP and raise a blocker.

In your Subagent Result Contract, populate the `preflight` object recording
the result of each command (`ok`, `fixed`, or `skipped:<reason>`).

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. Run `make test-unit` — your validator's pattern functions are pure and unit-testable; existing tests must still pass.
2. Run `make lint` and `make type-check`.
3. Do **NOT** report `tests_passed: true` unless `make test-unit` passes.

You do NOT need to run `make test-integration` — the integration-test work happens in S03 and is gated by S09 / S10 anyway.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "I-00061",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/qv_gate_validator.py",
    "orch/cli/item_commands.py",
    "orch/cli/batch_commands.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "Hook placement, conservative-default invariant, anything reviewers should know."
}
```
