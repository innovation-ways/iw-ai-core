# CR-00081_S01_Tests_prompt

**Work Item**: CR-00081 -- Strengthen the 78 highest-priority assertion-scanner baseline entries (71 no-assert + 7 mock-only)
**Step**: S01
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

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This CR adds **no** migrations. If your work seems to need one, you have
gone outside scope — stop and raise a blocker.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — for the current step list, status, prompt paths, gate commands, etc., prefer `uv run iw item-status CR-00081 --json`. The `workflow-manifest.json` file is a design-time snapshot and may be out of date (CR-00023).
- `ai-dev/active/CR-00081/CR-00081_CR_Design.md` -- **Source of truth** for scope, ACs, and the categorical split. Read first.
- `ai-dev/active/CR-00081/CR-00081_Functional.md` -- Human-facing summary.
- `tests/assertion_free_baseline.txt` -- The baseline list. Your in-scope set is exactly the lines tagged `# no-assert` (71 entries). Do NOT touch this file in S01 — S02 owns the rewrite.
- `scripts/check_test_assertions.py` -- The scanner. Read it to understand how it categorises tests (the four categories: `no-assert`, `tautology`, `mock-only`, `broad-raises`). Useful when deciding whether to STRENGTHEN/DELETE/CONVERT.
- `skills/iw-ai-core-testing/SKILL.md` -- The canonical rules for what a "good" assertion looks like. §0 (mutation-test heuristic), §2 (assertion-strength rules), §8 (assertion-scanner section). Read before writing a single assertion.
- `tests/CLAUDE.md` -- The testing rules (testcontainer-only, `monkeypatch.delenv`, FTS DDL, `event_metadata`, per-worktree-DB caveats, pytest-randomly default-on).
- `CLAUDE.md` -- Project-wide rules.

## Output Files

- `ai-dev/active/CR-00081/reports/CR-00081_S01_Tests_report.md` -- Step report

## Context

You are implementing **S01 of CR-00081** — strengthen the 71 `no-assert` entries in `tests/assertion_free_baseline.txt`. These are tests that today contain zero `assert …` statements; they cannot fail for a behaviour reason. The CR's goal is to remove all 78 worst entries (71 no-assert + 7 mock-only) from the baseline; this step owns the 71 no-assert half. S02 owns the 7 mock-only entries, the baseline rewrite, and the tracker update.

**Read `ai-dev/active/CR-00081/CR-00081_CR_Design.md` first.** Its *Current Behavior*, *Desired Behavior*, *Acceptance Criteria* (AC1–AC6), and *Notes* sections are the source of truth — especially the Notes section's "Risk: a strengthening surfaces a real bug" and "Risk: a strengthening becomes a tautology in disguise" guidance.

## Requirements

Do these in order. Deliverable 0 is your RED dump; deliverables 1–3 are the fixes; deliverable 4 is the targeted verification.

### 0. RED — dump the 71 in-scope entries

Capture the exact in-scope list verbatim (this is your `tdd_red_evidence`):

```bash
grep '# no-assert$' tests/assertion_free_baseline.txt
```

Count must equal **71**. If the count differs, STOP and raise a blocker — the baseline state has drifted since this CR was written, and the operator needs to triage.

Each line has the form `tests/<rel/path>::<test_name> # no-assert`. These are by construction tests that cannot currently fail for behaviour reasons — your job is to make them able to fail.

### 1. STRENGTHEN (preferred action)

For each in-scope entry, the default action is STRENGTHEN: open the test body, add at least one real, specific, behaviour-pinning assertion that would fail if the production code line the test ostensibly covers regressed. Apply the mutation-test heuristic from `skills/iw-ai-core-testing/SKILL.md` §0: *if I deleted (or inverted) the production code line this test covers, would the test go red?* If the answer is no, your assertion isn't strong enough — strengthen it.

**Forbidden assertions** (the reviewer will reject any of these):

