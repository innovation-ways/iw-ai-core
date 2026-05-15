# I-00084_S01_Pipeline_prompt

**Work Item**: I-00084 — Stale origin/main ref breaks make diff-coverage
**Step**: S01
**Agent**: pipeline-impl

---

## ⛔ Docker is off-limits

(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. No migration impact.)

## Input Files

- **Runtime step state**: `uv run iw item-status I-00084 --json`
- `ai-dev/active/I-00084/I-00084_Issue_Design.md` — READ FIRST
- `executor/worktree_setup.sh` — current worktree-creation script
- `Makefile` — `diff-coverage` target

## Output Files

- `ai-dev/work/I-00084/reports/I-00084_S01_Pipeline_report.md`
- Modified: `executor/worktree_setup.sh`, `Makefile`

## Context

Two-line fix. The first goes in `executor/worktree_setup.sh` immediately
after the `git worktree add ...` call. The second goes at the top of the
`diff-coverage:` Makefile target body, before any of the existing
`uv run pytest ...` lines.

## Requirements

### 1. `executor/worktree_setup.sh`

Immediately after `git worktree add <path> <branch>` (verify the exact
shell), add:

```bash
# I-00084: Sync origin/main ref to local main so diff-cover, scope_gate,
# and any other compare-vs-origin tools see the right base. This setup is
# local-only — origin/main never advances on its own.
git -C "$WORKTREE_DIR" fetch . main:refs/remotes/origin/main 2>/dev/null || true
```

The `2>/dev/null || true` makes it safe in environments where the local
`main` ref doesn't exist (fresh clone, edge cases).

### 2. `Makefile` — top of `diff-coverage:` target

```makefile
diff-coverage:
	@git fetch . main:refs/remotes/origin/main 2>/dev/null || true
	uv run pytest tests/unit/ --cov-fail-under=0 -q
	... (rest unchanged)
```

This is a defensive duplicate that handles any code path that runs
diff-coverage in a worktree NOT created by `worktree_setup.sh` (operator
debugging, CI variants, etc.).

### 3. Idempotency

Both invocations are no-ops when `origin/main` already matches local
`main`. Verify by running twice in succession; second run must be
silent / fast.

### 4. No GitHub-flow regression

If a real GitHub remote IS configured and reachable, the local `git fetch
. main:...` does NOT touch it (it fetches from `.` — the local repo
itself, not `origin`). Existing pull-from-GitHub behaviour is unchanged.

## Project Conventions

Read `CLAUDE.md` and `executor/CLAUDE.md`. Match the existing shell style
in `executor/worktree_setup.sh` (quoting, error handling, log lines).

## TDD Requirement

RED first: write the reproduction test from the design doc. Confirm it
fails against pre-fix code (`origin/main` will still be stale after
`worktree_setup.sh`). Capture the failing line in `tdd_red_evidence`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

- `make format`
- `make type-check` (likely no-op for shell + Makefile changes; still
  required to run)
- `make lint`

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/integration/test_worktree_setup_origin_main_sync.py -v
```

Do NOT run `make test-integration`.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "pipeline-impl",
  "work_item": "I-00084",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["executor/worktree_setup.sh", "Makefile"],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "tests/integration/test_worktree_setup_origin_main_sync.py::test_i00084_worktree_setup_syncs_origin_main — AssertionError: origin/main not synced",
  "blockers": [],
  "notes": ""
}
```
