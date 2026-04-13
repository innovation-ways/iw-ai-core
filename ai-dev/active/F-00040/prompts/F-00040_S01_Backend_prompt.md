# F-00040_S01_Backend_prompt

**Work Item**: F-00040 — Enhanced Document Diff
**Step**: S01
**Agent**: Backend
**Parallel With**: None — first step

---

## Input Files

- `ai-dev/active/F-00040/F-00040_Feature_Design.md` — Design document
- `orch/doc_service.py` — Existing `diff_versions()` to preserve
- `dashboard/routers/docs.py` — Existing diff endpoint to preserve
- `orch/doc_sections.py` — `extract_sections` / `split_by_sections` (added by F-00039)

## Output Files

- `ai-dev/active/F-00040/reports/F-00040_S01_Backend_report.md`

## Context

You are implementing the enhanced document diff module for **iw-ai-core**.

**Repository location**:
```
/home/sergiog/dev/iw-doc-plan/main/iw-ai-core
```

**CRITICAL**: Do NOT remove or rename `DocService.diff_versions()` in `orch/doc_service.py`.
Do NOT change the existing `/api/docs/{doc_id}/diff` endpoint behavior. Both must remain
identical to their pre-F-00040 state.

## Requirements

### 1. Create `orch/doc_diff.py`

```python
"""Section-aware document diff module for iw-ai-core.

Computes structured diffs between two document version strings by splitting
each version into H2-bounded sections and diffing each section pair individually.
This module has no database dependencies — it operates on strings only.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from typing import Literal

from orch.doc_sections import extract_sections, split_by_sections


@dataclass
class SectionDiff:
    """Diff result for a single document section."""

    section_name: str
    """H2 heading text, or 'Document' for docs with no H2 headings."""

    status: Literal["added", "removed", "changed", "unchanged"]
    """Change classification for this section between versions."""

    unified_diff: list[str] = field(default_factory=list)
    """Unified diff lines for this section (empty when status is 'unchanged')."""


@dataclass
class DocDiff:
    """Structured diff between two document versions."""

    version_old: int
    version_new: int
    sections: list[SectionDiff] = field(default_factory=list)


def diff_document_versions(
    old_content: str,
    new_content: str,
    version_old: int,
    version_new: int,
) -> DocDiff:
    """Compute a section-aware diff between two document version strings.

    Splits both versions into H2-bounded sections using extract_sections/
    split_by_sections, then diffs each section pair. Sections present only
    in the old version are classified as 'removed'; sections only in the new
    version are classified as 'added'.

    Documents with no H2 headings are treated as a single section named
    "Document".

    Args:
        old_content: Markdown content of the older version.
        new_content: Markdown content of the newer version.
        version_old: Version number of the old content.
        version_new: Version number of the new content.

    Returns:
        DocDiff with one SectionDiff per section found in either version.
    """
    old_sections = split_by_sections(old_content)
    new_sections = split_by_sections(new_content)

    all_section_names = list(dict.fromkeys(
        list(old_sections.keys()) + list(new_sections.keys())
    ))

    section_diffs: list[SectionDiff] = []
    for name in all_section_names:
        old_body = old_sections.get(name)
        new_body = new_sections.get(name)

        if old_body is None:
            section_diffs.append(SectionDiff(section_name=name, status="added", unified_diff=list(
                difflib.unified_diff([], new_body.splitlines(keepends=True),
                                     fromfile=f"v{version_old}/{name}", tofile=f"v{version_new}/{name}", n=3)
            )))
        elif new_body is None:
            section_diffs.append(SectionDiff(section_name=name, status="removed", unified_diff=list(
                difflib.unified_diff(old_body.splitlines(keepends=True), [],
                                     fromfile=f"v{version_old}/{name}", tofile=f"v{version_new}/{name}", n=3)
            )))
        elif old_body == new_body:
            section_diffs.append(SectionDiff(section_name=name, status="unchanged"))
        else:
            section_diffs.append(SectionDiff(section_name=name, status="changed", unified_diff=list(
                difflib.unified_diff(old_body.splitlines(keepends=True), new_body.splitlines(keepends=True),
                                     fromfile=f"v{version_old}/{name}", tofile=f"v{version_new}/{name}", n=3)
            )))

    return DocDiff(version_old=version_old, version_new=version_new, sections=section_diffs)
```

### 2. Add three new routes to `dashboard/routers/docs.py`

Add after the existing `/api/docs/{doc_id}/diff` endpoint (around line 675):

