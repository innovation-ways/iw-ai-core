# I-00111_S04_CodeReview_prompt

**Work Item**: I-00111 -- `GET /openapi.json` returns HTTP 500 — `create_app().openapi()` raises Pydantic `ForwardRef('Response')` error
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

Allowed exceptions:
  1. Testcontainers spun up by pytest fixtures.
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This step does NOT touch any Alembic migration.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00111 --json` is canonical.
- `ai-dev/active/I-00111/I-00111_Issue_Design.md` -- Design document (AC2 and AC3 are this step's review anchors)
- `ai-dev/work/I-00111/reports/I-00111_S03_Tests_report.md` -- S03 step report
- `tests/dashboard/test_openapi_schema.py` -- the new file created by S03
- `tests/dashboard/test_schemathesis_contract.py` -- the modified file (workaround removal)

## Output Files

- `ai-dev/work/I-00111/reports/I-00111_S04_CodeReview_report.md` -- Review report

## Context

You are reviewing the test work done in step S03 by the Tests agent for **I-00111**.

The S03 deliverables are: (a) a new regression test file with two semantic-correctness tests, and (b) removal of the schemathesis OpenAPI-generation workaround in the existing contract-fuzz test file. Your job is to catch:

1. **Shape-only assertions** that would let a regression slip through (I003 lesson).
2. **Incomplete workaround removal** — both the `_json_api_openapi` closure AND the `monkeypatch.setattr` line MUST be gone; either one left behind is a CRITICAL incompleteness.
3. **Full-suite test runs inside the step** — burns timeout budget.
4. **JSON_API_PATHS allow-list widening** — out of scope for this incident.

Read the design document AC2 and AC3 to understand the contract. Read the S03 report to understand what was done. Then review the two test files.

## Read the Design Document FIRST

- Read `## Acceptance Criteria` AC2 and AC3 — these are the literal contract for S03.
- Read `## TDD Approach` — note the two test names by path.
- Cross-check both test names against the S03 report's `files_changed`. If either is missing, **CRITICAL** finding.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Any NEW violations in `tests/dashboard/test_openapi_schema.py` or `tests/dashboard/test_schemathesis_contract.py` → CRITICAL finding.

## Review Checklist

### 1. Semantic correctness, not shape (I003 lesson)

Open `tests/dashboard/test_openapi_schema.py` and inspect every `assert` statement. For each assertion, ask: "would this assertion pass against a BUGGY but well-formed schema (e.g. the old `_json_api_openapi` workaround's partial schema)?"

- `assert "openapi" in schema` (alone) → BAD (shape only) → **HIGH** finding ("assertion is shape-only — would pass against a partial schema; pin a specific value")
- `assert schema["openapi"].startswith("3.")` → GOOD (semantic — specific value range)
- `assert "paths" in schema` (alone) → BAD (the partial workaround had this too)
- `assert len(schema["paths"]) > 0` → MEDIUM strength (the partial workaround had this too — the workaround returned ~6 routes)
- `assert len(schema["paths"]) > N` where N is a count significantly larger than the partial workaround's ~6 routes (e.g. > 20 if the full app has many more) → STRONG (semantic — pins "full app, not partial")

The PREFERRED form: a compound assertion combining `len(paths) > 0` AND `schema["openapi"].startswith("3.")` AND `schema["info"].get("title")` — three independent checks. If the file lacks any one of those three, raise a **MEDIUM (fixable)** finding.

### 2. Workaround removal is complete (AC3)

Open `tests/dashboard/test_schemathesis_contract.py` and search for any remaining traces of the workaround:

```bash
grep -nE "_json_api_openapi|monkeypatch.setattr.app, *.openapi" tests/dashboard/test_schemathesis_contract.py
```

- Any hit → **CRITICAL** finding ("workaround removal incomplete — `<grep_match>` still present; both the closure AND the monkeypatch line MUST be gone").

