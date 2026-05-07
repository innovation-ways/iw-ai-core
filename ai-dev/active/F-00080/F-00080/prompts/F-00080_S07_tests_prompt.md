# F-00080_S07_tests-impl_prompt

**Work Item**: F-00080 — First-Time User Onboarding & Contextual Help (Dashboard OSS-readiness)
**Step**: S07
**Agent**: tests-impl

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

Standard policies. No DB migrations are added in this work item.

## Input Files

- `uv run iw item-status F-00080 --json`
- `ai-dev/active/F-00080/F-00080_Feature_Design.md`
- All previous step reports
- `tests/CLAUDE.md` for test conventions
- Existing dashboard test patterns: `tests/dashboard/conftest.py`, `tests/dashboard/test_*.py`

## Output Files

- `tests/dashboard/test_help_router.py` — extend the bare RED test from S01 with full coverage
- `tests/dashboard/test_help_fragments_present.py` — orphan-slug strict integration test
- `tests/dashboard/test_empty_states.py` — empty-state macro rendering test
- `tests/dashboard/test_help_license.py` — Driver.js MIT license lockdown test (AC7)
- `tests/integration/test_help_smoke.py` — lightweight smoke test (TestClient, no real browser)
- `ai-dev/work/F-00080/reports/F-00080_S07_tests_report.md`

## Context

Implementation steps S01, S03, S05 are done. You write the formal test layer that locks the invariants from the design document into the test suite.

Per CLAUDE.md, dashboard tests use FastAPI's `TestClient` — they never need to touch docker directly. Browser-level verification is owned by S18 (qv-browser); this step does NOT need a real browser.

## Requirements

### 1. `tests/dashboard/test_help_router.py` — full coverage

Replace the placeholder tests written in S01 with a parametrised, comprehensive suite:

- **Per-slug 200 test**: parametrise over the full list of 22 slugs. For each, GET `/_help/<slug>` → 200, content-type `text/html`, body contains all 4 mandatory headings as plain substrings: `"What is this page?"`, `"What can I do here?"`, `"Vocabulary"`, and the literal string `"Take the 30-second tour"` (or `"Open full docs"`).
- **Unknown slug** → 404.
- **Path traversal** attempts → 404 for: `/_help/../etc/passwd`, `/_help/..%2Fetc%2Fpasswd`, `/_help/UPPERCASE`, `/_help/has spaces`, `/_help/123-leading-digit` (regex starts with `[a-z]`).
- **Empty slug** → 404 (`/_help/` ).
- **Slug too long** → 404 (33-char slug — exceeds the regex `{0,31}` quantifier).
- **Query-string ignored** — `/_help/queue?foo=bar` still 200.
- **Method test** — POST/PUT/DELETE on `/_help/queue` → 405.

### 2. `tests/dashboard/test_help_fragments_present.py` — orphan-slug strict integration test

Walk every Jinja template under `dashboard/templates/pages/**/*.html` AND `dashboard/templates/*.html`. For each file:

1. Use a regex to extract any `{% block page_help_slug %}<slug>{% endblock %}` declaration.
2. If a slug is declared, assert that `dashboard/templates/_partials/help/<slug>.html` exists.
3. Aggregate all violations and fail with the full list (do not fail on the first one).

Also add the **reverse** check: for every fragment file in `dashboard/templates/_partials/help/*.html`, assert at least one page template declares that slug. This catches dead fragments that no page is using.

Both checks must run as part of `make test-integration`.

### 3. `tests/dashboard/test_empty_states.py` — empty-state rendering test

Render each of the 10 list views via TestClient with a state that produces an empty list (e.g. a project with no items, or stub the underlying query to return `[]` via `monkeypatch`/dependency override). For each, assert the response HTML contains:

- `data-empty-state="<slug>"`
- An `<h3>` (the heading)
- A `<p>` (the body)
- An `<a class="empty-state__cta-primary">` (the primary CTA)

Failing pages should fail individually so we can see which one regressed.

### 4. `tests/dashboard/test_help_license.py` — Driver.js MIT license lockdown (AC7)

This test enforces Acceptance Criterion AC7 ("Apache 2.0 OSS license compatibility") so a future agent cannot accidentally ship without the MIT attribution. Pure file-content assertions, no TestClient needed:

- `test_driver_license_file_exists_and_is_mit`: `dashboard/static/vendor/driver/LICENSE` exists, is non-empty, and contains the literal substrings `"MIT"` and `"Permission is hereby granted, free of charge"` (the canonical opening of the MIT text).
- `test_driver_iife_has_mit_header`: the first ~40 lines of `dashboard/static/vendor/driver/driver.js.iife.js` include the literal substring `"MIT"` (the upstream MIT header comment).
- `test_third_party_licenses_lists_driver`: `THIRD_PARTY_LICENSES` (project root) exists and contains the literal substring `"Driver.js"` AND `"MIT"`.
- `test_no_agpl_onboarding_lib_vendored`: assert there is NO directory under `dashboard/static/vendor/` named `shepherd`, `intro` (or `intro-js`), `tour`, or any path whose `LICENSE` text contains `"AGPL"` (walk `dashboard/static/vendor/**/LICENSE` and grep).

Skip with a clear `pytest.skip("vendored Driver.js not present yet")` if any expected file is missing — but in CI on the merged work item, none of these files may be missing, so the test must run hot.

### 5. `tests/integration/test_help_smoke.py` — lightweight smoke test

Using TestClient (no real browser):

- Test A: GET `/project/<demo-id>/queue` → 200 → response HTML contains `data-help-slug="queue"`.
- Test B: GET `/_help/queue` → 200 → contains all four mandatory headings AND a `data-tour-start` button.
- Test C: GET `/static/help/help.js` → 200 (asset is served).
- Test D: GET `/static/help/tours.js` → 200 (asset is served).
- Test E: GET `/static/vendor/driver/driver.js.iife.js` → 200 (vendored Driver.js is reachable). HEAD is fine if your TestClient supports it.

Assert no test triggers an outbound network call (FastAPI TestClient never does, but document this in a comment so future maintainers don't add httpx mocks that could hide a regression).

### 6. Test conventions to follow

- See `tests/CLAUDE.md` for fixture rules.
- Use the existing dashboard test client fixtures rather than building your own.
- Do NOT mock the database in integration tests (CLAUDE.md hard rule).
- Keep each test under ~50 lines; split helpers into a `_helpers.py` file in the same dir if needed.

### 7. Coverage targets

- All 22 slugs covered by the parametrised 200 test in `test_help_router.py`.
- All 10 list views covered by `test_empty_states.py`.
- Orphan-slug check covers every page template in the codebase.
- Driver.js MIT licensing locked in via `test_help_license.py` (AC7).

## Project Conventions

Read root `CLAUDE.md` and `tests/CLAUDE.md`.

## TDD Requirement

These tests will go GREEN immediately when run against the post-S05 codebase (since the feature is already implemented). Treat them as the formal lockdown layer; do not soften assertions to make them pass.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification

Run `make test-unit && make test-integration` and confirm zero failures across the suite (your tests + existing tests must all pass).

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "tests-impl",
  "work_item": "F-00080",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/dashboard/test_help_router.py",
    "tests/dashboard/test_help_fragments_present.py",
    "tests/dashboard/test_empty_states.py",
    "tests/dashboard/test_help_license.py",
    "tests/integration/test_help_smoke.py"
  ],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "N passed, 0 failed (N includes 22 parametrised + 10 empty-state + ...)",
  "blockers": [],
  "notes": ""
}
```
