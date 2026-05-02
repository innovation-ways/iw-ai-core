# F-00076_S04_Pipeline_prompt

**Work Item**: F-00076 -- Cross-batch file-conflict gate
**Step**: S04
**Agent**: pipeline-impl

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

(Same constraints as the design document. Executor scripts MUST NOT call docker or alembic. See `executor/CLAUDE.md`.)

## Input Files

- `uv run iw item-status F-00076 --json`
- `ai-dev/active/F-00076/F-00076_Feature_Design.md` (sections: Description, Scope/In Scope items 6-9, AC1, AC2, AC5, Boundary Behavior, Invariants 3-7)
- `ai-dev/active/F-00076/reports/F-00076_S01_Database_report.md` (column shape)
- `orch/daemon/batch_manager.py:279-352` — `_process_batch()` launch loop
- `orch/daemon/merge_queue.py:222-250` — `_perform_merge()` where `merge_info` is written
- `orch/daemon/state_machine.py` — `_emit_event` helper used throughout daemon
- `executor/worktree_commit.sh:230-286` — rebase block
- `orch/db/models.py` — `BatchItem.merge_info`, `WorkItemType` enum, `BatchItemStatus` enum, `DaemonEvent`

## Output Files

- `ai-dev/active/F-00076/reports/F-00076_S04_Pipeline_report.md`
- `orch/daemon/scope_overlap.py` — new helper module (CREATE)
- `orch/daemon/batch_manager.py` — gate inserted in `_process_batch()`
- `orch/daemon/merge_queue.py` — `merge_info["conflict_files"]` capture
- `executor/worktree_commit.sh` — `CONFLICT_FILES` marker line
- Tests under `tests/unit/daemon/` and `tests/integration/daemon/`

## Context

You are wiring the cross-batch launch-time conflict gate. S03 populates `WorkItem.impacted_paths` at registration time; you consume it at daemon poll time. You also wire up `BatchItem.merge_info["conflict_files"]` so we have post-mortem data on rebase auto-resolutions.

S03 runs in parallel with you. Coordinate via the design doc: read `WorkItem.impacted_paths` directly, never call the parser yourself.

Read `orch/CLAUDE.md`, then `executor/CLAUDE.md` (the worktree_commit.sh changes must respect the no-docker-no-alembic rule).

## Requirements

### 1. New module `orch/daemon/scope_overlap.py`

Create the file with this surface:

```python
"""Glob intersection helpers for the F-00076 cross-batch conflict gate.

Pure functions — no DB, no logging beyond local imports. Imported by
batch_manager._process_batch() to decide whether a candidate item conflicts
with any in-flight item in the same project.
"""

from __future__ import annotations

from typing import Iterable

import pathspec

_TEST_PATH_MARKERS = (
    "/tests/", "/test/", "/__tests__/",
    "conftest", ".test.", ".spec.",
)


def is_test_path(glob: str) -> bool:
    """Return True when the glob targets test files only."""
    # Mirror orch/batch_planner.py:_is_test_path semantics.
    # Also recognise common '**/tests/**' and '**/__tests__/**' shorthand.
    ...


def _strip_test_globs(globs: Iterable[str]) -> list[str]:
    return [g for g in globs if not is_test_path(g)]


def globs_intersect(a: list[str], b: list[str]) -> list[str]:
    """Return globs from `a` that share at least one matching path with any
    glob in `b`, after stripping test-path globs from both sides.

    Implementation: build pathspec.GitWildMatchPattern for each side, then
    use a probe-based approximation: for each glob in `a`, generate a small
    set of representative paths (the literal pattern, the pattern with `**`
    expanded to a sample, etc.) and check whether any of those paths match
    the `b` pathspec. Two globs that both literally point at the same file
    (or share a common prefix in the directory case) trivially conflict.

    Returns the conflicting globs from `a` (deduped, original order
    preserved). Empty list when there is no overlap.
    """
    ...


def find_blocking_items(
    candidate_paths: list[str],
    in_flight: list[tuple[str, list[str]]],
) -> list[tuple[str, list[str]]]:
    """For each (item_id, paths) in `in_flight`, return those that conflict
    with `candidate_paths`. The second element of each result tuple is the
    list of conflicting globs (intersection from candidate's side).
    """
    ...
```

