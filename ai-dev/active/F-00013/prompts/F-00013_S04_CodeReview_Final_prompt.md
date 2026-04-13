# F-00013_S04_CodeReview_Final_prompt

**Work Item**: F-00013 — Project-Level Documentation System — Automation (Phase 3)
**Review Step**: S04 (Final Review)
**Implementation Steps Reviewed**: S01, S02, S03

---

## Input Files

- `ai-dev/active/F-00013/F-00013_Feature_Design.md` — Design document
- All implementation reports: `ai-dev/work/F-00013/reports/F-00013_S0{1,2,3}_*_report.md`
- All files listed in all implementation reports' `files_changed`
- `CLAUDE.md`, `orch/CLAUDE.md`, `dashboard/CLAUDE.md`

## Output Files

- `ai-dev/work/F-00013/reports/F-00013_S04_CodeReview_Final_report.md`

## Context

Final cross-agent review for **F-00013: Documentation Automation**. This phase introduces event-driven behavior (post-merge hook) and lint enforcement. Verify correctness, safety, and integration with Phases 1 and 2.

## Review Checklist

### 1. Completeness — All 8 AC Implemented

- [ ] AC1: Batch merge triggers doc regeneration (hook wired, auto_trigger_on_merge checked)
- [ ] AC2: Unchanged source files do not trigger jobs
- [ ] AC3: Stale badge appears on outdated docs
- [ ] AC4: Regenerate All enqueues jobs
- [ ] AC5: `iw docs-check-stale` exits 1 when stale
- [ ] AC6: Lint gate populates warnings without blocking doc status
- [ ] AC7: Concurrent job limit enforced (max 2 per project)
- [ ] AC8: Auto-trigger disabled per project

### 2. Post-Merge Hook Safety

- [ ] Hook only runs when `auto_trigger_on_merge = True` in project config
- [ ] Hook handles `git diff` failures gracefully (subprocess error → log warning, return [])
- [ ] Hook uses the correct pre/post merge SHAs from the `Batch` model (not hardcoded)
- [ ] Glob path matching is correct: `fnmatch.fnmatch()` called per changed_path × source_path

### 3. Lint Gate Correctness

- [ ] Lint does NOT change `DocStatus`
- [ ] Lint runs ONLY after `completed` (not `failed`) jobs
- [ ] Empty `lint_warnings` is stored as `[]` (not null) when lint passes
- [ ] Forbidden phrases list uses project config when available, falls back to default
- [ ] YAML frontmatter parse failure is caught and reported as a warning (not an exception)

### 4. Git Subprocess Safety

- [ ] `subprocess.run()` calls use `timeout=5` to prevent hanging
- [ ] `cwd=project.repo_root` is always set (no assumption about working directory)
- [ ] Subprocess output is decoded correctly (`.strip()`, handle empty output)
- [ ] No shell injection: path arguments are passed as list elements, not string interpolation

### 5. Config Panel

- [ ] Config saves to `Project.config["doc_generation"]` without overwriting other project config keys
- [ ] Config read uses `.get()` with defaults (no `KeyError` if key missing)
- [ ] Forbidden phrases are stored as a list (not a comma-separated string)

### 6. All Invariants

- [ ] Invariant 1: max 2 running jobs per project (enforced in DocJobPoller AND on Regenerate All)
- [ ] Invariant 2: auto_trigger=false → zero auto jobs
- [ ] Invariant 3: lint never changes DocStatus
- [ ] Invariant 4: `iw docs-check-stale` exits 0 or 1 (never crashes)
- [ ] Invariant 5: glob matching works in `find_docs_by_source_path()`

### 7. Test Coverage

- [ ] Post-merge hook tested with real git repo fixture
- [ ] Staleness detection tested with real git mtime
- [ ] Lint gate tested with valid and invalid content
- [ ] Config panel save/load tested

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — pass
2. `make test-integration` — pass
3. `make quality` — ruff + mypy pass

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview_Final",
  "work_item": "F-00013",
  "steps_reviewed": ["S01", "S02", "S03"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```
