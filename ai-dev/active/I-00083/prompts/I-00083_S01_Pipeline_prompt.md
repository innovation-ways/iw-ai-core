# I-00083_S01_Pipeline_prompt

**Work Item**: I-00083 — Branch-base drift across in-flight items
**Step**: S01
**Agent**: pipeline-impl

---

## ⛔ Docker is off-limits

(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. No migration impact.)

## Input Files

- **Runtime step state**: `uv run iw item-status I-00083 --json`
- `ai-dev/active/I-00083/I-00083_Issue_Design.md` — READ FIRST, especially the "Implementation options" subsection
- `orch/cli/item_commands.py` (the `approve` command and its chore-commit logic)
- `orch/daemon/batch_manager.py` (worktree-creation path)
- `executor/setup_worktree.sh` (`git worktree add` site)
- `orch/daemon/migration_rebase.py` (CR-00021 — the existing pre-merge rebase, useful pattern reference)

## Output Files

- `ai-dev/work/I-00083/reports/I-00083_S01_Pipeline_report.md`
- Modified files (depending on chosen option): see Requirements

## Context

CR-00053 needed three operator-applied carry-over fixes (5 assertion-baseline
entries, 1-line BatchStatus enum value, 1 migration-head revision constant)
because its branch base inherited CR-00052's tests but not CR-00052's
matching impl. This step picks one of the three implementation options
laid out in the design doc and ships it.

## Requirements

### 1. Pick one of the three options and document the choice

The design doc enumerates options (a), (b), (c). Operator preference is
**(b) — pre-commit only the design docs, not anything else under
`ai-dev/active/<ID>/`**. If you discover a fatal flaw in (b) during
implementation, write it up in `notes` and STOP — raise a blocker rather
than silently switching to (a) or (c).

### 2. Implement option (b)

Find the `approve` command in `orch/cli/item_commands.py` (or wherever
the chore commit is written). Today it likely does
`git add ai-dev/active/<ID>/ && git commit ...`. Change it to commit only
known design files:

- `ai-dev/active/<ID>/<ID>_*_Design.md`
- `ai-dev/active/<ID>/<ID>_Functional.md`
- `ai-dev/active/<ID>/workflow-manifest.json`
- `ai-dev/active/<ID>/prompts/**`

Anything else under `ai-dev/active/<ID>/` (test fixtures, scripts,
evidences) stays untracked at approval time and travels with the squash
merge instead.

### 3. Document the deliberate exclusion

Add a clearly-commented block in the chore-commit code naming exactly
what is excluded and why (cite I-00083). This is the kind of thing future
contributors will want to "fix" by re-adding everything.

### 4. Daemon log line at worktree-create time

In `orch/daemon/batch_manager.py` (or wherever the worktree is created),
emit one INFO line:

```
worktree create: item=<ID> base=<sha> in_flight_siblings=[<list>] excluded_drift_paths=[<count>]
```

Where `in_flight_siblings` is the list of other items currently in
`approved` / `executing` / `merging` status, and `excluded_drift_paths`
is the count of paths under their respective `ai-dev/active/<sib>/`
directories that exist on disk but were not part of any chore commit
(this should normally be zero after the fix; a non-zero value signals
the next drift).

### 5. Backwards compatibility

Items already approved with the old chore-commit shape continue to work
— do NOT retroactively rewrite history. The fix only affects items
approved after this change lands.

## Project Conventions

Read `CLAUDE.md` and `orch/CLAUDE.md`. Match the existing logging style
in `orch/daemon/`. Use the existing git-helper utilities; do not shell
out to raw `git` if a wrapper exists.

## TDD Requirement

RED first: write the reproduction test from the design doc. Confirm it
fails against pre-fix code (the chore commit will include extra files
or the worktree will inherit drift). Capture the failing line in
`tdd_red_evidence`. Then GREEN.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

- `make format`
- `make type-check` — zero errors involving touched files
- `make lint`

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/integration/test_branch_base_drift.py -v
```

Do NOT run `make test-integration`.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "pipeline-impl",
  "work_item": "I-00083",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["..."],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "tests/integration/test_branch_base_drift.py::test_i00083_b_worktree_does_not_inherit_a_pre_impl_test_drift — AssertionError: ...",
  "blockers": [],
  "notes": "Chose option (b). Justification: <one-sentence>"
}
```
