# CR-00090 S04 — Code Review Report

**Work Item**: CR-00090 — Fix E2E Polling Suppression — Replace UA Sniffing with IW_CORE_E2E_MODE Env Var
**Step**: S04 (Code Review)
**Reviewer**: code-review-impl
**Verdict**: ✅ **PASS**

---

## Summary

Reviewed S01 (backend), S02 (frontend), and S03 (tests) for CR-00090. All acceptance criteria are satisfied, no critical findings, no mandatory fixes required.

---

## Pre-Review Quality Gates

| Gate | Result |
|------|--------|
| `make lint` | ✅ All checks passed (ruff + check_templates.py) |
| `make format-check` | ✅ 944 files already formatted |

---

## Scope Discipline

`git diff --stat` shows 7 changed files — all within the allowed scope:

| File | Status |
|------|--------|
| `orch/config.py` | ✅ In scope |
| `dashboard/app.py` | ✅ In scope |
| `dashboard/templates/base.html` | ✅ In scope |
| `dashboard/templates/fragments/staleness_dot.html` | ✅ In scope |
| `dashboard/templates/pages/project_selector.html` | ✅ In scope |
| `ai-dev/iw-config/worktree-compose.template.yml` | ✅ In scope |
| `tests/unit/test_config.py` | ✅ In scope |
| `tests/dashboard/test_e2e_mode.py` | ✅ New file, in scope |

No out-of-scope changes detected.

---

## S01 Backend Review

### `orch/config.py`

- `get_e2e_mode()` is present and reads `os.environ.get("IW_CORE_E2E_MODE", "")` at call time (not import time) ✅
- Returns `True` for `"true"`, `"1"`, `"TRUE"`, `"True"` (case-insensitive via `.lower()`) ✅
- Returns `False` for absent, empty, `"false"`, `"0"`, and any other value ✅
- Function is exported in `__all__` ✅
- No `importlib.reload` used — tests use `monkeypatch.setenv/delenv` ✅

### `dashboard/app.py`

- `get_e2e_mode` is imported from `orch.config` ✅
- `templates.env.globals["_e2e_mode"] = get_e2e_mode()` is set at app construction time (before any request is served) ✅
- `_e2e_mode` is available in all templates rendered via `TemplateResponse` without per-route passing ✅

---

## S02 Frontend Review

### `base.html` (sidebar worktree badge)
```jinja
{% set _ua = (request.headers.get('user-agent', '')|lower) %}
{% set _headless = _e2e_mode or ('headlesschrome' in _ua) or ('playwright' in _ua) %}
```
- `_e2e_mode` is the primary signal, UA is the fallback ✅
- `hx-trigger="{% if _headless %}never{% else %}load, every 60s{% endif %}"` ✅
- `{% if not _headless %}hx-get="/system/nav/worktree-badge"{% endif %}` (omitted when suppressed) ✅

### `fragments/staleness_dot.html`
- Same `_e2e_mode or ('headlesschrome' in _ua) or ('playwright' in _ua)` expression ✅
- `|_default(false)` removed (redundant — `_e2e_mode` is always present) ✅

### `pages/project_selector.html`
- Same `_e2e_mode or ('headlesschrome' in _ua) or ('playwright' in _ua)` expression ✅
- `hx-trigger="{% if _headless %}never{% else %}load, every 15s{% endif %}"` ✅
- `|_default(false)` removed ✅

### `worktree-compose.template.yml`
- `IW_CORE_E2E_MODE: "true"` added to the `app` service's `environment:` block ✅
- No other changes to the compose template ✅

### Jinja2 format filters
- Enforced by `make lint → check_templates.py` ✅

---

## S03 Tests Review

### `tests/unit/test_config.py`

9 parametrized test cases for `get_e2e_mode()`:

| Value | Expected | Covered |
|-------|----------|---------|
| `"true"` | `True` | ✅ |
| `"1"` | `True` | ✅ |
| `"TRUE"` | `True` | ✅ |
| `"True"` | `True` | ✅ |
| `""` | `False` | ✅ |
| `"false"` | `False` | ✅ |
| `"0"` | `False` | ✅ |
| `"anything"` | `False` | ✅ |
| absent | `False` | ✅ |

