# I-00101_S01_Backend_prompt

**Work Item**: I-00101 -- Scope-violation escalations strand work items with no UI surface or remedy
**Step**: S01
**Agent**: Backend

---

## ⛔ Docker is off-limits

Standard policy (see `docs/IW_AI_Core_Agent_Constraints.md`). Testcontainer fixtures invoked by pytest are exempt; everything else (`docker compose up/down/restart/build`, `docker kill/stop/rm`, volume/network prune, `docker system prune`) is forbidden. Read-only introspection (`docker ps`, `docker inspect`, `docker logs`) is fine.

## ⛔ Migrations: agents generate, daemon applies

This step does NOT touch migrations. `FixCycle.fix_metadata` is JSONB and already carries `scope_violations`; the new event type `scope_amended_by_operator` is content, not schema. Standard policy applies — never run `alembic upgrade|downgrade|stamp` against the live DB.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00101 --json`
- `ai-dev/active/I-00101/I-00101_Issue_Design.md` — design document (READ FIRST; this prompt assumes you have read it)
- `orch/daemon/fix_cycle.py` — file you will modify (focus on `_max_cycles_for` at line ~336 and `should_attempt_fix_cycle`/`_complete_fix_cycle` at lines ~482-505 and ~1014-1122)
- `orch/db/models.py` — read-only; references for `FixCycle`, `FixStatus`, `WorkflowStep` columns
- `orch/daemon/project_registry.py` — read-only; references for `ProjectConfig.qv_fix_cycle_max` and `.aggregate_fix_cycle_max`

## Output Files

- `ai-dev/active/I-00101/reports/I-00101_S01_Backend_report.md` — Step report
- `orch/daemon/scope_amendment.py` — NEW pure-helper module (created in this step)

## Context

You are implementing the **Backend** step of **I-00101**. The design doc has the full Root Cause Analysis with file:line anchors and the rationale for every choice. Read it before opening any file.

There are two distinct deliverables in this step:
1. A budget-exemption filter so scope-violation escalations do not eat fix-cycle slots.
2. A new pure-helper module `orch/daemon/scope_amendment.py` that the dashboard will import. The dashboard wiring is S03's job; you only write the helpers.

## Requirements

### 1. Budget-exemption filter in `orch/daemon/fix_cycle.py`

Current behaviour (lines ~482 and ~498-504): both the per-step budget check (`existing = db.query(FixCycle).filter(FixCycle.step_id == step.id).count()`) and the aggregate per-work-item budget check (`aggregate_used = db.query(FixCycle).join(WorkflowStep, ...).count()`) count every FixCycle row — including those marked `escalated` because of scope violations.

Change both queries so they exclude rows where **both** of the following hold:
- `FixCycle.status == FixStatus.escalated`
- `FixCycle.fix_metadata->'scope_violations'` is a non-empty JSONB array (i.e., `jsonb_array_length(...) > 0`)

A vanilla `escalated` cycle without `scope_violations` metadata (e.g., from another future cause — `spec_mismatch` produces no `scope_violations` key) **must still count**. The filter is narrow on purpose.

Recommended SQL shape (using PostgreSQL JSONB operators):

```python
from sqlalchemy import and_, or_, not_, func
from orch.db.models import FixCycle, FixStatus

def _is_scope_escalation():
    """Predicate: True when the FixCycle is an escalation caused by scope violations."""
    return and_(
        FixCycle.status == FixStatus.escalated,
        FixCycle.fix_metadata.is_not(None),
        FixCycle.fix_metadata.op("->")("scope_violations").is_not(None),
        func.jsonb_array_length(
            FixCycle.fix_metadata.op("->")("scope_violations")
        ) > 0,
    )
```

Apply `.filter(not_(_is_scope_escalation()))` on both `.count()` queries. Keep the helper local to `fix_cycle.py` (do NOT export). The helper exists so both call sites share one definition — if you copy-paste the predicate inline twice, the reviewer will flag it.

Update the module docstring at the top of `orch/daemon/fix_cycle.py` with a `2026-05-18 (I-00101)` note recording: "Scope-violation escalations no longer count against per-step or aggregate fix-cycle budgets. They are an operator-decidable scope decision, not a real failed retry attempt. The filter excludes only `status=escalated AND fix_metadata.scope_violations non-empty` — other escalation causes (e.g. spec_mismatch) still consume budget."

### 2. New module `orch/daemon/scope_amendment.py`

Create the file with **pure helpers** (no DB writes, no logging side-effects beyond INFO-level traces). The dashboard endpoint composes these helpers with the DB write + event emit + step-restart in a single transaction; that composition is S03's job.

Three callables to implement:

```python
"""Scope amendment helpers for I-00101.

When a fix-cycle agent edits a file outside ``scope.allowed_paths``, the daemon
marks the cycle ``escalated`` and the step ``needs_fix``. The operator can then
either AMEND the manifest (add the offending paths to ``allowed_paths``) or
REVERT the agent's edits and re-queue the step.

These helpers are pure I/O against the worktree + parent manifest files and a
read-only DB query. The dashboard endpoint in ``actions.py`` composes them
with the side-effect-bearing DB writes (event emit + StepRun row + step-status
flip).
"""

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session