**Route 1: Section summary (JSON)**
```python
@router.get("/api/docs/{doc_id}/diff/sections")
def docs_diff_sections(
    project_id: str,
    doc_id: str,
    db: Session = Depends(get_db),
    v1: int = 0,
    v2: int = 0,
) -> Any:
    """Return a structured section-level diff as JSON."""
    _get_project_or_404(project_id, db)
    if v1 >= v2:
        raise HTTPException(status_code=422, detail=f"v1 ({v1}) must be less than v2 ({v2})")
    svc = DocService(db)
    doc = svc.get_doc(project_id, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {doc_id!r} not found")
    # Load both version contents
    from orch.db.models import ProjectDocVersion
    from sqlalchemy import select as sa_select
    def _get_ver(v: int) -> str:
        composite = f"{project_id}:{doc_id}"
        row = db.execute(
            sa_select(ProjectDocVersion)
            .where(ProjectDocVersion.doc_id == composite)
            .where(ProjectDocVersion.version == v)
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Version {v} not found for doc '{doc_id}'")
        return row.content or ""
    old_content = _get_ver(v1)
    new_content = _get_ver(v2)
    from orch.doc_diff import diff_document_versions, DocDiff, SectionDiff
    result: DocDiff = diff_document_versions(old_content, new_content, v1, v2)
    return {
        "version_old": result.version_old,
        "version_new": result.version_new,
        "sections": [
            {
                "section_name": s.section_name,
                "status": s.status,
                "unified_diff": s.unified_diff,
            }
            for s in result.sections
        ],
    }
```

**Route 2: Per-section unified diff (HTML)**
```python
@router.get("/api/docs/{doc_id}/diff/sections/{section_name}", response_class=HTMLResponse)
def docs_diff_section(
    project_id: str,
    doc_id: str,
    section_name: str,
    request: Request,
    db: Session = Depends(get_db),
    v1: int = 0,
    v2: int = 0,
) -> Any:
    """Return an HTML fragment showing the unified diff for a single named section."""
    import urllib.parse
    section_name = urllib.parse.unquote(section_name)
    _get_project_or_404(project_id, db)
    if v1 >= v2:
        raise HTTPException(status_code=422, detail=f"v1 must be less than v2")
    svc = DocService(db)
    doc = svc.get_doc(project_id, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {doc_id!r} not found")
    from orch.db.models import ProjectDocVersion
    from sqlalchemy import select as sa_select
    def _get_ver(v: int) -> str:
        composite = f"{project_id}:{doc_id}"
        row = db.execute(
            sa_select(ProjectDocVersion)
            .where(ProjectDocVersion.doc_id == composite)
            .where(ProjectDocVersion.version == v)
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Version {v} not found for doc '{doc_id}'")
        return row.content or ""
    old_content = _get_ver(v1)
    new_content = _get_ver(v2)
    from orch.doc_diff import diff_document_versions
    result = diff_document_versions(old_content, new_content, v1, v2)
    section_diff = next((s for s in result.sections if s.section_name == section_name), None)
    if section_diff is None:
        raise HTTPException(status_code=404, detail=f"Section '{section_name}' not found in diff")
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/docs_diff.html",  # reuse existing diff template
        {
            "diff_lines": section_diff.unified_diff,
            "v1": v1,
            "v2": v2,
            "doc_id": doc_id,
            "project_id": project_id,
        },
    )
```

**Route 3: AI summary stub (204)**
```python
@router.get("/api/docs/{doc_id}/diff/ai-summary")
def docs_diff_ai_summary(
    project_id: str,
    doc_id: str,
    db: Session = Depends(get_db),
    v1: int = 0,
    v2: int = 0,
) -> Any:
    """Stub endpoint for AI-powered diff summarization (F-00025 not yet shipped).

    Always returns HTTP 204 with X-Stub header until F-00025 provides the
    real implementation. No body is returned. Callers should handle 204 gracefully.
    """
    from fastapi.responses import Response
    _get_project_or_404(project_id, db)
    return Response(
        status_code=204,
        headers={"X-Stub": "waiting-for-F-00025"},
    )
```

## Project Conventions

Read `orch/CLAUDE.md` and `dashboard/CLAUDE.md` for:
- Router thin-layer pattern (delegate logic to service/module)
- Import order
- Type annotations

Match exactly the style of existing router endpoints.

## Constraints

- `DocService.diff_versions()` in `orch/doc_service.py` must NOT be modified
- The existing `/api/docs/{doc_id}/diff` endpoint must NOT be changed
- `orch/doc_diff.py` must have NO imports from `orch.doc_service` or SQLAlchemy
- Lazy-import `orch.doc_diff` inside the route functions to avoid circular imports if any

## Test Verification

```bash
cd /home/sergiog/dev/iw-doc-plan/main/iw-ai-core
.venv/bin/python -m ruff check orch/doc_diff.py dashboard/routers/docs.py
.venv/bin/python -m mypy orch/doc_diff.py dashboard/routers/docs.py
```

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "Backend",
  "work_item": "F-00040",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/doc_diff.py",
    "dashboard/routers/docs.py"
  ],
  "tests_passed": true,
  "test_summary": "N/A — lint and typecheck only at this step",
  "coverage": "N/A",
  "blockers": [],
  "notes": ""
}
```
