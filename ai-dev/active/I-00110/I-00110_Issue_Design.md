# I-00110: Keep-alive slot endpoints return HTTP 500 (psycopg NumericValueOutOfRange) on out-of-BIGINT slot_id path param

**Type**: Issue
**Severity**: Low-to-Medium
**Created**: 2026-05-24
**Reported By**: CR-00072 schemathesis property-fuzz allowlist (`tests/dashboard/test_schemathesis_contract.py:97-108`)
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt. This incident does NOT touch docker.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. **This incident leaves migrations unchanged.** No DB schema change — the `BIGINT` column is fine; the fix is at the FastAPI route boundary.

## Description

Two sibling handlers in `dashboard/routers/keep_alive.py` — `DELETE /api/keep-alive/slots/{slot_id}` and `PATCH /api/keep-alive/slots/{slot_id}/toggle` — declare `slot_id: int` as a FastAPI path parameter without an upper bound. Because Python `int` has no native width limit, FastAPI/Pydantic accept arbitrarily large integers and pass them straight to a SQL query against a PostgreSQL `BIGINT` column. When the caller supplies a `slot_id` above `2**63 - 1`, psycopg raises `psycopg.errors.NumericValueOutOfRange`, which propagates as an unhandled exception and surfaces as **HTTP 500**. The endpoints exist for human operators on the `/system/keep-alive` page; the resulting 5xx is a low-grade DoS smell (unauthenticated callers can poke the dashboard with one curl and crash error logs), with no data corruption or auth bypass.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Notably:
- Routers are thin (`dashboard/CLAUDE.md`) — validation belongs at the route boundary.
- Tests under `tests/dashboard/` use the FastAPI `client` fixture (see `tests/CLAUDE.md`); a test placed elsewhere will fail with `fixture 'client' not found` (I-00067).
- pytest-randomly is on by default — every new test must be order-independent.

## Browser Evidence

`browser_verification: false`. The bug class was surfaced by the schemathesis property-fuzz layer (CR-00072, merged 2026-05-22), not by browser interaction. New browser-evidence capture is skipped per the operator's instructions; the **`KNOWN_CONTRACT_5XX` allowlist entries in `tests/dashboard/test_schemathesis_contract.py:97-108` ARE the evidence**. Reproduced verbatim below:

```
KNOWN_CONTRACT_5XX: dict[str, str] = {
    "/api/keep-alive/slots/{slot_id}": (
        "TODO(file-incident): the keep-alive slot endpoints take an unbounded "
        "int path param and pass it straight to a BIGINT keyed query; an id "
        "above 2**63-1 raises psycopg NumericValueOutOfRange (-> HTTP 500) "
        "instead of 404/422. Genuine pre-existing handler bug."
    ),
    "/api/keep-alive/slots/{slot_id}/toggle": (
        "TODO(file-incident): same BIGINT-overflow 5xx as the slot DELETE "
        "endpoint — an out-of-int64-range slot_id path param raises psycopg "
        "NumericValueOutOfRange (-> HTTP 500). Genuine pre-existing handler bug."
    ),
}
```

Verification is via TestClient assertions, not a browser run.

## Steps to Reproduce

1. Start the dashboard locally (`./ai-core.sh start`).
2. Fire:
   ```bash
   curl -X DELETE 'http://localhost:9900/api/keep-alive/slots/99999999999999999999'
   ```
   Observe HTTP 500.
3. Fire:
   ```bash
   curl -X PATCH 'http://localhost:9900/api/keep-alive/slots/99999999999999999999/toggle'
   ```
   Observe HTTP 500.
4. Inspect logs — see `psycopg.errors.NumericValueOutOfRange` traceback.

**Expected**: Both endpoints reject out-of-range `slot_id` with a clean **HTTP 422** (validation error at the route boundary). Never HTTP 500.

**Actual**: HTTP 500 with an unhandled `psycopg.errors.NumericValueOutOfRange` propagating from the SQL driver.

## Root Cause Analysis

Both handlers declare `slot_id: int` without a `Path(..., le=2**63 - 1)` bound:

- `dashboard/routers/keep_alive.py:175-176` — `@router.delete("/api/keep-alive/slots/{slot_id}")` → `def delete_slot(slot_id: int, ...)`
- `dashboard/routers/keep_alive.py:187-188` — `@router.patch("/api/keep-alive/slots/{slot_id}/toggle")` → `def toggle_slot(slot_id: int, ...)`

FastAPI/Pydantic accept Python `int` values exceeding PostgreSQL `BIGINT` (max `2**63 - 1`) because Python `int` is unbounded. The values flow into `orch/keep_alive_service.py:delete_slot` (line 102) and `orch/keep_alive_service.py:toggle_slot` (line 112), which build SQL queries against a `BIGINT` keyed column. psycopg raises `NumericValueOutOfRange` server-side, which is not caught anywhere on the path back up. The dashboard's default exception handling produces HTTP 500.