@dataclass(frozen=True)
class AmendResult:
    paths_added: list[str]       # what we actually appended (deduped against existing)
    manifests_updated: list[Path]  # which files we wrote (worktree always; parent if found)


@dataclass(frozen=True)
class RevertResult:
    reverted: list[str]   # paths git successfully checked out
    failed: list[str]     # paths where `git checkout` failed (report under each path's stderr)


def amend_allowed_paths(
    worktree_path: Path,
    item_id: str,
    paths_to_add: list[str],
) -> AmendResult:
    """Append ``paths_to_add`` to ``scope.allowed_paths`` in BOTH manifests.

    Targets:
      - ``<worktree_path>/ai-dev/active/<item_id>/workflow-manifest.json`` (always)
      - ``<parent_repo>/ai-dev/active/<item_id>/workflow-manifest.json`` (when found)

    The parent repo path is computed by reading the worktree's ``.git`` file
    (it's a pointer-file for git worktrees: ``gitdir: /path/to/parent/.git/worktrees/<name>``)
    and walking up to the parent repo root. If the parent manifest cannot be
    located, write only the worktree copy and include a note in the result's
    ``manifests_updated`` list (worktree only).

    De-duplicate against existing entries before appending. Pretty-print with
    2-space indentation to match the existing file style. Preserve the
    ``_note`` field and all other top-level keys verbatim.
    """


def revert_paths_in_worktree(
    worktree_path: Path,
    paths_to_revert: list[str],
) -> RevertResult:
    """Run ``git -C <worktree_path> checkout -- <path>`` for each path.

    Use ``subprocess.run`` with ``cwd`` NOT set (rely on ``-C``); never spawn a
    shell. Capture stderr per-path. Return both the successful and failed
    paths so the caller can emit a partial-success event.
    """


def latest_scope_violation(db: Session, step_id: int) -> list[str] | None:
    """Return ``scope_violations`` from the LATEST FixCycle on the step, or None.

    ``LATEST`` means ``ORDER BY cycle_number DESC LIMIT 1``. Returns None when:
      - the step has no fix cycles, OR
      - the latest cycle is not status=escalated, OR
      - the latest cycle has no ``scope_violations`` key in ``fix_metadata``, OR
      - ``scope_violations`` is an empty list.
    """
```

Type annotations are required. Use `pathlib.Path`, not strings. Use `json.dumps(data, indent=2, sort_keys=False)` (so we preserve key order). Use `subprocess.run(..., check=False, capture_output=True, text=True)` — do NOT raise on non-zero exit; the caller decides.

**Idempotency**: `amend_allowed_paths` must be safe to call twice with the same `paths_to_add`. The second call appends nothing and returns `AmendResult(paths_added=[], manifests_updated=[...])`.

## Project Conventions

- Read `CLAUDE.md` and `orch/CLAUDE.md`.
- `orch/daemon/` modules are sync (single-threaded poll loop) — no `async`.
- SQLAlchemy 2.0 mapped-style; queries use `db.query(...)` (legacy style is still in use throughout `fix_cycle.py` — match the local style).
- Helper modules under `orch/daemon/` are DB-thin and side-effect-light. The scope_amendment helpers do file I/O + subprocess but no DB mutations.

## TDD Requirement

Behavioural tests for both deliverables are in S05. This step legitimately adds no behavioural test of its own — record `tdd_red_evidence: "n/a — Backend implements helpers consumed by S05's tests; S05 owns the RED-first runs"`.

Optional: run the existing `tests/unit/daemon/` suite to confirm no regression — `uv run pytest tests/unit/daemon/ -v --no-cov`.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, run in order and fix anything they report:

1. `make format` — auto-fix.
2. `make typecheck` — zero errors on touched files (`orch/daemon/fix_cycle.py`, `orch/daemon/scope_amendment.py`).
3. `make lint` — zero errors.

Populate the `preflight` object in your report.

## Test Verification (NON-NEGOTIABLE)

Targeted run only:

```bash
uv run pytest tests/unit/daemon/ -v --no-cov
```

This is the existing daemon-unit suite. No new test files exist yet (S05 writes them). The run should report all-pass — if anything regresses, fix it before reporting completion.

Do **NOT** run `make test-unit` or `make test-integration`. Those are S12/S13 QV gates.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "Backend",
  "work_item": "I-00101",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/daemon/fix_cycle.py",
    "orch/daemon/scope_amendment.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed (existing tests/unit/daemon/ suite)",
  "tdd_red_evidence": "n/a — Backend implements helpers consumed by S05's tests; S05 owns the RED-first runs",
  "blockers": [],
  "notes": ""
}
```
