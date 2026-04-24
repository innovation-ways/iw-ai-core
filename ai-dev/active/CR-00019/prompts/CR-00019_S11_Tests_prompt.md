# CR-00019_S11_Tests_prompt

**Work Item**: CR-00019 -- Selection-driven OSS Prepare with reviewable worktree lifecycle
**Step**: S11
**Agent**: tests-impl

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Same guards. Testcontainers are the only acceptable DB dependency.

## Input Files

- `ai-dev/active/CR-00019/CR-00019_CR_Design.md` — especially the AC list; every AC needs at least one test
- Reports from S01, S03, S05, S07, S09
- All implementation files listed in those reports
- `tests/conftest.py` — fixture patterns, testcontainer helper
- `tests/CLAUDE.md` — testing rules (testcontainer-only, FTS setup, no live DB)

## Output Files

- New / expanded test files under `tests/integration/` and `tests/unit/`
- `ai-dev/work/CR-00019/reports/CR-00019_S11_Tests_report.md`

## Context

You are writing the **additional** test coverage for CR-00019 beyond what was authored inline during S01/S03/S05/S07/S09. Goal: every AC has at least one test that fails on pre-change code and passes post-change. Existing integration tests that touch OSS routes / scanner / findings likely need updates for the new JSON body / rationale field / awaiting-review state.

## Requirements

### 1. Migration test (`tests/integration/test_cr_00019_migration.py`)

May already exist from S01. Ensure it covers:
- Both new enum values exist on `project_oss_job_status`.
- All four new columns exist on `project_oss_job` with correct types + nullability.
- The `rationale` column exists on `oss_finding`.
- Migration is idempotent (re-applying is a no-op).
- Down-migration drops the columns and documents that enum values remain.

### 2. Skill rationale + filter (`tests/unit/test_cr_00019_skill.py`)

- `Finding(..., rationale="...").to_dict()` includes `rationale`.
- `run_make_oss` with `check_ids={"OSS-LIC-01"}` only applies `OSS-LIC-01`.
- `run_make_oss` with `check_ids={"OSS-LIC-01"}` does NOT apply `OSS-ENV-03` (the old always-try).
- `run_make_oss` with `check_ids=None` applies all auto-fixable findings (legacy behavior).
- argparse parses `--check A --check B` into `["A", "B"]`.
- argparse rejects `--check` outside make_oss mode (exit 2).
- argparse rejects `make_oss` without `--check` (exit 2).
- Spot-check: for each of the 14 check modules, at least one emitted Finding carries a non-empty rationale string.

### 3. CLI `--check` (`tests/integration/test_cr_00019_cli.py`)

- `uv run iw oss prepare --project <id>` without `--check` exits non-zero with a clear stderr message.
- `uv run iw oss prepare --project <id> --check OSS-LIC-01` invokes the skill with `--check OSS-LIC-01`.
- Two `--check` flags are accumulated into a repeatable list.

(Use testcontainer PG + a minimal Project row fixture. Mock the subprocess or use a fake skill.)

### 4. Worker awaiting-review lifecycle (`tests/integration/test_cr_00019_worker.py`)

Use a real git-init'd tmp repo as `project.repo_root`. Mock the `uv run iw oss prepare` subprocess to:
- Succeed and stage some files → expect worktree persists, status=awaiting_review, `commit_sha`/`branch_name`/`files_changed_summary` populated.
- Succeed with no staged files → expect worktree removed, status=complete with "No changes produced" in error_message.
- Fail (non-zero exit) → expect worktree removed, status=error.

Use `unittest.mock.patch` to replace `asyncio.create_subprocess_exec` with a mock that returns your canned stdout + exit code. Don't run the real skill.

### 5. Accept route (`tests/integration/test_cr_00019_accept.py`)

- **Happy path**: create a job in awaiting_review, with real git worktree + prep branch. POST accept → main receives one squash-merge commit with expected message; prep branch deleted; worktree removed; job row status=complete.
- **Moved main**: move main HEAD after the job was created (simulate: commit something on main in the test repo). POST accept → 409, worktree intact, branch intact, job still awaiting_review.
- **Wrong status**: job in `complete` → POST accept → 409.
- **Wrong kind**: a scan job → POST accept → 400.

### 6. Discard route (`tests/integration/test_cr_00019_discard.py`)

- **Happy path**: awaiting_review → POST discard → branch deleted, worktree removed, status=discarded.
- **Idempotent when worktree already gone**: remove the worktree dir manually, then POST discard → still 200/409 per author's documented choice, status=discarded.
- **Idempotent when branch already gone**: delete the branch manually, then POST discard → still 200/409, status=discarded.
- **Wrong status**: `complete` → 409.

### 7. Concurrency gating (`tests/integration/test_cr_00019_concurrency.py`)

- One prepare job in `running`. POST new prepare → 409 with "already running".
- One prepare job in `awaiting_review`. POST new prepare → 409 with "awaiting review".
- One prepare job in `complete`. POST new prepare → 200 (starts a new one).

