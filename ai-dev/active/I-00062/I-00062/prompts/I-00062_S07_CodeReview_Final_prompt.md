# I-00062_S07_CodeReview_Final_prompt

**Work Item**: I-00062 -- Agent subprocess inherits orch DB env vars, allowing migrations to leak to port 5433
**Review Step**: S07 (Final Review)
**Implementation Steps Reviewed**: S01..S06

---

## ⛔ Docker is off-limits

You MUST NOT change Docker container/volume/network state. Read-only
introspection allowed. Testcontainers spawned by pytest fixtures are
exempt — Ryuk-managed. Full policy:
`docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live orch
DB. **Do NOT run bare `make`.** `alembic history/current/show` is allowed.
Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- For runtime step state, prefer `uv run iw item-status I-00062 --json`.
- `ai-dev/active/I-00062/I-00062_Issue_Design.md` — design document, all ACs
- `ai-dev/active/I-00062/I-00062_Functional.md` — functional doc
- All implementation step reports: `ai-dev/active/I-00062/reports/I-00062_S0{1,3,5}_*_report.md`
- All per-agent code review reports: `ai-dev/active/I-00062/reports/I-00062_S0{2,4,6}_CodeReview_report.md`
- All files modified by S01, S03, and S05 (see each report's `files_changed`)

## Output Files

- `ai-dev/active/I-00062/reports/I-00062_S07_CodeReview_Final_report.md` — final review

## Context

You are performing the cross-agent global review of I-00062's complete
fix package: persistence schema (S01), env injection / stripping /
fail-fast (S03), test suite (S05). The bug being fixed is an
**isolation breach between in-flight features and the orch source-of-truth
DB** — the most consequential class of bug this platform can ship. Be
strict.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run on the union of all `files_changed`:

```bash
make lint
make format
```

NEW violations → **CRITICAL** with `"category": "conventions"`.

## Review Checklist (I-00062-specific)

### 1. End-to-end isolation guarantee

Trace the agent-launch path manually from `_launch_step` outward and
confirm:

1. The agent subprocess env, in the **compose stack** case, contains the
   per-worktree DB connection (NOT 5433) AND `IW_CORE_ORCH_DB_PORT` is
   set to the daemon's orch port via the Layer 1 snapshot.
2. The agent subprocess env, in the **no-compose** case, does NOT contain
   any inherited `IW_CORE_DB_*` keys, but DOES contain `IW_CORE_ORCH_DB_*`
   set via the Layer 1 snapshot — without the snapshot, the Layer 3 guard
   in `orch/config.py` is vacuous for legacy worktrees.
3. The agent subprocess env, in the **browser-verification** case (bv_env
   provided), contains the bv-injected DB connection (NOT 5433, NOT the
   per-worktree DB), and the snapshot does NOT overwrite the existing
   `IW_CORE_ORCH_DB_*` (verify `setdefault` semantics).
4. If by some path the agent's `orch.config.get_db_url()` ever resolves
   to the operator's `IW_CORE_ORCH_DB_PORT`, it raises `RuntimeError`
   referencing I-00062. **Specifically verify this for the legacy case
   in (2): a worktree whose `.env` mirrors main → Layer 3 must fire.**

If any of (1)–(4) is broken, flag **CRITICAL** with `"cross_cutting":
true`.

### 2. AC coverage check (all six)

| AC | Where implemented | Where tested |
|----|-------------------|--------------|
| AC1 | S03 `_launch_step` injection block | S05 `test_launch_step_env_isolation.py::test_compose_stack_injects_all_five_db_vars` |
| AC2 | S03 `_agent_subprocess_env` snapshot + strip | S05 `test_agent_subprocess_env.py::test_snapshots_orch_creds_before_strip` AND `::test_strips_inherited_orch_db_vars` |
| AC3 | S03 `orch/config.py` guard | S05 `test_agent_context_failfast.py::test_agent_context_with_orch_port_raises` AND `::test_legacy_worktree_with_inherited_orch_port_raises` |
| AC4 | S05 reproducing tests | S05 itself |
| AC5 | S01 columns + migration | S05 `test_i_00062_migration.py::test_upgrade_adds_four_columns` + downgrade |
| AC6 | S03 bv_env merge ordering preserved | S05 `test_agent_subprocess_env.py::test_bv_env_overrides_strip` |

For each AC, confirm: (a) the implementation exists, (b) at least one
test asserts the specific expected behavior. Missing implementation OR
missing semantic test → **CRITICAL** with `"category":
"completeness"`.

### 3. Migration / merge pipeline interaction

The fix itself ships a new alembic migration. Confirm:
- The new migration's `down_revision` is `4876b3246ff2` (current main
  head).
- F-00077's migration `e53ce8e86a3c` is NOT in main's tree (would be a
  symptom of the original leak being committed). If you see it in the
  versions/ directory on the I-00062 branch, that's **CRITICAL**.
- The migration will be applied by the daemon's
  `migration_pipeline.run_post_merge_apply` only after I-00062 merges.
  No agent has applied it manually. Check the S01 report for any sign
  of `alembic upgrade head` or `make db-migrate` against 5433.

### 4. Cross-agent consistency

- The four `worktree_db_*` columns added by S01 are READ by S03 in
  exactly the locations the design specifies — no additional read
  sites elsewhere that would also need updating.
- `worktree_compose.UpResult.discovered_db_credentials` (S03) is
  consumed only by `batch_manager` (S03). No other module reads it.
- The fail-fast guard in `orch/config.py` (S03) does NOT regress
  daemon startup — daemon doesn't run with `IW_CORE_AGENT_CONTEXT=true`.
- The fail-fast guard does NOT break the dashboard process — same
  reason.
- The fail-fast guard does NOT break browser-verification — bv_env
  resolves to its own e2e port, not orch port.

### 5. Test pre-fix vs post-fix verification

Spot-check at least three S05 tests against the pre-fix code by
mentally reverting S03's changes and confirming the test would fail.
If any test passes both before and after, flag **HIGH** with
`"category": "testing"`.

### 6. Security & secrets

- The persisted `worktree_db_password` column stores dev credentials
  generated by `worktree-seed.sh` — acceptable. No production
  credentials.
- The `RuntimeError` in `_launch_step` does NOT include the resolved
  password, only presence flags.
- The `RuntimeError` in `orch/config.py` includes the I-00062 runbook
  reference, not credentials.
- No new logging statements echo the password column.

### 7. Backward compatibility

- Existing batches in flight (with `worktree_db_port` set but no
  host/name/user/password yet) are handled by the operator runbook
  documented in `I-00062_Issue_Design.md` Notes section: any
  `BatchItem` with `worktree_compose_path IS NOT NULL` and
  `worktree_db_host IS NULL` post-merge must be paused and re-set-up
  so a fresh `worktree_compose.up()` populates the four new columns.
  The S03 injection block raises `RuntimeError` on incomplete creds —
  this is by design (refuse to launch is safer than silent fallback).
  Confirm the runbook line is present in the design doc's Notes
  section; if missing, flag **MEDIUM (fixable)** with `"category":
  "consistency"`.
- Existing items WITHOUT `ai-dev/iw-config/` are unaffected — all
  four columns are NULL, the strip in `_agent_subprocess_env` removes
  inherited orch DB vars, and the agent's `orch.config.get_db_url()`
  fails-fast (good — it should not silently hit 5433 regardless).

If existing-item compatibility is broken, flag **HIGH**.

### 8. Functional doc accuracy

Read `I-00062_Functional.md`. Confirm it accurately describes
behavior the operator will observe AFTER the fix ships. Inaccuracies
or implementation leakage (file paths, class names) → **MEDIUM
(fixable)** with `"category": "consistency"`.

## Test Verification (NON-NEGOTIABLE)

Run **the full test suite**:

```bash
make test-unit
make test-integration
```

Both must pass. Pre-existing failures (if any) must be flagged but not
classified as new findings. Integration test failures involving
I-00062 files → **CRITICAL**.

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Isolation broken end-to-end, AC un-implemented or un-tested, F-00077 migration leaked into main, live-DB write |
| **HIGH** | bv_env regression, daemon/dashboard regression, test doesn't catch pre-fix |
| **MEDIUM (fixable)** | Convention drift, consistency issue, functional-doc inaccuracy |
| **MEDIUM (suggestion)** | Better naming, additional cross-check |
| **LOW** | Nitpick |

## Review Result Contract

```json
{
  "step": "S07",
  "agent": "CodeReview_Final",
  "work_item": "I-00062",
  "steps_reviewed": ["S01", "S02", "S03", "S04", "S05", "S06"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "completeness|consistency|integration|testing|architecture|security",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it",
      "cross_cutting": true
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```

`verdict: pass` requires zero CRITICAL/HIGH/MEDIUM (fixable) findings.