**Why didn't existing tests catch it?** The TestClient-driven dashboard tests only exercise in-range slot IDs. The bug surfaced only after CR-00072 introduced schemathesis property-fuzz, which generated random `int64`-overflow inputs. Rather than block the fuzz suite, CR-00072 added both routes to `KNOWN_CONTRACT_5XX` and filed a follow-up TODO — this incident.

## Affected Components

| Component | File | Impact |
|-----------|------|--------|
| Dashboard route — DELETE | `dashboard/routers/keep_alive.py:175-176` | Returns HTTP 500 on out-of-BIGINT `slot_id` instead of 422 |
| Dashboard route — PATCH toggle | `dashboard/routers/keep_alive.py:187-188` | Returns HTTP 500 on out-of-BIGINT `slot_id` instead of 422 |
| Schemathesis allowlist | `tests/dashboard/test_schemathesis_contract.py:97-113` | Currently excludes both routes from fuzzing; both entries must be removed once fix lands |

## Fix Plan

### Agents and Execution Order

> **Step-granularity rule**: each implementation step targets one cohesive concern. The fix has two cohesive concerns — the route-boundary `Path(...)` bound (S01 Backend) and the regression test suite + schemathesis allowlist cleanup (S03 Tests). They are split so each gets its own per-agent code review, matching the canonical incident pattern used by I-00107..I-00111.

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Backend | Add `Path(..., ge=1, le=_BIGINT_MAX)` to both `slot_id` parameters in `dashboard/routers/keep_alive.py` via the `Annotated[int, Path(...)]` form. Introduce `_BIGINT_MAX = 2**63 - 1` as a module-level constant with a short comment referencing I-00110. Do NOT touch `orch/keep_alive_service.py`. Do NOT create test files (tests live in S03). | — |
| S02 | CodeReview | Per-agent review of S01 (route-boundary fix only) | — |
| S03 | Tests | Create `tests/dashboard/test_keep_alive_slot_overflow.py` with the six regression tests verbatim from `## Test to Reproduce`. Remove both `KNOWN_CONTRACT_5XX` entries from `tests/dashboard/test_schemathesis_contract.py` (the `JSON_API_FUZZ_PATHS` filter recomputes automatically). All six tests must PASS against the S01-fixed handlers. As a dedicated coverage step, S03 is RED-exempt — the RED evidence is owned by S01's pre-/post-fix in-process probe; S03 documents per-test pre-S01 failure reasoning in its `notes` but MUST NOT revert S01 at runtime. | — |
| S04 | CodeReview | Per-agent review of S03 (tests + allowlist edit) | — |
| S05 | CodeReview_Final | Global cross-agent review of S01..S04 | — |
| S06..S13 | QV Gates | lint, format, typecheck, arch-check, security-sast, unit-tests, frontend-tests (alias for dashboard-tests), integration-tests | — |
| S14 | SelfAssess | Self-assessment (project has `self_assess = true`) | — |

**Step count**: 14 (matches the canonical incident pattern — every other recent incident in this project uses Backend → CodeReview → Tests → CodeReview → CodeReview_Final → QV gates → SelfAssess).

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: No migration. The `BIGINT` column itself is correct; the fix is purely at the route boundary.

### Code Changes

- **Files to modify**:
  - `dashboard/routers/keep_alive.py` — add `Path(..., ge=1, le=2**63 - 1)` to both handlers (the fix).
  - `tests/dashboard/test_schemathesis_contract.py` — remove both `KNOWN_CONTRACT_5XX` entries (the `JSON_API_FUZZ_PATHS` filter recomputes automatically).
- **Files to create**:
  - `tests/dashboard/test_keep_alive_slot_overflow.py` — new regression test file.
- **Nature of change**: route-boundary input validation. The simplest, cheapest fix; aligns with FastAPI conventions; produces a clean 422 with a structured message the caller can parse.

### Why 422 (route-boundary) and not 404 (service-layer)

The skill text suggested both. The design picks **422 at the route boundary** because:
1. It is the cheapest fix (one `Path()` per handler).
2. It is the most informative — the caller knows immediately the value was *invalid*, not that the resource was *missing*.
3. It is consistent with FastAPI's idiomatic handling of constrained path params.
4. It catches the bad value before any DB round-trip — no SQL noise in logs.

A defensive `try/except psycopg.errors.NumericValueOutOfRange` in the service layer is intentionally NOT added — it would only fire if a future caller somehow bypassed the route-level validation (e.g., a new route reusing the service), and the empty service-layer catch would mask a real bug. If a future endpoint needs the same validation, it should re-apply the `Path(...)` constraint at its own boundary.

