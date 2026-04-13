# F-00014_S05_CodeReview_Final_prompt

**Work Item**: F-00014 — Project-Level Documentation System — Polish (Phase 4)
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01, S02, S03, S04

---

## Input Files

- `ai-dev/active/F-00014/F-00014_Feature_Design.md` — Design document
- All implementation reports: `ai-dev/work/F-00014/reports/F-00014_S0{1,2,3,4}_*_report.md`
- All files listed in all reports' `files_changed`
- `CLAUDE.md`, `dashboard/CLAUDE.md`

## Output Files

- `ai-dev/work/F-00014/reports/F-00014_S05_CodeReview_Final_report.md`

## Context

Final cross-agent review for **F-00014: Documentation Polish** — the last phase of the documentation system. Verify correctness, safety, and that all 7 acceptance criteria and 5 invariants are satisfied. Pay special attention to security (ZIP path traversal, external URL fetching, diff rendering of user content).

## Review Checklist

### 1. Completeness — All 7 AC Implemented

- [ ] AC1: Version diff shows line-level changes with correct colors
- [ ] AC2: Global search returns results across projects, grouped by project
- [ ] AC3: Export bundle ZIP contains .md, .html, .pdf, _generation_notes.md
- [ ] AC4: Multi-select export bundles multiple docs in subdirectories
- [ ] AC5: Broken link validation detects dead links and updates DB
- [ ] AC6: `iw docs-export` generates bundles locally with correct structure
- [ ] AC7: Global search filters work correctly

### 2. Security — Critical for This Phase

- [ ] **ZIP path traversal**: `iw docs-export --output-dir` must be validated as absolute and not escape it. Are `slug` values sanitized before use as ZIP entry names? (`os.path.basename()` or slug validation)
- [ ] **Diff rendering**: Diff content comes from user-generated markdown — is it HTML-escaped before rendering in the diff viewer? (prevent XSS from malicious content in doc versions)
- [ ] **Link validation external fetch**: Is there a timeout? (yes — 5s in spec). Is there protection against SSRF? (internal network URLs like `http://localhost:9900` — should these be blocked?)
- [ ] **Global search**: Is the `q` parameter sanitized? (`plainto_tsquery()` is safe but verify no raw interpolation)

### 3. Diff Viewer

- [ ] Lines are HTML-escaped (doc content may contain `<script>` tags)
- [ ] Diff is capped at 100 lines in the template (or configurable)
- [ ] "Show all" button works or is clearly marked as Phase 4b future work
- [ ] Identical versions shows correct empty state (no JS errors)
- [ ] Version selection checkboxes enforce exactly 2 selected (not more)

### 4. Export Bundle

- [ ] ZIP does not include docs with `content=None`
- [ ] `_generation_notes.md` contains useful metadata (not just empty)
- [ ] Multiple-doc ZIP uses subdirectories (not flat with colliding filenames)
- [ ] `iw docs-export` path traversal protection: `--output-dir` validated

### 5. Global Search

- [ ] Archived docs excluded by default
- [ ] `ts_headline()` output is properly escaped (FastAPI/Jinja2 auto-escaping active?)
- [ ] Results grouped correctly by project (no doc appearing in wrong project group)
- [ ] Empty query returns empty state, not all docs (unbounded)

### 6. Link Validation

- [ ] External HTTP requests run in `asyncio.to_thread` (not blocking the event loop)
- [ ] Max 20 links enforced (no OOM on docs with hundreds of links)
- [ ] 5xx responses treated as transient (not stored as broken)
- [ ] `broken_links` updated atomically with the doc (single session commit)

### 7. All 5 Invariants

- [ ] I1: Diff always shows older version on left/top (lower version number)
- [ ] I2: Export ZIP filenames are slug-safe
- [ ] I3: `broken_links` only set after explicit validation
- [ ] I4: Global search excludes archived by default
- [ ] I5: `iw docs-export` never writes outside output-dir

### 8. Test Coverage

- [ ] Diff: identical content, wrong order, unknown version, real change
- [ ] Export: single, multi, no-content skip, CLI
- [ ] Link validation: internal found/not-found, external 404, 5xx transient, max limit
- [ ] Global search: cross-project, filter, highlight, grouped, empty
- [ ] All boundary rows have tests

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — pass
2. `make test-integration` — pass
3. `make quality` — ruff + mypy pass

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "F-00014",
  "steps_reviewed": ["S01", "S02", "S03", "S04"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```