Also verify:
- The `contract_app` fixture's body ends with `yield app` directly after `app.dependency_overrides[get_db] = _override_get_db` (no intervening route-filtering / monkeypatch logic).
- The `contract_schema` fixture loads via `schemathesis.openapi.from_asgi("/openapi.json", contract_app)` against the real app (the call site is unchanged from pre-S03; the docstring should now describe it as the full-app schema).
- The module docstring at lines 21-30 (or wherever it now sits) references I-00111 and notes that the underlying ForwardRef bug was fixed. If the old "OpenAPI generation work-around" prose is still there verbatim, **HIGH** finding ("docstring not updated; reader will be misled about the test-app instrumentation").

### 3. JSON_API_PATHS allow-list NOT widened

```bash
git diff origin/main -- tests/dashboard/test_schemathesis_contract.py | grep -E "^[+-].*JSON_API_PATHS|^[+-].*KNOWN_CONTRACT_5XX|^[+-].*JSON_API_FUZZ_PATHS"
```

- Any `+` or `-` line touching those three lists → **HIGH** finding ("scope creep — this incident only removes the workaround; the fuzz allow-list is unchanged").

### 4. Test-file location, fixture usage, lazy imports

- `tests/dashboard/test_openapi_schema.py` MUST be under `tests/dashboard/` (the `client` fixture is registered only there — see `tests/CLAUDE.md`). A test placed elsewhere → **CRITICAL** finding (will fail at collection time with `fixture 'client' not found`).
- The in-process test (`test_i_00111_app_openapi_callable_returns_dict`) MUST import `from dashboard.app import create_app` INSIDE the function body, not at module top — otherwise the live-DB guard plumbing in `tests/dashboard/conftest.py` is not in effect at import time. Module-top import → **HIGH** finding.
- `from fastapi.testclient import TestClient` should be gated behind `if TYPE_CHECKING:` for the annotation only.

### 5. Targeted verification only — no full-suite runs in the step

Search the S03 report for evidence of `make test-integration`, `make test-unit`, `make check`, or `pytest tests/` (without a specific file path):

- Any such command in the report's verification narrative → **HIGH** finding ("S03 ran full-suite verification — burns step timeout budget; full-suite is S10/S11's job").
- The S03 report's `test_summary` field MUST cite both targeted commands (the new test file AND `test_json_api_paths_exist_in_schema -m contract_fuzz`) with their pass counts.

### 6. No production code changes in S03

```bash
git diff origin/main --name-only | grep -vE "^tests/|^ai-dev/"
```

- Any non-test, non-design file in S03's diff → **CRITICAL** finding ("S03 is a Tests step — production changes belong to S01; if S03 modified production code, the fix scope is being expanded silently").

### 7. Test names match design doc

The design doc's `## Test to Reproduce` section names two tests:
- `test_i_00111_openapi_endpoint_returns_valid_schema`
- `test_i_00111_app_openapi_callable_returns_dict`

Both names MUST appear in `tests/dashboard/test_openapi_schema.py`. Any rename → **MEDIUM (fixable)** finding ("test name drift from design — S05 cross-checks design's TDD section against `files_changed`; renamed tests cause spurious 'missing test' findings").

## Test Verification (NON-NEGOTIABLE)

Run the same targeted commands the Tests agent ran, plus the project's unit suite to verify no regressions:

```bash
uv run pytest tests/dashboard/test_openapi_schema.py -v --no-cov
uv run pytest tests/dashboard/test_schemathesis_contract.py::test_json_api_paths_exist_in_schema -v --no-cov -m contract_fuzz
make test-unit
```

Report results accurately in the result contract.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Workaround removal incomplete; production code change in S03; test in wrong directory | Must fix before merge |
| **HIGH** | Shape-only assertion; module-top `create_app` import; JSON_API_PATHS widening; full-suite run in step; docstring not updated | Must fix before merge |
| **MEDIUM (fixable)** | Missing one of the three compound semantic asserts; test name drift; convention drift | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Better assertion pattern available | Optional |
| **LOW** | Nitpick, style preference | Informational |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00111",
  "step_reviewed": "S03",
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

- `verdict`: `pass` if zero CRITICAL or HIGH findings AND zero MEDIUM (fixable) findings.
- `mandatory_fix_count`: count of CRITICAL + HIGH + MEDIUM (fixable) findings.
