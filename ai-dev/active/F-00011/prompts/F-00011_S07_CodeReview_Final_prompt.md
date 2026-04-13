# F-00011_S07_CodeReview_Final_prompt

**Work Item**: F-00011 — Project-Level Documentation System — Foundation (Phase 1)
**Review Step**: S07 (Final Review)
**Implementation Steps Reviewed**: S01, S02, S04, S05, S06

---

## Input Files

- `ai-dev/active/F-00011/F-00011_Feature_Design.md` — Design document
- All implementation reports: `ai-dev/work/F-00011/reports/F-00011_S0{1,2,3,4,5,6}_*_report.md`
- All files listed in all implementation reports' `files_changed`
- `CLAUDE.md` — Project conventions

## Output Files

- `ai-dev/work/F-00011/reports/F-00011_S07_CodeReview_Final_report.md` — Final review report

## Context

You are performing the **final cross-agent review** of ALL implementation work for **F-00011: Project-Level Documentation System — Foundation (Phase 1)**.

Per-agent reviews have already been done by S03. Your job is to review the complete picture: how Database + Backend + CLI + Frontend + Tests integrate, and whether the system as a whole satisfies every acceptance criterion and invariant in the design document.

## Review Checklist

### 1. Completeness vs Design Document

Go through every section of the design document and verify implementation:

**Models:**
- [ ] `ProjectDoc` — all fields present with correct types, FTS trigger wired
- [ ] `ProjectDocVersion` — immutable snapshots, FK cascade
- [ ] `DocGenerationJob` — UUID PK, job status enum

**CLI:**
- [ ] `iw doc-update` (or `iw doc update`) is registered and callable
- [ ] All options implemented: `--content`, `--content-file`, `--status`, `--version`, `--source-paths`, `--editorial-category`, `--audience`, `--title`, `--slug`, `--generated-by`, `--trigger-reason`
- [ ] Content-from-stdin (`--content-file -`) works
- [ ] Exit codes are correct (0/1/2/3)
- [ ] Output is valid JSON to stdout on success
- [ ] Errors go to stderr (not stdout)

**Frontend routes:**
- [ ] `GET /project/{id}/docs` — library page
- [ ] `GET /project/{id}/docs/{doc_id}` — detail page
- [ ] `GET /project/{id}/docs/{doc_id}/pdf` — PDF download
- [ ] `GET /api/project/{id}/docs/search` — htmx search fragment
- [ ] `GET /api/project/{id}/docs/{doc_id}/versions` — version drawer fragment
- [ ] "Docs" added to sidebar nav (8th entry)

**Acceptance Criteria (all 6 from design doc):**
- [ ] AC1: Docs tab visible in project navigation
- [ ] AC2: Doc library renders with filter and search
- [ ] AC3: `iw doc-update` creates doc and version snapshot
- [ ] AC4: Document detail renders elegantly with metadata sidebar
- [ ] AC5: Version history drawer shows all snapshots
- [ ] AC6: PDF download is served correctly

**Invariants (all 7 from design doc):**
- [ ] I1: Every `ProjectDocVersion` has an associated `ProjectDoc` (FK)
- [ ] I2: `version` counter == count of version snapshots
- [ ] I3: New snapshot only when content hash differs
- [ ] I4: `content_search` always current (DB trigger)
- [ ] I5: `iw doc-update` is idempotent with same content
- [ ] I6: `ProjectDoc.id` is always `"{project_id}:{doc_id}"`
- [ ] I7: `pdf_path` only set on successful generation

### 2. Cross-Agent Integration

- Does the CLI command correctly import and use `DocService` from Backend?
- Does the Frontend router correctly import and use `DocService`?
- Do all routes that need a DB session use the session management pattern consistently?
- Is `DocService.upsert_doc()` called correctly from both CLI and any future use?
- Is the PDF route checking `content is None` before attempting to generate?
- Does the sidebar nav correctly highlight the active "Docs" tab?

### 3. InnoForge Strategy Alignment

Verify the implementation correctly reflects the InnoForge documentation strategy:
- Is the `tier` enum present and populated correctly by `iw doc-update`?
- Is the `editorial_category` enum mapped to the correct InnoForge categories?
- Is `source_paths` stored as a list (enabling future staleness detection)?
- Is `generated_by` stored (enabling attribution in version history)?
- Does the UI show tier information prominently (Tier 1/2/3 = Automated/Semi-Auto/Human)?

### 4. Test Coverage Completeness

Check that the following are covered by tests:
- All 6 acceptance criteria have at least one test
- All 7 invariants have at least one test
- All rows from the Boundary Behavior table have at least one test
- The full end-to-end CLI → DB → dashboard route roundtrip is tested

### 5. Security

- PDF generation path: is the file path constructed safely? (no path traversal — `project.repo_root` + fixed subdirectory + sanitized filename)
- CLI content input: is there a maximum size check on content? (prevent OOM from huge stdin pipe)
- Search input: is `plainto_tsquery()` used (safe) not raw string interpolation?
- Route parameters: are `project_id` and `doc_id` validated before DB lookup (no SQL injection possible)?

### 6. Performance

- Does `list_docs()` use pagination (`limit`/`offset`)? The library page must not load unbounded records.
- Is the FTS index used for search (not `LIKE %q%`)?
- Does the PDF route serve cached PDFs directly (not regenerate on every request)?

### 7. UI Elegance (for S05)

Verify that all non-negotiable UI requirements are implemented:
- Badge colors are all distinct and correctly mapped per type/status/tier
- Card hover animations are present
- Version history drawer has open/close animation
- Empty state is illustrated (icon + descriptive text)
- Markdown renders with syntax highlighting (not raw text)
- Detail page is two-column on desktop, single column on mobile

## Test Verification (NON-NEGOTIABLE)

Before submitting:
1. `make test-unit` — all unit tests pass
2. `make test-integration` — all integration tests pass
3. `make quality` — ruff + mypy pass

## Review Result Contract

```json
{
  "step": "S07",
  "agent": "CodeReview_Final",
  "work_item": "F-00011",
  "steps_reviewed": ["S01", "S02", "S03", "S04", "S05", "S06"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "completeness|consistency|integration|testing|architecture|security",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it",
      "cross_cutting": true
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```
