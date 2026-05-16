# F-00085 — S12 Cross-Agent Final Code Review (Implementation)

## What was done

- Reviewed cross-agent integration across S01+S04+S06+S08+S10 using:
  - Feature + Functional design docs
  - Reports S01, S02, S04, S05, S06, S07, S08, S09, S10, S11
  - Current implementation files in DB/daemon/aggregator/API/templates
- Executed full test suites for integration confidence:
  - `make test-unit`
  - `make test-integration`

## Cross-agent findings

### 1) **CRITICAL** — Phase-0 chip invariant still broken in shared base layout
- **Agents**: frontend-impl (S10), api-impl (S08)
- **Files**: `dashboard/templates/base.html`, `dashboard/routers/auto_merge_ui.py`
- **Issue**: Header always renders a chip container and fetches `/<project>/auto-merge/status?compact=1` via htmx. This violates the strict invariant requiring chip **not rendered at all** in phase 0 by server-side Jinja gate.

### 2) **HIGH** — Config POST emits audit event on no-op writes
- **Agents**: api-impl (S08)
- **File**: `dashboard/routers/auto_merge_ui.py`
- **Issue**: `POST /auto-merge/config` always inserts `auto_merge_config_updated`, even when old/new payload are identical. This pollutes audit trail and was already flagged in S09.

### 3) **HIGH** — Config POST does not validate project existence up front
- **Agents**: api-impl (S08)
- **File**: `dashboard/routers/auto_merge_ui.py`
- **Issue**: Handler does not call `_get_project_or_404`; unknown project may fail at DB FK/commit level instead of deterministic 404.

### 4) **HIGH** — Settings form payload contract is ambiguous/unsafe
- **Agents**: frontend-impl (S10), api-impl (S08)
- **File**: `dashboard/templates/fragments/auto_merge_settings.html`
- **Issue**: Duplicate field names for select and radio (`phase`, `runtime_option_id`) can produce multi-value JSON payloads with `hx-ext="json-enc"`, conflicting with API schema `int | null`.

### 5) **HIGH** — End-to-end example (phase=1, runtime_option_id=4) cannot be trusted as implemented
- **Agents**: frontend-impl (S10), api-impl (S08), backend-impl (S06)
- **Files**: `auto_merge_settings.html`, `auto_merge_ui.py`, `orch/auto_merge_aggregator.py`
- **Issue**: Because of (4), submitted config can be malformed/ambiguous; therefore the required deterministic chain (UI save → DB row → resolver runtime model attribution) is not reliable.

### 6) **HIGH** — Reserved phases 2/3 still accepted by TOML loader
- **Agents**: pipeline-impl (S04), backend-impl (S06)
- **File**: `orch/daemon/auto_merge.py`
- **Issue**: `AutoMergeConfig.load()` still accepts arbitrary `phase` int from TOML. API/DB guard only protects UI path; TOML path should also refuse reserved 2/3 per invariant.

### 7) **MEDIUM** — Event detail query can miss valid events beyond first 1000
- **Agents**: backend-impl (S06), api-impl (S08)
- **File**: `orch/auto_merge_aggregator.py`
- **Issue**: `get_event_detail()` scans only first page (`page_size=1000`) of recent events; older valid event IDs return false 404.

### 8) **MEDIUM** — Rollup windows use Python wall-clock instead of DB window expression
- **Agents**: backend-impl (S06)
- **File**: `orch/auto_merge_aggregator.py`
- **Issue**: `datetime.now()` is used in app layer for rollups; review checklist requested DB-side/parameterized window semantics.

### 9) **MEDIUM** — AC1 required empty-state copy not implemented
- **Agents**: frontend-impl (S10)
- **File**: `dashboard/templates/fragments/auto_merge_events_table.html`
- **Issue**: Displays `No events found.` instead of required AC copy.

### 10) **MEDIUM** — Modal accessibility behavior incomplete
- **Agents**: frontend-impl (S10)
- **File**: `dashboard/templates/fragments/auto_merge_event_detail.html`
- **Issue**: No Escape-key dismissal path.

### 11) **MEDIUM** — Documentation cross-reference obligations not met
- **Agents**: backend-impl (S06), frontend-impl (S10)
- **Files**: `orch/auto_merge_aggregator.py`, `dashboard/templates/fragments/auto_merge_settings.html`
- **Issue**: No local citation/comment to `R-00076` / `AUTO_MERGE_RESOLUTION.md` at required touchpoints.

