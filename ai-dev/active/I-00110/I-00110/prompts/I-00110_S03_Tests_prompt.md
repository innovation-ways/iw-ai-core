# I-00110_S03_Tests_prompt

**Work Item**: I-00110 -- Keep-alive slot endpoints return HTTP 500 on out-of-BIGINT slot_id path param
**Step**: S03
**Agent**: Tests

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

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run alembic upgrade/downgrade/stamp commands against the live orchestration DB. This step adds no migrations.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00110 --json`.
- `ai-dev/active/I-00110/I-00110_Issue_Design.md` -- Design document (READ THIS FIRST — especially `## Test to Reproduce` for the verbatim test code)
- `ai-dev/work/I-00110/reports/I-00110_S01_Backend_report.md` -- S01 backend report
- `ai-dev/work/I-00110/reports/I-00110_S02_CodeReview_report.md` -- S02 review report
- `dashboard/routers/keep_alive.py` -- The post-S01 handlers with the new `Path(...)` bound
- `tests/dashboard/test_schemathesis_contract.py` (lines 80-113) -- The KNOWN_CONTRACT_5XX allowlist whose two entries must be removed
- `tests/dashboard/conftest.py` -- The `client` fixture (read-only, for orientation)

## Output Files

- `ai-dev/work/I-00110/reports/I-00110_S03_Tests_report.md` -- Step report
- Created: `tests/dashboard/test_keep_alive_slot_overflow.py`
- Modified: `tests/dashboard/test_schemathesis_contract.py`

## Context

You are writing the regression test suite for **I-00110** AND removing the schemathesis allowlist workaround that masked the bug. S01 has already applied the `Path(...)` bound on both handlers; your job is to codify the GREEN contract going forward — tests that pass against the post-S01 code and would FAIL against any future regression of the same class.

Read the design document `ai-dev/active/I-00110/I-00110_Issue_Design.md` in full before touching any code. The `## Test to Reproduce` section contains the six test functions verbatim — copy them, do not paraphrase.

Then read `CLAUDE.md` and `tests/CLAUDE.md` for project-specific patterns and conventions.

## Requirements

### 1. Create the regression test file

Create `tests/dashboard/test_keep_alive_slot_overflow.py` with the six tests verbatim from the design's `## Test to Reproduce` section:

- `test_delete_slot_overflow_returns_422_not_500` — DELETE with `slot_id > 2**63 - 1` returns 422 + `slot_id` in `detail[].loc`
- `test_toggle_slot_overflow_returns_422_not_500` — PATCH toggle with same input returns 422 + `slot_id` in `detail[].loc`
- `test_delete_slot_at_bigint_max_does_not_500` — DELETE at exact BIGINT max (`2**63 - 1`) returns 200 OR 404 (NEVER 422 or 500)
- `test_toggle_slot_at_bigint_max_does_not_500` — PATCH toggle at exact BIGINT max returns 200 OR 404
- `test_delete_slot_zero_returns_422` — `slot_id=0` violates `ge=1` → 422
- `test_toggle_slot_negative_returns_422` — negative `slot_id` violates `ge=1` → 422

**File location MUST be `tests/dashboard/`** — NOT `tests/unit/` or `tests/integration/`. The `client` fixture is registered only in `tests/dashboard/conftest.py`; a test placed elsewhere will fail with `fixture 'client' not found` (I-00067 gotcha; see `tests/CLAUDE.md`).

Every assertion MUST be **semantic** — specific status codes (422, 200, 404) AND structured `detail[].loc` content. Shape-only assertions like `assert "detail" in body` alone are INSUFFICIENT (I003 lesson) — pair them with semantic checks.

### 2. Run the new file targeted and confirm GREEN

```bash
uv run pytest tests/dashboard/test_keep_alive_slot_overflow.py -v --no-cov
```

