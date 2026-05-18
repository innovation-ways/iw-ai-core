# I-00091_S05_Tests_prompt

**Work Item**: I-00091 — Auto-merge settings form stays "Use global default" after partial-axis override
**Step**: S05
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

Standard policy. Testcontainers in pytest fixtures are exempt.

## ⛔ Migrations: agents generate, daemon applies

N/A — this step does not touch alembic.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00091 --json`.
- `ai-dev/active/I-00091/I-00091_Issue_Design.md` — **mandatory read**;
  the `Test to Reproduce`, `Acceptance Criteria`, and `TDD Approach`
  sections enumerate the tests you must write.
- `ai-dev/active/I-00091/reports/I-00091_S01_Backend_report.md` —
  ResolvedConfig signature, edge-case notes
- `ai-dev/active/I-00091/reports/I-00091_S03_Frontend_report.md` —
  rendered DOM shape (especially the `id="auto-merge-settings"` and the
  hx-swap-oob chip pattern)
- `orch/auto_merge_aggregator.py` — the resolver under test
- `dashboard/templates/fragments/auto_merge_settings.html`
- `dashboard/routers/auto_merge_ui.py`
- `tests/CLAUDE.md` — test layer rules
- `skills/iw-ai-core-testing/SKILL.md` — IW AI Core testing standards
- `tests/dashboard/test_auto_merge_routes.py` — defines the local
  `client` fixture used by dashboard tests in that file (the
  `tests/dashboard/conftest.py` does NOT define `client` directly; the
  fixture lives in the test file itself).
- `tests/integration/test_auto_merge_control_surface.py` — defines the
  local `_client(db_session)` helper used by integration tests in that
  file. The `tests/integration/auto_merge_fixtures.py` file referenced
  in earlier drafts does NOT exist — do not import from it.

## Output Files

- `ai-dev/active/I-00091/reports/I-00091_S05_Tests_report.md` — step report

## Context

You write the regression suite that locks in the four-cell matrix
behaviour fixed by S01 + S03. The suite spans **three layers**:

- **Unit** — `tests/unit/test_auto_merge_config_resolution.py` extended
  with four matrix tests targeting `resolve_project_config`.
- **Dashboard (TestClient)** —
  `tests/dashboard/test_auto_merge_routes.py` extended with four matrix
  tests asserting the rendered HTML's `<option … selected>` attributes
  and the footer attribution text.
- **Integration (testcontainer DB)** —
  `tests/integration/test_auto_merge_control_surface.py` extended with
  one test that POSTs to `/auto-merge/config` and asserts the response
  body contains BOTH the new `id="auto-merge-settings"` settings-form
  fragment AND the `hx-swap-oob` status chip fragment.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is
non-empty) and passed. But the bug was NOT fixed. Tests must verify
SPECIFIC VALUES:

- BAD: `assert "phase" in html` (shape only — passes against the bug)
- BAD: `assert "<option" in html` (passes against the bug)
- BAD: `assert "selected" in html` (passes — "selected" appears on the
  wrong option, but the substring is there)
- GOOD: `assert 'value="1" selected' in phase_block` (semantic —
  verifies the specific option is selected)
- GOOD: `assert 'value="global" selected' not in phase_block`
  (semantic — verifies the unwanted option is NOT selected)
- GOOD: helper `_extract_select_block(html, name="phase")` scoped to the
  Phase `<select>` element so a `selected` in the Runtime select can't
  satisfy a Phase assertion.

Write a small helper at the top of `test_auto_merge_routes.py` (or in a
sibling conftest if cleaner):

```python
import re

def _extract_select_block(html: str, name: str) -> str:
    """Return the inner HTML of <select name="{name}">...</select>.
    Raises AssertionError if the select is missing — that itself is a useful failure.
    """
    pattern = re.compile(
        rf'<select\b[^>]*\bname="{re.escape(name)}"[^>]*>(.*?)</select>',
        re.DOTALL,
    )
    match = pattern.search(html)
    assert match is not None, f"<select name=\"{name}\"> not found in response"
    return match.group(1)
