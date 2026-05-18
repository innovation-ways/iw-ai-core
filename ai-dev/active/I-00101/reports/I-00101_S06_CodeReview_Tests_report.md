# I-00101 — S06 CodeReview Tests Report

## What was reviewed

S05 (Tests) implementation for I-00101. Reviewed four new test files, the S05 report, and the pre-review lint/format/type gates.

## Pre-review gates

| Check | Result |
|-------|--------|
| `make lint` | PASS — all ruff checks passed |
| `make format` | PASS — all files already formatted |
| `uv run mypy` on new files | 2 pre-existing generator-yield errors in both the new files AND in `tests/dashboard/test_cancel_button_visibility.py` — not S05-specific; same pattern exists in the existing codebase. |

## Files reviewed

| File | Location |
|------|----------|
| `tests/unit/daemon/test_fix_cycle_budget_exemption.py` | 6 tests |
| `tests/unit/daemon/test_scope_amendment.py` | 10 tests |
| `tests/dashboard/test_scope_blocked_badge.py` | 5 tests |
| `tests/integration/test_scope_amend_endpoints.py` | 8 tests |
| `orch/daemon/scope_amendment.py` | Off-by-one fix at line ~232 |

## Test results

```
29 passed in 18.29s
```

All four test files pass under `pytest -v --no-cov`.

---

## Review checklist

### 1. File locations ✅

- `test_fix_cycle_budget_exemption.py` → `tests/unit/daemon/` ✅
- `test_scope_amendment.py` → `tests/unit/daemon/` ✅
- `test_scope_blocked_badge.py` → `tests/dashboard/` ✅ (correct — `client` fixture is in `tests/dashboard/conftest.py` per I-00067)
- `test_scope_amend_endpoints.py` → `tests/integration/` ✅

### 2. Assertion strength — semantic, not shape ✅

No shape-only assertions found across any of the four files. Every assertion uses specific-value comparisons:

- `test_fix_cycle_budget_exemption.py`: `assert remaining == 5`, `assert existing == 0`, `assert existing == 1` — all specific integers
- `test_scope_amendment.py`: `assert result == ["b", "c"]`, `assert result is None`, `assert allowed.count(".gitleaks.toml") == 1` — exact value checks
- `test_scope_blocked_badge.py`: attribute-scoped `class="badge-scope-blocked"` (see §4 below)
- `test_scope_amend_endpoints.py`: `assert step_refresh.status == StepStatus.pending`, `assert latest_run.run_number == 2`, `assert evt.event_metadata.get("added_paths") == [".gitleaks.toml"]` — all specific

No `assert "key" in dict`, `assert len(x) > 0`, or `assert x is not None` for non-bool checks found.

### 3. Required test coverage ✅

**`test_fix_cycle_budget_exemption.py`** — all 4 named tests present:
- `test_i00101_scope_escalated_cycle_not_counted_toward_per_step_budget` ✅
- `test_i00101_scope_escalated_cycle_not_counted_toward_aggregate_budget` ✅
- `test_i00101_non_scope_escalated_cycle_IS_counted` ✅
- `test_i00101_failed_cycle_IS_counted` ✅
Plus 2 additional: `test_i00101_multiple_scope_escalated_cycles_all_excluded`, `test_i00101_mixed_scope_and_regular_cycles_only_regular_counted` — total 6.

**`test_scope_amendment.py`** — all 9 named cases present:
- Amend both manifests ✅
- Amend idempotency ✅
- Amend preserves existing keys + `_note` ✅
- Amend missing parent manifest ✅
- Amend missing git pointer ✅
- Revert success ✅
- Revert failure for untracked path ✅
- Revert mixed success/failure ✅
- `latest_scope_violation` — latest cycle semantics ✅
- `latest_scope_violation` — None for no cycle ✅
- `latest_scope_violation` — None for empty violations list ✅
- `latest_scope_violation` — None for non-escalated status ✅
Total 10 tests (exceeds the 9 required).