## File Manifest

All files for this work item live under `ai-dev/active/I-00110/`:

| File | Type | Purpose |
|------|------|---------|
| `I-00110_Issue_Design.md` | Design | This document |
| `I-00110_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I-00110_S01_Backend_prompt.md` | Prompt | S01 route-boundary fix |
| `prompts/I-00110_S02_CodeReview_Backend_prompt.md` | Prompt | S02 per-agent review of S01 |
| `prompts/I-00110_S03_Tests_prompt.md` | Prompt | S03 regression tests + allowlist edit |
| `prompts/I-00110_S04_CodeReview_Tests_prompt.md` | Prompt | S04 per-agent review of S03 |
| `prompts/I-00110_S05_CodeReview_Final_prompt.md` | Prompt | S05 global code review |
| `prompts/I-00110_S14_SelfAssess_prompt.md` | Prompt | S14 self-assessment |

Reports are created during execution in `ai-dev/work/I-00110/reports/`.

## Test to Reproduce

Place this in `tests/dashboard/test_keep_alive_slot_overflow.py` (uses the dashboard `client` fixture; goes under `tests/dashboard/`):

```python
"""Regression tests for I-00110.

The dashboard's keep-alive slot endpoints previously returned HTTP 500
(psycopg.errors.NumericValueOutOfRange) when handed a slot_id above
2**63 - 1 (the PostgreSQL BIGINT max). FastAPI now bounds the path param
at the route boundary, so out-of-range values surface as HTTP 422.
"""

BIGINT_MAX = 2**63 - 1
OVERFLOW = BIGINT_MAX + 1  # 9223372036854775808


def test_delete_slot_overflow_returns_422_not_500(client):
    """An out-of-BIGINT slot_id on DELETE must surface as 422, not 500."""
    resp = client.delete(f"/api/keep-alive/slots/{OVERFLOW}")
    assert resp.status_code == 422, resp.text
    # Semantic: response must mention the slot_id parameter and the bound.
    body = resp.json()
    assert "detail" in body
    # FastAPI's standard validation envelope. We assert the parameter
    # name appears so the caller can locate the failing field.
    assert any(
        "slot_id" in str(err.get("loc", ())) for err in body["detail"]
    ), body


def test_toggle_slot_overflow_returns_422_not_500(client):
    """An out-of-BIGINT slot_id on PATCH toggle must surface as 422, not 500."""
    resp = client.patch(f"/api/keep-alive/slots/{OVERFLOW}/toggle")
    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert "detail" in body
    assert any(
        "slot_id" in str(err.get("loc", ())) for err in body["detail"]
    ), body


def test_delete_slot_at_bigint_max_does_not_500(client):
    """The boundary value 2**63 - 1 must NOT be rejected — it's a valid
    BIGINT, just non-existent. Expect 404 (not found) not 422 (validation)."""
    resp = client.delete(f"/api/keep-alive/slots/{BIGINT_MAX}")
    # Either 404 (slot not found) or 200 (if a slot at MAX existed in seed).
    # Critically: NOT 422 and NOT 500.
    assert resp.status_code in (200, 404), resp.text


def test_toggle_slot_at_bigint_max_does_not_500(client):
    """The boundary value 2**63 - 1 must NOT be rejected on toggle either."""
    resp = client.patch(f"/api/keep-alive/slots/{BIGINT_MAX}/toggle")
    assert resp.status_code in (200, 404), resp.text


def test_delete_slot_zero_returns_422(client):
    """slot_id=0 violates the ge=1 lower bound — must be 422."""
    resp = client.delete("/api/keep-alive/slots/0")
    assert resp.status_code == 422, resp.text


def test_toggle_slot_negative_returns_422(client):
    """A negative slot_id violates ge=1 — must be 422."""
    resp = client.patch("/api/keep-alive/slots/-1/toggle")
    assert resp.status_code == 422, resp.text
```

All assertions are **semantic** — they verify specific status codes (422 vs 500 vs 404) AND the structured `detail.loc` content (the parameter name `slot_id` appears in the validation error). They do not merely check response shape.

## Acceptance Criteria

### AC1: Bug is fixed

```
Given the dashboard is running
When a client sends DELETE /api/keep-alive/slots/{slot_id} with slot_id > 2**63 - 1
Then the response is HTTP 422 with a FastAPI validation envelope mentioning slot_id
And the same applies to PATCH /api/keep-alive/slots/{slot_id}/toggle
```

### AC2: Regression test exists

```
Given the fix is applied
When the test suite runs
Then tests/dashboard/test_keep_alive_slot_overflow.py passes
And the two KNOWN_CONTRACT_5XX entries are removed from
    tests/dashboard/test_schemathesis_contract.py
And the schemathesis contract fuzz suite stays green with both routes
    back in JSON_API_FUZZ_PATHS
```