- `assert True` / `assert 1 == 1` / `assert obj is obj` / `assert <constant> == <constant>`
- `assert len(x) >= 0` (always true for sequences)
- `assert isinstance(x, <statically-known-type>)` (when the return type is annotated and the constructor literally returns that type)
- `mock.assert_called*` as the **only** assertion (that's a `mock-only` test in disguise — handle as in §3 below)
- `assert x is not None` when `x` is constructed unconditionally in the test setup

**Good assertions** (examples — adapt to your test):

- `assert result.status == "completed"` (specific literal)
- `assert rows[0].batch_id == batch.id` (specific DB-row column value)
- `assert caplog.records[-1].levelname == "ERROR"` and `assert "stale job" in caplog.records[-1].message`
- `with pytest.raises(ValueError, match=r"^expected: \d+ got: \d+$"):` (regex on exception message)
- `assert response.status_code == 422` and `assert response.json()["detail"][0]["loc"] == ["body", "name"]`

### 2. DELETE (use sparingly)

Permitted only when: (a) the test is provably checking nothing of value AND (b) the surface is already covered by another existing test. For every DELETE, the S01 report MUST record one line of the form:

```
DELETE tests/<path>::<test_name> — covered by tests/<other_path>::<other_test_name> (one-line reason)
```

Without a named covering test, the deletion is rejected at S03 review. If no covering test exists, STRENGTHEN the test instead (default action) — even a thin strengthening is better than removing the test.

### 3. CONVERT (rare for `no-assert`)

If you discover an entry tagged `# no-assert` that is actually a mock-only test in disguise (the scanner classifies based on AST — sometimes it categorises as `no-assert` when the only "assertion" is via a non-standard mock helper), rewrite it to assert on a real observable (return value, DB row, or log line via `caplog`). The mock may stay for isolation but cannot be the only check. Note the conversion in the S01 report.

### 4. Targeted verification

After each strengthening/conversion, run the targeted test to confirm it passes WITH the new assertion:

```bash
uv run pytest tests/<modified_file>::<test_name> -v
```

**Do NOT** run the full unit or integration suite — those are S10/S11's job. Running them here will time out this step and waste budget (see I-00073/S03 post-mortem).

**Do NOT** re-run the scanner here — that's S02's job. If you do, you'll re-write the baseline without S02's tracker edits and S04 will flag the mismatch.

## Hard scope rules

- **Allowed paths**: `tests/**` only. NOT `tests/assertion_free_baseline.txt` (S02's scope). NOT `ai-dev/work/TESTS_ENHANCEMENT.md` (S02's scope).
- **NO production code edits** under `orch/`, `dashboard/`, `executor/`, `scripts/`, `bin/`, `templates/`, `skills/`, `.claude/skills/`, `.github/`. If a strengthening *requires* a production-code change (the production code lacks an observable to assert on), DELETE the test (since the surface has no observable) AND raise a blocker so the operator can decide whether to file a separate Feature/CR to add the observable. Do not silently expand scope.
- **NO Alembic migrations.** None expected.
- **DO NOT touch** the 7 `mock-only` entries — S02 owns those.
- **DO NOT touch** any of the 548 `tautology` entries — they are explicitly out of scope for this CR.

## If a strengthening fails against current main

If you write what you believe is a correct assertion and the targeted test goes red against current `main`'s production code, you have surfaced a real bug. Procedure:

1. Confirm the failure is a real bug, not a fixture/scaffolding issue (re-run with `-vv --tb=long` and read carefully).
2. Raise a blocker in the report describing the bug (file/line, expected vs actual, suspected root cause).
3. Keep the strengthening AND add `@pytest.mark.xfail(strict=False, reason="<bug summary; will be filed as Incident>")` so the gate stays green while the operator triages.

**Do NOT weaken the assertion to "make it pass" — that defeats the entire CR.**

## Project Conventions

Read the project's `CLAUDE.md` for project-wide rules. Read `tests/CLAUDE.md` for testing rules. Read `skills/iw-ai-core-testing/SKILL.md` for the canonical assertion-strength rules — this is the source of truth for what a "good" assertion looks like.

## TDD Requirement

This step is unusual because it adds assertions to tests that lack them. The TDD-RED evidence is the scanner's pre-edit dump (deliverable 0) — the 71 entries themselves are by construction tests that cannot fail. The TDD-GREEN evidence is the targeted `uv run pytest tests/<file>::<test> -v` run after each strengthening: the test now passes with a real assertion (not before, when there was no assertion to evaluate).

Record `tdd_red_evidence` in the report as: the deliverable-0 grep output (the 71-entry list) PLUS, for one representative strengthening, the literal assertion line you added and a brief argument for why it would fail against pre-change production code if the covered line were regressed.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, you MUST run these in order and fix any issues they report:

1. **`make format`** — auto-fixes formatting drift on the test files you touched. If it reformats files, inspect the diff and re-stage; do NOT skip.
2. **`make typecheck`** — must report zero errors involving the test files you touched. Errors elsewhere are pre-existing — note them but do not ignore your own.
3. **`make lint`** — must report zero errors on the files you touched.

If a tool isn't available in your worktree, STOP and raise a blocker — do not silently skip.

In your Subagent Result Contract, populate the `preflight` object recording the result of each command.

## Test Verification (NON-NEGOTIABLE)

After implementation, verify your changes — but **DO NOT run the full test suite**. Full-suite execution is owned by S10/S11/S12.

- For each modified test file, run only that file's test:
  ```bash
  uv run pytest tests/<modified_file>::<test_name> -v
  ```
- Run lint + typecheck on touched files.
- Do NOT report `tests_passed: true` unless ALL targeted runs pass with zero failures (other than any xfail-pinned ones from the "strengthening surfaced a bug" path).

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "tests-impl",
  "work_item": "CR-00081",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/<file_a>.py",
    "tests/<file_b>.py",
    "…"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "<N targeted tests passed, 0 failed>",
  "tdd_red_evidence": "<71-line grep output of '# no-assert$' baseline entries> // PLUS for one representative strengthening: '<assertion line>' — would fail against pre-change production code at <file>:<line> if the covered line were regressed",
  "blockers": [],
  "notes": "<strengthen/delete/convert split (e.g. 65 STRENGTHEN, 4 DELETE, 2 CONVERT); any DELETE entries listed as 'DELETE <path>::<test> — covered by <other_path>::<other_test> (reason)'; any xfail-pinned strengthenings that surfaced real bugs>"
}
```

Notes:
- `tdd_red_evidence` is required. See the "TDD Requirement" section above for what to record.
- `notes` MUST include: (a) the strengthen/delete/convert split (counts add to 71); (b) every DELETE line in the prescribed format; (c) any xfail-pinned strengthenings with the suspected bug summary.
- `completion_status`: `complete` if all 71 entries are addressed and targeted tests pass; `partial` if some entries remain (then S02 will not be unblocked — raise a blocker); `blocked` if you hit a procedural issue (e.g. baseline drift).
