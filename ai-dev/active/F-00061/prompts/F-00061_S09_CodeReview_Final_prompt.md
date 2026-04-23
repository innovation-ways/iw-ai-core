# F-00061_S09_CodeReview_Final_prompt

**Work Item**: F-00061 -- Baseline QV gates to prevent fix-cycle scope expansion
**Step**: S09
**Agent**: code-review-final-impl
**Reviews**: S01, S02, S03, S04, S05, S06, S07, S08 (global cross-agent review)

---

## ⛔ Docker is off-limits

(Same policy as S01. Read-only `docker ps/inspect/logs` is fine. Testcontainers via pytest fixtures are the only exception. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.)

## ⛔ Migrations: agents generate, daemon applies

(NEVER `alembic upgrade|downgrade|stamp` against port 5433. S01 wrote the migration; the pipeline applies it at merge time.)

## Input Files

- `ai-dev/active/F-00061/F-00061_Feature_Design.md` — full design; every section is reviewable
- All eight prior step reports in `ai-dev/active/F-00061/reports/` — S01 through S08
- `ai-dev/active/F-00061/workflow-manifest.json` — the `scope.allowed_paths` list you're enforcing
- Every file the feature touches or creates (from the design's File Manifest)

## Output Files

- `ai-dev/active/F-00061/reports/F-00061_S09_CodeReview_Final_report.md`

## Context

You are the last human-proxy gate before the QV gates (S10–S14) and the P1 scope gate at merge. Your review synthesises every step's output against the design's acceptance criteria, invariants, and scope discipline. A finding at your level often points to a cross-step issue — e.g. S03's parser contract doesn't match what S05's subtraction actually expects, or S07 tests an AC that S05 didn't implement. Catch those class of bugs here before they hit S10–S14.

## Review Focus

This is NOT a re-run of S02/S04/S06/S08 at finer granularity. Your scope is **integration across steps** and **contract against the design**.

### CRITICAL — must pass

1. **AC1–AC7 genuinely covered end-to-end**.
   - AC1 (pre-existing excluded): S03 parsers + S05 subtraction + S07 integration test together cover the full path. Confirm by tracing one reported failure from gate output → `_get_qv_findings` → test assertion.
   - AC2 (regression surfaced cleanly): same trace, confirm delta is non-empty and ordering is preserved per Invariant 4.
   - AC3 (baselines created at setup): S05's `_compute_qv_baselines` is called at the right moment; S07 asserts the expected row count.
   - AC4 (rebase invalidation): S05's stale-SHA detection works correctly; S07 validates.
   - AC5 (kill switch): S03 + S05 + S07 all respect `baseline_qv_enabled=False`.
   - AC6 (legacy items): S05's zero-rows path + S07's legacy test.
   - AC7 (scope_gate.py tests): `tests/unit/executor/test_scope_gate.py` covers the eight enumerated sub-cases in AC7.

2. **Scope discipline is IRON-TIGHT.**
   - `git diff main..HEAD --name-only` must list EXACTLY the files declared in `workflow-manifest.json` scope.allowed_paths (plus `ai-dev/active/F-00061/**` artefacts).
   - Compare against the File Manifest in the design doc row by row.
   - Any file modified that isn't in scope.allowed_paths is a CRITICAL failure. The P1 scope gate at merge will reject it regardless, but you should catch it first.
   - Particular file to double-check: `dashboard/routers/items.py` MUST NOT appear in the diff (no drive-by step-duration changes).
   - `executor/scope_gate.py` MUST NOT be modified by F-00061 — only tests against it are added (AC7 is "tests only").

3. **Invariants hold across the whole codebase**.
   - Invariant 1: unique constraint on qv_baselines verified by S02 + enforced by S01 migration
   - Invariant 2: kill switch fully quiets the feature (no stray reads/writes)
   - Invariant 3: subtraction is monotonic — S04 verified algebraically, S07 tested
   - Invariant 4: order preservation — confirm in S05 and covered in S07
   - Invariant 5: missing vs empty baseline distinction — confirm both code paths exist and are tested
   - Invariant 6: parser determinism — S04 + S07 both exercised this
   - Invariant 7: CASCADE delete — confirm FK in S01, row lifecycle in S05 + S07
   - Invariant 8: `executor/scope_gate.py` unchanged — confirm by diff

4. **No CLAUDE.md rule is broken**:
   - Port 5433 never touched by tests
   - No `importlib.reload(orch.config)`
   - `DaemonEvent.metadata` — irrelevant here but confirm we didn't introduce a similar collision with `QvBaseline`
   - No `docker compose` calls
   - No `playwright install`

5. **Test pipeline passes at main integration level**:
   - Run `make test-unit` — F-00061 tests green; no pre-existing regression; baseline failures (pre-existing, unrelated) are documented by name in the report
   - Run `make test-integration` — same
   - Run `uv run mypy orch/ dashboard/` — no new errors from F-00061
   - Run `make lint` — no new errors from F-00061
   - Run `uv run ruff format --check .` — no new violations

### HIGH — should pass

6. **Migration up/down tested in a testcontainer** during S07; the migration pipeline's pre-merge dry-run will run this again, but confirm S07 at least exercised it.
7. **Log message quality**: every new log line is grep-friendly (`[F-00061]` prefix per the S05 spec) and uses appropriate level (INFO/WARNING/DEBUG).
8. **No secrets, hardcoded paths, or hardcoded ports** anywhere in F-00061's diff.
9. **Risks documented in the design are still present**: parser drift risk (in S03/S07), baseline compute time (noted in design Notes) — these are acceptable for v1 and should NOT have been "fixed" by overreach.
10. **Rebase-invalidation race (AC4)**: confirm S05 handles the IntegrityError path per S06 checklist item 10, with the unique constraint being the mutual-exclusion primitive.

### MEDIUM_FIXABLE

11. Design doc matches implemented behaviour. If S05 diverged from the design's AC4 semantics (e.g. opted for eager invalidation instead of lazy), the design doc should be updated to reflect reality, OR the behaviour reverted.
12. Report files in `ai-dev/active/F-00061/reports/` are present and consistent.

## Verification Commands

```bash
# Scope discipline
git diff main..HEAD --name-only | sort > /tmp/f00061_changed.txt
jq -r '.scope.allowed_paths[]' ai-dev/active/F-00061/workflow-manifest.json | sort > /tmp/f00061_declared.txt
# Every file in /tmp/f00061_changed.txt not under ai-dev/active/F-00061/** should match something in /tmp/f00061_declared.txt

# Full quality sweep
make lint
uv run ruff format --check .
uv run mypy orch/ dashboard/
make test-unit
make test-integration

# AC7 sanity: scope_gate.py unchanged
git diff main..HEAD -- executor/scope_gate.py  # must be empty
```

## Report

Write `ai-dev/active/F-00061/reports/F-00061_S09_CodeReview_Final_report.md` with:

- What was reviewed (table: files × changed-by-which-step)
- AC coverage table: every AC row with its implementing step + test + status
- Invariants table: every invariant with its owning step + test + status
- Scope discipline: list of files in diff, checked against allow-list
- Test results: full counts per suite + any pre-existing failures documented (by name, confirmed unrelated)
- Findings table grouped by severity
- Overall verdict (**pass** only if zero CRITICAL + zero HIGH)

On pass: `iw step-done F-00061 --step S09 --report <path>`.
On fail: `iw step-fail F-00061 --step S09 --reason "<short>" --report <path>`.

## Subagent Result Contract

```json
{
  "step": "S09",
  "agent": "code-review-final-impl",
  "work_item": "F-00061",
  "steps_reviewed": ["S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "acceptance_criteria_coverage": {
    "AC1": {"step": "S03+S05+S07", "test": "test_ac1_...", "status": "covered"},
    "AC2": {"step": "...", "test": "...", "status": "covered"},
    "AC3": {"step": "...", "test": "...", "status": "covered"},
    "AC4": {"step": "...", "test": "...", "status": "covered"},
    "AC5": {"step": "...", "test": "...", "status": "covered"},
    "AC6": {"step": "...", "test": "...", "status": "covered"},
    "AC7": {"step": "S07", "test": "tests/unit/executor/test_scope_gate.py", "status": "covered"}
  },
  "scope_files_declared": ["..."],
  "scope_files_actual": ["..."],
  "scope_drift_detected": false,
  "tests_passed": true,
  "test_summary": "X unit, Y integration, Z scope-gate; no new pre-existing failures",
  "missing_requirements": [],
  "notes": ""
}
```

`verdict: "pass"` only if every AC is covered, every invariant holds, scope drift is false, and all tests pass.
