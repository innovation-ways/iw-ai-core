# CR-00081_S02_Tests_prompt

**Work Item**: CR-00081 -- Strengthen the 78 highest-priority assertion-scanner baseline entries (71 no-assert + 7 mock-only)
**Step**: S02
**Agent**: tests-impl

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

  1. Testcontainers spun up by pytest fixtures.
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets.

If your task seems to require a prohibited command, STOP and raise a blocker.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This CR adds **no** migrations. If your work seems to need one, you have gone outside scope — stop and raise a blocker.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00081 --json`.
- `ai-dev/active/CR-00081/CR-00081_CR_Design.md` -- **Source of truth.** Read first.
- `ai-dev/active/CR-00081/CR-00081_Functional.md` -- Human-facing summary.
- `ai-dev/active/CR-00081/reports/CR-00081_S01_Tests_report.md` -- S01's report; read its `notes` (strengthen/delete/convert split) and verify it says all 71 no-assert entries are addressed before you start.
- `tests/assertion_free_baseline.txt` -- Baseline. Your in-scope set is exactly the lines tagged `# mock-only` (7 entries). You also OWN the baseline rewrite at the end of this step.
- `scripts/check_test_assertions.py` -- The scanner. You will invoke it to rewrite the baseline.
- `skills/iw-ai-core-testing/SKILL.md` -- §0 mutation-test heuristic, §2 assertion-strength rules, §8 scanner section. Read before writing assertions.
- `tests/CLAUDE.md` -- Testing rules.
- `ai-dev/work/TESTS_ENHANCEMENT.md` -- §5 row `P1-CR-A-followup`, v1.3 header status block, §11 changelog. You will update all three.
- `CLAUDE.md` -- Project-wide rules.

## Output Files

- `ai-dev/active/CR-00081/reports/CR-00081_S02_Tests_report.md` -- Step report

## Context

You are implementing **S02 of CR-00081** — strengthen the 7 `mock-only` baseline entries, re-run the scanner to shrink the baseline by exactly the 78 entries this CR addresses (71 from S01 + 7 from S02), verify the result, and update the plan tracker.

**Pre-condition**: S01 has already completed. If S01's report shows `completion_status` other than `complete`, or `notes` does not record all 71 no-assert entries as addressed, STOP and raise a blocker — the baseline rewrite must not run until both halves of the cleanup are in.

**Read `ai-dev/active/CR-00081/CR-00081_CR_Design.md` first.** AC1, AC2, AC3, AC4, AC5 all bear on this step.

## Requirements

### 0. Pre-flight: confirm S01 is complete

```bash
uv run iw item-status CR-00081 --json | jq '.steps[] | select(.step=="S01") | {status, completion_status}'
```

If S01 is not `complete`, raise a blocker. Do not proceed.

### 1. RED — dump the 7 in-scope entries

```bash
grep '# mock-only$' tests/assertion_free_baseline.txt
```

Count must equal **7**. If the count differs, STOP and raise a blocker — the baseline has drifted.

Record the 7-entry list verbatim in the report as part of `tdd_red_evidence`.

### 2. CONVERT (default action for mock-only)

For each of the 7 entries, the default action is CONVERT: open the test, rewrite it so it asserts on a real observable (return value, DB row, log line via `caplog`) instead of only `mock.assert_called*` / `mock.call_args`. The mock may stay to isolate the unit but must no longer be the only assertion.

**Forbidden conversions** (S04 will reject):

- Replacing one `mock.assert_called*` with another (no-op conversion).
- `assert True` / `assert obj is obj` / `assert <constant> == <constant>` / `assert len(x) >= 0` / `assert isinstance(x, <statically-known-type>)`.
- `assert x is not None` when `x` is constructed unconditionally in the test setup.

**Good conversions**:

