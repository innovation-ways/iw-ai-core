# F-00021_S03_Tests_prompt

**Work Item**: F-00021 — Research Panel in AI Dashboard
**Step**: S03
**Agent**: Tests
**Parallel With**: None — sequential after S02

---

## Input Files

- `ai-dev/active/F-00021/F-00021_Feature_Design.md`
- `ai-dev/active/F-00021/reports/F-00021_S01_Frontend_report.md`
- `ai-dev/active/F-00021/reports/F-00021_S02_CodeReview_Frontend_report.md`

## Output Files

- `ai-dev/active/F-00021/reports/F-00021_S03_Tests_report.md`

## Context

Add integration tests for the Research panel routes. Extend the existing test file
`tests/integration/test_dashboard_pages.py` in `iw-ai-core`.

**Repository**: ``

## Architecture References

Read before implementing:

- `tests/integration/test_dashboard_pages.py` — Existing page tests and fixtures
- `tests/integration/conftest.py` — `client`, `db_session`, `test_project` fixtures
- `orch/doc_service.py:upsert_doc` — How to seed research docs in tests
- `orch/db/models.py` — `DocType`, `DocStatus`, `EditorialCategory`, `ProjectDoc`

## Previous Steps

- S01: Research router, templates, nav, and app.py updated
- S02: Code review passed

## Requirements

Add these tests to `tests/integration/test_dashboard_pages.py`:

### Helper: `_seed_research_doc`

```python
def _seed_research_doc(
    db_session,
    project_id: str,
    doc_id: str = "R-00001",
    title: str = "Test Research",
    content: str = "# Findings\nSome findings.",
    status: str = "published",
    category: str = "technical",
) -> None:
    """Seed a research ProjectDoc via DocService (handles composite PK, slug, tier, etc.)."""
    from orch.db.models import DocStatus, DocTier, DocType, EditorialCategory
    from orch.doc_service import DocService
    svc = DocService(db_session)
    svc.create_doc(
        project_id=project_id,
        doc_id=doc_id,
        title=title,
        doc_type=DocType.research,
        tier=DocTier.human_authored,
        editorial_category=EditorialCategory(category),
        status=DocStatus(status),
        content=content,
    )
```

### Test 1: `test_research_library_page_empty`

```python
def test_research_library_page_empty(client, test_project):
    """Research library page renders with empty state when no research docs exist."""
    response = client.get(f"/project/{test_project.id}/research")
    assert response.status_code == 200
    assert "research" in response.text.lower() or "iw-research" in response.text
```

### Test 2: `test_research_library_page_with_docs`

```python
def test_research_library_page_with_docs(client, db_session, test_project):
    """Research library lists seeded research documents."""
    _seed_research_doc(db_session, test_project.id, doc_id="R-00001", title="API Rate Limiting Research")
    response = client.get(f"/project/{test_project.id}/research")
    assert response.status_code == 200
    assert "R-00001" in response.text
    assert "API Rate Limiting Research" in response.text
```

### Test 3: `test_research_detail_page`

```python
def test_research_detail_page(client, db_session, test_project):
    """Research detail page renders markdown content."""
    _seed_research_doc(
        db_session, test_project.id,
        doc_id="R-00002",
        title="Queue Strategy Research",
        content="# Queue Strategy\n\nRedis is **fast**.",
    )
    response = client.get(f"/project/{test_project.id}/research/R-00002")
    assert response.status_code == 200
    assert "Queue Strategy Research" in response.text
    # Markdown rendered to HTML
    assert "<strong>fast</strong>" in response.text or "fast" in response.text
```

### Test 4: `test_research_detail_page_not_found`

```python
def test_research_detail_page_not_found(client, test_project):
    """Research detail page returns 404 for unknown doc_id."""
    response = client.get(f"/project/{test_project.id}/research/R-99999")
    assert response.status_code == 404
```

### Test 5: `test_research_detail_wrong_doc_type_returns_404`

```python
def test_research_detail_wrong_doc_type_returns_404(client, db_session, test_project):
    """Research detail page returns 404 if doc_id belongs to a non-research doc."""
    from orch.db.models import DocStatus, DocTier, DocType, EditorialCategory
    from orch.doc_service import DocService
    svc = DocService(db_session)
    svc.create_doc(
        project_id=test_project.id,
        doc_id="MOD-00001",
        title="Module Doc",
        doc_type=DocType.module,
        tier=DocTier.human_authored,
        editorial_category=EditorialCategory.technical,
        status=DocStatus.published,
        content="# Module",
    )
    response = client.get(f"/project/{test_project.id}/research/MOD-00001")
    assert response.status_code == 404
```

### Test 6: `test_research_detail_null_content`

```python
def test_research_detail_null_content(client, db_session, test_project):
    """Research detail page renders gracefully when content is None."""
    from orch.db.models import DocStatus, DocTier, DocType, EditorialCategory
    from orch.doc_service import DocService
    svc = DocService(db_session)
    svc.create_doc(
        project_id=test_project.id,
        doc_id="R-00003",
        title="Empty Research",
        doc_type=DocType.research,
        tier=DocTier.human_authored,
        editorial_category=EditorialCategory.technical,
        status=DocStatus.draft,
        content=None,
    )
    response = client.get(f"/project/{test_project.id}/research/R-00003")
    assert response.status_code == 200
```

## Test Verification

```bash
cd /home/sergiog/dev/iw-doc-plan/main/iw-ai-core
.venv/bin/pytest tests/integration/test_dashboard_pages.py -x --timeout=120 -q
```

All new tests and all existing dashboard page tests must pass.

## Constraints

- Only modify `tests/integration/test_dashboard_pages.py`
- Use existing fixtures — do not add to `conftest.py`
- Tests must be independent (no shared state between tests)

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "Tests",
  "work_item": "F-00021",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/integration/test_dashboard_pages.py"
  ],
  "tests_passed": true,
  "test_summary": "N passed, 0 failed — all existing + 6 new tests pass",
  "coverage": "N/A",
  "blockers": [],
  "notes": ""
}
```
