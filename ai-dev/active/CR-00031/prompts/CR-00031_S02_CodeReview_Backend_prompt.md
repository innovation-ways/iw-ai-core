# CR-00031_S02_CodeReview_Backend_prompt

**Work Item**: CR-00031 — Add CLAUDE.md Critical Rule for `make css` no-op fallback to direct CSS append
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

Allowed exceptions: testcontainers in pytest fixtures, read-only docker introspection, `./ai-core.sh` / `make` invocations.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

No migration in this CR. Do not run alembic against the live DB.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00031 --json`.
- `ai-dev/active/CR-00031/CR-00031_CR_Design.md` — Design document (acceptance criteria are AC1–AC4).
- `ai-dev/work/CR-00031/reports/CR-00031_S01_Backend_report.md` — S01 implementation report.
- `CLAUDE.md` — The modified file.
- `git diff main..HEAD -- CLAUDE.md` — The change under review.

## Output Files

- `ai-dev/work/CR-00031/reports/CR-00031_S02_CodeReview_report.md` — Review report.

## Context

You are reviewing the documentation edit made in S01 for CR-00031. The CR adds **one** bullet to `CLAUDE.md`'s `## Critical Rules` section. The change has no runtime behavior; correctness is judged purely by reading the diff against `main`.

The design has **five** acceptance criteria (AC1–AC5). AC5 was added during design review to ensure the new rule is scoped as a temporary mitigation — confirm the design doc's AC5 is satisfied alongside AC1–AC4.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run these two commands; treat NEW violations in the changed files as CRITICAL findings:

```bash
make lint
make format-check
```

For a doc-only change against `CLAUDE.md`, both commands should produce zero new violations. If either reports a Python/lint regression, that means S01 did more than the spec allowed and you must flag it.

## Review Checklist

### 1. Acceptance Criteria Compliance

Verify each criterion from the design document by reading `git diff main..HEAD -- CLAUDE.md`:

- **AC1 — Bullet present, names symptom AND action**:
  - Does the bullet name the symptom? (must mention `make css` "Nothing to be done" OR Tailwind CLI failure / module-not-found)
  - Does it prescribe the action? (must say to append CSS directly to `dashboard/static/styles.css`)
  - If either half is missing, that's CRITICAL.

- **AC2 — References I-00067**:
  - Does the bullet contain an inline reference to I-00067? (e.g., "see I-00067", "per I-00067")
  - If absent, that's HIGH.

- **AC3 — No other content changed**:
  - Is `CLAUDE.md` the only modified file in the diff? Run `git diff --name-only main..HEAD`.
  - Within `CLAUDE.md`, is the change confined to the `## Critical Rules` section?
  - Are any unrelated bullets reformatted, reordered, or rewrapped?
  - Any of these violations is CRITICAL.

- **AC4 — Style consistent with surrounding bullets**:
  - Does the new bullet use a bold keyword from the existing palette (`**MUST**`, `**NEVER**`, `**CRITICAL**`, `**NEW**`)? `**MUST**` is preferred for this rule; flag novel keywords like `**WHEN**` as MEDIUM_FIXABLE.
  - Is the tone directive and terse, matching peers?
  - Style mismatches are MEDIUM (fixable).

- **AC5 — Rule is scoped as a temporary mitigation**:
  - Does the bullet include explicit "until the Tailwind toolchain is repaired in worktrees" (or equivalent) language so the rule is removed when the upstream platform fix lands?
  - If absent, that's MEDIUM_FIXABLE — the bullet still works without it but risks calcifying into permanent advice.

### 2. Bullet Placement

- Confirm the bullet is appended **inside** the existing `## Critical Rules` unordered list, not in a different section, not above/below the section header.

### 3. Markdown Hygiene

- The bullet renders as a single list item in standard markdown (starts with `- `, single line or wrapped).
- No stray trailing whitespace or accidental tab/space mix.
- File still ends with a single trailing newline (no extra blank lines added).

### 4. Wording Does Not Contradict Existing Rules

- Skim the existing bullets in `## Critical Rules`. Confirm the new rule does not conflict with any (e.g., does not contradict the playwright-cli rule, the docker-compose rule, etc.).

### 5. Project Conventions

Read `CLAUDE.md` for the project's bullet style and ensure the new entry fits.

## Test Verification (NON-NEGOTIABLE)

This is a documentation-only change. Run `make test-unit` once to confirm there are no regressions caused by an unintended edit (S01 should only have touched `CLAUDE.md`, but verify).

If unit tests run cleanly, set `tests_passed: true`. If S01 inadvertently broke something, that's a CRITICAL finding.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | AC1 violated, AC3 violated (other files touched), or tests broken | Must fix before merge |
| **HIGH** | AC2 violated (no I-00067 reference) | Must fix before merge |
| **MEDIUM (fixable)** | AC4 style mismatch, AC5 missing temporary-mitigation language, markdown hygiene issue | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Wording could be clearer | Optional |
| **LOW** | Nitpick | Informational only |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "CR-00031",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "CLAUDE.md",
      "line": 0,
      "description": "...",
      "suggestion": "..."
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

- `verdict`: `pass` if zero CRITICAL/HIGH/MEDIUM_FIXABLE findings; otherwise `fail`.
- `mandatory_fix_count`: count of CRITICAL + HIGH + MEDIUM_FIXABLE.
