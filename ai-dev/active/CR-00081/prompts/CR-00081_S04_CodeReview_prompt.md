# CR-00081_S04_CodeReview_prompt

**Work Item**: CR-00081 -- Strengthen the 78 highest-priority assertion-scanner baseline entries (71 no-assert + 7 mock-only)
**Step Being Reviewed**: S02 (tests-impl)
**Review Step**: S04

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

This CR adds no migrations — if you see one in the diff, flag CRITICAL out-of-scope.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00081 --json`.
- `ai-dev/active/CR-00081/CR-00081_CR_Design.md` -- Design (source of truth for ACs).
- `ai-dev/active/CR-00081/reports/CR-00081_S02_Tests_report.md` -- S02's report.
- All files listed in S02's report's `files_changed`.
- `tests/assertion_free_baseline.txt` -- Updated by S02. You will inspect its counts.
- `ai-dev/work/TESTS_ENHANCEMENT.md` -- Updated by S02. You will inspect §5 row + v1.3 header + §11 changelog.
- `skills/iw-ai-core-testing/SKILL.md` -- Assertion-strength benchmark.

## Output Files

- `ai-dev/active/CR-00081/reports/CR-00081_S04_CodeReview_report.md` -- Review report

## Context

You are reviewing **S02 of CR-00081** — the conversion of 7 `mock-only` baseline entries, the baseline rewrite, and the plan tracker updates. S03 (separate review) covered S01's 71 no-assert entries.

## Read the Design Document FIRST

- **AC1** (Baseline `no-assert` and `mock-only` entries fully addressed) is the load-bearing check after S02's baseline rewrite.
- **AC2** (Strengthened tests carry real, behaviour-pinning assertions) applies to the 7 conversions.
- **AC3** (DELETE rationale) applies to any DELETE in S02's report.
- **AC4** (Scope) — for S02, allowed paths are `tests/**`, `tests/assertion_free_baseline.txt`, `ai-dev/work/TESTS_ENHANCEMENT.md` ONLY.
- **AC5** (Plan tracker reflects the cleanup) is the rubric for the §5 row + v1.3 header + §11 changelog edits.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Classify any NEW violations as CRITICAL with `"category": "conventions"`.

## Review Checklist

### 1. Baseline count check (CRITICAL category — this is the load-bearing assertion of the CR)

Run all three counts and verify exactly:

```bash
grep -c '# no-assert$' tests/assertion_free_baseline.txt
grep -c '# mock-only$' tests/assertion_free_baseline.txt
grep -c '# tautology$' tests/assertion_free_baseline.txt
```

Expected: `0`, `0`, `548`.

- If `# no-assert$` is non-zero, raise CRITICAL — AC1 fails; either S01 missed entries OR S02 ran the scanner without S01 being complete.
- If `# mock-only$` is non-zero, raise CRITICAL — AC1 fails; S02 missed conversions.
- If `# tautology$` is NOT 548 (lower or higher), raise CRITICAL — S02 touched out-of-scope tests (lower) OR the scanner detected new tautology violations introduced by S02's conversions (higher). Either way, AC4 fails.

Then verify the gate:

```bash
make test-assertions
```

Must exit 0. If not, raise CRITICAL.

### 2. Scope compliance (CRITICAL category)

Every file in `files_changed` must be under `tests/**`, OR exactly `tests/assertion_free_baseline.txt`, OR exactly `ai-dev/work/TESTS_ENHANCEMENT.md`. Any other path = CRITICAL.

No new file under `orch/db/migrations/versions/**`.

### 3. Assertion-strength of the 7 conversions (HIGH category)

For each of the 7 conversions, open the diff. Verify the new assertion is on a **real observable** (return value, DB row, log line via `caplog`) — NOT another `mock.assert_called*` call (that would be a no-op conversion).

Reject (HIGH, mandatory fix):

- Replacing `mock.assert_called*` with another `mock.assert_called*` (still mock-only).
- `assert True` / tautological forms / `assert len(x) >= 0` / `assert isinstance(x, <statically-known-type>)`.
- `assert x is not None` when `x` is constructed unconditionally with no possibility of `None`.

For each of the 7 conversions, reason explicitly in the review report:
- The production code surface the test now observes.
- Whether the new assertion would go red if that surface regressed.

### 4. DELETE rationale check (HIGH)

For every DELETE in S02's report `notes`, verify the prescribed format AND open the named covering test to confirm surface match. Reject any DELETE without rationale or with non-matching covering test.

### 5. Production-code edits (CRITICAL)

S02 must not have modified any file outside `tests/**` + the baseline + the tracker. Any other modification = CRITICAL.

### 6. Tracker edits (HIGH if any missing or inconsistent — AC5)

Open `ai-dev/work/TESTS_ENHANCEMENT.md` and verify all three locations updated:

**(a) §5 row `P1-CR-A-followup`**: records "78 of 626 baseline entries strengthened in this CR (CR-00081, 2026-05-24); remaining 548 `tautology` entries deferred to future per-module CRs" (or substantively equivalent prose with the same load-bearing facts).

**(b) v1.3 header status block**: P1-CR-A-followup line updated from `626 entries: 71 no-assert / 7 mock-only / 548 tautology` to `~548 entries: 0 no-assert / 0 mock-only / 548 tautology` with CR-00081 + 2026-05-24 attribution.

**(c) §11 changelog**: new entry dated 2026-05-24 describing the 78-entry strengthening, the strengthen/delete/convert split (counts adding to 78), and a forward link from CR-00046's entry.

The three locations must be **internally consistent**: same total count (78), same date (2026-05-24), same CR-ID (CR-00081), same residual baseline count (~548 entries: 0/0/548). Any inconsistency = HIGH finding.

### 7. no-assert / tautology entries untouched

S02's test-edit scope is only the 7 `mock-only` entries. Verify (by reading the diff) that S02 did NOT modify any test that S01 already touched, AND did not modify any test in the `# tautology` bucket. If it did, raise a HIGH finding.

### 8. tdd_red_evidence quality

Confirm S02's report `tdd_red_evidence` contains:
- The 7-line grep output of `# mock-only$` baseline entries.
- For at least one representative conversion: the literal new observable-assertion line + the old mock assertion line it replaces + a mutation-test argument.

If missing or generic, raise HIGH.

### 9. xfail-pinned conversions (HIGH if mishandled)

Same as S03's §7 — if a conversion was pinned with xfail because it surfaced a real bug, verify the assertion is still real (not weakened) and a blocker was raised.

### 10. Conventions

Read `tests/CLAUDE.md`. Verify no rules broken in any test edit.

## Test Verification (NON-NEGOTIABLE)

Targeted re-runs:

```bash
uv run pytest <each unique file from S02's files_changed, excluding the baseline and tracker> -v
```

Plus:

```bash
make test-assertions
```

If any test fails (other than xfail-pinned), or `make test-assertions` fails, raise CRITICAL/HIGH appropriately.

Do NOT run the full suite.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| CRITICAL | Baseline count wrong, out-of-scope edit, lint/format new violation, `make test-assertions` red, weakened conversion | Must fix |
| HIGH | Forbidden assertion, missing/wrong DELETE rationale, missing tdd_red_evidence, missing/inconsistent tracker edit, failed targeted test | Must fix |
| MEDIUM (fixable) | Borderline conversion, tracker prose vague | Should fix |
| MEDIUM (suggestion) | Better assertion available | Optional |
| LOW | Style / nitpick | Info |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "CR-00081",
  "step_reviewed": "S02",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "scope|assertion_strength|delete_rationale|baseline_count|tracker|conventions|testing",
      "file": "<path>",
      "line": 42,
      "description": "<exact issue>",
      "suggestion": "<how to fix>"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "<N files re-run, all green>; make test-assertions: ok|fail",
  "notes": "<baseline verification: no-assert=<N>, mock-only=<N>, tautology=<N>; tracker check: §5=present|missing, header=updated|stale, §11=dated 2026-05-24 with split>"
}
```
