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
because its worktree base inherited tests for an in-flight sibling whose
matching impl had not yet merged. The design (see "Implementation
options — DECIDED" section) ships **two complementary changes** in this
step:

- **(b)** narrow the `iw approve` chore commit so it can never again
  leak non-design files to `main` at approval time.
- **Launch-time sibling-scope check** in `batch_manager.py` so the
  daemon surfaces cross-item drift at worktree-create time (the actual
  CR-00053 bite, which (b) alone does not fix).

## Requirements

### 1. Narrow the `iw approve` chore commit (sub-cause 1)

Find the `approve` command in `orch/cli/item_commands.py` (or wherever
the chore commit is written). Today it likely does
`git add ai-dev/active/<ID>/ && git commit ...`. Change it to commit
**only** these paths:

- `ai-dev/active/<ID>/<ID>_*_Design.md`
- `ai-dev/active/<ID>/<ID>_Functional.md`
- `ai-dev/active/<ID>/workflow-manifest.json`
- `ai-dev/active/<ID>/prompts/**`

Anything else under `ai-dev/active/<ID>/` (test fixtures, scripts,
evidences, ad-hoc notes) stays untracked at approval time and travels
with the squash merge instead.

Add a clearly-commented allow-list block in the code naming exactly
what is excluded and why (cite I-00083). Future contributors will want
to "fix" this by re-adding everything; the comment exists to stop them.

If you discover a fatal flaw in (b) during implementation, write it up
in `notes` and STOP — raise a blocker rather than silently switching
to (a) or (c).

### 2. Launch-time sibling-scope check (sub-cause 2)

In `orch/daemon/batch_manager.py` (or wherever the worktree is created
after `git worktree add`), implement a check that runs once per
worktree creation:

1. Load all `WorkItem`s in the **same project** whose status is one of
   `approved` / `executing` / `merging` AND whose ID is **not** the
   one being created.
2. For each in-flight sibling `S`, parse `S.impacted_paths` (or
   `workflow-manifest.json:scope.allowed_paths` if that's the
   authoritative source — see CLAUDE.md / F-00076) into a list of
   gitignore-style globs.
3. For each glob, check whether B's base tree contains files matching
   it AND those files were last modified by a commit that is NOT one
   of `S`'s merge commits. (For v1, "modified by a commit that's not
   `S`'s merge commit" is approximated by "S has no merge commit yet
   and the files exist in B's base".)
4. The set of matching paths is `sibling_paths_without_merge` for
   sibling `S`. The total count across all siblings is the headline
   number.

Emit exactly one INFO line per worktree-create event:

```
worktree create: item=<ID> base=<sha> in_flight_siblings=[<sib1>,<sib2>,...] sibling_paths_without_merge=<N> details=[<sib1>:<count>,<sib2>:<count>,...]
```

- `in_flight_siblings` — list of sibling IDs (empty list if none).
- `sibling_paths_without_merge` — total count (single integer).
- `details` — per-sibling breakdown when any count is non-zero;
  omit the bracket entirely when total is zero.

**v1 behavior**: WARN only. Do NOT block worktree creation on
non-zero counts. A follow-up CR can promote this to BLOCK once
operators have lived with the WARN signal.

### 3. Backwards compatibility

- Items already approved with the old chore-commit shape continue to
  work — do NOT retroactively rewrite history.
- The fix only affects items approved or worktrees created **after**
  this change lands.
- Solo-item runs (no in-flight siblings) must emit the log line with
  `in_flight_siblings=[] sibling_paths_without_merge=0` and otherwise
  behave identically to today.

## Project Conventions

Read `CLAUDE.md` and `orch/CLAUDE.md`. Match the existing logging style
in `orch/daemon/`. Use the existing git-helper utilities; do not shell
out to raw `git` if a wrapper exists.

## TDD Requirement

RED first. Create `tests/integration/test_branch_base_drift.py` with
**only the AC1 reproduction test** (the two-in-flight-items scenario
from the design doc's "Test to Reproduce" section). Confirm it fails
against pre-fix code (B's base contains sibling A's drift paths and the
new log line is missing). Capture the failing assertion in
`tdd_red_evidence`. Then implement the fix and confirm GREEN.

**Do NOT** add the AC3 happy-path regression here, and do NOT add the
shared fake-repo helpers as reusable utilities. Those are S03's scope.
This step ships just enough test to prove RED → GREEN on AC1.

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
