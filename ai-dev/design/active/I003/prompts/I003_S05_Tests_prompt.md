# I003_S05_Tests_prompt

**Work Item**: I003 — History Page Sorting Broken — Replace with Client-Side JS Sorting
**Step**: S05
**Agent**: Tests

---

## Input Files

- `ai-dev/design/active/I003/I003_Issue_Design.md` — Design document
- `ai-dev/design/active/I003/reports/I003_S01_Frontend_report.md` — S01 report
- `ai-dev/design/active/I003/reports/I003_S03_Backend_report.md` — S03 report

## Output Files

- `ai-dev/design/active/I003/reports/I003_S05_Tests_report.md` — Step report

## Context

You are writing reproduction and regression tests for I003. The fix replaced server-side sorting (via page reloads) with client-side JavaScript sorting on the History page, and removed server-side pagination.

Read the design document and prior reports first, then read `CLAUDE.md`.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "permissions" in data` (shape only)
- GOOD: `assert "brands:manage" in permissions` (semantic — verifies specific expected value)
- GOOD: `assert "*" not in permissions` (semantic — verifies unwanted value is absent)

Apply this principle to ALL tests below.

## Requirements

### 1. Reproduction Test (MANDATORY)

Write a test that **would have FAILED** before the fix and **PASSES** after:

```python
def test_i003_history_no_server_sort_links(client, ...):
    """History page must NOT contain server-side sort links.
    
    Before fix: response contained <a href="?sort_by=..."> links.
    After fix: response contains sortTable() JS instead.
    """
    response = client.get("/project/iw-ai-core/history")
    html = response.text
    
    # Must NOT contain server-side sort links
    assert '?sort_by=' not in html
    assert '?sort_dir=' not in html
    assert 'sort_header' not in html  # macro should be gone
    
    # MUST contain client-side sorting
    assert 'sortTable' in html
    assert 'data-sort-key=' in html
    assert 'data-sort-id=' in html
```

### 2. Regression Tests (MANDATORY)

Write tests covering:

#### 2a. Client-side sort attributes present on rows

```python
def test_i003_history_rows_have_sort_data_attributes(client, ...):
    """Each history item row must have data-sort-* attributes for client-side sorting."""
    # Create test items that will appear in history (completed/failed status)
    # Request the history page
    # Assert each row has: data-sort-id, data-sort-type, data-sort-title,
    #   data-sort-status, data-sort-created_at, data-sort-duration
    # Assert SPECIFIC values in the attributes (not just existence)
```

#### 2b. No pagination in response

```python
def test_i003_history_no_pagination(client, ...):
    """History page must not contain pagination UI."""
    response = client.get("/project/iw-ai-core/history")
    html = response.text
    
    assert '← Prev' not in html
    assert 'Next →' not in html
    assert 'page=' not in html  # no page query params in any links
```

#### 2c. All items returned (no slicing)

```python
def test_i003_history_returns_all_items(client, ...):
    """History page must return all matching items, not paginated subset."""
    # Create 25+ completed items (more than old _HISTORY_PAGE_SIZE of 20)
    # Request history page
    # Assert ALL items appear in response (not just first 20)
```

#### 2d. Backend function signature

```python
def test_i003_history_items_no_sort_params():
    """_history_items() must not accept sort_by, sort_dir, or page params."""
    import inspect
    from dashboard.routers.project_pages import _history_items
    
    sig = inspect.signature(_history_items)
    param_names = set(sig.parameters.keys())
    
    assert 'sort_by' not in param_names
    assert 'sort_dir' not in param_names
    assert 'page' not in param_names
```

#### 2e. Filters still work

```python
def test_i003_history_filters_still_work(client, ...):
    """Type and status filters must still function after sorting fix."""
    # Create items of different types/statuses
    # Filter by specific type
    # Assert only matching items appear (verify SPECIFIC item IDs)
```

#### 2f. sortTable JS function present

```python
def test_i003_history_has_sort_js(client, ...):
    """History page must contain inline sortTable() JavaScript."""
    response = client.get("/project/iw-ai-core/history")
    html = response.text
    
    assert 'function sortTable' in html or 'window.sortTable' in html
    assert 'isNumeric' in html
    assert 'sort-icon' in html
```

### 3. Test Organization

- Place tests in `tests/unit/test_history_sorting.py` (for signature checks, response content checks)
- Place integration tests in `tests/integration/test_history_sorting.py` (for DB-backed tests with real items)
- Follow existing test patterns in the project (check `tests/` for fixtures and conventions)

## Project Conventions

Read the project's `CLAUDE.md` for:
- pytest + testcontainers for integration tests
- NEVER connect to live DB (port 5433)
- testcontainers returns psycopg2 URLs — replace with psycopg
- After `Base.metadata.create_all()`, execute `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL`

## TDD Requirement

These tests formalize the fix that S01 and S03 already implemented. Write tests that verify the current (fixed) behavior. All tests must pass.

## Test Verification (NON-NEGOTIABLE)

After writing tests:
1. Run `make test-unit` — ALL tests must pass
2. Run `make test-integration` — ALL tests must pass
3. Do **NOT** report `tests_passed: true` unless ALL tests pass with zero failures

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "Tests",
  "work_item": "I003",
  "completion_status": "complete|partial|blocked",
  "files_changed": [],
  "tests_passed": true,
  "test_summary": "",
  "blockers": [],
  "notes": ""
}
```