Implementation notes:
- For `globs_intersect`, the probe set approach is acceptable because real-world declarations are dominated by `dir/**` and exact paths. Document the limitation in the docstring: "Patterns that diverge significantly from gitignore-style (e.g. character classes intersecting only on synthetic strings) may produce false-negative non-overlaps; in that case rebase-time scope_gate is the safety net."
- Required probes per pattern:
  1. The pattern itself stripped of trailing `/**` and `*` segments (the "anchor").
  2. The anchor + a synthetic file `{anchor}/probe.py` to ensure dir-glob matches.
  3. The literal pattern as-is.
- Confirm that two `**` globs collide via the empty-anchor case.

### 2. Launch-time gate in `batch_manager._process_batch()`

In `orch/daemon/batch_manager.py:_process_batch()` between the existing parallelism check (`if executing_count >= batch.max_parallel: break`, around line 349) and the call to `self._launch_item(...)`, insert the gate. Before that, hoist the in-flight scope query above the launch loop so it runs once per `_process_batch` call:

```python
# F-00076: gather in-flight items across the project (any batch) for the
# cross-batch conflict gate. Excludes Research items per design.
in_flight_scopes = self._collect_in_flight_scopes(db)
```

`_collect_in_flight_scopes` is a new method on `BatchManager` that queries:
- `BatchItem.status IN (setting_up, executing, merging)`
- `BatchItem.project_id == self.project_id`
- joined with `WorkItem` where `WorkItem.type != WorkItemType.research`
- returns `list[tuple[work_item_id, impacted_paths]]`

In the launch loop, before `self._launch_item(db, item)`:

```python
work_item = db.get(WorkItem, (self.project_id, item.work_item_id))
if work_item is None:
    continue
if work_item.type != WorkItemType.research:
    blocked_by = find_blocking_items(
        list(work_item.impacted_paths or []),
        in_flight_scopes,
    )
    if blocked_by:
        for blocking_id, conflicting_globs in blocked_by:
            _emit_event(
                db,
                self.project_id,
                "item_held_for_scope",
                item.work_item_id,
                "work_item",
                f"Held: {item.work_item_id} overlaps with {blocking_id} on "
                f"{', '.join(conflicting_globs[:3])}",
                {
                    "candidate_item_id": item.work_item_id,
                    "blocking_item_id": blocking_id,
                    "conflicting_globs": conflicting_globs,
                },
            )
        db.commit()
        continue  # leave status=pending; do not consume parallelism slot
self._launch_item(db, item)
```

Order: the gate runs AFTER the `pending` status check but BEFORE the parallelism-limit check — a held item should NOT count against `max_parallel`. Do not increment `executing_count` for a held item.

After launching the item, append its scope to `in_flight_scopes` so that subsequent items in the same poll cycle see it (prevents two items in the same group from launching simultaneously when their globs overlap and neither is in flight at the start of the cycle).

### 3. `merge_info["conflict_files"]` capture

`executor/worktree_commit.sh` rebase block (lines 230-286): after the `conflicting=$(git diff --name-only --diff-filter=U ...)` line, AND after the auto-resolve loop completes successfully, emit a structured marker line to stdout:

```bash
# F-00076: emit conflict file list as JSON for merge_queue to capture.
if [[ -n "$conflicting" ]]; then
    _conflict_json=$(printf '%s\n' "$conflicting" | jq -R . | jq -s -c .)
    echo "[worktree_commit] CONFLICT_FILES $_conflict_json"
fi
```

