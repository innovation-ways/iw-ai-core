# CR-00049_S02_CodeReview_prompt

**Work Item**: CR-00049 -- Re-enable `pytest-randomly` by default (P1-CR-C-followup-randomly)
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

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

This CR adds **no** migrations. If you see one in `files_changed`, flag it as
CRITICAL (scope creep) and verify it wasn't a hallucination from S01's tooling.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — for the current step list, status, prompt paths, gate commands, etc., prefer `uv run iw item-status CR-00049 --json`. The `workflow-manifest.json` file is a design-time snapshot and may be out of date (CR-00023).
- `ai-dev/active/CR-00049/CR-00049_CR_Design.md` -- Design document (source of truth)
- `ai-dev/active/CR-00049/reports/CR-00049_S01_Backend_report.md` -- Implementation step report
- All files listed in the implementation report's `files_changed`

## Output Files

- `ai-dev/active/CR-00049/reports/CR-00049_S02_CodeReview_report.md` -- Review report

## Context

You are reviewing S01's implementation of **CR-00049 — Re-enable `pytest-randomly` by default**. This is the cleanup follow-up to CR-00048 (merged `a789701`, 2026-05-13), which shipped with `-p no:randomly` in `addopts` because the integration-suite collection failed under random order. S01's job in this CR was: (a) reproduce the failure, (b) diagnose the leak, (c) fix it at the fixture level where possible, (d) quarantine the residue with `@pytest.mark.order_dependent` + `xfail(strict=False)`, (e) remove `-p no:randomly` from `addopts`, (f) flip the docs from "off-by-default" to "default-on", (g) close out the follow-up row + item 1.4 in `ai-dev/work/TESTS_ENHANCEMENT.md`.

Read the design first. The "Acceptance Criteria" (AC1–AC5) are mandatory checks. The "Current Behavior" section lists the 12 modules where collection-time `sqla…` errors originally surfaced — every one of them must either pass under randomisation now, or carry a quarantine marker (NOT a `skip`, NOT a comment-out).

## Read the Design Document FIRST

Read the design document **before** running the lint/format gate and **before** opening any changed files. Specifically:

- Read the `## Acceptance Criteria` section in full — every criterion is a mandatory check, not a suggestion.
- Cross-check S01's `files_changed` against the design's "Impacted Paths". Any file in `files_changed` outside that list is a **CRITICAL** scope-violation finding (e.g., production code under `orch/`, `dashboard/`, or `executor/` would be a serious red flag — the design says explicitly "no production code change").
- Note every test module the design's *Current Behavior* lists; carry these into the Review Checklist below as a first-class anchor — each must either pass under random order in S01's deliverable-4 sweep or carry the quarantine marker.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading any code, run these two commands on the files in `files_changed`. Fix nothing yourself — only report.

```bash
make lint          # ruff check — catches unused imports, etc.
make format-check  # ruff format --check — catches formatting drift
```

If either reports NEW violations in the changed files, classify each as a **CRITICAL** finding with `"category": "conventions"`, `"file"` and `"line"`, and the exact violation message.

## Review Checklist

### 1. The fallback is actually removed

- `pyproject.toml` `[tool.pytest.ini_options] addopts` no longer contains the substring `no:randomly` anywhere. Grep the file: `grep -n 'no:randomly' pyproject.toml` must return nothing.
- `--strict-markers` is still in `addopts` (do not regress CR-00048's marker change).
- The comment block above `addopts` reflects the new state and preserves the CR-00048 history as an "Earlier fallback" note rather than silently deleting it.

### 2. Order-dependent failures are genuinely fixed or correctly quarantined

For each of the 12 modules listed in the design's *Current Behavior* (or any additional ones S01's deliverable-0 reproduction surfaced), confirm:

- The module either runs cleanly under `-p randomly` across all 4 seeds (12345/67890/11111/42424) — i.e., the failures listed in S01's `tdd_red_evidence` are gone, OR
- Each still-failing test in that module carries:
  - `@pytest.mark.order_dependent` (the marker is already registered at `pyproject.toml` line 154; no duplicate registration)
  - `@pytest.mark.xfail(strict=False, reason="<one-line: which fixture/state is leaking, what other test it depends on>")` — `strict=False` is mandatory (the test passes in alphabetical order — strict=True would xpass-fail)
  - A `# NOTE(P1-CR-C-followup-randomly):` tracking comment naming the suspected leak source
