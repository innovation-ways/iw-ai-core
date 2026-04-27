# F-00063 S08 — Final Cross-Layer Code Review

**Work item**: F-00063 — Stale Process & Migration Detector
**Step**: S08 (code-review-final-impl)
**Date**: 2026-04-27
**Steps reviewed**: S01, S02, S03, S04, S05, S06, S07

---

## Executive Summary

All four quality gates pass. The feature is complete, well-integrated across all layers, and all prior per-agent review findings were properly fixed. No new mandatory issues were found in the cross-layer review.

---

## Test Gate Results

| Gate | Command | Result |
|------|---------|--------|
| Unit tests | `make test-unit` | **1852 passed, 2 skipped** |
| Integration tests | `make test-integration` | **1125 passed, 18 skipped** |
| Lint | `make lint` | **exit 0** |
| Typecheck | `make typecheck` | **exit 0 (190 source files)** |
| Staleness-specific | `pytest tests/unit/staleness/ tests/dashboard/test_staleness_router.py tests/dashboard/test_staleness_templates.py` | **183 passed** |

---

## Cross-Layer Consistency Checks

### 1. Data Shape: `ProjectStalenessResult` → Template

`orch/staleness/service.py` defines:
- `ProjectStalenessResult(project_id, services, alembic, is_stale)`
- `ServiceStaleness(name, status, start_time, start_commit, commits, error, hot_reload, actions)`
- `AlembicStatus(status, current, head, pending, error)`
- `CommitSummary(sha, subject)` from `git_lookup.py`
- `RevisionSummary(rev_id, message)` from `alembic_check.py`

`staleness_panel.html` accesses: `staleness.services`, `staleness.alembic`, `staleness.is_stale`, per-service `svc.name`, `svc.status`, `svc.start_time`, `svc.actions`, `svc.commits`, `svc.error`, per-commit `commit.sha`, `commit.subject`, and alembic fields `staleness.alembic.status`, `.current`, `.head`, `.pending`, per-revision `rev.rev_id`, `rev.message`.

All field names match exactly. **PASS**.

### 2. Router Context Keys → Template Variables

The S06 review found (and fixed) that the original endpoints passed `result`/`project_id` while the template expected `staleness`/`project.id`. After the S06 fix, the router now passes:
```python
{"staleness": result, "project": type("_Project", (), {"id": project_id})()}
```

Verified in `dashboard/routers/staleness.py` lines 209-213 and 241-244. **PASS**.

### 3. Endpoint URLs: Templates → Router Declarations

All htmx endpoint references in templates match router declarations exactly:

| Template reference | Router declaration |
|---|---|
| `hx-get="/projects/{{ project.id }}/staleness"` | `GET /projects/{project_id}/staleness` |
| `hx-get="/projects/{{ project.id }}/staleness-dot"` (project_selector) | `GET /projects/{project_id}/staleness-dot` |
| `hx-get=".../alembic/upgrade/confirm"` | `GET /projects/{project_id}/alembic/upgrade/confirm` |
| `hx-get=".../services/{{ svc.name }}/restart/confirm"` | `GET /projects/{project_id}/services/{service_name}/restart/confirm` |
| `hx-get=".../services/{{ svc.name }}/stop/confirm"` | `GET /projects/{project_id}/services/{service_name}/stop/confirm` |
| `hx-get=".../services/{{ svc.name }}/start/confirm"` | `GET /projects/{project_id}/services/{service_name}/start/confirm` |
| `hx-post="{{ action_url }}"` (confirm dialog) | Populated dynamically: `.../restart`, `.../start`, `.../stop`, `.../alembic/upgrade` |

All match. **PASS**.

### 4. Toast Trigger Format

`_toast_response` in `staleness.py` line 138:
```python
trigger = json.dumps({"showToast": {"message": message, "type": "success"}})
```

`toast.html` JS line 37: `var type = data.type || 'info';`

The `"type"` key matches. The S05 review fixed the original `"kind"` bug. **PASS**.

### 5. `restart_command` Strings vs Actual Scripts

`projects.toml` seeds:
- `daemon.restart_command = "./ai-core.sh daemon restart"` — `ai-core.sh` exists and handles `daemon restart` (line 754 in `ai-core.sh`). **PASS**.
- `dashboard.restart_command = "bin/restart-dashboard.sh"` — `bin/restart-dashboard.sh` exists, is executable (0755), has `#!/usr/bin/env bash` shebang, and calls `./ai-core.sh dashboard start` at the end. **PASS**.

### 6. `bin/restart-dashboard.sh` Integration Check

- File: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/bin/restart-dashboard.sh`
- Permissions: `-rwxrwxr-x` (executable) ✓
- Shebang: `#!/usr/bin/env bash` ✓
- Behaviour: sleeps 1s for HTTP flush, SIGTERM + 10s grace + SIGKILL fallback, then `exec ./ai-core.sh dashboard start` ✓
- The `cd "$(dirname "$0")/.."` at top ensures it runs from the project root regardless of invocation path ✓

### 7. Architecture Layer Separation

`orch/staleness/` contains zero imports from `dashboard/`. Verified with grep. **PASS**.

### 8. No New DB Schema Changes

No new Alembic migration files were created for this feature. The three pre-existing migrations in `orch/db/migrations/versions/` with untracked status are from the pre-existing OSS work (I-00042) and are not related to F-00063. **PASS** (Invariant 1).

### 9. Invariant 6: No Caching

Both `orch/staleness/service.compute_project_staleness` and `dashboard/routers/staleness._load_projects_toml` re-read `projects.toml` from disk on every call. Module-level `_projects_toml_path()` is a named function (not a constant) to support patching in tests. Verified in source + `test_inv6_projects_toml_reread_on_each_call`. **PASS**.

