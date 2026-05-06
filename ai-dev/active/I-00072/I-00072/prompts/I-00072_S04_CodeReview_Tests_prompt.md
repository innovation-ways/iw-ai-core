# I-00072_S04_CodeReview_Tests_prompt

**Work Item**: I-00072 -- iw merge-queue retry-merge rejects items in merge_failed status
**Step Being Reviewed**: S03 (Tests)
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

Allowed: testcontainers from pytest fixtures; read-only `docker ps|inspect|logs`; `./ai-core.sh` and `make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade|downgrade|stamp` against the live DB. Review-only step.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00072 --json` (canonical).
- `ai-dev/active/I-00072/I-00072_Issue_Design.md` — Design document; "TDD Approach" section is the spec for tests.
- `ai-dev/active/I-00072/reports/I-00072_S03_Tests_report.md` — S03 implementation report.
- `tests/unit/test_merge_queue_cli.py` — the file S03 modified.
- `orch/cli/merge_queue_commands.py` and `orch/daemon/merge_queue.py` — to cross-check that the tests target the actual code paths S01 changed.

## Output Files

- `ai-dev/active/I-00072/reports/I-00072_S04_CodeReview_Tests_report.md` — Review report.

## Context

You are reviewing the test additions for I-00072. The tests must:

1. Verify **semantic outcomes** (status flipped, audit event written, exit code) — NOT just shape (response is non-empty, key exists).
2. Cover **all four** recoverable statuses + the **legacy** failed-with-merge-notes path + the **rejection** of non-merge `failed` rows.
3. Pin **CLI/dashboard parity** through an `is`-identity import comparison.
4. Be **falsifiable** — each test would have failed against pre-S01 code.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Any NEW violations on `tests/unit/test_merge_queue_cli.py` are **CRITICAL** findings with `"category": "conventions"` and exact rule code/message.

## Review Checklist

### 1. Semantic correctness (top priority — this is why this review exists)

Walk through every assertion and grade it. Findings:

- `assert result.exit_code == 0` — semantic. **OK**.
- `assert result.exit_code != 0` — shape. **MEDIUM (fixable)** unless followed by an assertion on the specific exit code value or specific error string.
- `assert "merge_retry_requested" in [e.event_type for e in events]` — semantic. **OK**.
- `assert events` (i.e., truthy) — shape. **CRITICAL** — the test would pass if any other event were written, including a wrong one.
- `assert item.status == BatchItemStatus.completed` — semantic. **OK**.
- `assert item.status != BatchItemStatus.merge_failed` — shape. **HIGH** — `failed`, `merging`, `pending` all pass this. Replace with the specific expected enum.
- `assert "Merge failed" in error_msg` (when checking the rejection path's user-facing message) — semantic. **OK**.

For each assertion that fails the rule, file a **HIGH or CRITICAL** finding (depending on how loadbearing it is to the test's correctness story).

### 2. Coverage matrix

Check that S03 actually wrote a test row for every input class:

| Input | Required test? | Present? |
|-------|---------------|----------|
| `merge_failed` accepted | YES | ? |
| `migration_invalid` accepted | YES | ? |
| `migration_rebase_failed` accepted | YES | ? |
| `migration_rolled_back` accepted | YES | ? |
| Legacy `failed` + notes "Merge failed: …" accepted | YES | ? |
| `failed` + non-merge notes rejected | YES | ? |
| Worktree-missing rejected | YES | ? |
| CLI/dashboard parity (`is` identity import check) | YES | ? |
| Enum-coverage assertion | YES | ? |

Anything missing → **CRITICAL** finding.

### 3. Falsifiability

For each acceptance test (cases 1–5 in the table), verify it would have failed against pre-S01 code. Concretely:

- The reproduction test for `merge_failed` against `main` would hit `_retryable = (failed, migration_rebase_failed)` and exit non-zero with "No failed batch item found". Confirmed falsifiable.
- The `migration_invalid` test would similarly miss the pre-fix filter. Confirmed.
- The legacy-path acceptance test must use a `BatchItemStatus.failed` row — that path **already worked** on pre-S01 code (the CLI accepted `failed` blanket-style). So this test is NOT a falsifiability test against pre-S01; it's a **lock-in** test against future regressions. Make sure the test description / docstring says so — otherwise it's misleading. **MEDIUM (fixable)** if the docstring claims falsifiability falsely.
- The non-merge `failed` rejection test must fail on pre-S01 code (which would accept that row). Confirmed falsifiable.

### 4. Parity test (`is`-identity check)

The parity test must use `is` (identity), not `==` (equality). A `==` check would pass even if S01 left a stale local copy that happens to contain the same enum members — defeating the whole point. If S03 used `==`, **CRITICAL**.

### 5. Test isolation and determinism

- Each test seeds its own BatchItem (no shared mutable state across tests).
- Each test runs against a fresh testcontainer DB session OR cleans up reliably.
- No tests order-depend on each other (run with `pytest -p no:randomly` reversed if needed to verify).
- No real filesystem writes outside the worktree fixture.
- No real DB connections to port 5433.

Any violation → **HIGH**.

### 6. Test location

All new tests must be in `tests/unit/test_merge_queue_cli.py`. If any are placed in `tests/dashboard/` or `tests/integration/`, that's a **HIGH** finding (CLI tests don't need the `client` fixture; integration tests are over-kill for this scope; both choices break the I-00067 lesson on test-file location).

### 7. Naming and discoverability

Each test name should:

- Start with `test_i00072_` so it's grep-able from the work item ID.
- State its expected outcome in the present tense (e.g., `test_i00072_retry_merge_accepts_merge_failed_status`).
- Avoid "should" wording (project convention; check existing tests for the pattern).

### 8. No accidental scope expansion

S03 was scoped to `tests/unit/test_merge_queue_cli.py`. Any new test files, fixture refactors, or seeding helpers in other modules → **MEDIUM (suggestion)** at minimum, **HIGH** if they materially expand the surface area or block S05.

## Test Verification (NON-NEGOTIABLE)

1. Run `make test-unit`.
2. Confirm S03's new tests are visible in the output.
3. Confirm zero failures.

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Test verifies shape not semantics on a load-bearing assertion; missing test row for a status; parity test uses `==` instead of `is`; tests connect to live DB |
| **HIGH** | Falsifiability claim wrong; tests in wrong directory; isolation broken |
| **MEDIUM (fixable)** | Misleading docstring; minor shape-vs-semantic on a non-loadbearing assertion |
| **MEDIUM (suggestion)** | Better fixture pattern available |
| **LOW** | Naming nitpicks |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00072",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "testing|conventions|architecture",
      "file": "tests/unit/test_merge_queue_cli.py",
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

- `verdict`: `pass` if zero CRITICAL/HIGH/MEDIUM-fixable findings.
