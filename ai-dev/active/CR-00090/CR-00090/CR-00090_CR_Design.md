# CR-00090: Fix E2E Polling Suppression — Replace UA Sniffing with IW_CORE_E2E_MODE Env Var

**Type**: Change Request
**Priority**: Medium
**Reason**: Reliability / false-positive elimination in browser verification steps
**Created**: 2026-05-27
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

No migration required. This CR does not touch the database schema.

---

## Description

HTMX polling on `worktree-badge` and `staleness-dot` is currently suppressed in browser-driven contexts by checking the browser User-Agent for `headlesschrome` or `playwright`. Modern Playwright (v1.27+) with `--headless=new` sends a normal Chrome UA — the check always evaluates to `False`, polling runs during E2E verification, and when the worktree container restarts between fix cycles the browser receives `ERR_CONNECTION_REFUSED` on stale poll requests, causing false `code_defect` verdicts. This CR replaces the unreliable UA heuristic with an explicit `IW_CORE_E2E_MODE=true` env var injected by the compose template and propagated to every Jinja2 template as the global `_e2e_mode` variable.

## Project Context

Read `CLAUDE.md` for architecture, conventions, and hard rules. Key constraints for this CR: plain CSS (no Tailwind recompile), `make lint` enforces Jinja2 `%`-style format filters, `NEVER` use `agent-browser`, `NEVER` modify `.playwright/cli.config.json`.

## Current Behavior

The worktree compose template (`ai-dev/iw-config/worktree-compose.template.yml`) starts an isolated app container with no explicit E2E signal. Templates detect headless mode by sniffing the browser User-Agent at render time:

```jinja
{% set _headless = ('headlesschrome' in _ua) or ('playwright' in _ua) %}
```