### 10. Invariant 2: Opt-out Zero Footprint

When a project has no `services` and no `alembic` block, both the panel and dot endpoints return an HTTP 200 with empty body (`content=""`). htmx replaces the placeholder with nothing. Verified in `staleness_panel.html` line 1 (`{% if staleness and (staleness.services or staleness.alembic) %}`) and `staleness_dot.html` line 1. **PASS**.

### 11. Confirm Dialog Endpoints (S06 Critical Fix)

The S06 review found and fixed that the four confirm-dialog GET endpoints were missing entirely. The router now declares them at lines 252, 280, 308, 336. The action button `hx-get` calls and the alembic upgrade button `hx-get` all match these endpoints. **PASS**.

### 12. Alembic Upgrade Button: Single htmx Verb (S06 High Fix)

The original button had both `hx-post` and `hx-get`. After the S06 fix, only `hx-get` pointing to the confirm endpoint remains in `staleness_panel.html` line 57-64. **PASS**.

---

## Coverage Completeness

### Acceptance Criteria Coverage

| AC | Description | Test |
|----|---|---|
| AC1 | Stale service → red dot + panel detail | `test_dot_renders_red_class_when_stale`, `test_panel_renders_stale_service_section` |
| AC2 | Restart button → confirm → POST → 429 on repeat | `test_restart_invokes_subprocess_with_command`, `test_restart_returns_429_on_second_post_within_5s` |
| AC3 | Alembic head mismatch → Migrations section first + upgrade button | `test_migrations_section_before_services`, `test_alembic_upgrade_happy_path` |
| AC4 | Project with no config → zero footprint | `test_panel_empty_body_for_optout_project`, `test_dot_empty_for_optout_project` |
| AC5 | Auto-refresh every 15s | `hx-trigger="every 15s"` on panel section and dot span (template structure) |
| AC6 | Not-running → grey, no red dot | `TestStalenessDotNotRunning`, `test_inv8_not_running_only_produces_no_red_dot` |

All six acceptance criteria are covered. **PASS**.

### All 10 Invariants Covered

| Inv | Coverage |
|-----|---|
| 1: No new DB tables | `test_inv1_no_new_db_tables` (S07) |
| 2: Opt-out zero DOM | Template tests + router opt-out empty body |
| 3: Main worktree only | `test_process_cwd_outside_repo_root_treated_as_not_running` (S07) |
| 4: 5s duplicate rejection | `test_inv4_three_rapid_restart_posts_only_one_subprocess`, plus start/stop variants |
| 5: alembic DB env | `test_alembic_upgrade_db_url_env_injected_into_subprocess`, `test_alembic_upgrade_no_db_url_env_uses_parent_env` |
| 6: projects.toml re-read | `test_inv6_projects_toml_reread_on_each_call`, `test_inv6_projects_toml_reread_per_call` |
| 7: Migrations before Services | `test_migrations_section_before_services` (template), `test_panel_renders_service_and_alembic_sections` (router wiring) |
| 8: Not-running no red dot | `test_inv8_not_running_only_produces_no_red_dot` (S07) |
| 9: Confirm dialogs before action | `test_confirm_endpoint_renders_service_name_and_command` (S07) |
| 10: Dashboard self-restart non-blocking | `test_self_restart_returns_202`, `test_self_restart_spawns_detached_process` (S07) |

All 10 invariants covered. **PASS**.

---

## Notable Design Decisions (Verified Correct)

1. **Self-restart detection**: `status_code = 202 if "restart-dashboard" in command else 204` — fragile if the script is renamed, but documented. Currently matches `"bin/restart-dashboard.sh"` in `projects.toml`. Noted LOW.

2. **shell=True documented**: `dashboard/routers/staleness.py` module docstring and `# noqa: S602` comment explains the trust boundary. **PASS**.

3. **Minimal `_Project` object**: `type("_Project", (), {"id": project_id})()` is an unconventional but functional way to satisfy `project.id` template access without importing full ORM models into the router.

4. **Docker service deferred**: `orch/staleness/service.py` notes docker detection deferred; service returns `not_running`. This is the intended behavior per the S01 design. The corresponding unit test (`test_docker_service_returns_not_running` / equivalent) exists in S07. **PASS**.

---

## Findings Summary

No new CRITICAL, HIGH, or MEDIUM_FIXABLE findings discovered. All prior findings from S02/S05/S06 were fixed in those steps.

### Pre-existing LOW findings (no action required)

- **S02-F3**: `watch_paths=[]` accepted without warning (false-positive stale risk; very low operational risk with real configs).
- **S02-F4**: `repo_root` fallback to `Path("")` — unexploitable due to `project_registry.py` guard.
- **S05-LOW-2**: Self-restart 202/204 branch by substring match — stable for current config, documented.
- **S05-LOW-3**: Soft-lock set before spawn; on `Popen` failure lock remains engaged for 5s — very unlikely with `shell=True`.

---

## Subagent Result Contract

```json
{
  "step": "S08",
  "agent": "code-review-final-impl",
  "work_item": "F-00063",
  "steps_reviewed": ["S01", "S02", "S03", "S04", "S05", "S06", "S07"],
  "verdict": "pass",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "make test-unit: 1852 passed, 2 skipped. make test-integration: 1125 passed, 18 skipped. make lint: exit 0. make typecheck: exit 0 (190 files). Staleness-specific: 183 passed.",
  "missing_requirements": [],
  "notes": "All cross-layer consistency checks pass. No new issues found. All prior S02/S05/S06 findings were fixed in place. Four pre-existing LOW findings remain as documented (no action required)."
}
```
