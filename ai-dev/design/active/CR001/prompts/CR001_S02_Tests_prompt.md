# CR001 S02 — Tests: Verify Favicon Serving and Template Integration

## Context

CR001 S01 added `dashboard/static/favicon.svg` and a `<link rel="icon">` in `base.html`. This step adds test coverage.

- Dashboard app factory: `dashboard/app.py` → `create_app()`
- Static files mounted at `/static` from `dashboard/static/`
- Base template: `dashboard/templates/base.html`
- Test directory: `tests/` (unit in `tests/unit/`, integration in `tests/integration/`)

## Tasks

### 1. Add a test for favicon serving

Create or extend a test file (e.g., `tests/unit/test_dashboard_favicon.py`) that:

1. Uses FastAPI's `TestClient` with `create_app()` to make a GET request to `/static/favicon.svg`
2. Asserts the response status is 200
3. Asserts the content type contains `svg` (either `image/svg+xml` or similar)
4. Asserts the response body contains `<svg` (basic SVG validity check)

### 2. Add a test for base template favicon link

Verify that the base template includes the favicon `<link>` tag:

1. Read `dashboard/templates/base.html` as a string
2. Assert it contains `rel="icon"` and `href="/static/favicon.svg"`

Or alternatively, render a page via TestClient and check the HTML output.

## Files to Change

| File | Action |
|------|--------|
| `tests/unit/test_dashboard_favicon.py` | **Create** — favicon tests |

## Acceptance Criteria

- [ ] Tests pass with `uv run pytest tests/unit/test_dashboard_favicon.py -v`
- [ ] No modifications to production code
- [ ] `ruff check` and `ruff format --check` pass