```

Use this helper in every dashboard test. **NEVER** assert on the bare
`html` body with substrings that could match the wrong `<select>`.

## Requirements

### 1. Unit tests (`tests/unit/test_auto_merge_config_resolution.py`)

Extend the existing file with **four** new tests (you may reuse the
phase-only test added in S01 as RED evidence — that one already exists;
add the remaining three):

| Test | Setup | Asserted ResolvedConfig fields |
|------|-------|-------------------------------|
| `test_resolve_project_config_records_per_axis_source_phase_only_override` | `AutoMergeProjectConfig(project_id=P, phase=1, runtime_option_id=NULL)` | `phase == 1`, `phase_source == "per_project_db"`, `runtime_source in ("toml","hardcoded")` |
| `test_resolve_project_config_records_per_axis_source_runtime_only_override` | `(phase=NULL, runtime_option_id=<enabled_row.id>)` | `runtime_option_id == enabled_row.id`, `runtime_source == "per_project_db"`, `phase_source in ("toml","hardcoded")` |
| `test_resolve_project_config_records_per_axis_source_both_axes_override` | `(phase=1, runtime_option_id=<enabled_row.id>)` | both `*_source == "per_project_db"` |
| `test_resolve_project_config_records_per_axis_source_no_override` | No `AutoMergeProjectConfig` row | both `*_source != "per_project_db"` |

Reuse the TOML config fixture pattern already in the file. Use **enabled
runtime rows only** for `runtime_option_id` to avoid the disabled-runtime
fallthrough path — that case is a separate concern.

Add one additional test for the disabled-runtime fallthrough:

| Test | Setup | Asserted |
|------|-------|----------|
| `test_resolve_project_config_falls_back_when_per_project_runtime_disabled` | `AgentRuntimeOption(enabled=False)` referenced by `AutoMergeProjectConfig.runtime_option_id` | `runtime_source != "per_project_db"` (it should fall through to TOML or hardcoded — the per-project value was rejected) |

### 2. Dashboard tests (`tests/dashboard/test_auto_merge_routes.py`)

Add four matrix tests using the `client` fixture. **All tests in this
file MUST live under `tests/dashboard/`** — the `client` fixture is
registered only in `tests/dashboard/conftest.py` (I-00067).

For each test:

1. Seed a project + (optionally) an `AutoMergeProjectConfig` row + an
   `AgentRuntimeOption(enabled=True)` if the test needs a real id.
2. `response = client.get(f"/project/{project.id}/auto-merge")`
3. `assert response.status_code == 200`
4. Extract `phase_block = _extract_select_block(response.text, name="phase")`
   and `runtime_block = _extract_select_block(response.text, name="runtime_option_id")`.
5. Assert the **specific** option is `selected` and the unwanted option
   is **not** selected, per the matrix:

| Test | Phase block must contain | Phase block must NOT contain | Runtime block must contain | Runtime block must NOT contain | Footer text |
|------|--------------------------|-------------------------------|-----------------------------|---------------------------------|-------------|
| `test_settings_form_reflects_phase_only_override` | `value="1" selected` | `value="global" selected` | `value="global" selected` | `value="1" selected`, `value="0" selected` | `Last changed:` |
| `test_settings_form_reflects_runtime_only_override` | `value="global" selected` | `value="1" selected` | `value="<runtime_id>" selected` | `value="global" selected` | `Last changed:` |
| `test_settings_form_reflects_both_axes_override` | `value="1" selected` | `value="global" selected` | `value="<runtime_id>" selected` | `value="global" selected` | `Last changed:` |
| `test_settings_form_clears_back_to_global` | `value="global" selected` | `value="1" selected`, `value="0" selected` | `value="global" selected` | `value="<runtime_id>" selected` | `Using global default` |

For footer assertions, scope on the `<section …>` enclosing the form
(or the unique `Using global default` / `Last changed:` strings — they
appear only inside the settings section).

Each test name MUST start with `test_settings_form_` and end with the
matrix-cell descriptor — the design document references those exact
names.

### 3. Integration test (`tests/integration/test_auto_merge_control_surface.py`)

**Match the existing pattern in this file** — there is no `client`
fixture under `tests/integration/`. The file already defines a local
`_client(db_session)` helper and uses the session-scoped `test_project`
fixture; new tests MUST follow that pattern. There is also no
`project_factory` or `runtime_option_factory` — use `test_project` for
the project and the existing `_seed_runtime(db_session, rid, enabled=True)`
helper for the runtime row.

Add one test:

```python
def test_save_config_returns_combined_fragment(db_session, test_project) -> None:
    _seed_runtime(db_session, 1, enabled=True)
    with _client(db_session) as c:
        response = c.post(
            f"/project/{test_project.id}/auto-merge/config",
            json={"phase": 1, "runtime_option_id": 1},
            headers={"Accept": "text/html"},
        )

    assert response.status_code == 200
    html = response.text

    # Settings form fragment present (NOT just the chip).
    assert 'id="auto-merge-settings"' in html, "settings fragment must be returned"
    phase_block = _extract_select_block(html, name="phase")
    assert 'value="1" selected' in phase_block

    # Chip is also present and marked as out-of-band swap (hx-swap-oob).
    assert 'id="auto-merge-status-chip"' in html
    assert 'hx-swap-oob' in html, "chip must be hx-swap-oob so it updates alongside the form"
