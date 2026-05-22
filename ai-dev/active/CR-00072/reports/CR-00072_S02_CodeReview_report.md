# CR-00072 — S02 Code Review Report

**Work item**: CR-00072 — Contract / No-5xx Route Sweep + schemathesis Fuzzing
**Step**: S02 (code-review-impl)
**Reviewed**: S01 (backend-impl)
**Date**: 2026-05-22
**Reviewer**: S02 CodeReview agent

---

## What was reviewed

S01's implementation of CR-00072 — a test-only CR that adds a no-5xx route-contract sweep and a nightly schemathesis fuzz module. Reviewed against the design document's acceptance criteria (AC1–AC6), TDD approach, and the S02 review checklist.

---

## Pre-Review Gates

| Gate | Command | Result |
|------|---------|--------|
| Lint | `make lint` | ✅ All checks passed |
| Format check | `make format-check` | ✅ All files formatted |
| Assertion scanner | `make test-assertions` | ✅ No new violations |

No new violations introduced by S01 in any gate.

---

## Review Findings

### Scope Discipline (CRITICAL category)

**CRITICAL check 1**: No production code touched.
- `git diff origin/main -- dashboard/ orch/ executor/ scripts/` → **empty**
- `tests/dashboard/test_route_contract_sweep.py` and `test_schemathesis_contract.py` are pure test files; no throwaway `__cr72_*` route remains in committed code.

**CRITICAL check 2**: No deliberate-break injection left behind.
- S01 registered throwaway routes on the test app only, demonstrated the failures, then removed them.
- `git diff origin/main` confirms no residual `__cr72_*` route in either test file.

✅ **PASS** — zero CRITICAL scope violations.

---

### AC1 — Route sweep correctness

| Check | Detail |
|-------|--------|
| Enumerates `app.routes` | ✅ `_collect_get_routes()` iterates `app.routes`, filters GET/HEAD, skips `SKIP_ROUTES` |
| `raise_server_exceptions=False` | ✅ `TestClient(app, raise_server_exceptions=False)` in `sweep_client` fixture |
| Asserts `status_code < 500` | ✅ `assert response.status_code < 500` with route-naming error message |
| Parametrized one case per route | ✅ `pytest_generate_tests` generates `pytest.param(method, path, id=f"{method} {path}")` |
| Skip set documented | ✅ `SKIP_ROUTES` (14 entries) — SSE/streaming, static mount, OpenAPI/Swagger, AI-runtime-gated chat — each with one-line rationale |
| `UNRESOLVED` paths asserted | ✅ `test_unresolved_routes_match_expected` guards against silent drift |

✅ **AC1 met.**

---

### AC2 — Blocking gate — no new QV gate introduced

The sweep lives under `tests/dashboard/`, so `make test-integration` collects it automatically. The S01 report explicitly confirms "no new canonical QV gate" and the design document §5 gate table entry shows it runs as part of `make test-integration`.

✅ **AC2 met.**

---

### AC3 — schemathesis module + marker exclusion

| Check | Detail |
|-------|--------|
| `schemathesis>=4,<5` in `[dependency-groups] dev` | ✅ `pyproject.toml` line 107 |
| `uv lock` consistent | ✅ `uv sync --frozen` → 0 packages changed |
| `contract_fuzz` marker registered | ✅ `pyproject.toml` line 171 |
| `addopts` excludes `contract_fuzz` | ✅ `pyproject.toml` line 162: `-m 'not browser and not quarantine and not contract_fuzz'` |
| `--strict-markers` present | ✅ present in `addopts` |
| Marker exclusion actually works | ✅ `pytest tests/dashboard/test_schemathesis_contract.py --collect-only` → "no tests collected (2 deselected)" |
| JSON API paths only (not HTML/htmx) | ✅ `JSON_API_PATHS` = keep-alive API + runtime-overrides; route sweep covers the HTML/htmx surface |

✅ **AC3 met.**

---

### AC4 — Nightly workflow

| Check | Detail |
|-------|--------|
| Triggers on `schedule` + `workflow_dispatch` | ✅ `.github/workflows/contract-fuzz.yml`: `cron: "17 3 * * *"` + `workflow_dispatch: {}` |
| Never on `push` / `pull_request` | ✅ Confirmed — no `push` or `pull_request` triggers in the workflow |
| Runs `make test-contract-fuzz` | ✅ `uv run make test-contract-fuzz` in steps |
| `continue-on-error: true` (burn-in) | ✅ `jobs.contract-fuzz.continue-on-error: true` |
| Environment mirrors `test-quality.yml` | ✅ PostgreSQL service, `IW_CORE_DB_*`, `uv sync`, alembic migration — coherent |

✅ **AC4 met.**

---

### AC5 — Genuine 5xx handled correctly

