# CR-00081_S05_CodeReview_Final_prompt

**Work Item**: CR-00081 -- Strengthen the 78 highest-priority assertion-scanner baseline entries (71 no-assert + 7 mock-only)
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S04

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Allowed exceptions: testcontainer pytest fixtures; read-only `docker ps`/`inspect`/`logs`; `./ai-core.sh` and `make` targets.

If your task seems to require a prohibited command, STOP and raise a blocker.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This CR adds no migrations.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00081 --json`.
- `ai-dev/active/CR-00081/CR-00081_CR_Design.md` -- Design (source of truth for ACs 1–6).
- `ai-dev/active/CR-00081/reports/CR-00081_S01_Tests_report.md`
- `ai-dev/active/CR-00081/reports/CR-00081_S02_Tests_report.md`
- `ai-dev/active/CR-00081/reports/CR-00081_S03_CodeReview_report.md`
- `ai-dev/active/CR-00081/reports/CR-00081_S04_CodeReview_report.md`
- All files listed in S01 + S02 reports' `files_changed`.
- `tests/assertion_free_baseline.txt` (post-S02 state).
- `ai-dev/work/TESTS_ENHANCEMENT.md` (post-S02 state).
- `skills/iw-ai-core-testing/SKILL.md` -- Assertion-strength benchmark.

## Output Files

- `ai-dev/active/CR-00081/reports/CR-00081_S05_CodeReview_Final_report.md` -- Final review report

## Context

You are performing the **final cross-agent review** of all implementation work for CR-00081. Per-agent reviews (S03 covered S01; S04 covered S02) have already run. Your job is to catch cross-cutting issues:

- Internal consistency between S01's and S02's reported splits and the baseline file's final counts.
- AC-level completeness across S01 + S02 (not just step-level).
- The combined diff against `main` stays inside `scope.allowed_paths`.
- The tracker edits reflect the full 78-entry cleanup, not just S02's 7.

## Read the Design Document FIRST

Read all six ACs (AC1–AC6). Each is a mandatory check.

The CR has no separately-named TDD test files (the in-scope baseline entries are themselves the deliverables) — there is no "TDD-section test file missing" risk to check.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run on the **union** of S01's + S02's `files_changed`:

```bash
make lint
make format-check
```

Classify any NEW violations as CRITICAL with `"category": "conventions"`.

## Review Checklist

### 1. AC1 — Baseline `no-assert` and `mock-only` entries fully addressed (CRITICAL if fails)

```bash
grep -c '# no-assert$' tests/assertion_free_baseline.txt   # MUST be 0
grep -c '# mock-only$' tests/assertion_free_baseline.txt   # MUST be 0
grep -c '# tautology$' tests/assertion_free_baseline.txt   # MUST be 548
```

If any of the three values is wrong, raise CRITICAL.

### 2. AC2 — Strengthened tests carry real, behaviour-pinning assertions (HIGH per violation)

Sample-based: pick **10 random** modified tests across S01's + S02's `files_changed` (mix of `no-assert` strengthenings and `mock-only` conversions). For each:

- Identify the production code line(s) the test ostensibly covers.
- Read the new assertion(s).
- Reason explicitly: *would the assertion go red if the production line were deleted or inverted?*

For at least 2 of the 10, take it one step further: if it's safe in this worktree (the change is small and easy to revert), scope-stash only the production-code hunks the test covers, re-run the test, confirm it fails, then `git stash pop`. State explicitly in the report whether you performed this optional check.

Reject (HIGH) any forbidden pattern: `assert True`, `assert obj is obj`, `assert <const> == <const>`, `assert len(x) >= 0`, `assert isinstance(x, <statically-known-type>)`, `mock.assert_called*` as the sole assertion, `assert x is not None` where `x` is unconditional.

### 3. AC3 — Every DELETE has a one-line rationale naming a real covering test (HIGH per violation)

Combine the DELETE entries listed in S01's + S02's `notes`. For each:

- Confirm the prescribed format: `DELETE tests/<path>::<test> — covered by tests/<other>::<other_test> (one-line reason)`.
- Open the named covering test and confirm it actually covers the same surface.

### 4. AC4 — Scope is tests + baseline + plan tracker only (CRITICAL if violated)

Run a diff summary against `main`:

```bash
git diff --name-only origin/main...HEAD
```

(or the equivalent against the worktree base branch). Every line must match one of:
- `tests/**`
- `tests/assertion_free_baseline.txt`
- `ai-dev/work/TESTS_ENHANCEMENT.md`
- `ai-dev/active/CR-00081/**` (workflow artefacts, reports — implicit scope)

Any other path = CRITICAL.

### 5. AC5 — Plan tracker reflects the cleanup (HIGH per missing/inconsistent location)

Re-verify the three locations in `ai-dev/work/TESTS_ENHANCEMENT.md`:

- §5 row `P1-CR-A-followup` — records 78-of-626 with CR-00081 + 2026-05-24 + the deferred-tautology note.
- v1.3 header status block — P1-CR-A-followup line updated to `~548 entries: 0 no-assert / 0 mock-only / 548 tautology` with CR-00081 + 2026-05-24 attribution.
- §11 changelog — new entry dated 2026-05-24 with the strengthen/delete/convert split (counts adding to 78) and a forward link from CR-00046's entry.

The three locations must be **internally consistent** (same total 78, same date 2026-05-24, same CR-ID CR-00081, same residual counts). The strengthen/delete/convert split in §11 must match the union of S01's and S02's report `notes`. Any inconsistency = HIGH.

### 6. Cross-step consistency

- S01's `files_changed` should NOT include `tests/assertion_free_baseline.txt` or `ai-dev/work/TESTS_ENHANCEMENT.md` (S02's scope).
- S02's `files_changed` MUST include `tests/assertion_free_baseline.txt` AND `ai-dev/work/TESTS_ENHANCEMENT.md`.
- S01's reported no-assert count addressed (71 STRENGTHEN + DELETE + CONVERT) must add to 71.
- S02's reported mock-only count addressed (7 CONVERT + DELETE) must add to 7.
- Union must add to 78.
- Per-step reports' `tdd_red_evidence` fields must be present and substantive (not generic "strengthened tests").

Any inconsistency between reports and baseline = HIGH.

### 7. xfail-pinned strengthenings/conversions (HIGH if mishandled)

If S01 or S02 pinned any test with `@pytest.mark.xfail(strict=False, …)` because the strengthening surfaced a real bug, verify:
- The xfail `reason` names the suspected bug.
- A blocker was raised in the relevant report (not silently buried in `notes`).
- The assertion is still real (not weakened).
- Note in your final review report that an Incident should be filed for each xfail (operator follow-up — not a CR-00081 blocker but worth surfacing).

### 8. Architecture / conventions

Read `CLAUDE.md` and `tests/CLAUDE.md`. Verify combined diff respects: testcontainer-only (no live-DB writes from tests), `monkeypatch.delenv` instead of `importlib.reload(orch.config)`, `DaemonEvent.event_metadata` not `metadata`, FTS DDL hook present where needed. (Most of these are unlikely in a strengthening CR, but check anyway — the universe of assertion sites is wide.)

### 9. No scope creep

- No production code changed.
- No skill / template / brand / doc-system files changed.
- No `pyproject.toml`, `Makefile`, `.github/`, or `scripts/check_test_assertions.py` changes.
- No Alembic migrations added.

Any of the above = CRITICAL.

## Test Verification (NON-NEGOTIABLE)

Run a **broader** check than per-step reviews — but still not the full unit + integration suites (the QV gates S10/S11 own those budgets):

```bash
uv run pytest <union of every unique test file across S01+S02 files_changed, excluding the baseline and tracker> -v
make test-assertions
```

If any test fails (other than xfail-pinned ones), or `make test-assertions` fails, raise CRITICAL. `make check` NOT run here — that's S10/S11/S12.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| CRITICAL | AC1 fails, AC4 fails, scope creep, weakened assertion, lint/format new violation, `make test-assertions` red | Must fix |
| HIGH | AC2/AC3/AC5 individual violation, cross-step inconsistency, missing tdd_red_evidence | Must fix |
| MEDIUM (fixable) | Borderline assertion, tracker prose vague but counts correct | Should fix |
| MEDIUM (suggestion) | Better assertion shape available | Optional |
| LOW | Style / nitpick | Info |

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "CR-00081",
  "steps_reviewed": ["S01", "S02"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "completeness|consistency|scope|assertion_strength|delete_rationale|baseline_count|tracker|conventions|testing|architecture",
      "file": "<path>",
      "line": 42,
      "description": "<exact issue>",
      "suggestion": "<how to fix>",
      "cross_cutting": true
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "<N files re-run; make test-assertions: ok|fail>",
  "missing_requirements": [],
  "notes": "<sample size for AC2 mutation-test reasoning (10 random); whether the optional 2-test stash-revert was performed; baseline final counts no-assert=<N>/mock-only=<N>/tautology=<N>; tracker consistency check; any xfail-pinned strengthenings flagged for operator follow-up Incidents>"
}
```

- `verdict: pass` requires zero CRITICAL + zero HIGH + zero MEDIUM (fixable) findings.
- `mandatory_fix_count` = CRITICAL + HIGH + MEDIUM (fixable).
- `missing_requirements`: list any AC with no corresponding implementation; each is automatically CRITICAL.
- `cross_cutting: true` on findings that span S01 + S02 boundaries (consistency, tracker, baseline-count).