All six tests must PASS against the post-S01 code. The two overflow tests (`test_*_overflow_returns_422_not_500`) and the two ge=1/ge=1-violation tests (`test_*_zero_returns_422`, `test_*_negative_returns_422`) verify the new `Path(...)` constraint. The two boundary tests (`test_*_at_bigint_max_does_not_500`) verify the bound does NOT reject the legitimate maximum value.

If any test fails GREEN, escalate immediately — either S01 didn't fully apply the fix (in which case raise a blocker and let the operator restart the cycle), or the test is wrong (fix the test).

### 3. Remove the two `KNOWN_CONTRACT_5XX` entries

Edit `tests/dashboard/test_schemathesis_contract.py` (around lines 97-108). Delete both dict entries:

- `"/api/keep-alive/slots/{slot_id}"`
- `"/api/keep-alive/slots/{slot_id}/toggle"`

The `JSON_API_FUZZ_PATHS` derivation (`[p for p in JSON_API_PATHS if p not in KNOWN_CONTRACT_5XX]`) recomputes automatically — both paths will re-enter the fuzz set. Do NOT add the paths back manually anywhere; the filter is the source of truth.

After deletion, `KNOWN_CONTRACT_5XX` will be empty. Leave it as `KNOWN_CONTRACT_5XX: dict[str, str] = {}` (do not delete the dict itself — future incidents may re-populate it). Preserve the surrounding comment block explaining what the dict is for.

### 4. Optionally sanity-check the schemathesis contract module

To verify the allowlist deletion didn't break the contract suite's collection, you may optionally run:

```bash
uv run pytest tests/dashboard/test_schemathesis_contract.py::test_json_api_paths_exist_in_schema -v --no-cov
```

This is OPTIONAL. The full schemathesis contract run is owned by the QV `integration-tests` gate (S13).

### 5. Test Verification — TARGETED ONLY

After all edits, the only verification command you run is:

```bash
uv run pytest tests/dashboard/test_keep_alive_slot_overflow.py -v --no-cov
```

All six tests must PASS. **DO NOT run `make test-integration`, `make test-unit`, `make test-dashboard`, or `make allure-integration`.** Full-suite execution belongs to the QV gate steps downstream (`unit-tests` S11, `frontend-tests` S12, `integration-tests` S13). Duplicating them here blows the step's timeout budget (I-00073/S03 post-mortem, 2026-05-08).

### 6. Do NOT manually revert S01 to "verify RED"

Do NOT instruct yourself to `git checkout HEAD~1 -- dashboard/routers/keep_alive.py`, `git stash`, or otherwise revert source files at runtime to "confirm the test would have failed pre-fix". That is a thrash-prone operation explicitly forbidden by the workflow contract. The RED evidence is already in S01's report (the in-process probe showing pre-fix HTTP 500 + `psycopg.errors.NumericValueOutOfRange`); your job is to write tests that codify the GREEN contract going forward.

For each new test, reason about whether it would fail against pre-S01 code and document that reasoning in your step report's `notes` field (e.g. "`test_delete_slot_overflow_returns_422_not_500` would have failed against pre-S01 code with `AssertionError: assert 500 == 422` because the unbounded `int` path param accepted 2**63 and the downstream BIGINT query raised `psycopg.errors.NumericValueOutOfRange`").

## Project Conventions

Read the project's `CLAUDE.md` AND `tests/CLAUDE.md` for:

- Tests under `tests/dashboard/` use the `client` fixture from `tests/dashboard/conftest.py` (I-00067 gotcha).
- pytest-randomly is on by default — every new test must be order-independent. The tests in this step are stateless (no DB writes), so order independence is automatic.
- Coding conventions: `ruff format` is the formatter, `ruff check` is the linter, `mypy` is the type checker. `make lint`, `make format`, `make typecheck` are the entry points.

## TDD Requirement (Dedicated Coverage Step — RED-Exempt)

This is a `tests-impl` step — a dedicated coverage step that adds tests after the code exists. Per `skills/iw-workflow/SKILL.md`, dedicated coverage steps are **exempt from RED-first** by design.