| Check | Detail |
|-------|--------|
| `EXPECTED_5XX` entries have `TODO(file-incident)` placeholder | ✅ One entry: `/project/{project_id}/docs/{doc_id}/pdf` with full `TODO(file-incident)` rationale |
| Each `xfail`-ed | ✅ `pytest.mark.xfail(strict=True)` applied to the parametrized case |
| Each surfaced as operator follow-up | ✅ S01 report "Operator follow-up" section lists 3 items (PDF cache permission, BIGINT overflow, `/openapi.json` ForwardRef) |
| No incident package created inside worktree | ✅ Confirmed — no `ai-dev/active/I-*` in the changeset |
| Sweep exits 0 on current `main` | ✅ `make test-route-sweep` → 124 passed, 1 xfailed, 0 unexpected failures |

✅ **AC5 met.**

---

### AC6 — Docs / skill / plan

| Check | Detail |
|-------|--------|
| `docs/IW_AI_Core_Testing_Strategy.md` describes Layer 6 (§2) | ✅ §2 "Layer 6 — Contract tests" with table row; §5 gate table rows 3.2 (route sweep) and 3.2b (schemathesis) present; §9 row 3.2 ✅ |
| `skills/iw-ai-core-testing/SKILL.md` §11 notes contract layer + extend | ✅ §11 "Contract test layer" with module table, honest-sweep rules, extension guide |
| `.claude/skills/iw-ai-core-testing/SKILL.md` byte-identical to master | ✅ `diff` → "IDENTICAL" |
| `ai-dev/work/TESTS_ENHANCEMENT.md` item 3.2 → DONE | ✅ `DONE 2026-05-21 (CR-00072)`; §11 changelog entry (7 lines) added; §9 row 3.2 ✅ |

✅ **AC6 met.**

---

### Test Quality & Isolation

| Check | Detail |
|-------|--------|
| Uses testcontainer `db_session` | ✅ Both `sweep_client` and `contract_app` fixtures take `db_engine`, `db_session`, `test_project` |
| No live DB (port 5433) touched | ✅ `monkeypatch.setattr(session_module, "_engine", db_engine)`, `monkeypatch.delenv("IW_CORE_EXPECTED_INSTANCE_ID")` — orch DB engine rebound to testcontainer |
| Order-independent | ✅ Per-test `db_session` (function-scoped, rolled back); `pytest-randomly` on; `test_route_returns_no_5xx` is parametrized with no cross-case state |
| Strong behavioural assertions | ✅ `assert response.status_code < 500` — would fail on any 5xx regression; error message names the route |

✅ **Quality standards met.**

---

### TDD RED Evidence

The S01 report's `tdd_red_evidence` section records:

- **Route sweep**: throwaway `GET /__cr72_selfcheck__` raising `RuntimeError` registered on the test app; the sweep picked it up and failed with `AssertionError: Route GET /__cr72_selfcheck__ returned HTTP 500. assert 500 < 500`; route removed.
- **schemathesis**: throwaway JSON `GET /__cr72_jsonfuzz__` raising `RuntimeError` added to the fuzz target; schemathesis reported `SUBFAILED ...[GET /__cr72_jsonfuzz__]` on the `not_a_server_error` check; route removed.
- `git diff origin/main -- dashboard/ orch/` confirmed empty in both cases.

✅ **RED evidence present and credible.**

---

## Test Execution Results

### Route sweep (`make test-route-sweep`)
```
124 passed, 1 xfailed in 50.20s
```
- 123 parametrized route cases (122 pass + 1 xfail)
- 2 meta tests pass (`test_unresolved_routes_match_expected`, `test_route_sweep_covers_a_meaningful_surface`)

### schemathesis (`make test-contract-fuzz`)
```
2 passed, 5 subtests passed in 27.76s
```
- Guard test (`test_json_api_paths_exist_in_schema`): PASS
- Fuzz test (`test_json_api_never_returns_5xx`): PASS (5 subtests — all JSON API operations passed the `not_a_server_error` check)

### Marker exclusion
```
uv run pytest tests/dashboard/test_schemathesis_contract.py --collect-only -q
no tests collected (2 deselected) in 21.67s
```
✅ schemathesis tests are **not collected** by the default selection — they would not run in the blocking suite.

---

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "CR-00072",
  "step_reviewed": "S01",
  "verdict": "pass",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "Route sweep: 124 passed, 1 xfailed (EXPECTED_5XX) in 50.20s. schemathesis: 2 passed, 5 subtests passed in 27.76s. Marker exclusion verified: 2 deselected on default collection. All pre-review gates passed (lint, format-check, assertion-scanner, uv sync --frozen).",
  "notes": "S01 is a clean, complete implementation. Zero CRITICAL or HIGH findings. The deliberate-break demonstration (both route-sweep and schemathesis RED failures, then reverted) provides credible TDD evidence. Operator follow-up items for the 3 genuine pre-existing 5xx are correctly surfaced in the S01 report without creating incident packages inside the worktree."
}
```

---

## Summary

S01 (backend-impl) passes all AC checks, all review checklist items, and all pre-review gates. The implementation is faithful to the design document: the route sweep correctly uses `raise_server_exceptions=False` and asserts `status_code < 500`; schemathesis is excluded from the default suite via the `contract_fuzz` marker; the nightly workflow is cron-only; genuine 5xx are correctly allowlisted with `TODO(file-incident)` placeholders surfaced as operator follow-up; the skill is synced; the docs and plan are updated. No production code was touched and no throwaway routes remain. **S01 is approved.**