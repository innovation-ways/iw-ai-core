# I-00099_S01_Backend_prompt

**Work Item**: I-00099 -- Scope-overlap sibling-dir rule generates false-positive cross-batch holds
**Step**: S01
**Agent**: Backend

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This step does NOT touch migrations. Standard policy applies — do not run any `alembic upgrade/downgrade/stamp` commands.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00099 --json`.
- `ai-dev/active/I-00099/I-00099_Issue_Design.md` — design document
- `orch/daemon/scope_overlap.py` — file you will modify
- `orch/daemon/batch_manager.py` — caller (read-only; do NOT modify here, only confirm your change keeps its contract)

## Output Files

- `ai-dev/work/I-00099/reports/I-00099_S01_Backend_report.md` — Step report

## Context

You are implementing the **Backend** step of **I-00099 — Scope-overlap sibling-dir rule generates false-positive cross-batch holds**.

Read the design document first; the Root Cause Analysis and Affected Components sections give you the exact lines and the rationale. Then read `CLAUDE.md` and `orch/CLAUDE.md` for project-specific patterns.

## Requirements

### 1. Remove the sibling-directory fallback

In `orch/daemon/scope_overlap.py`:

1. **Delete `_same_parent()`** at lines 128–132. Do NOT keep it as dead code; do NOT comment it out. The fix is subtractive — no dormant code path may remain.
2. **Remove the sibling-case fallback inside `find_blocking_items()`** at lines 160–168 (the `if not intersecting: for cp in candidate_paths: for ifp in in_flight_paths: if _same_parent(cp, ifp): ...` block). After removal, `find_blocking_items` returns the result of `globs_intersect` directly when it's non-empty, and `[]` otherwise.
3. **Do NOT touch** `globs_intersect()` or `_strip_test_globs()`. Their bodies must be byte-identical to the pre-fix versions. The fix is purely deletion of the sibling branch + helper.
4. **Update the module docstring** at the top of the file. Add a paragraph noting:
   - The sibling-directory rule was removed in I-00099 (2026-05-18) after it generated false-positive holds on large dirs like `docs/`, `orch/daemon/`, `dashboard/routers/`.
   - The remaining safety nets are: (a) `globs_intersect` still catches exact-file matches and glob-anchor containment; (b) items that genuinely need module-level exclusion declare `dir/**` explicitly; (c) git merge resolves real text conflicts.
   - Two concrete cases motivating the removal: `docs/IW_AI_Core_Testing_Strategy.md` vs `docs/IW_AI_Core_AI_Assistant_Models.md` (CR-00060 ↔ CR-00057) and `orch/daemon/batch_manager.py` vs `orch/daemon/project_registry.py` (same two items).

### 2. Confirm the caller contract still holds

Open `orch/daemon/batch_manager.py:_launch_pending_items` (around line 397) and verify that the event-emission site uses `conflicting_globs` returned by `find_blocking_items`. With the sibling fallback gone, those globs now always originate from `globs_intersect` — so the existing `Held: {item} overlaps with {blocking} on {globs}` message becomes accurate by construction (it now names real intersecting paths, not the misleading candidate-side sibling path).

**Do NOT modify** `batch_manager.py`. Just confirm the contract. Note your finding in the report.

## Project Conventions

Read `CLAUDE.md` and `orch/CLAUDE.md` for:

- SQLAlchemy 2.0 sync conventions (not relevant here, but standard background).
- Pure-helper module style: `orch/daemon/scope_overlap.py` is intentionally DB-free and import-light.
- Docstring style: module docstrings use the existing `"""..."""` shape.

## TDD Requirement

This step is **subtractive Backend** — you are removing code, not adding behaviour. The reproduction tests live in S03 (Tests step), not here.

**TDD RED evidence rule**: Because S03 owns the new behavioural tests, you record `tdd_red_evidence: "n/a — pure code removal; reproduction + regression tests are added in S03 by tests-impl"` in your report.

You may, optionally, run the existing `tests/unit/daemon/test_scope_overlap.py` after your change to confirm:
- `test_non_test_sibling_still_blocks` now FAILS (because the sibling rule is gone — this is expected and documents the behavioural change; S03 deletes that test).
- All other tests in the file PASS unchanged.

Capture the resulting test summary in your report under `notes`.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, you MUST run these and fix any issues they report:

1. **`make format`** — auto-fixes formatting drift.
2. **`make typecheck`** — must report zero errors involving the files you touched.
3. **`make lint`** — must report zero errors.

If a tool isn't available in your worktree, STOP and raise a blocker.

In your Subagent Result Contract, populate the `preflight` object.

## Test Verification (NON-NEGOTIABLE)

Run only the targeted unit tests for the affected module:

```bash
uv run pytest tests/unit/daemon/test_scope_overlap.py -v
```

You should see:
- All glob-intersect tests pass.
- All I-00071 (test-path stripping) tests pass.
- `test_non_test_sibling_still_blocks` FAILS — this is expected and proves the sibling rule is removed. S03 deletes that test.

Do NOT run `make test-unit` or `make test-integration` — those are S09/S10 QV gates with their own budgets.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "Backend",
  "work_item": "I-00099",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/daemon/scope_overlap.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 1 failed (test_non_test_sibling_still_blocks — expected; S03 deletes it)",
  "tdd_red_evidence": "n/a — pure code removal; reproduction + regression tests are added in S03 by tests-impl",
  "blockers": [],
  "notes": "Confirmed batch_manager.py:_launch_pending_items contract still holds — event message remains accurate by construction now that find_blocking_items only emits globs_intersect results."
}
```
