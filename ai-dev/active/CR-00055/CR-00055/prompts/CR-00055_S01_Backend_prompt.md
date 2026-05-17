# CR-00055_S01_Backend_prompt

**Work Item**: CR-00055 -- Re-enable `pytest-randomly` by default via per-test PostgreSQL template-clone (P1-CR-C-followup-randomly-v2)
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived infrastructure containers are outside your scope. Touching them can cause multi-hour outages and data loss (see the 2026-04-22 incident in `docs/IW_AI_Core_DB_Setup.md`).

Allowed exceptions:
  1. Testcontainers spun up by pytest fixtures (they self-label and self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which commands are safe.

If your task seems to require a prohibited command, STOP and raise a blocker. Do not work around this rule.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This CR adds **no** Alembic migrations. If your work seems to need one, you have gone outside scope — STOP and raise a blocker.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- **Runtime step state** — for the current step list, status, prompt paths, gate commands, etc., prefer `uv run iw item-status CR-00055 --json`. The `workflow-manifest.json` file is a design-time snapshot and may be out of date (CR-00023).
- `ai-dev/active/CR-00055/CR-00055_CR_Design.md` -- **Source of truth** for scope, ACs, and the failure list. Read first.
- `ai-dev/active/CR-00055/CR-00055_Functional.md` -- Human-facing summary.
- **`docs/research/R-00077-pytest-randomly-isolation-strategy.md`** — Full design rationale. Appendix A contains the implementation outline this prompt follows.
- **`spike/pgtestdbpy-isolation` branch** — the spike that empirically validated this strategy (2026-05-16, 4 seeds all green at ~10–13 min wall-clock per sweep). **You should `git diff main..spike/pgtestdbpy-isolation` to crib the exact working code** — this is faster and lower-risk than re-implementing from the design. The spike covers every implementation file in this CR's scope (config + the 6 test-file edits). The spike does NOT cover the doc flips, the comment-block rewrite in pyproject.toml, the TESTS_ENHANCEMENT.md updates, or `iw sync-skills --force` — those you write yourself.
- `ai-dev/work/TESTS_ENHANCEMENT.md` §5 (`P1-CR-C-followup-randomly` row), item 1.4 row, and §11 changelog (CR-00048 fallback + CR-00049 cancellation).
- `tests/CLAUDE.md` §7 — current opt-in recipe + cleanup contract (you will flip this).
- `docs/IW_AI_Core_Testing_Strategy.md` §3 (pytest-randomly subsection) and §9 row "Test-order randomisation" — both currently ⚠️; you will flip to ✅.
- `skills/iw-ai-core-testing/SKILL.md` §2 — current opt-in recipe; will be flipped.
- `pyproject.toml` lines around `[tool.pytest.ini_options]` (`addopts` contains `-p no:randomly` today) and `[dependency-groups] dev` (where you'll add `pgtestdbpy`).
- `tests/integration/conftest.py` — the file you'll rewrite (the spike's diff is the source).
- `tests/dashboard/conftest.py` — re-exports integration fixtures (you'll add `_pgtestdb_setup` to the re-export list).
- The 5 test files that need carry-forward edits (2 class teardowns + 3 quarantines + 1 module-level autouse).
- `CLAUDE.md` for project-wide rules (testcontainer-only, `monkeypatch.delenv` over `importlib.reload`, FTS DDL, `event_metadata`).

## Output Files

- `ai-dev/active/CR-00055/reports/CR-00055_S01_Backend_report.md` -- Step report.

## Context

You are implementing **CR-00055 — Re-enable `pytest-randomly` by default**. This is the second attempt at item 1.4 cleanup (TESTS_ENHANCEMENT.md). The first attempt (CR-00049) was cancelled 2026-05-16 after exploring two designs that either left correctness gaps (savepoint-only, per-module TRUNCATE) or regressed wall-clock by 3× (per-test TRUNCATE-CASCADE).

**Read `ai-dev/active/CR-00055/CR-00055_CR_Design.md` first** — its "Current Behavior", "Desired Behavior", "Acceptance Criteria" (AC1–AC6), "Impacted Paths", and "Notes" sections are the source of truth. Then read `docs/research/R-00077-pytest-randomly-isolation-strategy.md` for the underlying rationale.

The strategy: per-test PostgreSQL template-clone via `pgtestdbpy>=0.0.1`. Each test gets its own fresh database in ~25 ms via `CREATE DATABASE … TEMPLATE …` (with a 1-line override to use the WAL_LOG strategy instead of the library's hardcoded FILE_COPY — the perf-cliff hinge). The clone URL is exported via `IW_CORE_DB_*` env vars so `iw` CLI subprocesses inherit the isolated DB and their commits cannot leak.

This is the only implementation step in this CR. No Database / API / Frontend / Pipeline / Template steps. Scope is tests + configs + docs only.

## Requirements

Do these in order. Deliverable 0 is your RED reproduction; deliverables 1–10 are the fix; deliverable 11 is the multi-seed sweep.

### 0. RED — capture the unfixed-state seed-12345 sweep counts

Before any code change, run the design's reproduction recipe **once** to capture `tdd_red_evidence`:

```bash
uv run pytest tests/integration/ tests/dashboard/ --ignore=tests/dashboard/browser \
  -p randomly --randomly-seed=12345 -q --no-cov 2>&1 | tail -10
```

Expected (from the design's Current Behavior): ~271 failed + ~12 errors in ~12 min. **This is your `tdd_red_evidence` and is the only "full sweep" before the GREEN verification at the end** — do NOT iterate on this run; the failure pattern is well-understood (see the design's Current Behavior section and `/tmp/cr49_seed12345_v3.log` if available locally).

### 1. Crib the working implementation from the spike branch

```bash
git fetch origin  # or the local refs
git diff main..spike/pgtestdbpy-isolation -- \
  pyproject.toml \
  uv.lock \
  tests/integration/conftest.py \
  tests/dashboard/conftest.py \
  tests/integration/test_oss_migration.py \
  tests/integration/test_project_oss_job_migration.py \
  tests/integration/test_db_identity_integration.py \
  tests/integration/test_pending_migration_log_migration.py \
  tests/integration/db/test_i_00062_migration.py
```

The spike diff is the exact working code. Apply each file's diff to your worktree. Read each diff carefully — every line is there for a reason and was empirically validated by the spike's 4-seed green sweep on 2026-05-16. In particular, pay attention to:

- **The WAL_LOG override on `pgtestdbpy.QRY_DB_CLONE`** (in `tests/integration/conftest.py`, inside `_pgtestdb_setup` BEFORE entering `pgtestdbpy.templates()`). The library hardcodes `STRATEGY=FILE_COPY` in its query template; on this codebase's schema FILE_COPY is **~310 ms per clone** while WAL_LOG is **~25 ms per clone**. The difference is the gap between a ~28-min sweep and a ~10-min sweep. If you skip this override, S09 will likely timeout and the CR will burn fix-cycles. The override is one line: `pgtestdbpy.QRY_DB_CLONE = 'CREATE DATABASE "{db_name}" WITH TEMPLATE "{template}" OWNER "{user}"'` (drops the `STRATEGY=FILE_COPY` suffix).
- **The `_pgtestdb_setup` re-export in `tests/dashboard/conftest.py`** alongside `_db_test_connection`, `db_engine`, `db_session`, `db_session_factory`, `pg_container`, `test_project`. Without this re-export every dashboard test fails with `fixture '_pgtestdb_setup' not found` (the spike's v1 sweep had 549 such errors before the re-export was added).
- **The module-level autouse `_restore_iw_core_instance_row`** in `tests/integration/test_db_identity_integration.py`. This is a NEW fixture, not just a carry-forward. It mirrors the existing `TestDashboardHealthzIdentity::ensure_instance_row` class fixture but at module scope so it covers `TestDaemonStartupGate` and `TestMigrationRoundtrip` too.

### 2. Add `pgtestdbpy>=0.0.1` to `[dependency-groups] dev` in `pyproject.toml`

Regenerate `uv.lock` with `uv lock`. Commit `uv.lock` to the worktree.

### 3. Rewrite `tests/integration/conftest.py` fixture chain (apply the spike's diff)

The spike's diff for this file is the authoritative reference. Briefly: add `_migrate_template(url: str) -> None` (moves the existing OSS enums + alembic upgrade + `Base.metadata.create_all` work into a callable that runs once against the template), add session-scoped `_pgtestdb_setup(pg_container)` (overrides `QRY_DB_CLONE` for WAL_LOG, wraps `pgtestdbpy.templates(config, migrator)` and yields `(config, migrator)`), change `db_engine` from session-scoped to function-scoped (clones via `pgtestdbpy.clone`, monkeypatches `IW_CORE_DB_*`, yields the engine), simplify `_db_test_connection` (just `connection = db_engine.connect(); yield connection; connection.close()` — the outer transaction is unnecessary now). Keep `db_session`, `db_session_factory`, `test_project`, `cli_get_session` API byte-for-byte (the spike does not change them).

Add the `pgtestdbpy` and `urlparse` imports together with their first usage in the same Edit — the project's formatter strips unused imports if added alone (verified during the spike).

### 4. Re-export `_pgtestdb_setup` from `tests/dashboard/conftest.py`

One-line addition to the existing `from tests.integration.conftest import (...)` block. Apply the spike's diff. This is NON-NEGOTIABLE — without it, the dashboard suite is unrunnable.

### 5. Add 2 class teardowns

- `tests/integration/test_oss_migration.py::TestOssMigrationDowngrade::test_downgrade_drops_tables` — after the existing `DOWNGRADE_SQL` assertion at the end of the test, re-apply `MIGRATION_SQL` so siblings find the schema migrated. The spike's diff shows the exact 3-line addition with a `# CR-00049 / R-00077:` comment — update the comment to reference `# CR-00055 / R-00077:`.
- `tests/integration/test_project_oss_job_migration.py::TestProjectOssJobMigrationDowngrade::test_downgrade_drops_table` — same pattern.

### 6. Add 1 module-level autouse fixture

`tests/integration/test_db_identity_integration.py` — add `_restore_iw_core_instance_row` as a module-level autouse fixture (NOT a class fixture; module-scope so it applies to every test class in the file). The spike's diff is authoritative. Update the docstring comment to `# R-00077 / CR-00055:` (the spike has `# R-00077 / CR-00055` already).

### 7. Add 3 quarantines

All with `@pytest.mark.order_dependent` + `@pytest.mark.xfail(strict=False, reason="…")` + `# NOTE(P1-CR-C-followup-randomly):` tracking comment:

- `tests/integration/test_db_identity_integration.py::TestMigrationRoundtrip::test_downgrade_drops_table_and_upgrade_recreates_with_new_uuid`
- `tests/integration/test_pending_migration_log_migration.py::test_valid_enum_values_accepted`
- `tests/integration/db/test_i_00062_migration.py::TestI00062MigrationRoundTrip::test_re_upgrade_after_downgrade`

Hard rules:
- `strict=False` is MANDATORY (these tests pass in alphabetical order; strict would xpass-fail green runs).
- `reason` strings MUST name the leak source, not just "order-dependent".
- `# NOTE(P1-CR-C-followup-randomly):` tracking comment goes inside the test body's first line.
- Do NOT re-register the `order_dependent` marker — it's already in `pyproject.toml [tool.pytest.ini_options] markers` from CR-00048.

### 8. Remove `-p no:randomly` from `pyproject.toml [tool.pytest.ini_options] addopts`

Rewrite the explanatory comment block above `addopts` to describe default-on behaviour (reproduce / disable recipes); preserve the CR-00048 fallback as a brief "Earlier fallback (CR-00048)" historical note (one paragraph). **Keep `--strict-markers`** in addopts.

### 9. Flip 4 doc locations to default-on

Each location should describe the **mechanism** (per-test `CREATE DATABASE … TEMPLATE …` via `pgtestdbpy` + `IW_CORE_DB_*` monkeypatch for subprocess inheritance) and preserve the CR-00048 fallback as a short historical note:

- `tests/CLAUDE.md` §7 ("pytest-randomly — test-order randomisation")
- `docs/IW_AI_Core_Testing_Strategy.md` §3 subsection ("pytest-randomly — test-order randomisation (...)" → rename and rewrite for CR-00055)
- `docs/IW_AI_Core_Testing_Strategy.md` §9 row "Test-order randomisation (`pytest-randomly`)" — flip ⚠️ to ✅; new prefix `"✅ (CR-00055, 2026-05-16) — default-on; integration suite robust to randomisation via per-test PostgreSQL template-clone..."`
- `skills/iw-ai-core-testing/SKILL.md` §2 ("pytest-randomly — test-order randomisation (currently OFF-by-default)" → rename and rewrite)

### 10. Sync the skill

```bash
uv run iw sync-skills --force iw-ai-core-testing
```

The `--force` is required because `iw-ai-core-testing` is registered as a project override on iw-ai-core itself. Verify with `diff -q skills/iw-ai-core-testing/SKILL.md .claude/skills/iw-ai-core-testing/SKILL.md` — output must be empty.

### 11. Update `ai-dev/work/TESTS_ENHANCEMENT.md`

- **§5 grouping table** — `P1-CR-C-followup-randomly` row → **DONE (CR-00055, 2026-05-16)** with the strategy summary (template-clone via pgtestdbpy + WAL_LOG override + 2 teardowns + 1 autouse + 3 quarantines) and the 4-seed verification numbers.
- **Item 1.4 row** — flip from `⚠️ PARTIAL (CR-00048, 2026-05-13) — fallback used` to `✅ DONE (CR-00055, 2026-05-16)` with a one-liner naming what changed.
- **§11 changelog** — new entry dated 2026-05-16. Format: "**2026-05-16** — **Item 1.4 completed → CR-00055 (P1-CR-C-followup-randomly-v2).** `-p no:randomly` removed from pyproject.toml addopts. Strategy: per-test PostgreSQL template-clone via `pgtestdbpy>=0.0.1` (with a 1-line `QRY_DB_CLONE` override to use WAL_LOG strategy instead of the library's hardcoded `STRATEGY=FILE_COPY` — ~10x faster on this codebase's schema). Each test gets its own ephemeral DB in ~25 ms via `CREATE DATABASE … TEMPLATE …`; `IW_CORE_DB_*` env vars are monkeypatched per-test so `iw` CLI subprocesses inherit the isolated clone. 1 new module-level autouse fixture in test_db_identity_integration.py (_restore_iw_core_instance_row), 2 class teardowns (TestOssMigrationDowngrade + TestProjectOssJobMigrationDowngrade re-apply MIGRATION_SQL), 3 quarantines on `migrated_engine`-bound tests. Verified green across seeds 12345/67890/11111/42424. Wall-clock impact on `make test-integration`: 10m54s on the reference dev box (vs ~10 min unrandomised baseline). Docs flipped: tests/CLAUDE.md §7, strategy §3 + §9 row, skill §2 — default-on with CR-00048 fallback preserved as historical note. `iw sync-skills --force iw-ai-core-testing` ran. Item 1.4 → DONE. P1-CR-C-followup-randomly → DONE. Reference: R-00077."

### 12. GREEN — 4-seed sweep

```bash
for seed in 12345 67890 11111 42424; do
  echo "=== seed $seed ==="
  uv run pytest tests/integration/ tests/dashboard/ --ignore=tests/dashboard/browser \
    -p randomly --randomly-seed=$seed -q --no-cov 2>&1 | tail -5
done
```

End state (mandatory): **all 4 runs exit 0**. Quarantined tests show as `xfailed` or `xpassed` (strict=False, either is fine — depends on the seed's order). Expected counts per seed: `~2520 passed, ~34 skipped, ~3–6 xfailed/xpassed total, 0 failures, 0 errors`. If you see a 5th-seed offender beyond the 3 known quarantines, **stop and raise a blocker** — the strategy needs more triage and the spike did not surface that test.

**Bake `--no-cov` into the sweep** — running `--cov` 4 times in S01 is wasted work (S10 builds its own coverage). The CR-00049 daemon-launched S01 burned its 80 m budget partly on `--cov` sweeps.

Do NOT run `make check` / `make test-integration` / `make diff-coverage` / extra full-suite runs — those are S08 / S09 / S10's job.

## Scope discipline

Touch ONLY the files in the design's "Impacted Paths":

- `pyproject.toml`
- `uv.lock`
- `tests/integration/conftest.py`
- `tests/dashboard/conftest.py`
- `tests/integration/test_oss_migration.py`
- `tests/integration/test_project_oss_job_migration.py`
- `tests/integration/test_db_identity_integration.py`
- `tests/integration/test_pending_migration_log_migration.py`
- `tests/integration/db/test_i_00062_migration.py`
- `tests/CLAUDE.md`
- `docs/IW_AI_Core_Testing_Strategy.md`
- `skills/iw-ai-core-testing/SKILL.md`
- `.claude/skills/iw-ai-core-testing/SKILL.md` (re-synced)
- `ai-dev/work/TESTS_ENHANCEMENT.md`

Plus this CR's `ai-dev/active/CR-00055/**`. **No production code touched** (`orch/`, `dashboard/` outside `dashboard/conftest.py`, `executor/`). **No migrations.** **No Makefile / .github changes.**

## Project Conventions

Read the project's `CLAUDE.md` for:
- Architecture patterns and layer boundaries
- Coding conventions and naming rules
- Test organization and fixtures
- Build and run commands

Follow all rules defined there exactly. When in doubt, match existing code.

## TDD Requirement

This CR's TDD anchor is **the RED reproduction itself** — deliverable 0's failing seed-12345 sweep counts. Record the exact `pytest` invocation + the "X failed, Y errors" line as `tdd_red_evidence`. The GREEN evidence is deliverable 12's 4-seed sweep ending all-clean.

Do **not** write new behavioural tests to "prove" the fix — the existing 2 500+ tests, now passing under randomisation, are the proof.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, you MUST run these in order and fix any issues they report. Skipping any of these wastes a fix-cycle slot when the QV gate steps catch the same issue downstream:

1. **`make format`** — auto-fixes formatting drift. If it reformats files, inspect the diff and re-stage; do NOT skip.
2. **`make typecheck`** — must report zero errors involving the files you touched.
3. **`make lint`** — must report zero errors.

If a tool isn't available in your worktree, STOP and raise a blocker — do not silently skip.

In your Subagent Result Contract, populate the `preflight` object recording the result of each command:
- `"ok"` — ran cleanly, no changes / no errors
- `"fixed"` — applies to `format` only; the tool auto-fixed something
- `"skipped:<reason>"` — only if you raised a blocker explaining why

## Test Verification (NON-NEGOTIABLE)

> **Bounded exception — this is a testing-infrastructure CR.** The standard rule is "an implementation step never runs the full suite — that's the QV gates' job" (I-00073/S03 timeout lesson). CR-00055's *deliverable* is making the full integration + dashboard suite robust to `pytest-randomly` — provable only by running it under several seeds. **Deliverables 0 + 12 are explicitly allowed** to run `pytest tests/integration/ tests/dashboard/ --ignore=tests/dashboard/browser -p randomly --randomly-seed=<N> --no-cov` (1 + 4 = 5 sweeps total). Outside those two deliverables the standard rule still applies in full — no `make check`, no `make test-integration`, no `make diff-coverage`.

Scope rules:

1. **This step** — bounded multi-seed sweep allowed (deliverables 0 + 12). Plus targeted `pytest <file>` runs for any test file you edit if you want to spot-check before the full sweep.
2. Run lint and type checking on your touched files (`make lint`, `make typecheck`).
3. Do **NOT** report `tests_passed: true` unless your deliverable-12 sweep is all-green AND your targeted re-runs (if any) pass.
4. If a seed surfaces a new offender mid-sweep beyond the 3 known quarantines, **stop and raise a blocker** — the spike was definitive that 3 quarantines is enough; a 4th means something has changed in the suite since 2026-05-16.

## Subagent Result Contract

When your work is complete, report results in this JSON structure:

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "CR-00055",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "pyproject.toml",
    "uv.lock",
    "tests/integration/conftest.py",
    "tests/dashboard/conftest.py",
    "tests/integration/test_oss_migration.py",
    "tests/integration/test_project_oss_job_migration.py",
    "tests/integration/test_db_identity_integration.py",
    "tests/integration/test_pending_migration_log_migration.py",
    "tests/integration/db/test_i_00062_migration.py",
    "tests/CLAUDE.md",
    "docs/IW_AI_Core_Testing_Strategy.md",
    "skills/iw-ai-core-testing/SKILL.md",
    ".claude/skills/iw-ai-core-testing/SKILL.md",
    "ai-dev/work/TESTS_ENHANCEMENT.md"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "4-seed sweep (12345/67890/11111/42424) of tests/integration/ + tests/dashboard/ under -p randomly --no-cov: all four exit 0 (<N> passed, ~5 xfailed/xpassed total, 0 failures, 0 errors per seed). Wall-clock: ~<N> min per sweep.",
  "tdd_red_evidence": "Deliverable 0: uv run pytest tests/integration/ tests/dashboard/ --ignore=tests/dashboard/browser -p randomly --randomly-seed=12345 -q --no-cov → <N> failed + <M> errors in ~<T> min (vs ~10 min unrandomised baseline). The failure pattern matches the design's Current Behavior section (cross-module CLI-subprocess leaks + intra-module migration mutation).",
  "blockers": [],
  "notes": "Cribbed implementation from spike/pgtestdbpy-isolation per the prompt. WAL_LOG override applied. _pgtestdb_setup re-exported in tests/dashboard/conftest.py. iw sync-skills --force iw-ai-core-testing ran (.claude/ in sync). Docs flipped across tests/CLAUDE.md §7, strategy §3 + §9 row, skill §2 — default-on with CR-00048 fallback preserved as 'Earlier fallback (CR-00048)' historical note. TESTS_ENHANCEMENT.md §5 row + item 1.4 + §11 changelog all DONE (CR-00055)."
}
```

- `tdd_red_evidence`: deliverable 0's failing seed-12345 sweep counts + first line of summary. Do not write `"n/a"`.
- `completion_status`: `complete` if all 12 deliverables done + sweep all-green. `partial` if the sweep surfaced a new offender (beyond the 3 known quarantines) — stop, raise a blocker, do NOT add a 4th quarantine without operator approval (the spike was definitive). `blocked` if the spike branch is unavailable or `pgtestdbpy` install fails.
- `blockers`: List any issues that prevented full completion.
- `notes`: Counts, file paths, follow-ups filed.

## Lifecycle Commands

When you START working on this step, run:
```bash
uv run iw step-start CR-00055 --step S01
```

When you COMPLETE this step successfully:
1. Write a brief markdown report to `ai-dev/active/CR-00055/reports/CR-00055_S01_Backend_report.md` summarising:
   - What was done (deliverable-by-deliverable)
   - Files changed
   - 4-seed sweep results (numbers per seed)
   - Wall-clock per seed
   - Any issues or observations (e.g. if the WAL_LOG override required tweaking, or if a sibling test surfaced an unexpected pass)
2. Run:
```bash
mkdir -p ai-dev/active/CR-00055/reports
uv run iw step-done CR-00055 --step S01 --report ai-dev/active/CR-00055/reports/CR-00055_S01_Backend_report.md
```

If this step FAILS, run:
```bash
uv run iw step-fail CR-00055 --step S01 --reason "brief reason"
```

IMPORTANT: You MUST call step-done (with --report) or step-fail before exiting.
