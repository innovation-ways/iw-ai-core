# I-00071_S02_CodeReview_prompt

**Work Item**: I-00071 -- Scope-overlap gate over-blocks items due to backtick-wrapped paths and leading-slash test marker
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

Allowed exceptions:
  1. Testcontainers spun up by pytest fixtures
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`
  3. Invoking `./ai-core.sh` or `make` targets

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This item adds NO migrations. You MUST NOT run alembic upgrade/downgrade/stamp.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00071 --json`
- `ai-dev/active/I-00071/I-00071_Issue_Design.md` -- Design document
- `ai-dev/active/I-00071/reports/I-00071_S01_Backend_report.md` -- S01 implementation report
- All files listed in S01's `files_changed`:
  - `orch/design_doc_parser.py`
  - `orch/daemon/scope_overlap.py`
  - `orch/batch_planner.py` (if S01 updated parity)

## Output Files

- `ai-dev/active/I-00071/reports/I-00071_S02_CodeReview_report.md` -- Review report

## Context

You are reviewing the implementation work done in step S01 by `backend-impl` for **I-00071: Scope-overlap gate over-blocks items**.

Read the design document to understand what was intended. Read the implementation report to understand what was done. Then review all changed files.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading any code, run:

```bash
make lint
make format-check
```

If either reports NEW violations in the changed files, classify each as **CRITICAL** with `"category": "conventions"` and quote the exact code/message.

If a command is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. Architecture Compliance

- `orch/design_doc_parser.py` and `orch/daemon/scope_overlap.py` are pure modules — no DB, no I/O, no logging beyond stdlib warnings. Confirm no DB or I/O imports were added.
- `parse_impacted_paths` and `is_test_path` are pure functions. Confirm side-effect-free behaviour.
- Read `orch/CLAUDE.md` to confirm no rule was violated.

### 2. Code Quality

- **Backtick stripping (Bug 1)**: Does the fix strip exactly the surrounding code-span backticks (`` ` `` at both ends with no whitespace inside)? Reject implementations that:
  - Strip backticks anywhere in the string (would corrupt globs that legitimately contain backticks mid-string).
  - Use a regex that also strips other formatting (asterisks, underscores) — out of scope.
  - Skip stripping in either the bullet-line or fenced-code-block branch (must apply to both).
- **`is_test_path` broadening (Bug 2)**: Does the new predicate:
  - Return True for `tests/foo.py`, `test/foo.py`, `__tests__/foo.py` (relative anchors)?
  - Continue to return True for `src/tests/foo.py`, `conftest.py`, `foo.test.ts`, `bar.spec.js`?
  - Continue to return False for `testscript.sh`, `test_data.json`, `src/test_utils.py`?
- **Parity check**: If `orch/batch_planner.py:_is_test_path` was NOT updated in lock-step with `scope_overlap.is_test_path`, this is a **HIGH** finding (the docstring says "Mirror" — divergence is a known footgun).
- **No scope creep**: S01 must not have refactored unrelated code, renamed `_TEST_PATH_MARKERS`, or restructured `globs_intersect`.

### 3. Project Conventions

- Read `CLAUDE.md` and `orch/CLAUDE.md`.
- Naming, formatting, import order match the existing module style.
- No emojis added to code or docs (per project rules).
- Comments only added for non-obvious WHY (e.g. "strip markdown code-span — I-00071"). Reject comments that just restate the code.

### 4. Security

- No hardcoded secrets, credentials, API keys.
- No user-input boundary code touched here — pure helpers operate on already-validated strings.

### 5. Testing

- S01 should NOT have modified `tests/unit/test_design_doc_parser.py` or `tests/unit/daemon/test_scope_overlap.py` — those are owned by S03. If S01 did add tests there, flag as **MEDIUM (fixable)** with `"category": "conventions"` (workflow violation).
- Existing tests in those files must still pass — `make test-unit` must report zero failures.

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. Run `make test-unit` and confirm zero failures.
2. Report the exact pass count in the result contract.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Breaks functionality, data loss risk, security vulnerability | Must fix before merge |
| **HIGH** | Significant bug, missing requirement, architectural violation | Must fix before merge |
| **MEDIUM (fixable)** | Code quality issue, missing edge case, convention violation | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Design improvement, better pattern available | Optional |
| **LOW** | Nitpick, style preference | Informational only |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "I-00071",
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
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

- `verdict`: `pass` only if zero CRITICAL/HIGH findings AND zero MEDIUM_FIXABLE findings.
- `mandatory_fix_count`: count of CRITICAL + HIGH + MEDIUM_FIXABLE.