- Replace `service_mock.publish.assert_called_once_with(msg)` with `assert published_messages == [msg]` (assert on the queue's state, not the mock call).
- Replace `db_mock.commit.assert_called()` with `assert db_session.query(WorkItem).filter_by(id=item.id).one().status == "approved"` (assert on the DB row, not the commit call).
- Replace `logger_mock.info.assert_called_with(...)` with a `caplog`-based check: `assert any(r.message == "expected" for r in caplog.records)`.

### 3. DELETE (use sparingly)

Permitted only when: (a) the test is provably checking nothing of value AND (b) the surface is already covered by another existing test AND (c) the production code legitimately has no observable side-effect (rare — most mocked surfaces have an observable somewhere). For every DELETE, record one line in the report:

```
DELETE tests/<path>::<test_name> — covered by tests/<other>::<other_test> (one-line reason)
```

If no covering test exists, CONVERT instead (default action).

### 4. Targeted verification per conversion

After each conversion, run the targeted test:

```bash
uv run pytest tests/<modified_file>::<test_name> -v
```

Do NOT run the full unit/integration suite. That's S10/S11.

### 5. Rewrite the baseline

After all 7 mock-only entries are addressed, invoke the scanner to re-write the baseline. This is the load-bearing step — the scanner re-scans `tests/` and replaces `tests/assertion_free_baseline.txt` with only the entries that *still* match.

```bash
uv run python scripts/check_test_assertions.py --write-baseline tests/assertion_free_baseline.txt tests/
```

### 6. Verify the baseline state

Verify all three counts in order. ALL three must match:

```bash
grep -c '# no-assert$' tests/assertion_free_baseline.txt   # MUST be 0
grep -c '# mock-only$' tests/assertion_free_baseline.txt   # MUST be 0
grep -c '# tautology$' tests/assertion_free_baseline.txt   # MUST be 548 (untouched — out of scope)
```

If `# no-assert$` is non-zero, S01 missed entries (S01 should have caught this — re-open the blocker). If `# mock-only$` is non-zero, your conversion missed entries (this step). If `# tautology$` is NOT 548, you have touched out-of-scope tests AND/OR the scanner detected a regression in the tautology bucket — STOP and raise a blocker; do not "fix" by editing tautology tests (those are deferred to future CRs).

Then verify the gate passes against the shrunken baseline:

```bash
make test-assertions
```

Must exit 0.

### 7. Update the plan tracker

Edit `ai-dev/work/TESTS_ENHANCEMENT.md` to record the cleanup. Three locations:

**(a) §5 row `P1-CR-A-followup`** — update the row's description to record: "78 of 626 baseline entries strengthened in this CR (CR-00081, 2026-05-24); remaining 548 `tautology` entries deferred to future per-module CRs."

**(b) v1.3 header status block** — find the line that reads (verbatim, with current counts):

> P1-CR-A-followup — incremental scrub of the assertion baseline (now **626 entries**: 71 no-assert / 7 mock-only / 548 tautology; commit `d6cc446d` strengthened 33 on 2026-05-21)

and update to:

> P1-CR-A-followup — incremental scrub of the assertion baseline (now **~548 entries**: 0 no-assert / 0 mock-only / 548 tautology; CR-00081 strengthened 78 on 2026-05-24, commit `d6cc446d` strengthened 33 on 2026-05-21)

(adjust the prose to match the surrounding sentence structure — the load-bearing facts are the new counts and the CR-00081/2026-05-24 attribution).

**(c) §11 changelog** — add a new entry dated **2026-05-24** at the top of the changelog list:

```
- **2026-05-24** — **CR-00081 merged (P1-CR-A-followup, 78-entry baseline scrub).** Strengthened the 71 `no-assert` and 7 `mock-only` entries in `tests/assertion_free_baseline.txt`. Strengthen/delete/convert split: <fill from S01 + S02 reports>. The 548 `tautology` entries stay in the baseline, deferred to future per-module CRs. Baseline count: **626 → ~548** (-78). Forward link from CR-00046's 2026-05-12 entry (the scanner + initial baseline).
```

Fill the strengthen/delete/convert split from S01's `notes` + S02's own conversions. The line MUST appear in the changelog body, dated 2026-05-24.

## Hard scope rules

- **Allowed paths**: `tests/**`, `tests/assertion_free_baseline.txt`, `ai-dev/work/TESTS_ENHANCEMENT.md`. NO other paths.
- **NO production code edits** under `orch/`, `dashboard/`, `executor/`, `scripts/`, `bin/`, `templates/`, `skills/`, `.claude/skills/`, `.github/`. If a conversion requires a production-code change to expose an observable, DELETE the test AND raise a blocker — do not silently expand scope.
- **NO Alembic migrations.**
- **NO touching the 548 `tautology` entries** — out of scope.
- **NO touching the 71 `no-assert` entries** — S01 owns those; you should not see any of them on your edit list.

## If a conversion fails against current main

Same procedure as S01's: confirm real bug, raise blocker in report, keep the conversion AND add `@pytest.mark.xfail(strict=False, reason="<bug>; will be filed as Incident")`. Do NOT weaken the assertion.

## Project Conventions

Read `CLAUDE.md`, `tests/CLAUDE.md`, `skills/iw-ai-core-testing/SKILL.md` (§0, §2, §8).

## TDD Requirement

Same shape as S01: the RED is the scanner's pre-edit dump (deliverable 1, the 7 mock-only entries — they cannot fail for behaviour reasons because they only check the test's own mock scaffolding); the GREEN is the targeted pytest run after each conversion.

Record `tdd_red_evidence` as: the deliverable-1 grep output (7 entries) PLUS, for one representative conversion, the literal observable-assertion line you added and a brief argument for why it would fail against pre-change production code if the covered behaviour regressed.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`:

1. **`make format`** — auto-fix formatting drift on touched files.
2. **`make typecheck`** — zero errors on touched files.
3. **`make lint`** — zero errors on touched files.

Populate `preflight` in the result contract.

## Test Verification (NON-NEGOTIABLE)

Targeted runs only:

```bash
uv run pytest tests/<modified_file>::<test_name> -v
```

PLUS the assertion-gate verification:

```bash
make test-assertions
```

Do NOT run the full unit/integration suite — S10/S11 own those.

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "tests-impl",
  "work_item": "CR-00081",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/<file_a>.py",
    "tests/<file_b>.py",
    "…",
    "tests/assertion_free_baseline.txt",
    "ai-dev/work/TESTS_ENHANCEMENT.md"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "<N targeted tests passed, 0 failed>; make test-assertions: ok",
  "tdd_red_evidence": "<7-line grep output of '# mock-only$' baseline entries> // PLUS for one representative conversion: '<observable assertion line>' replaces '<old mock assertion line>' — would fail against pre-change production code at <file>:<line> if the covered behaviour regressed",
  "blockers": [],
  "notes": "<convert/delete split (e.g. 6 CONVERT, 1 DELETE); any DELETE entries in the prescribed format; baseline verification: no-assert=0, mock-only=0, tautology=548; tracker edits applied to §5 row + v1.3 header + §11 changelog with 2026-05-24 date>"
}
```

Notes:
- `tdd_red_evidence` is required.
- `notes` MUST include: (a) the convert/delete split (counts add to 7); (b) the post-scanner baseline verification counts; (c) confirmation the tracker §5 + header + §11 edits all carry CR-00081 + 2026-05-24.
- `completion_status: complete` requires: all 7 conversions done; baseline rewritten with 0/0/548; `make test-assertions` exits 0; tracker updated in three locations.