### AC3: In-range values still work

```
Given the fix is applied
When a client sends DELETE or PATCH toggle with a valid in-range slot_id
    (1 <= slot_id <= 2**63 - 1)
Then the response is the pre-fix behaviour (200 on success, 404 if not found)
And NEVER 422 due to the new bound
```

## Regression Prevention

1. **The regression test file** explicitly covers the overflow case, the BIGINT boundary, zero, and negative values. Any future regression that drops or weakens the `Path(...)` bound will fail at least one of these tests.
2. **Removing the `KNOWN_CONTRACT_5XX` entries** restores schemathesis fuzz coverage of both routes. The schemathesis suite generates arbitrary integer inputs every run; any new 5xx-on-overflow regression would be caught by the contract fuzz, not silently allowlisted.
3. **Convention reminder for future keep-alive routes**: any new endpoint that accepts `slot_id: int` (or any BIGINT-keyed id) MUST apply the same `Path(..., ge=1, le=2**63 - 1)` constraint at the route boundary. The S01 prompt mentions this explicitly so the reviewer can catch any new similar handlers.

## Dependencies

- **Depends on**: None
- **Blocks**: None
- **Related**: CR-00072 (the schemathesis property-fuzz layer that surfaced the bug). This is one of the operator-follow-up incidents from `ai-dev/work/TESTS_ENHANCEMENT.md` §10 "Phase 3 operator-follow-up incidents".

## Impacted Paths

- `dashboard/routers/keep_alive.py`
- `tests/dashboard/test_schemathesis_contract.py`
- `tests/dashboard/test_keep_alive_slot_overflow.py`

## TDD Approach

- **Reproducing test**: `tests/dashboard/test_keep_alive_slot_overflow.py::test_delete_slot_overflow_returns_422_not_500` and `::test_toggle_slot_overflow_returns_422_not_500` — both FAIL against the pre-fix handlers (would return 500) and PASS against the patched handlers (return 422).
- **Unit tests**: N/A — the change is at the FastAPI route boundary, not in a pure unit. Route-level behaviour is best tested via the dashboard TestClient (integration-flavoured but lives under `tests/dashboard/`).
- **Integration tests**: The schemathesis contract fuzz in `tests/dashboard/test_schemathesis_contract.py` is the integration-level regression net — once the two allowlist entries are removed, every fuzz run independently re-verifies that no overflow input crashes either route.

**RED evidence ownership under the Backend → Tests split** (per `skills/iw-workflow/SKILL.md` and the canonical pattern in I-00111):

- **S01 (Backend) captures RED at design-time, before applying the fix.** The S01 prompt requires a tiny in-process reproduction: instantiate the app with `create_app()`, drive `TestClient` against the unmodified handler with `slot_id = 2**63`, and capture the 500 response + `psycopg.errors.NumericValueOutOfRange` traceback. That snippet is recorded in S01's report `tdd_red_evidence` field. Then S01 applies `Path(..., ge=1, le=_BIGINT_MAX)`, re-runs the same in-process probe, and confirms the response is now 422.
- **S03 (Tests) is RED-exempt** — dedicated coverage steps (`tests-impl`) add tests after the code exists and are not RED-first by nature. S03's `tdd_red_evidence` field uses the `"n/a — dedicated coverage step; RED evidence is in S01 report (...)"` form. The agent MUST reason in S03's `notes` about whether each test would have failed against pre-S01 code (e.g. "test_delete_slot_overflow_returns_422_not_500 would have raised AssertionError with actual=500 against the pre-S01 unbounded handler"). The agent MUST NOT `git checkout`, `git stash`, or otherwise revert S01's source at runtime to "verify RED" — this is explicitly forbidden by the skill (thrash-prone, blocking on I-00073-style timeouts).

## Notes

- The fix is intentionally minimal — two `Path(...)` constraints, ~5-10 LOC. We do NOT add a defensive `try/except psycopg.errors.NumericValueOutOfRange` in the service layer (would mask future legitimate overflow bugs from new callers).
- `2**63 - 1` is the PostgreSQL `BIGINT` max. We pin this as a module-level constant in the handler file (or import from a shared constants module if one exists) so the magic number is explained in code.
- Schema-level alternative: a Pydantic constrained type (`PositiveInt` with a custom upper bound). Rejected because FastAPI `Path(..., ge=1, le=...)` is idiomatic for path params and avoids introducing a new type alias for a one-off constraint.
- No design-doc-tracker incident-link entry is needed — this is filed from `ai-dev/work/TESTS_ENHANCEMENT.md` §10.
- `browser_verification: false` — schemathesis allowlist entries ARE the evidence; verification is via TestClient assertions.