- All use `monkeypatch.setenv`/`monkeypatch.delenv` (no `importlib.reload`) ✅
- Design doc required 6 cases; 9 are present (additional `"True"` and `"anything"` are sensible edge cases) ✅

### `tests/dashboard/test_e2e_mode.py`

7 tests across 3 classes:

**TestWorktreeBadgeE2eMode** (AC1 + AC2):
- `test_polling_suppressed_when_e2e_mode_true`: asserts `hx-trigger="never"` present AND `hx-get="/system/nav/worktree-badge"` absent ✅
- `test_polling_present_when_e2e_mode_off`: asserts `hx-trigger="never"` absent AND `hx-get` present ✅

**TestStalenessDotE2eMode** (AC1 + AC2):
- `test_staleness_dot_suppresses_polling_when_e2e_mode_true`: asserts `hx-trigger="never"` present AND `hx-get` absent ✅
- `test_staleness_dot_polls_when_e2e_mode_off`: asserts `hx-trigger="every 15s"` and `hx-get` present ✅
- `test_staleness_dot_renders_dot_class_when_e2e_mode_true`: asserts `iw-staleness-dot--red` present (visual element not suppressed) ✅

**TestE2eModeGlobalPresent** (AC5):
- `test_e2e_mode_global_usable_in_sidebar_when_e2e_true`: 200 response + `hx-trigger="never"` confirms global used ✅
- `test_e2e_mode_global_usable_in_sidebar_when_e2e_false`: 200 response + `hx-get` present confirms global used ✅

All tests assert on **behaviour** (the HTML attributes in the rendered response), not just on their own mocks. Mutation test criterion is satisfied — a broken `_e2e_mode` injection would cause test failures. ✅

Staleness router's module-level `Jinja2Templates` instance is patched alongside `app.state.templates` in both fixtures. ✅

---

## Acceptance Criteria Completeness

| AC | Description | Evidence | Status |
|----|-------------|----------|--------|
| AC1 | `IW_CORE_E2E_MODE=true` → `hx-trigger="never"` + no `hx-get` | Test B (suppression tests) + S02 templates | ✅ |
| AC2 | Unset env var → polling attributes present | Test C (polling present tests) + S02 templates | ✅ |
| AC3 | UA fallback preserved when env var absent | Template OR expression (`_e2e_mode or (...)`) | ✅ |
| AC4 | `get_e2e_mode()` handles all truthy/falsy cases | 9 parametrized unit tests | ✅ |
| AC5 | `_e2e_mode` global present without per-route passing | `app.py` injection + `TestE2eModeGlobalPresent` tests | ✅ |
| AC6 | No regression in adjacent flows | `make lint` clean; tests use `monkeypatch` isolation; no route/logic changes | ✅ |

---

## Test Results

```
tests/unit/test_config.py::test_get_e2e_mode_*   9 passed, 21 deselected
tests/dashboard/test_e2e_mode.py                  7 passed
```

---

## Security

- No hardcoded credentials or secrets ✅
- `IW_CORE_E2E_MODE` is read-only; no new security surface introduced ✅
- Env var value `"true"` is non-sensitive ✅

---

## Findings

| Severity | Count | Details |
|----------|-------|---------|
| Critical | 0 | — |
| Major | 0 | — |
| Minor | 0 | — |
| Notes | 2 | See below |

### Notes

1. **Design doc says 6 AC cases, 9 are tested**: The design doc (AC4) lists `"true"`, `"1"`, `"TRUE"` as truthy cases and absent/empty/`"false"`/`"0"` as falsy — 6 cases. S01 added 2 additional edge cases (`"True"` and `"anything"`). This is beneficial, not a deviation. All AC4 requirements are met.

2. **`_headless` variable name preserved**: Per the design doc's note, the existing `_headless` variable name was kept throughout. The change is only in how `_headless` is computed (adding `_e2e_mode` as the primary signal). This maintains backward compatibility with any downstream code that references `_headless`.

---

## Verdict

```
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "CR-00090",
  "step_reviewed": "S01-S03",
  "verdict": "pass",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "16 passed, 0 failed (9 unit + 7 dashboard)",
  "notes": "All 6 acceptance criteria satisfied. All 7 in-scope files correctly implemented. No critical or major findings. Pre-review lint and format gates clean."
}
```
