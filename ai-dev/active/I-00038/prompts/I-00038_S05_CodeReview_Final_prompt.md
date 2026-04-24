# I-00038_S05_CodeReview_Final_prompt

**Work Item**: I-00038 -- Dashboard hangs when multiple tabs are open (SSE connection exhaustion)
**Step**: S05
**Agent**: code-review-final-impl

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Same guards. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `ai-dev/active/I-00038/I-00038_Issue_Design.md`
- All step reports: `ai-dev/active/I-00038/reports/I-00038_S0{1,2,3,4}_*_report.md`
- All files touched by S01 and S03 (see `files_changed` in each report)
- `CLAUDE.md` and `dashboard/CLAUDE.md`

## Output Files

- `ai-dev/active/I-00038/reports/I-00038_S05_CodeReview_Final_report.md`

## Context

Final cross-layer review. Per-agent reviews have already been done; your job is to catch integration issues and completeness gaps they could not.

## Review Checklist

### 1. Completeness vs design document

Open `I-00038_Issue_Design.md` and verify each section is fully realized:

- **Affected Components table** → every file listed has the expected change; no file listed is untouched.
- **Fix Plan** table → every step has a corresponding report; no step is missing.
- **Acceptance Criteria** AC1–AC7 → each has code OR test evidence:
  - AC1 — multi-tab responsiveness: covered by S01 + S03 browser test.
  - AC2 — connection count ≤ 1: covered by S03 reproduction test.
  - AC3 — fallback path: covered by S01 client implementation; test either exists or is explicitly deferred with rationale.
  - AC4 — all event types fan out: covered by worker fanout logic in S01 + event-type test in S03.
  - AC5 — regression test exists: confirm `tests/dashboard/browser/test_sse_shared_worker.py` is collected by pytest.
  - AC6 — zero `new EventSource('/api/stream/events')` in `dashboard/templates/`.
  - AC7 — job-specific `EventSource` usages preserved.
- **File Manifest** → every file exists at the claimed path.

### 2. The architectural guard (CRITICAL)

Run this grep yourself:

```bash
grep -rn "new EventSource\\s*(\\s*['\"]\\s*/api/stream/events" dashboard/templates/
```

The result MUST be empty. If ANY match remains, this is a CRITICAL finding — the bug is not fully fixed.

Also verify out-of-scope usages are preserved:

```bash
grep -rn "new EventSource(" dashboard/templates/
# expected: only matches for other stream URLs (docs, oss, code job streams)
```

### 3. Cross-agent consistency

- The event-type names hardcoded in `sse-shared-worker.js` match the client-facing SSE event names emitted by `_event_generator` in `dashboard/routers/sse.py` — specifically the `yield f"event: ..."` lines (currently `sse.py:180,190,200,210,223`): `running-update`, `status-update`, `test-update`, `quality-update`, `toast`. A mismatch causes silent drops. Do NOT look at `_WATCHED_EVENTS` — that constant is a set of `DaemonEvent.event_type` values (`step_started`, `batch_completed`, etc.) used to filter the DB query, not the SSE names forwarded to the browser.
- The handler signature `iwSSE.on(type, fn)` contract is the same in the client, in every migrated page, and in the test assertions.
- `sse-client.js` is loaded in `base.html` BEFORE any `{% block scripts %}` content that calls `iwSSE.on(...)` — verify script order.

### 4. Integration points

- Open `./ai-core.sh dashboard start` (or use the worktree stack) and spot-check a page in the browser:
  - Open devtools → Network → filter by `stream/events`.
  - With two tabs open, confirm only ONE upstream connection is visible (it will live in the SharedWorker, not the page).
  - Confirm `iwSSE` is defined globally (`typeof iwSSE === 'object'`) on every migrated page.
- No circular imports, no dead code (old `var es = new EventSource(...)` blocks fully removed, not commented out).

### 5. Regression prevention is real

- The regression test runs as part of `make test-integration`. Run it yourself and observe it pass.
- The architectural grep in section 2 is documented in the design doc's **Regression Prevention** section and should be picked up by future `CodeReview_Final` runs via code-review convention (design doc is the canonical source).

### 6. Scope discipline

- **Server-side `sse.py` is unchanged.** If S01 modified `dashboard/routers/sse.py`, flag as HIGH (scope creep unless explicitly justified).
- **No other EventSource refactor.** OSS, docs, code-index SSE endpoints are intentionally untouched. Any migration of those is scope creep.
- **No new tests unrelated to this bug.**

### 7. `CLAUDE.md` compliance

- `dashboard/CLAUDE.md` rules: routers are thin; no docker/alembic from dashboard code; Tailwind is prebuilt (no new dynamic class strings).
- Project `CLAUDE.md` rules: no live-DB connections in tests; no `importlib.reload(orch.config)`; testcontainer URL replacement applied.

### 8. Browser-compat notes are accurate

- The fallback path in `sse-client.js` actually triggers on `typeof SharedWorker === 'undefined'` and on worker instantiation errors (e.g. CSP violation, private-browsing restrictions). Walk the code.

## Test Verification (NON-NEGOTIABLE)

```bash
make lint
make format          # format-check
make typecheck
make test-unit
make test-integration
```

All must pass. Any integration test failure is CRITICAL.

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| CRITICAL | Stray `new EventSource('/api/stream/events')` remains, or event-type list is out of sync with server, or test suite fails | Must fix |
| HIGH | Missing AC coverage, scope creep into server-side SSE, missing base.html include | Must fix |
| MEDIUM (fixable) | Inconsistent naming, incomplete fallback path | Should fix |
| MEDIUM (suggestion) | Better structure / docstrings | Optional |
| LOW | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "I-00038",
  "steps_reviewed": ["S01", "S02", "S03", "S04"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```
