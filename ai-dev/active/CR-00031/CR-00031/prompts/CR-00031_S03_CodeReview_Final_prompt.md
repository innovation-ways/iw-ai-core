# CR-00031_S03_CodeReview_Final_prompt

**Work Item**: CR-00031 — Add CLAUDE.md Critical Rule for `make css` no-op fallback to direct CSS append
**Review Step**: S03 (Final Review)
**Implementation Steps Reviewed**: S01

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

No migration in this CR.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00031 --json`.
- `ai-dev/active/CR-00031/CR-00031_CR_Design.md` — Design document with AC1–AC4.
- `ai-dev/work/CR-00031/reports/CR-00031_S01_Backend_report.md` — S01 implementation report.
- `ai-dev/work/CR-00031/reports/CR-00031_S02_CodeReview_report.md` — S02 per-agent review report.
- `CLAUDE.md` — The modified file.
- `git diff main..HEAD` — Full branch diff (must be confined to the in-scope paths).

## Output Files

- `ai-dev/work/CR-00031/reports/CR-00031_S03_CodeReview_Final_report.md` — Final review report.

## Context

You are performing the **final cross-step review** of CR-00031. This CR has only one implementation step (S01), so "cross-cutting" mostly means: confirm the diff is bounded to the design's scope, all five acceptance criteria (AC1–AC5) are satisfied, and no other repo file is touched.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run:

```bash
make lint
make format-check
```

Both must produce zero new violations. Any new violation in the changed files is CRITICAL.

## Review Checklist

### 1. Completeness vs Design Document

Verify all five acceptance criteria against the actual diff:

- **AC1**: New bullet in `## Critical Rules` names BOTH the symptom (`make css` no-op or Tailwind CLI failure) AND the action (append plain CSS to `dashboard/static/styles.css`).
- **AC2**: Bullet contains an inline reference to I-00067.
- **AC3**: Diff scope is bounded — `git diff --name-only main..HEAD` should list only `CLAUDE.md` and `ai-dev/active/CR-00031/**` files. Inside `CLAUDE.md`, only the `## Critical Rules` section gains the new bullet; no other section, formatting, or whitespace changes.
- **AC4**: Bullet style matches surrounding peers — uses `**MUST**` (preferred) or another existing keyword from `**NEVER**` / `**CRITICAL**` / `**NEW**`; terse imperative tone. Novel keywords like `**WHEN**` are MEDIUM_FIXABLE.
- **AC5**: Bullet includes "until the Tailwind toolchain is repaired in worktrees" (or equivalent) language flagging it as a temporary mitigation, so the rule is removed once the upstream platform fix lands.

If any criterion is unmet, classify as CRITICAL (AC1, AC3) or HIGH (AC2) or MEDIUM_FIXABLE (AC4, AC5).

### 2. Cross-Step Consistency

This CR has a single implementation step, so cross-step consistency is trivially satisfied. Confirm:

- S01's report's `files_changed` lists only `CLAUDE.md`.
- The actual diff matches that claim.

### 3. Integration Points

Documentation has no integration points. Skip.

### 4. Test Coverage (Holistic)

This CR adds documentation only. There are no new code paths, no new tests required. Confirm:

- Existing unit and integration tests still pass (run `make test-unit` and `make test-integration`).
- Any failure here suggests S01 modified something outside the scope claimed in its report → CRITICAL.

### 5. Architecture Compliance

Confirm the new rule does not contradict any existing rule in `CLAUDE.md`. In particular, scan the existing `## Critical Rules` bullets for any rule about CSS or Tailwind handling — there should be none currently, so no conflict is expected, but verify.

### 6. Security (Cross-Cutting)

Not applicable to a documentation change.

## Test Verification (NON-NEGOTIABLE)

Run the full test suite:

1. `make test-unit`
2. `make test-integration`

Both must pass with zero failures. Any failure is CRITICAL because this CR should have introduced no runtime change.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | AC1 or AC3 violated, tests broken, scope expanded beyond CLAUDE.md | Must fix before merge |
| **HIGH** | AC2 violated (no I-00067 reference) | Must fix before merge |
| **MEDIUM (fixable)** | AC4 style mismatch, AC5 missing temporary-mitigation language | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Wording could be clearer or more action-oriented | Optional |
| **LOW** | Nitpick | Informational only |

## Review Result Contract

```json
{
  "step": "S03",
  "agent": "code-review-final-impl",
  "work_item": "CR-00031",
  "steps_reviewed": ["S01"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "completeness|consistency|integration|testing|architecture|security",
      "file": "CLAUDE.md",
      "line": 0,
      "description": "...",
      "suggestion": "...",
      "cross_cutting": false
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```

- `verdict`: `pass` if zero CRITICAL/HIGH/MEDIUM_FIXABLE findings AND no missing requirements.
- `missing_requirements`: list any AC1–AC5 that have no corresponding diff content. Missing AC1 or AC3 is automatically CRITICAL; missing AC2 is HIGH; missing AC4 or AC5 is MEDIUM_FIXABLE.