Playwright v1.27+ uses `--headless=new` (Chromium's new headless mode), which sends an ordinary Chrome UA string with no `HeadlessChrome` or `playwright` substring. The detection always returns `False`. HTMX polling elements (`hx-trigger="load, every 60s"`) fire on page load and every N seconds. When the daemon tears down and restarts the E2E container between fix cycles, HTMX polls from the previously loaded page hit the old (now-closed) port and receive `ERR_CONNECTION_REFUSED`. The `qv-browser` agent catches these network errors in the console log and reports a `code_defect` verdict, even though no application code is at fault.

This failure pattern was diagnosed during F-00090 S16 browser verification (7 fix cycles exhausted on a false positive). The `_headless` variable was added in F-00090 as the intended fix, but the UA detection mechanism was incorrect for modern Playwright.

## Desired Behavior

The compose template sets `IW_CORE_E2E_MODE: "true"` in the app container's environment. The dashboard reads this env var via `orch/config.py` at startup and injects `_e2e_mode = True` into the global Jinja2 template context (alongside the existing `is_db_stale` and `static_v` globals). Every template that previously relied on the UA heuristic uses `_e2e_mode` as the primary signal, with the UA check retained as a fallback for direct Playwright automation outside the compose stack:

```jinja
{% set _headless = _e2e_mode or ('headlesschrome' in _ua) or ('playwright' in _ua) %}
```

When `_headless` is `True`, polling elements have `hx-trigger="never"` and no `hx-get` attribute, producing no background requests from the browser. Browser verification steps no longer receive spurious `ERR_CONNECTION_REFUSED` errors from stale HTMX polls.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `orch/config.py` | No E2E mode awareness | Adds `get_e2e_mode() -> bool` reading `IW_CORE_E2E_MODE` |
| `dashboard/app.py` | `templates.env.globals` has `is_db_stale`, `static_v` | Adds `_e2e_mode` global injected from `get_e2e_mode()` |
| `dashboard/templates/base.html` | UA-only `_headless` detection | OR with `_e2e_mode` global |
| `dashboard/templates/fragments/staleness_dot.html` | UA-only `_headless` detection | OR with `_e2e_mode` global |
| `dashboard/templates/pages/project_selector.html` | UA-only `_headless` detection | OR with `_e2e_mode` global |
| `ai-dev/iw-config/worktree-compose.template.yml` | No `IW_CORE_E2E_MODE` in app env | Adds `IW_CORE_E2E_MODE: "true"` |

### Breaking Changes

None. In production the env var is absent; `get_e2e_mode()` returns `False`; `_e2e_mode` is `False`; all templates behave identically to today. The UA fallback is preserved for non-compose automation.

### Data Migration

Not required.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | `backend-impl` | `orch/config.py` (add `get_e2e_mode()`); `dashboard/app.py` (inject `_e2e_mode` global) | — |
| S02 | `frontend-impl` | `base.html`, `staleness_dot.html`, `project_selector.html` (update `_headless` detection); `worktree-compose.template.yml` (add env var) | — |
| S03 | `tests-impl` | Unit tests for `get_e2e_mode()`; dashboard tests confirming `_e2e_mode` in template context; dashboard tests confirming polling suppressed | — |
| S04 | `code-review-impl` | Per-agent review of S01–S03 | — |
| S05 | `code-review-final-impl` | Global cross-step review | — |
| S06 | `qv-gate` | `make lint` | — |
| S07 | `qv-gate` | `make format-check` | — |
| S08 | `qv-gate` | `make type-check` | — |
| S09 | `qv-gate` | `make arch-check` | — |
| S10 | `qv-gate` | `make security-sast` | — |
| S11 | `qv-gate` | `make test-unit` | — |
| S12 | `qv-gate` | `make allure-integration` | — |
| S13 | `qv-browser` | Verify polling suppressed in E2E container; verify no regression in production-like mode | — |
| S14 | `self-assess-impl` | Self-assessment via `iw-item-analyze` skill | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: N/A

### API Changes

- **New endpoints**: None
- **Modified endpoints**: None
- **Removed endpoints**: None

### Frontend Changes

- **Modified templates**: `base.html`, `staleness_dot.html`, `project_selector.html`
- **New templates**: None
- **Removed templates**: None

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `CR-00090_CR_Design.md` | Design | This document |
| `CR-00090_Functional.md` | Design | Human-facing summary |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/CR-00090_S01_Backend_prompt.md` | Prompt | S01: config + app.py |
| `prompts/CR-00090_S02_Frontend_prompt.md` | Prompt | S02: templates + compose template |
| `prompts/CR-00090_S03_Tests_prompt.md` | Prompt | S03: unit + dashboard tests |
| `prompts/CR-00090_S04_CodeReview_prompt.md` | Prompt | S04: per-agent review |
| `prompts/CR-00090_S05_CodeReview_Final_prompt.md` | Prompt | S05: global review |
| `prompts/CR-00090_S13_BrowserVerification_prompt.md` | Prompt | S13: browser verification |
| `prompts/CR-00090_S14_SelfAssess_prompt.md` | Prompt | S14: self-assessment |

## Acceptance Criteria

### AC1: E2E mode env var suppresses polling

```
Given  the app container has IW_CORE_E2E_MODE=true set in its environment
When   any page containing worktree-badge or staleness-dot elements is rendered
Then   those elements have hx-trigger="never" and no hx-get attribute,
       producing zero background polling requests from the browser
```

### AC2: Production mode unchanged

```
Given  the app runs without IW_CORE_E2E_MODE set (production / dev)
When   any page containing worktree-badge or staleness-dot elements is rendered
Then   those elements retain their normal hx-get and hx-trigger="load, every Ns" attributes,
       and polling behaviour is identical to before this CR
```

### AC3: UA fallback preserved

```
Given  IW_CORE_E2E_MODE is not set and the browser User-Agent contains "headlesschrome"
When   a page is rendered
Then   _headless evaluates to True and polling is suppressed (existing fallback still works)
```

### AC4: get_e2e_mode() reads the env var correctly

```
Given  IW_CORE_E2E_MODE is set to "true", "1", or "TRUE"
When   get_e2e_mode() is called
Then   it returns True

Given  IW_CORE_E2E_MODE is absent or set to any other value
When   get_e2e_mode() is called
Then   it returns False
```

### AC5: _e2e_mode global present in all template contexts

```
Given  the dashboard app is started
When   any template is rendered via TemplateResponse
Then   the Jinja2 context includes _e2e_mode as a boolean (True or False)
       without requiring the route handler to pass it explicitly
```

### AC6: No regression in adjacent flows

```
Given  the dashboard is running with IW_CORE_E2E_MODE unset
When   a browser visits the project selector, project dashboard, history, batches, or item detail pages
Then   worktree-badge and staleness-dot poll normally,
       no console errors appear for these endpoints,
       and all other dashboard functionality is unaffected
```

## Rollback Plan

- **Database**: N/A — no schema changes
- **Code**: Revert the CR-00090 commit. The compose template change takes effect on next container start; no running container needs to be restarted manually.
- **Data**: No data loss on rollback

## Dependencies

- **Depends on**: None
- **Blocks**: None (F-00090 is already in flight with the workaround of skipping S16)

## Impacted Paths

- `orch/config.py`
- `dashboard/app.py`
- `dashboard/templates/base.html`
- `dashboard/templates/fragments/staleness_dot.html`
- `dashboard/templates/pages/project_selector.html`
- `ai-dev/iw-config/worktree-compose.template.yml`
- `tests/unit/test_config.py`
- `tests/dashboard/test_e2e_mode.py`

## TDD Approach

- **Unit tests** (`tests/unit/test_config.py`): parametrize `get_e2e_mode()` over `IW_CORE_E2E_MODE` values (`"true"`, `"1"`, `"TRUE"`, `""`, `"false"`, absent). Each assertion must fail before the implementation exists.
- **Dashboard tests** (`tests/dashboard/test_e2e_mode.py`): use `TestClient` with `monkeypatch.setenv("IW_CORE_E2E_MODE", "true")` to verify: (a) `_e2e_mode` appears in a rendered page's context; (b) polling attributes are absent on a page rendered under E2E mode; (c) polling attributes are present without the env var.
- **Updated tests**: None expected — this CR adds new behaviour, does not change existing routes or models.

## Notes

- The F-00090 worktree already introduced `_headless` in templates as the intended mechanism, but the UA detection was wrong. This CR corrects the signal source. The template variable name `_headless` is preserved for continuity; the change is only to how it is computed.
- The `ai-dev/iw-config/worktree-compose.template.yml` is consumed by `orch/daemon/worktree_compose.py` at container-launch time. Changing the template affects all future worktree containers; currently-running containers are unaffected until their next restart.
- Other templates that reference `_headless` may be added in future features. The global `_e2e_mode` injection in `dashboard/app.py` means no per-template change is needed for future templates — they can immediately use `_e2e_mode` in their local `{% set _headless = ... %}`.