If `jq` is not available, fall back to a hand-rolled JSON encoder (escape `"` and `\`, wrap in `[...]`). Confirm `jq` availability — `which jq || echo missing`. The script already runs in the worktree shell; jq should be present, but document the fallback.

In `orch/daemon/merge_queue.py:_perform_merge()` (around line 237), parse the marker from `result.stdout` and store it:

```python
import re
import json as _json

_CONFLICT_MARKER_RE = re.compile(
    r"^\[worktree_commit\] CONFLICT_FILES (\[.*\])$",
    re.MULTILINE,
)

# ... inside _perform_merge after a successful rebase:
conflict_files: list[str] = []
m = _CONFLICT_MARKER_RE.search(stdout)
if m:
    try:
        conflict_files = _json.loads(m.group(1))
    except _json.JSONDecodeError:
        conflict_files = []

batch_item.merge_info = {
    "stdout": stdout[:_MERGE_INFO_STDOUT_LIMIT],
    "stdout_truncated": len(stdout) > _MERGE_INFO_STDOUT_LIMIT,
    "conflict_files": conflict_files,
}
```

When the rebase has zero conflicts, the marker line is absent and `conflict_files` stays `[]`. Do NOT add the key with `None` — the design contract (Invariant 6) requires it always be a JSON array.

When rebase fails AND the merge raises a `MergeError`, the existing `except` block at line 288 must ALSO write `conflict_files` if the error path produced one. Add the same parser there, applied to whatever stdout/stderr is available.

### 4. Tests

- `tests/unit/daemon/test_scope_overlap.py` — `is_test_path`, `globs_intersect` (exact match, `dir/**`, mixed test+prod, both empty, `["**"]` vs anything, no overlap returns `[]`).
- `tests/integration/daemon/test_batch_manager_scope_gate.py`:
  - Two Features in different batches, overlapping globs → second is held, `item_held_for_scope` event emitted.
  - In-flight Feature, candidate Research with overlapping globs → Research launches.
  - In-flight Feature in `merged` status → candidate launches (not in-flight).
  - In-flight Feature in `setup_failed` → candidate launches.
  - Held item resumes when in-flight reaches `merged`.
  - Two pending items in the same group with mutually overlapping globs — only one launches per cycle.
- `tests/integration/daemon/test_merge_info_conflict_files.py`:
  - Rebase with `uv.lock` conflict (auto-resolved) → `merge_info["conflict_files"] == ["uv.lock"]`.
  - Clean rebase (no conflicts) → `merge_info["conflict_files"] == []`.

For the integration tests, use the existing daemon fixtures and seed worktrees that can drive the rebase path. If your fixtures cannot exercise the full bash script, mock `subprocess.run` and feed stdout containing the marker — record this approach in your report.

## Project Conventions

- `orch/CLAUDE.md`, `executor/CLAUDE.md`, `tests/CLAUDE.md`.
- Daemon logging via `logger.info / logger.warning / logger.error`.
- `_emit_event(db, project_id, event_type, entity_id, entity_type, message, event_metadata)` is the standard event-emission helper.
- Bash scripts in `executor/` use `set -euo pipefail`; preserve that.

## TDD Requirement

Unit tests for `scope_overlap` first; then implementation. Integration tests for the gate before modifying `_process_batch`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`

`make lint` runs `node --check` over `dashboard/static/**/*.js` — your changes do not touch that, but the gate runs anyway.

## Test Verification

1. `make test-unit`
2. `make test-integration`
3. Do NOT report `tests_passed: true` unless all pass.

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "pipeline-impl",
  "work_item": "F-00076",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/daemon/scope_overlap.py",
    "orch/daemon/batch_manager.py",
    "orch/daemon/merge_queue.py",
    "executor/worktree_commit.sh",
    "tests/unit/daemon/test_scope_overlap.py",
    "tests/integration/daemon/test_batch_manager_scope_gate.py",
    "tests/integration/daemon/test_merge_info_conflict_files.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