- No test is hidden via `@pytest.mark.skip`, `@pytest.mark.skipif`, or comment-out. Quarantined tests must still run.
- The xfail `reason` strings are *substantive* (name what's leaking), not just "order-dependent" (that would be a HIGH finding).

### 3. Test-isolation fixes only

Inspect every test/fixture diff in `files_changed`. Diffs under `tests/**` must be:

- Test-isolation repairs (adding `monkeypatch.delenv`, scoping `patch.dict(..., clear=True)`, draining module-level caches, adding teardowns to autouse fixtures, etc.).
- Quarantine markers (per checkpoint 2).
- The above documented at the fixture site with a `# CR-00049:` comment.

Diffs that **change test assertions**, **weaken assertions**, **comment tests out**, **remove tests**, or **add new behavioural tests** are out of scope. Each such diff is a CRITICAL or HIGH finding (depending on whether the test still meaningfully verifies something).

### 4. No production code changes

Grep `files_changed` for any path under `orch/`, `dashboard/`, `executor/`, `bin/`, `scripts/`. If any appears, that is a **CRITICAL** scope violation — this CR's design says explicitly "no production code change."

(Exception: `.claude/skills/iw-ai-core-testing/SKILL.md` is allowed because it's the synced copy of the master in `skills/`. Verify both files exist in `files_changed` if either does.)

### 5. Documentation flipped correctly

- `tests/CLAUDE.md` §7 — describes the new default-on state. The old off-by-default paragraph is preserved as a brief "Earlier fallback (CR-00048)" historical note (not silently deleted).
- `docs/IW_AI_Core_Testing_Strategy.md` §3 — same flip + same historical-note pattern.
- `docs/IW_AI_Core_Testing_Strategy.md` §9 row "Test-order randomisation (`pytest-randomly`)" — prefix `"✅ (CR-00049, YYYY-MM-DD) — default-on; suite robust to randomisation; …"`. NOT ⚠️.
- `skills/iw-ai-core-testing/SKILL.md` §2 — same flip.
- `.claude/skills/iw-ai-core-testing/SKILL.md` byte-for-byte equal to its master. Verify with: `diff -q skills/iw-ai-core-testing/SKILL.md .claude/skills/iw-ai-core-testing/SKILL.md` — must report `Files match` (or no output).

### 6. Plan + changelog updated

- `ai-dev/work/TESTS_ENHANCEMENT.md` §5 row `P1-CR-C-followup-randomly` marked **DONE (CR-00049, YYYY-MM-DD)** with fix-vs-quarantine counts.
- §5 item 1.4 row flipped from PARTIAL → DONE (CR-00049) with a one-liner.
- §11 has a new dated changelog entry naming: leak source, fixes count, quarantine count, seeds passed.

### 7. RED evidence

The S01 report's `tdd_red_evidence` field must record the failing seed-12345 reproduction (the `sqla…` traceback). It must NOT be `"n/a"` — this CR has a concrete RED anchor by design.

### 8. No scope creep

S01 must not have:
- Fixed the `integration-tests` no-op gate (that's P1-CR-E).
- Flipped `vulture`/`deptry` to hard gates.
- Scrubbed the assertion baseline (P1-CR-A-followup).
- Ported the change to sibling projects.
- Added new tests, new fixtures, new makefile targets, new GH workflow jobs.
- Touched production code (Checklist 4 covers this).

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. Run `make test-unit -- -p randomly --randomly-seed=12345` and `make test-unit -- -p randomly --randomly-seed=67890` — both must pass (the unit suite must be robust to randomisation; it was already green in CR-00048's bounded sweep).
2. Run the design's exact reproduction recipe against `tests/integration/` + `tests/dashboard/` at one seed (12345 is enough — S01's deliverable 4 already swept 4):

   ```bash
   uv run pytest tests/integration/ tests/dashboard/ --ignore=tests/dashboard/browser -p randomly --randomly-seed=12345 -q
   ```

   Confirm it exits 0 (quarantined tests showing as `xfailed` count as passing). If it does not, that is a **CRITICAL** finding — the implementation failed AC1.

3. Report test results accurately in the result contract.

Do **NOT** run `make check`, `make test-integration`, or `make diff-coverage` — those are S08/S09/S10's job and re-running them risks step-timeout. The targeted runs above are sufficient to validate the fix.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Breaks functionality, scope violation, AC failure | Must fix before merge |
| **HIGH** | Significant bug, missing requirement, weak quarantine `reason` | Must fix before merge |
| **MEDIUM (fixable)** | Code quality issue, missing edge case, convention violation | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Design improvement, better pattern available | Optional, author decides |
| **LOW** | Nitpick, style preference, minor readability | Informational only |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "CR-00049",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "Unit suite under -p randomly: <N> passed (seeds 12345 + 67890). Integration+dashboard under -p randomly --randomly-seed=12345: <N> passed, <M> xfailed (quarantined).",
  "notes": ""
}
```

- `verdict`: `pass` if zero CRITICAL + zero HIGH + zero MEDIUM (fixable). `fail` otherwise.
- `mandatory_fix_count`: CRITICAL + HIGH + MEDIUM (fixable).
- Only CRITICAL / HIGH / MEDIUM (fixable) trigger fix cycles.