```

Add a sibling test that asserts the JSON branch is unchanged:

```python
def test_save_config_json_response_unchanged(db_session, test_project) -> None:
    with _client(db_session) as c:
        response = c.post(
            f"/project/{test_project.id}/auto-merge/config",
            json={"phase": 1, "runtime_option_id": None},
            headers={"Accept": "application/json"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "ok": True,
        "project_id": test_project.id,
        "phase": 1,
        "runtime_option_id": None,
    }
```

`_extract_select_block` should be imported (or copied to a sibling
position) from the dashboard test module so the assertion form is shared
across the two layers.

`tests/integration/auto_merge_fixtures.py` does **not** currently exist
(verified at design time). Do NOT create it just to host these two
tests — the existing helpers in `test_auto_merge_control_surface.py`
already cover their needs. If during implementation you find you need a
shared helper across files, create it as a private function in the
existing test module rather than introducing a new fixture file.

### 4. Assertion scoping for CSS class names (I-00067 lesson)

If any of your tests assert on a CSS class name in the rendered HTML
(e.g. an `is-active` chip), use the **attribute-scoped** form, not the
bare-substring form:

```python
# BAD — substring match that can false-positive on JSON in <script>, data-* attrs, or CSS comments
assert "auto-merge-save-indicator--saved" in html

# GOOD — attribute-scoped (specific element actually carries the class)
import re
assert re.search(r'class\s*=\s*"[^"]*auto-merge-save-indicator--saved[^"]*"', html)
# or
assert 'class="auto-merge-save-indicator auto-merge-save-indicator--saved"' in html
```

### 5. Test-file placement matters (I-00067 lesson)

- Tests using the `client` fixture → `tests/dashboard/`
- Pure-Python aggregator/resolver tests → `tests/unit/`
- Tests needing the testcontainer DB → `tests/integration/`

Mixing these placements causes `fixture 'client' not found` errors.

## Project Conventions

- `tests/CLAUDE.md` and `skills/iw-ai-core-testing/SKILL.md` define the
  test framework, fixtures, naming, and quality rules.
- Tests MUST NOT connect to the live DB (port 5433). Use testcontainers
  (`tests/conftest.py` engine fixtures).
- Tests MUST replace `postgresql+psycopg2://` with `postgresql+psycopg://`
  on testcontainer URLs.
- Tests MUST run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after
  `Base.metadata.create_all()` — already handled by the existing engine
  fixture; do not duplicate.
- Use `monkeypatch.delenv()` for env vars; **NEVER** call
  `importlib.reload(orch.config)`.
- `DaemonEvent.metadata` is `event_metadata` in Python — gotcha.

## TDD Requirement (RED → GREEN)

The tests you write here MUST follow the RED-first discipline:

1. After S01 and S03 have landed, your new dashboard / integration tests
   should pass **only** because of S01+S03. If you cannot demonstrate
   this empirically without reverting (the runtime is already GREEN),
   instead assert in your report's `notes` that the tests target the
   exact assertion gap that pre-fix code would have failed on — citing
   the specific substring `value="1" selected` in the Phase block, which
   the pre-fix template literally cannot emit because the
   `{% if _is_override and ... %}` guard collapses to False on
   phase-only override.
2. Do **NOT** revert S01/S03 mid-step to "prove RED" — the design's
   `Tests prompt` section bans `git stash` / `git checkout HEAD~1` style
   reverts inside the workflow (see I-00073/S03 post-mortem).
3. Targeted run only — see "Test Verification" below.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification (NON-NEGOTIABLE)

Run **only** the test files you wrote or modified:

```bash
uv run pytest tests/unit/test_auto_merge_config_resolution.py -v
uv run pytest tests/dashboard/test_auto_merge_routes.py -v
uv run pytest tests/integration/test_auto_merge_control_surface.py -v
```

Do **NOT** run `make test-unit` / `make test-integration` /
`make allure-integration` — those are S12 / S13 QV gates and have their
own (longer) budgets. Duplicating them here is a routine cause of
step-timeout (see I-00073/S03 post-mortem, 2026-05-08).

## Migration Verification

N/A — no migration changes.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "tests-impl",
  "work_item": "I-00091",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/test_auto_merge_config_resolution.py",
    "tests/dashboard/test_auto_merge_routes.py",
    "tests/integration/test_auto_merge_control_surface.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed across unit/dashboard/integration, 0 failed",
  "tdd_red_evidence": "n/a — coverage step (tests-impl). Targets specific gap: pre-fix template cannot emit 'value=\"1\" selected' in the Phase block on phase-only override.",
  "blockers": [],
  "notes": "List the four-cell matrix names and their files; document any helper extracted to share between the dashboard and integration test modules."
}
```