1. Write each test.
2. Run it (targeted) and confirm it PASSES against the current (post-S01) code. A test that fails GREEN means either S01 didn't fully fix the bug (escalate) or the test is wrong (fix it).
3. Reason about whether the test would have failed against pre-S01 code, and record that reasoning in the step report's `notes`.

**Do NOT** revert S01 at runtime. **Do NOT** simulate RED via stash/checkout. The `tdd_red_evidence` field for this step uses the `"n/a — dedicated coverage step; RED evidence is in S01 report (in-process probe showed 500 → 422 transition)"` form.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, you MUST run these in order and fix any issues they report:

1. **`make format`** — auto-fixes formatting drift in your new and modified test files. If it reformats files, inspect the diff and re-stage; do NOT skip.
2. **`make typecheck`** — must report zero errors involving the files you touched (`tests/dashboard/test_keep_alive_slot_overflow.py`, `tests/dashboard/test_schemathesis_contract.py`). Errors elsewhere are pre-existing — note them in your report but do not ignore your own.
3. **`make lint`** — must report zero errors.

If a tool isn't available in your worktree, STOP and raise a blocker — do not silently skip.

In your Subagent Result Contract, populate the `preflight` object recording the result of each command:
- `"ok"` — ran cleanly, no changes / no errors
- `"fixed"` — applies to `format` only; the tool auto-fixed something
- `"skipped:<reason>"` — only if you raised a blocker explaining why

## CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "detail" in body` (shape only — every FastAPI error has a `detail`)
- GOOD: `assert resp.status_code == 422` (semantic — specific expected status)
- GOOD: `assert any("slot_id" in str(err.get("loc", ())) for err in body["detail"])` (semantic — verifies the validator names the right field)
- GOOD: `assert resp.status_code in (200, 404)` for the boundary case (semantic — verifies absence of 422/500)
- BAD: `assert resp.status_code != 500` alone (under-constrained — accepts 422 which is wrong for the BIGINT_MAX boundary case)
- BAD: `assert resp.status_code == 404` alone (over-constrained — slot at BIGINT_MAX could legitimately exist in seed data)

Every assertion in the new test file MUST be semantic, not shape-only.

## Subagent Result Contract

When your work is complete, report results in this JSON structure:

```json
{
  "step": "S03",
  "agent": "Tests",
  "work_item": "I-00110",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/dashboard/test_keep_alive_slot_overflow.py",
    "tests/dashboard/test_schemathesis_contract.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "tests/dashboard/test_keep_alive_slot_overflow.py: 6 passed, 0 failed",
  "tdd_red_evidence": "n/a — dedicated coverage step (tests-impl); RED evidence is in S01 report (in-process probe showed pre-fix DELETE/PATCH -> 500 with psycopg.errors.NumericValueOutOfRange, post-fix -> 422 with slot_id in detail[].loc).",
  "blockers": [],
  "notes": "Pre-S01 RED semantics: test_delete_slot_overflow_returns_422_not_500 and test_toggle_slot_overflow_returns_422_not_500 would have failed with `AssertionError: assert 500 == 422` against pre-S01 code; test_delete_slot_zero_returns_422 and test_toggle_slot_negative_returns_422 would have failed because the unbounded `int` accepted 0 and -1, falling through to the service which returned 404 (not 422). KNOWN_CONTRACT_5XX is now {} — both entries removed cleanly; JSON_API_FUZZ_PATHS derivation unchanged."
}
```

- `tdd_red_evidence`: use the `"n/a — …"` form — this is a dedicated coverage step (`tests-impl`), exempt from RED-first.
- `completion_status`: `complete` only if all six tests pass AND both `KNOWN_CONTRACT_5XX` entries are removed (not just one).
- `notes`: MUST include per-test reasoning about why each would have failed against pre-S01 code, AND a one-line confirmation that the allowlist removal is complete.
