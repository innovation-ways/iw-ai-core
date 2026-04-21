# F-00058_S08_Tests_prompt

**Work Item**: F-00058
**Step**: S08
**Agent**: tests-impl

---

## Input Files

- `ai-dev/active/F-00058/F-00058_Feature_Design.md` — Boundary Behavior + Invariants
- All prior reports

## Output Files

- `ai-dev/active/F-00058/reports/F-00058_S08_Tests_report.md`
- `tests/integration/test_oss_dashboard_boundary.py` (new)
- `tests/integration/test_oss_dashboard_sse.py` (new)
- `tests/integration/test_oss_dashboard_templates_extras.py` (new — invariant-driven renders)

(Tests in `test_oss_dashboard_routes.py`, `test_oss_dashboard_service.py`, `test_oss_dashboard_templates.py` were added in S03/S05/S06; this step fills gaps.)

## Context

Add tests covering every Boundary Behavior row and every Invariant from the design doc.

## Requirements

### 1. `tests/integration/test_oss_dashboard_boundary.py`

One test per Boundary Behavior row:
- disabled project → OSS tab absent, frame shows Install CTA, `/oss` redirects or renders install state
- no scans yet → gray pill + prominent Scan button
- scan in progress → pill shows spinner, Scan button disabled
- scan errored → pill previous color, banner with stdout_tail, rescan button
- HEAD advanced → stale banner, annotated pill
- Tier-1 missing → install modal preselected, Scan disabled
- concurrent scan → 409 + toast (client code) / 409 in API (server)
- SSE disconnect → replay-on-reconnect sends tail events
- prepare on dirty tree → throwaway worktree, user's tree untouched (spot check via fixture)
- delete project with active jobs → cascaded cleanup, worktrees removed

### 2. `tests/integration/test_oss_dashboard_sse.py`

- `test_sse_emits_status_progress_complete_in_order`
- `test_sse_reconnect_replays_tail` — open stream, kill connection, reopen, assert replay events precede live ones
- `test_sse_heartbeat_every_20s` — with monkeypatched sleep

### 3. Invariant tests

One test per invariant from the design doc:
- Inv #1 (no working-tree mutation): prepare via dashboard → user's working tree hash unchanged
- Inv #2 (monotonic status): attempting to transition running→queued fails or is ignored
- Inv #3 (orphan recovery): insert a `running` job older than startup → on service init, becomes `error`; matching `/tmp/oss-*` removed
- Inv #4 (SSE idempotent replay): same as dashboard_sse test above
- Inv #5 (pill color parity): dashboard pill color == F-00057 CLI status --json pill color for same scan
- Inv #6 (tab visibility): exactly iff `oss_enabled=true`
- Inv #7 (frame presence): frame rendered on every project page — iterate over /code, /tests, /quality, /documentation, /oss, assert frame fragment present in response HTML

## Project Conventions

Testcontainer Postgres, FTS trigger install, no live DB, no `importlib.reload`.

## TDD Requirement

Each test must fail against pre-S0X code and pass against the merged implementation (red-before-green).

## Test Verification (NON-NEGOTIABLE)

`make test-integration` + `make test-unit` + `make lint` pass.

## Subagent Result Contract

Standard JSON.
