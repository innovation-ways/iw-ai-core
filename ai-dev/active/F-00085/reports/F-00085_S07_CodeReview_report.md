# F-00085 — S07 Code Review Report (S06 Backend)

## Scope Reviewed

- Design: `ai-dev/active/F-00085/F-00085_Feature_Design.md` (focused on Invariants 1,2,3,5,7 and S06 backend scope)
- Implementation report: `ai-dev/active/F-00085/reports/F-00085_S06_Backend_report.md`
- Files reviewed:
  - `orch/auto_merge_aggregator.py`
  - `orch/daemon/auto_merge_health.py`
  - `orch/daemon/auto_merge.py`
  - `orch/daemon/merge_queue.py`
  - `orch/daemon/main.py`
  - `tests/unit/test_auto_merge_aggregator.py`
  - `tests/unit/test_auto_merge_config_resolution.py`
  - `tests/unit/test_auto_merge_health.py`
  - `tests/unit/test_auto_merge_pricing.py`

## Checks Run

- `uv run pytest tests/unit/test_auto_merge_aggregator.py tests/unit/test_auto_merge_config_resolution.py tests/unit/test_auto_merge_health.py tests/unit/test_auto_merge_pricing.py tests/unit/test_merge_queue.py -q --no-cov` → **26 passed**
- `uv run pytest tests/unit/test_auto_merge_*.py -q --no-cov` → **75 passed**

## Findings

### 1) TOML loader still accepts reserved phases 2/3 (Invariant 5 violation)
- **Severity**: HIGH
- **File**: `orch/daemon/auto_merge.py`
- **Line(s)**: 224-225, and behavior asserted in test at `tests/unit/test_auto_merge_config.py:80-106`
- **Description**: `AutoMergeConfig.load()` directly accepts any integer `phase` from TOML. This allows phase 2/3 to be loaded and only rejected later by `attempt_resolution()`. The design invariant requires TOML loader refusal for phase >=2 (not deferred runtime rejection).
- **Suggested fix**: Validate phase in loader (`phase in {0,1}`), return `(defaults, error_string)` when TOML sets 2/3, and update the unit test expectation accordingly.

### 2) Windowed rollups use Python wall-clock instead of DB-side parameterized `now()-interval`
- **Severity**: MEDIUM
- **File**: `orch/auto_merge_aggregator.py`
- **Line(s)**: 281, 302, 321, 353
- **Description**: Rollup queries compute `since` with `datetime.now(UTC)` in Python, not DB-side parameterized window expressions. Step checklist explicitly asks for parameterized `now() - interval` filters (and no string interpolation). Current code is safe from interpolation but does not satisfy the requested query pattern.
- **Suggested fix**: Replace Python timestamp calculation with SQLAlchemy expressions using DB `now()` and typed interval arithmetic (bound values), e.g. `DaemonEvent.created_at >= func.now() - text("interval '7 days'")` or equivalent parameterized expression.

### 3) `get_event_detail` is functionally paged and can miss valid events
- **Severity**: MEDIUM
- **File**: `orch/auto_merge_aggregator.py`
- **Line(s)**: 273-277
- **Description**: `get_event_detail()` loads only first 1000 recent rows via `list_recent_events(..., page_size=1_000)` and scans in memory. Events outside that slice return `None` even when they exist for the project/event_id.
- **Suggested fix**: Implement direct single-row query by `(project_id, event_id)` with LEFT JOIN to `merge_auto_verdicts`, rather than scanning a paginated listing.

### 4) Invalid per-project phase fallback is silent
- **Severity**: LOW
- **File**: `orch/auto_merge_aggregator.py`
- **Line(s)**: 157-159
- **Description**: If `AutoMergeProjectConfig.phase` is not in `{0,1}`, resolver silently coerces to `0` without warning/event. Checklist asks invalid phase to be rejected by DB CHECK or filtered with clear log.
- **Suggested fix**: Keep fallback-to-0, but emit a clear warning/event metadata indicating invalid phase was ignored.

## Notes

- Multi-project scoping is present across aggregator queries through `project_id` filters and/or project-scoped joins.
- `list_recent_events` correctly uses LEFT JOIN with `merge_auto_verdicts`.
- Unknown models correctly contribute `$0` and set `has_unknown_models=True`.
- Health probe integration is placed after batch+merge processing and wrapped in per-project `try/except`, preserving non-blocking daemon behavior.
- No `DaemonEvent` UPDATE/DELETE operations were introduced in reviewed scope.

```json
{
  "step": "S07",
  "agent": "code-review-impl",
  "work_item": "F-00085",
  "reviewed_agent": "backend-impl",
  "verdict": "NEEDS_FIX",
  "mandatory_fix_count": 3,
  "findings": [
    {
      "severity": "HIGH",
      "file": "orch/daemon/auto_merge.py",
      "lines": "224-225",
      "description": "TOML loader accepts reserved phases 2/3 instead of refusing them",
      "suggested_fix": "Validate phase in loader and return defaults+error for phase>=2"
    },
    {
      "severity": "MEDIUM",
      "file": "orch/auto_merge_aggregator.py",
      "lines": "281,302,321,353",
      "description": "Rollup windows use Python datetime.now() instead of DB-side now()-interval filtering",
      "suggested_fix": "Switch to parameterized SQL window expressions"
    },
    {
      "severity": "MEDIUM",
      "file": "orch/auto_merge_aggregator.py",
      "lines": "273-277",
      "description": "get_event_detail scans only first 1000 recent events and can miss valid event_id",
      "suggested_fix": "Query event detail directly by project_id + event_id with LEFT JOIN"
    },
    {
      "severity": "LOW",
      "file": "orch/auto_merge_aggregator.py",
      "lines": "157-159",
      "description": "Invalid per-project phase coerces silently to 0",
      "suggested_fix": "Log/emit clear invalid-phase signal when coercing"
    }
  ],
  "notes": "Targeted tests pass; issues are spec-compliance and edge-case correctness."
}
```