### 8. Stale-scan UI gate (`tests/integration/test_cr_00019_stale_ui.py`)

- With `scan_summary.is_stale=True`, rendered HTML contains an element with `data-oss-stale="true"` on the prepare button (or equivalent disabled-state indicator).

### 9. Template rendering (`tests/integration/test_cr_00019_oss_template.py`)

- Table groups findings by domain.
- Within a group, rows are ordered MUST → SHOULD → INFO → MAY.
- Checkbox enablement rule:
  - fail + auto_fix_available=true → enabled (no `disabled` attr).
  - fail + auto_fix_available=false → disabled (tooltip present).
  - pass → no checkbox element at all.
  - skip → no checkbox element at all.
- No occurrence of "→ Fix via Prepare" anywhere in the response body.
- Details modal HTML block contains `finding.rationale` content.
- OSPS anchor href is exactly `https://baseline.openssf.org/#OSPS-LE-03.01` for a finding with `osps_control="OSPS-LE-03.01"`.

### 10. Worktrees page surfaces OSS-prep worktrees (`tests/integration/test_cr_00019_worktrees_page.py`)

- Create an OSS-prep worktree at `{working_dir}/.worktrees/oss-prep-42/`.
- GET `/system/worktrees` includes it with an "OSS prep" label.
- Agent worktrees (if any) still render in their existing slot.

### 10b. Publish regression (AC15) — `tests/integration/test_cr_00019_publish_regression.py`

AC15 requires the Publish flow to be **byte-for-byte unchanged** by this CR. Add a dedicated regression test file with these assertions:

- POST `/project/{id}/oss/publish` still accepts its existing body shape (no JSON-body break, no `checks` field required).
- A publish job still uses `/tmp/` for its worktree (NOT `.worktrees/oss-prep-*`) — spot-check the worktree path on the created job row, or assert the `_run_worktree` branch for `kind=publish` still force-removes on exit.
- On clean exit, a publish job transitions directly to `status=complete` — it **does NOT** enter `awaiting_review` (the new state applies only to `kind=prepare`).
- The concurrency gating for Publish is unchanged: a running `publish` does not block a `prepare`, and vice versa (the new `_active_prepare_job` filter is scoped to `kind=prepare` only).
- No `base_sha` / `branch_name` / `commit_sha` / `files_changed_summary` columns are written for a publish job (they remain NULL).

These assertions are intentionally narrow — they fence off the publish path so future regressions surface loudly. Do not re-assert publish's full behavior; that's covered by existing `test_oss_dashboard_*` tests.

### 11. Existing tests touched

Grep for tests that POST to `/oss/prepare` without a body, or expect findings without a `rationale` field. Update them:
- `tests/integration/test_oss_dashboard_routes.py`
- `tests/integration/test_oss_scanner.py`
- `tests/integration/test_oss_cli.py`
- `tests/integration/test_oss_dashboard_*.py` (multiple)

For any test that breaks because of the JSON body / rationale field / awaiting_review changes, adapt the test to the new contract (don't delete the assertion — move it forward).

## Project Conventions

Read `tests/CLAUDE.md`:
- Testcontainers only. `postgresql+psycopg://` URL replacement.
- `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()`.
- Never `importlib.reload(orch.config)` — use `monkeypatch.delenv()`.
- `DaemonEvent.metadata` is `event_metadata` in Python.
- Append-only tables: never UPDATE `step_runs`, `fix_cycles`, `daemon_events`, `test_runs`, `project_doc_versions`.

Naming: `test_cr_00019_<topic>.py`. Fixtures reuse existing patterns (see `conftest.py` for `db_session`, `tmp_project_repo`, etc.).

## TDD Requirement

Every test must fail on pre-change code (verify by checking out main without CR-00019 patches) and pass on post-change code. If any test passes on main, it's not testing the CR — rewrite it.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — zero failures.
2. `make test-integration` — zero failures (be patient; this is slow).
3. `make lint` — clean.
4. `uv run mypy orch/ dashboard/` — clean.
5. Every AC from the design doc (AC1 through AC15) has at least one passing test you can point at.

## Subagent Result Contract

```json
{
  "step": "S11",
  "agent": "tests-impl",
  "work_item": "CR-00019",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/integration/test_cr_00019_migration.py",
    "tests/unit/test_cr_00019_skill.py",
    "tests/integration/test_cr_00019_cli.py",
    "tests/integration/test_cr_00019_worker.py",
    "tests/integration/test_cr_00019_accept.py",
    "tests/integration/test_cr_00019_discard.py",
    "tests/integration/test_cr_00019_concurrency.py",
    "tests/integration/test_cr_00019_stale_ui.py",
    "tests/integration/test_cr_00019_oss_template.py",
    "tests/integration/test_cr_00019_worktrees_page.py",
    "tests/integration/test_cr_00019_publish_regression.py",
    "... any updated existing tests"
  ],
  "tests_passed": true,
  "test_summary": "X unit, Y integration, 0 failed",
  "blockers": [],
  "notes": "AC → test-file mapping table"
}
```