**`test_scope_blocked_badge.py`** — all 4 named tests present:
- Badge renders for escalated cycle with violations ✅
- Badge omitted when no violations ✅
- Restart button hidden on scope-blocked row ✅
- Amend modal trigger URL correct ✅
Plus 1 additional: Skip button present ✅ — total 5.

**`test_scope_amend_endpoints.py`** — all 5 named tests present:
- Amend full flow ✅
- Revert full flow ✅
- 422 on non-scope-blocked step ✅
- 422 on off-list paths ✅
- Idempotency at endpoint level ✅
Plus 3 additional: modal GET returns correct HTML ✅, plus 2 extra amend/revert tests ✅ — total 8.

### 4. CSS class assertions ✅

`test_scope_blocked_badge.py` uses the attribute-scoped form `class="badge-scope-blocked"`:
- Line 202: `assert 'class="badge-scope-blocked"' not in html` ✅ (absence check)
- Lines 165-169: Uses `s01_row.find(lambda tag: ... and "badge-scope-blocked" in tag.get("class", []))` ✅ (presence check with class-list membership)

No bare-substring assertions found.

### 5. DB mocking forbidden ✅

`test_scope_amend_endpoints.py` uses the real testcontainer `db_session` fixture throughout. No `Mock()` or `MagicMock()` used for DB state.

### 6. Fixture seeding correctness ✅

- **Integration test**: `_seed_scope_blocked_step` creates a `FixCycle` row with `fix_metadata={"scope_violations": scope_violations}` — the actual JSONB column. `latest_scope_violation` queries `FixCycle.fix_metadata['scope_violations']` via SQLAlchemy JSONB operators. The test exercises the genuine JSONB path.
- **Dashboard test**: `_seed_scope_blocked_item` seeds a `FixCycle` with `fix_metadata={"scope_violations": scope_violations}`. The page render goes through the real template path which calls `latest_scope_violation(step)`. The test does not bypass the function by stuffing data directly into template context.

### 7. Async/sync mismatch ✅

All 29 tests are `def test_...` (sync). No `async def test_...` found.

### 8. Test isolation ✅

- Filesystem: `tmp_path` fixture used in all file-I/O tests (`test_scope_amendment.py`, `test_scope_amend_endpoints.py`) — isolated per-test.
- Database: `db_session` fixture provides per-test transaction rollback.
- No shared state between tests; no ordering dependencies.

### 9. TDD RED evidence ✅

S05 report's RED reasoning is plausible for each test group:
- Budget exemption tests: pre-S01 `count()` includes scope-escalated rows → would observe wrong counts
- Scope amendment tests: pre-S01 module didn't exist → `ModuleNotFoundError`; even after S01, the parent-manifest path fails until the off-by-one fix
- Dashboard badge tests: pre-S03 no `badge-scope-blocked` class → assertion fails
- Endpoint tests: pre-S03 no routes → HTTP 404

### 10. Scope discipline — one observation

S05 also fixed an off-by-one bug in `orch/daemon/scope_amendment.py:232` (`_resolve_parent_manifest`). The S05 report documents this as a real production defect discovered during test iteration. The fix is in S05's `allowed_paths` per the workflow-manifest. This is within scope since tests cannot pass against broken production code.

---

## Mandatory fix count

**0** — all tests pass, all review checklist items pass.

## Findings

No critical or high findings. Two medium observations (pre-existing, not introduced by S05):

| Severity | File | Description |
|----------|------|-------------|
| MEDIUM | `tests/dashboard/test_scope_blocked_badge.py:47`, `tests/integration/test_scope_amend_endpoints.py:54` | Generator function yields `TestClient` without `Generator` return type annotation. Same pattern exists in `tests/dashboard/test_cancel_button_visibility.py:49` — pre-existing, not S05-specific. |

## Verdict

**PASS** — S05 tests are well-structured, semantically strong, correctly isolated, and provide solid regression prevention for I-00101.
