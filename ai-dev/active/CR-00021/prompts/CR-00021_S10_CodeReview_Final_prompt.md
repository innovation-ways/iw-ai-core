# CR-00021_S10_CodeReview_Final_prompt

**Work Item**: CR-00021 -- Rebase alembic down_revision at merge time
**Review Step**: S10 (Final Review)
**Implementation Steps Reviewed**: S01..S09

---

## ⛔ Docker is off-limits

Testcontainer fixtures only. Read-only docker introspection fine. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Do NOT run `alembic upgrade/downgrade/stamp` against the live DB. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `ai-dev/active/CR-00021/CR-00021_CR_Design.md` — Design document
- All implementation reports: `ai-dev/active/CR-00021/reports/CR-00021_S*_*_report.md`
- All per-step review reports: `ai-dev/active/CR-00021/reports/CR-00021_S*_CodeReview_report.md`
- All files changed across S01–S09 (see each step's `files_changed` in its report)

## Output Files

- `ai-dev/active/CR-00021/reports/CR-00021_S10_CodeReview_Final_report.md` — final review report

## Context

Final cross-layer review of CR-00021. The per-step reviews (S02/S04/S06/S08) have already verified local correctness. Your job is to verify the whole system: does the merge pipeline's new 4-step shape (Rebase → Dry-run → Squash → Apply) actually deliver AC1–AC7, with no regression to CR-00017's existing behaviour and no broken operator CLI path?

## Review Checklist

### 1. Completeness vs Design

Walk each AC through the code end-to-end:

- **AC1** (rewrite): does `migration_rebase.run_pre_merge_rebase` rewrite the file, commit, write log row, emit DaemonEvent? Is it wired into `merge_queue._merge_item`?
- **AC2** (idempotent): does the module short-circuit when `down_revision` already matches main head? Does it still emit the DaemonEvent?
- **AC3** (multi-file chain): does chain ordering + rewrite preserve internal links?
- **AC4** (rebase conflict): does `--abort` run, `migration_rebase_failed` set, queue NOT frozen?
- **AC5** (worktree-aware dry-run): does `run_pre_merge_dry_run` pass `script_location=<worktree>/orch/db/migrations` to `safe_migrate.dry_run`? Is `_build_alembic_config` using it?
- **AC6** (parallel disjoint): does the integration test exercise the full pipeline end-to-end for two batches and produce a linear chain?
- **AC7** (parallel conflict): does the integration test verify rebase succeeds + dry-run fails + main untouched + queue not frozen?

Any AC without end-to-end coverage is a CRITICAL finding.

### 2. Cross-Agent Consistency

- `BatchItemStatus.migration_rebase_failed` (S01) matches the value written in `merge_queue.py` (S05)?
- `PendingMigrationLog.old_revision` (S01) matches writes in `migration_rebase.py` (S03) and `safe_migrate._write_migration_log` (S05)?
- `RebaseResult` fields used in `migration_rebase.py` (S03) match what `merge_queue._merge_item` reads (S05)?
- Docs (S09) describe behaviour actually shipped (S03/S05), not the design's wishes — grep for function names, field names, enum values to verify.

### 3. Integration Points — the tricky parts

- `worktree_commit.sh` Step 2.5 (`git rebase main`) is a NO-OP after S05 — merge-base should already equal main's SHA. Verify by reading the bash logic: `if [[ "$(git merge-base HEAD main)" == "$MAIN_SHA" ]]` hits the "no rebase needed" branch. No bash edits required; confirm none were made.
- **Scope gate** in `worktree_commit.sh` Step 2.25 — the rebase commit introduces diffs in `orch/db/migrations/versions/*.py`. These files were already changed by the agent's Database step, so the scope-gate input (`git diff merge-base..HEAD --name-only`) produces the same file list with or without the rebase commit. No scope-gate bypass needed. Verify by reasoning about the diff.
- **Alembic chain** after rebase-and-rewrite: `orch/db/safe_migrate.list_pending_revisions` (called by Phase 2) walks from head to base; the rewritten `down_revision` must produce a single-head chain. Verify by mental walk: main after rebase has rev1 → revA (from prior batch); worktree adds revB with `down='revA'`; post-squash-merge: rev1 → revA → revB — single head. ✓
- **`_latest_main_revision` implementation**: verify the helper excludes the batch's own files (via tmp-dir copy of main-only migrations, or equivalent). Running `ScriptDirectory` against the raw post-rebase worktree is wrong — it produces `MultipleHeadsError` in the stale case and a self-reference in the already-correct case. Grep `migration_rebase.py` for `tempfile` / `TemporaryDirectory` and confirm the filter is applied.
- **Effective-ref consistency**: grep `migration_rebase.py` for every `"origin/main"`, `"main"`, and the `effective_ref` variable. Confirm that `merge-base`, `rev-parse`, and `rebase` ALL use the same ref value on any given code path. Mixing `main` and `origin/main` across those three calls was the design flaw caught in the pre-implementation review — verify the fix landed. Fetch-failure fallback path: `fetch_succeeded=False` → `effective_ref="main"` → merge-base/rev-parse/rebase all use local `main`. Happy path: `fetch_succeeded=True` → all three use `origin/main`. Preflight DaemonEvent metadata must include `effective_ref` and `fetch_succeeded` on BOTH paths.

### 4. Test Coverage (Holistic)

- Integration tests hit `pg_engine` (testcontainer), not a mock?
- Both AC6 and AC7 have their own integration test file?
- Unit tests mock subprocess / DB but integration tests run real git and real PG?
- Backward-compat tests: calling `run_pre_merge_dry_run(batch_id)` without `worktree_path` still works and uses the old behaviour?

### 5. Architecture Compliance

- `orch/daemon/migration_rebase.py` imports only `orch.config`, `orch.db.models`, stdlib, sqlalchemy, alembic? No cross-layer imports from `dashboard/`, `orch/cli/`, `orch/rag/`?
- Module mirrors `orch/daemon/migration_pipeline.py` in style (dataclass + runner + event emission + log writes)?
- Composite PKs / append-only tables / DaemonEvent `event_metadata` gotcha all respected?

### 6. Security (Cross-Cutting)

- No `subprocess.run(..., shell=True)` anywhere in the new code?
- `worktree_path` value comes from DB (trusted), but still passed as list args to `subprocess.run` (not interpolated into strings)?
- Migration rewrite regex cannot be tricked into arbitrary code execution (file is edited with `str.replace` / `re.sub`, not `exec`)?
- No secrets printed in DaemonEvent metadata (SHAs are OK; paths are OK; stderr tails are truncated per existing pattern)?

### 7. Docs and CLAUDE.md

- `CLAUDE.md` Quick Navigation row for `migration_rebase.py` present?
- `orch/CLAUDE.md` Daemon Modules row for `migration_rebase.py` present?
- `docs/IW_AI_Core_Daemon_Design.md` has a clear "Phase 0" subsection?
- `docs/IW_AI_Core_Database_Schema.md` reflects the 3 schema deltas (enum, CHECK, column)?

### 8. No Scope Creep

- No unrelated refactors to `merge_queue.py` beyond the rebase-phase wiring?
- No new config env vars added that aren't mentioned in the design?
- No changes to operator CLI commands (`iw migrations ...`) that the design didn't describe?

## Test Verification (NON-NEGOTIABLE)

1. Run the **full test suite**: `make test-unit` + `make test-integration` — both must pass
2. Run `make lint` / `make format` / `make typecheck` — must pass
3. Report accurately with separate unit + integration counts
4. If any integration test fails, this is a CRITICAL finding

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | AC not covered end-to-end, integration tests fail, operator CLI broken, queue-not-frozen invariant broken, scope-gate bypass, docs describe un-shipped behaviour |
| **HIGH** | Cross-step desync (field renamed in one module, old name used in another), Phase 2 behaviour regressed, testcontainer conventions violated |
| **MEDIUM (fixable)** | Missing AC-coverage citation in a test, docs slightly stale, one module's error handling inconsistent with another |
| **MEDIUM (suggestion)** | Could extract a helper shared between migration_rebase and migration_pipeline |
| **LOW** | Formatting, nitpicks, suggestions for future CRs |

## Review Result Contract

```json
{
  "step": "S10",
  "agent": "code-review-final-impl",
  "work_item": "CR-00021",
  "steps_reviewed": ["S01","S02","S03","S04","S05","S06","S07","S08","S09"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "completeness|consistency|integration|testing|architecture|security|docs|scope",
      "file": "path/to/file.py",
      "line": 42,
      "description": "",
      "suggestion": "",
      "cross_cutting": true
    }
  ],
  "ac_coverage_map": {
    "AC1": "file:lines + test citation",
    "AC2": "...",
    "AC3": "...",
    "AC4": "...",
    "AC5": "...",
    "AC6": "...",
    "AC7": "..."
  },
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "unit X passed; integration Y passed; 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```
