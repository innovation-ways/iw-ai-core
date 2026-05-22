# I-00104_S05_CodeReview_Final_prompt

**Work Item**: I-00104 -- Batch planner false-negative overlap analysis + Max Parallel display mismatch
**Step**: S05
**Agent**: code-review-final-impl

---

## ⛔ Docker is off-limits
(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies
This Incident adds no migration.

## Input Files

- `ai-dev/active/I-00104/I-00104_Issue_Design.md`
- `ai-dev/active/I-00104/reports/I-00104_S01_Backend_report.md` … `I-00104_S04_CodeReview_report.md`
- The full diff against `origin/main`.

## Output Files

- `ai-dev/active/I-00104/reports/I-00104_S05_CodeReview_Final_report.md`

## Scope

Global cross-agent review across S01..S04.

## Checks

### 1. AC coverage matrix

| AC | Owner | Verification |
|---|---|---|
| AC1 — fnmatch overlap | S01 + S03 | `test_glob_vs_concrete_file_overlap` + `test_dir_glob_vs_dir_glob_overlap` + `test_cross_batch_overlap_uses_globs_intersect` |
| AC2 — reproduction passes | S03 + S01 | All new tests green in QV gates |
| AC3 — max_parallel | S01 + S03 | `test_create_batch_plan_reads_max_parallel` (dashboard, value 5) + `test_execution_plan_md_renders_given_max_parallel` (unit, values 3/7) |
| AC4 — no-overlap regression | S03 | `test_strictly_disjoint_paths_no_overlap` |
| AC5 — no incidental regression | This step | Run `make test-unit` and `make test-integration` |

Any AC missing a concrete artifact → CRITICAL.

### 2. Scope discipline

```bash
git diff origin/main -- orch/
```

Should be confined to `orch/batch_planner.py` (overlap loops + import line).

```bash
git diff origin/main -- dashboard/
```

Should be confined to `dashboard/routers/actions.py` (the three `4` literals).

```bash
git diff origin/main -- executor/
```

Empty.

```bash
git diff origin/main -- orch/db/
```

Empty.

```bash
git diff origin/main -- orch/daemon/
```

Empty — we are importing FROM `orch/daemon/scope_overlap.py`, not modifying it.

Anything else changed in S01 = CRITICAL scope violation.

### 3. globs_intersect adoption — final pass

`grep -n 'set(files_[ab]) & set' orch/batch_planner.py` MUST return zero lines. Same for `set(... ) & active_files`. The cross-batch loop's intersection must also use `globs_intersect`.

### 4. max_parallel hardcode — final pass

`grep -n 'generate_execution_plan_md\|generate_drawio\|generate_png' dashboard/routers/actions.py` — confirm every call passes `batch.max_parallel`, not an integer literal.

Bonus check: `grep -rn 'generate_execution_plan_md' dashboard/ orch/` — are there OTHER call sites that also passed literal integers? If yes, flag MEDIUM (out of scope for this Incident but worth a follow-up Incident).

### 5. Full test suite — re-verify

Run `make test-unit` and `make test-integration`. All green, including the new tests.

### 6. Class-of-bug analysis

The root cause of Bug 1 was duplicated overlap logic (planner vs runtime). After this fix, the planner imports the runtime helper. Is there any OTHER place in the codebase that re-implements overlap detection?

```bash
grep -rn '& set(' orch/ dashboard/ | grep -i 'path\|file\|glob\|impact'
```

Note any matches in the report as MEDIUM follow-up findings.

## Severity Guide

- CRITICAL: missing AC artifact; scope violation; remaining `& set(` overlap computation; remaining `, 4)` literal.
- HIGH: failing test suite; class-of-bug grep finds another duplicated overlap implementation and S05 didn't surface it.
- MEDIUM: other call site of `generate_execution_plan_md` still passes a literal integer; non-blocking but file as follow-up.
- LOW: comment polish.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "code-review-final-impl",
  "work_item": "I-00104",
  "completion_status": "complete",
  "files_changed": [],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "<X> passed across unit + integration",
  "tdd_red_evidence": "n/a — final review",
  "blockers": [],
  "notes": "<one-line summary>"
}
```