### 12) **MEDIUM** — Health config comment mismatch vs implementation semantics
- **Agents**: pipeline-impl (S04), backend-impl (S06), frontend-impl (S10)
- **File**: `executor/auto_merge.toml`
- **Issue**: Comment says threshold uses `auto_merge_resolution_failed` count; code computes health from failing `auto_merge_health_probe` events. Operator-facing docs are inaccurate.

### 13) **MEDIUM** — SAST regression introduced by diff template rendering
- **Agents**: frontend-impl (S10), api-impl (S08)
- **File**: `dashboard/templates/fragments/auto_merge_event_detail.html`
- **Issue**: `{{ diff.diff_html | safe }}` triggers semgrep blocking rule (`template-unescaped-with-safe`) and currently fails integration suite.

## Invariant and behavior checks

- **Append-only daemon_events**: PASS (no `update(DaemonEvent)` / `delete(DaemonEvent)` found).
- **Health probe non-blocking placement**: PASS (`maybe_run_probe` runs after merge queue and inside isolated try/except).
- **Disabled-runtime defense-in-depth**: PARTIAL PASS
  - UI and API use `enabled=True` filtering/check.
  - Aggregator fallback + `auto_merge_config_invalid` emission exists.
  - But config POST still lacks project 404 guard and no-op suppression.
- **F-00084 backward compatibility (phase-0 default/no-UI action)**: PARTIAL RISK
  - Backend has TOML fallback path.
  - But chip rendering invariant is broken at template level for phase 0.

## Full test suite result

- `make test-unit`: passed.
- `make test-integration`: failed with 3 failures.
  1. `tests/integration/daemon/test_phase2_apply_no_self_deadlock.py::test_i_00063_apply_does_not_self_deadlock_when_caller_holds_share_lock`
  2. `tests/integration/daemon/test_phase2_apply_no_self_deadlock.py::test_i_00063_apply_succeeds_when_no_blocking_lock`
  3. `tests/integration/test_security_sast_baseline.py::test_semgrep_baseline_is_zero_blocking_findings` (new auto-merge modal template `|safe` usage)

## Files changed in this step

- `ai-dev/active/F-00085/reports/F-00085_S12_CodeReviewFinal_report.md` (this report)

## 5-line integration health summary

1. Config resolution chain is partially implemented but not yet trustworthy end-to-end due to settings payload ambiguity and config no-op audit noise.
2. Audit trail is partially present (old/new config event + verdict table), but event emission semantics are incorrect for no-op updates.
3. Append-only `daemon_events` invariant is intact (insert-only pattern retained).
4. Phase 2/3 reservation is enforced at DB/API/UI, but TOML loader still accepts reserved phases and must hard-refuse.
5. Disabled-runtime defense-in-depth exists across UI/API/aggregator, yet final reliability is blocked by unresolved API/frontend contract issues.

```json
{
  "step": "S12",
  "agent": "code-review-final-impl",
  "work_item": "F-00085",
  "decision": "request_changes",
  "verdict": "NEEDS_FIX",
  "mandatory_fix_count": 8,
  "findings": [
    {"severity": "CRITICAL", "title": "Phase-0 chip still rendered via htmx placeholder"},
    {"severity": "HIGH", "title": "Config POST emits audit event on no-op"},
    {"severity": "HIGH", "title": "Config POST missing deterministic project 404 guard"},
    {"severity": "HIGH", "title": "Settings form duplicate names produce ambiguous JSON payload"},
    {"severity": "HIGH", "title": "TOML loader still accepts reserved phase 2/3"},
    {"severity": "MEDIUM", "title": "Event detail query limited to first 1000 events"},
    {"severity": "MEDIUM", "title": "Required docs cross-references/comments missing"},
    {"severity": "MEDIUM", "title": "Semgrep baseline broken by template safe rendering"}
  ],
  "notes": "Cross-agent integration is not yet shippable; S13 should include tests for no-op config POST, phase-0 non-render, TOML reserved-phase refusal, event-detail lookup beyond 1000 rows, and semgrep-safe diff rendering path."
}
```
