# CR-00081_S03_CodeReview_prompt

**Work Item**: CR-00081 -- Strengthen the 78 highest-priority assertion-scanner baseline entries (71 no-assert + 7 mock-only)
**Step Being Reviewed**: S01 (tests-impl)
**Review Step**: S03

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

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live orch DB (port 5433). This CR adds no migrations — if you see one in the diff, flag it as a CRITICAL out-of-scope finding.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00081 --json`.
- `ai-dev/active/CR-00081/CR-00081_CR_Design.md` -- Design (source of truth for ACs).
- `ai-dev/active/CR-00081/reports/CR-00081_S01_Tests_report.md` -- S01's report.
- All files listed in S01's report's `files_changed`.
- `skills/iw-ai-core-testing/SKILL.md` -- §0 mutation-test heuristic, §2 assertion-strength rules. Your assertion-quality benchmark.
- `tests/assertion_free_baseline.txt` -- NOTE: S01 does NOT modify this. If it appears in S01's `files_changed`, raise a CRITICAL finding (S01 went out of scope; S02 owns this file).

## Output Files

- `ai-dev/active/CR-00081/reports/CR-00081_S03_CodeReview_report.md` -- Review report

## Context

You are reviewing **S01 of CR-00081** — the strengthening of 71 `no-assert` baseline entries. The CR's goal is to remove all 71 no-assert + 7 mock-only entries from the baseline; S01 owns the 71 no-assert half. S02 (separate review by S04) owns the 7 mock-only entries, the baseline rewrite, and the tracker update.

## Read the Design Document FIRST

Read `ai-dev/active/CR-00081/CR-00081_CR_Design.md` before opening any changed test files. Specifically:

- **AC2** (Strengthened tests carry real, behaviour-pinning assertions) is the main rubric for this review.
- **AC3** (Deleted tests have a one-line rationale naming the covering test) — every DELETE in S01's report must conform.
- **AC4** (Scope is tests + baseline + plan tracker only) — for S01 specifically, allowed paths are `tests/**` ONLY (baseline + tracker are S02's scope).
- *Notes* section: "Risk: a strengthening becomes a tautology in disguise" — apply the listed forbidden-assertion patterns.

Note the design has no separately-named TDD test files for this CR (the in-scope tests are themselves the deliverables) — there is no "TDD-section test file missing" risk to check.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run on the files in S01's `files_changed`:

```bash
make lint
make format-check
```

If either reports NEW violations in the changed files (not present on `main`), classify each as a **CRITICAL** finding with `"category": "conventions"`, `"file"`, `"line"`, and `"description"` quoting the code and message.

If a command is unavailable, STOP and raise a blocker. Do NOT skip.

## Review Checklist

### 1. Scope compliance (CRITICAL category)

- Every file in `files_changed` is under `tests/**`. If any file is `tests/assertion_free_baseline.txt`, `ai-dev/work/TESTS_ENHANCEMENT.md`, or anything under `orch/`, `dashboard/`, `executor/`, `scripts/`, `bin/`, `templates/`, `skills/`, `.claude/skills/`, `.github/` — raise a CRITICAL finding (out of scope).
- No new file is added under `orch/db/migrations/versions/**`.

### 2. Assertion strength (HIGH category for each violation)

For every strengthened test (open the diff, read the assertion the agent added), apply the mutation-test question from `skills/iw-ai-core-testing/SKILL.md` §0: *if the production code line this test ostensibly covers were deleted or inverted, would this assertion go red?*

Reject (HIGH finding, mandatory fix) any assertion matching:

- `assert True` / `assert 1 == 1` / `assert obj is obj` / `assert <constant> == <constant>`
- `assert len(x) >= 0` (always true for sequences)
- `assert isinstance(x, <statically-known-type>)` when the constructor literally returns that type
- `mock.assert_called*` as the **only** assertion (the conversion is incomplete — it's still a mock-only test)
- `assert x is not None` when `x` is constructed unconditionally in the same test setup with no possibility of being `None`

For at least 5 randomly-chosen strengthenings, reason explicitly in the review report:
- The production code line(s) the test covers.
- Whether the new assertion would go red if those lines were regressed.
- If you cannot answer "yes" with confidence, flag the finding.

### 3. DELETE rationale check (HIGH category for each violation)

For every DELETE in S01's report `notes`, verify the line matches the prescribed format:

```
DELETE tests/<path>::<test_name> — covered by tests/<other_path>::<other_test_name> (one-line reason)
```

Then OPEN the named covering test and verify it actually covers the same production surface as the deleted test. If the covering test does not match the surface (e.g. it tests a different code path, or doesn't exist), raise a HIGH finding.

Reject any DELETE without a one-line rationale or with a non-existent / mismatched covering test.

### 4. Production-code edits (CRITICAL)

If S01 modified ANY file outside `tests/**` (including the baseline, the tracker, or any orch/dashboard/executor/scripts/skill file), raise a CRITICAL finding. The S01 prompt explicitly forbids this.

### 5. mock-only / tautology entries untouched

S01's scope is only the 71 `no-assert` entries. Verify (by reading the diff) that S01 did NOT modify any test that appears in the baseline tagged `# mock-only` or `# tautology`. If it did, raise a HIGH finding (those are S02's or future-CR scope).

### 6. tdd_red_evidence quality

Confirm S01's report `tdd_red_evidence` contains:
- The 71-line grep output of `# no-assert$` baseline entries (the RED dump).
- For at least one representative strengthening: the literal new assertion line + a brief mutation-test argument.

If the field is missing, generic ("strengthened tests"), or doesn't include the per-test argument, raise a HIGH finding.

### 7. xfail-pinned strengthenings (HIGH if mishandled)

If S01's `notes` lists any strengthening that surfaced a real bug and was pinned with `@pytest.mark.xfail(strict=False, …)`, verify:
- The xfail `reason` names the suspected bug.
- A blocker was raised in the report (not silently buried in `notes`).
- The strengthening assertion itself is still real (not weakened).

If a strengthening fails against current main and was simply weakened to pass, raise a CRITICAL finding (defeats the entire CR).

### 8. Conventions

Read `tests/CLAUDE.md`. Verify no rules broken: no `importlib.reload(orch.config)`, no live-DB connection, `DaemonEvent.event_metadata` used (not `metadata`), etc. (These are unlikely failure modes in a test-strengthening CR but check anyway.)

## Test Verification (NON-NEGOTIABLE)

Run a targeted re-run of each modified test file (sample if there are many; cover every unique file at least once):

```bash
uv run pytest <each unique file from files_changed> -v
```

If any test fails (other than xfail-pinned ones from §7), raise a HIGH finding.

Do NOT run the full suite — that's S10/S11.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| CRITICAL | Out-of-scope edit, lint/format new violation, weakened strengthening | Must fix |
| HIGH | Forbidden assertion, missing/wrong DELETE rationale, missing tdd_red_evidence, failed targeted test | Must fix |
| MEDIUM (fixable) | Borderline assertion (could be stronger), DELETE rationale present but thin | Should fix |
| MEDIUM (suggestion) | Better assertion shape available | Optional |
| LOW | Style / nitpick | Info only |

## Review Result Contract

```json
{
  "step": "S03",
  "agent": "CodeReview",
  "work_item": "CR-00081",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "scope|assertion_strength|delete_rationale|conventions|testing",
      "file": "tests/<file>.py",
      "line": 42,
      "description": "<exact issue>",
      "suggestion": "<how to fix>"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "<N files re-run, all green>",
  "notes": "<sample size for the §2 mutation-test reasoning, e.g. 'reasoned about 8 of N strengthenings'; any patterns observed across multiple findings>"
}
```

- `verdict: pass` requires zero CRITICAL + zero HIGH + zero MEDIUM (fixable).
- `mandatory_fix_count` = CRITICAL + HIGH + MEDIUM (fixable).
- Only CRITICAL, HIGH, MEDIUM (fixable) trigger a fix cycle.
