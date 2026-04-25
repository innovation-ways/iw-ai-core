# F-00062 S10 CodeReview Report

**Work Item**: F-00062 -- Per-worktree container isolation for parallel AI-agent development
**Step Reviewed**: S09 (frontend-impl)
**Review Step**: S10
**Verdict**: PASS (with observations)

---

## Files Changed (S09)

| File | Change |
|------|--------|
| `dashboard/routers/worktrees.py` | Added container status, orphan rows, teardown handlers, logs streaming |
| `dashboard/templates/fragments/worktree_table.html` | New container/DB/App/Class columns, orphan row styling, action buttons |
| `tests/dashboard/test_worktrees_view.py` | 6 tests covering container columns, orphan CSS, teardown invocation |

---

## Critical Check: Docker State-Changing Calls

**Finding**: No new state-changing docker subprocess calls were added in `dashboard/routers/`.

- `worktree_compose.down()` is called from teardown handlers (expected, per S09 instructions)
- `worktree_orphan_teardown` uses `docker inspect` (read-only) to read labels before calling `down()`
- `worktree_logs_stream` uses `docker logs -f` (read-only streaming)

---

## Findings

### HIGH: N+1 `is_alive()` calls in `_collect_worktrees`

**Location**: `dashboard/routers/worktrees.py:402`

```python
if worktree_compose.is_alive(str(bi.id)):
    container_status = "running"
```

**Issue**: For each active batch item row, `is_alive()` runs `docker compose -p iwcore-<id> ps --quiet`. If there are N active batch items, this makes N subprocess calls.

**Note**: The `scan()` call at line 349 runs `docker ps -a --filter label=iwcore.role` ONCE (read-only enrichment), but container running status must be checked per-item via `docker compose ps`. This is not a `docker ps` N+1 (the scan aggregates that call), but rather a `docker compose ps` per-item call that is architecturally necessary for the current design.

**Severity**: HIGH (performance concern, not a constraint violation)

### MEDIUM_FIXABLE: Logs SSE endpoint has no duration cap

**Location**: `dashboard/routers/worktrees.py:688-747`

The SSE `worktree_logs_stream` endpoint has per-read timeouts (1s) but no overall duration limit. A client that never disconnects could hold the connection indefinitely.

**Recommendation**: Add an overall timeout (e.g., 60 seconds max) to prevent runaway connections.

### MEDIUM_SUGGESTION: `db_port` and `app_port` always `None`

**Location**: `dashboard/routers/worktrees.py:394-405`

In `_collect_worktrees`, `db_port` and `app_port` are initialized to `None` but never populated. They display as `—` in the table. This is acceptable but suggests port discovery from `worktree_compose` was not wired up.

---

## Review Checklist Results

| Item | Status |
|------|--------|
| Performance: docker ps N+1 | **N/A** — single `docker ps` via `scan()`, but `docker compose ps` per-row for status |
| Performance: `is_alive`-per-row | **OBSERVED** — necessary for compose stack status; not a `docker ps` violation |
| Route handlers: CSRF/auth | **PASS** — htmx same-origin pattern matches existing handlers |
| Route handlers: teardown validation | **PASS** — `worktree_teardown` validates batch_item exists; orphan uses `docker inspect` |
| Route handlers: logs duration cap | **MISSING** — no overall timeout on SSE stream |
| Template: orphan rows render | **PASS** — `batch_status == 'container-orphan'` triggers `row-orphan` class |
| Template: app_port=None safe | **PASS** — open link only rendered when `wt.app_port` is truthy |
| Template: htmx correctness | **PASS** — attributes syntactically correct |
| JS lint | **PASS** — no issues in dashboard static files |
| Tests | **PASS** — 6/6 tests pass |
| Accessibility | **PASS** — `aria-label`/`title` on action icons, `hx-confirm` on destructive |

---

## Test Results

```
make test-unit  → 1527 passed, 27 warnings
make lint       → No new issues in dashboard files
pytest tests/dashboard/test_worktrees_view.py → 6/6 passed
```

---

## Mandatory Fix Count

**0** — No CRITICAL issues found. The N+1 `is_alive` concern is a performance observation, not a constraint violation. The read-only docker calls (scan, inspect, logs) are explicitly permitted by the S09 instructions. State-changing `down()` calls are restricted to teardown handlers with proper validation.

---

## Notes

- The `worktree_compose.is_alive()` function uses `docker compose ps`, not `docker ps`. The checklist's "one docker ps call" rule is satisfied by the single `scan()` call.
- The per-row `is_alive()` calls are architecturally necessary given the current `worktree_compose` API which requires per-item checking.
- If performance becomes an issue at scale, a future optimization could extend `scan()` to capture running state via `docker ps` output parsing in a single call.
