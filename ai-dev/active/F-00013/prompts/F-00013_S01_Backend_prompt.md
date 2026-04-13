# F-00013_S01_Backend_prompt

**Work Item**: F-00013 — Project-Level Documentation System — Automation (Phase 3)
**Step**: S01
**Agent**: Backend

---

## Input Files

- `ai-dev/active/F-00013/F-00013_Feature_Design.md` — Design document (read fully)
- `ai-dev/active/F-00012/F-00012_Feature_Design.md` — F-00012 context
- `orch/daemon/` — All daemon files (post-merge flow)
- `orch/doc_service.py` — DocService (extend)
- `orch/db/models.py` — All models
- `CLAUDE.md`, `orch/CLAUDE.md`

## Output Files

- `orch/db/migrations/versions/{timestamp}_add_doc_lint_warnings.py` — Migration
- `orch/db/models.py` — Add `lint_warnings` column to `DocGenerationJob`
- `orch/doc_service.py` — Extended with: `find_docs_by_source_path()`, upgraded `get_stale_docs()`, `lint_doc_content()`
- `orch/daemon/batch_merge_hooks.py` — New file (or extend existing merge completion logic)
- `orch/cli/doc_commands.py` — Add `iw docs-check-stale` command
- `ai-dev/work/F-00013/reports/F-00013_S01_Backend_report.md` — Step report

## Context

You are implementing the automation backend for **F-00013: Documentation Automation**.

This step makes documentation generation event-driven. After a batch merges, the daemon must detect which source files changed and enqueue doc regeneration jobs. It also adds staleness detection using git mtime and a lightweight editorial lint gate.

Read the daemon's batch merge completion flow thoroughly before writing any code. Find where a `Batch` transitions to `merged` and add the hook there.

## Requirements

### 1. Migration: `lint_warnings` Column

Add `lint_warnings JSONB nullable` to `doc_generation_jobs`. Each element: `{"rule": str, "message": str, "section": str | null}`.

### 2. DocService: `find_docs_by_source_path()`

```python
def find_docs_by_source_path(
    self,
    project_id: str,
    changed_paths: list[str],
) -> list[ProjectDoc]
```

- Returns `ProjectDoc` records where any element in `source_paths` (JSONB array) matches any element in `changed_paths`
- Supports both exact matches AND glob patterns in `source_paths` (e.g., `"docs/auth/**/*.md"` matches `"docs/auth/middleware/token.md"`)
- Use `fnmatch.fnmatch()` for glob matching — iterate in Python after fetching all docs for the project (acceptable for Phase 3; Phase 4 can optimize with GIN index)
- Filter: only docs with `status != archived`

### 3. DocService: Upgrade `get_stale_docs()`

Replace the time-threshold approach with git mtime checking:

```python
def get_stale_docs(
    self,
    project_id: str,
    repo_root: str,
    threshold_hours: int = 24,
) -> list[tuple[ProjectDoc, str, datetime]]
```

- Returns list of `(doc, changed_source_path, source_mtime)` tuples
- For each `ProjectDoc` in the project with non-empty `source_paths` and non-null `generated_at`:
  - For each path in `source_paths`, run:
    ```python
    result = subprocess.run(
        ["git", "log", "-1", "--format=%ct", "--", path],
        cwd=repo_root, capture_output=True, text=True, timeout=5
    )
    ```
  - If `mtime > doc.generated_at.timestamp()` → doc is stale; record which path and when
- Skip docs with `status == archived`
- Return empty list if no stale docs

### 4. DocService: `lint_doc_content()`

```python
def lint_doc_content(
    self,
    content: str,
    editorial_category: EditorialCategory,
    forbidden_phrases: list[str] | None = None,
) -> list[dict]
```

Returns list of warning dicts `{"rule": str, "message": str, "section": str | None}`.

Rules to enforce:

**All categories:**
- `frontmatter_required`: content must start with `---` YAML frontmatter block
- `frontmatter_parseable`: the frontmatter must parse without error (`yaml.safe_load`)
- `forbidden_phrase`: any of `forbidden_phrases` (default: `["cutting-edge", "state-of-the-art", "revolutionary", "game-changing", "leverage", "synergy", "robust solution"]`) found in content

**technical:**
- `required_section_purpose`: must contain `## Purpose` heading
- `required_section_architecture`: must contain `## Architecture` heading
- `has_code_block`: must contain at least one fenced code block (` ``` `)

**functional:**
- `required_section_overview`: must contain `## Overview`
- `required_section_capabilities`: must contain `## Key Capabilities`

**guide:**
- `required_section_prerequisites`: must contain `## Prerequisites`
- `required_section_steps`: must contain `## Steps`

Returns empty list if content passes all applicable rules.

### 5. Integrate Lint into Job Completion

In `DocService.complete_doc_job()` (F-00012), after marking `completed`:
- Fetch the associated `ProjectDoc`
- If `doc.content` is not None: call `lint_doc_content()` with the doc's `editorial_category` and project-configured `forbidden_phrases`
- If warnings exist: store in `DocGenerationJob.lint_warnings`
- Do NOT change `DocStatus` — lint only populates warnings

### 6. Post-Merge Hook

Create `orch/daemon/batch_merge_hooks.py` (or extend existing merge completion function):

```python
def trigger_doc_regeneration_on_merge(
    session: Session,
    batch_item: BatchItem,
    project: Project,
) -> list[DocGenerationJob]:
    """
    Called immediately after a BatchItem transitions to merged (squash commit landed).
    Returns list of newly created DocGenerationJob records.
    """
```

Implementation:
1. Check `project.config.get("doc_generation", {}).get("auto_trigger_on_merge", False)` — if False, return `[]`
2. Compute changed files using `git diff HEAD^..HEAD --name-only` in `project.repo_root`:
   ```python
   result = subprocess.run(
       ["git", "diff", "HEAD^..HEAD", "--name-only"],
       cwd=project.repo_root, capture_output=True, text=True, timeout=10
   )
   if result.returncode != 0:
       logger.warning("[%s] git diff failed: %s", project.id, result.stderr)
       return []
   changed_files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
   ```
   This works correctly because: (a) the daemon processes one merge at a time (single-threaded), so `HEAD` is always the freshly landed squash commit; (b) no SHAs need to be stored on the `Batch` or `BatchItem` model.
3. Call `DocService.find_docs_by_source_path(project.id, changed_files)`
4. For each matched doc: call `DocService.create_doc_job(project.id, doc.doc_id, requested_by="auto:batch-merge")` with `trigger_reason=f"batch-merge:{batch_item.batch_id}:{batch_item.work_item_id}"`
5. Return created jobs

Wire this function into `orch/daemon/merge_queue.py` — call it immediately after `_emit_event(..., "item_merged", ...)` succeeds (after `db.commit()` on the merged status). Pass the `batch_item` and `project` objects.

### 7. CLI: `iw docs-check-stale`

Add to `orch/cli/doc_commands.py`:

```
iw docs-check-stale PROJECT_ID [--threshold-hours INTEGER]
```

- Calls `DocService.get_stale_docs(project_id, repo_root, threshold_hours)`
- If no stale docs: print "All docs are current." to stdout, exit 0
- If stale docs: print formatted table:
  ```
  STALE  module-auth         docs/auth/middleware.py   (modified 3h ago)
  STALE  api-reference       docs/api/routes.py         (modified 1d ago)
  ```
  Exit code 1

## TDD Requirement

Tests in `tests/unit/test_doc_automation.py`:
- `test_find_docs_by_source_path_exact_match`
- `test_find_docs_by_source_path_glob_match`
- `test_find_docs_by_source_path_no_match`
- `test_get_stale_docs_with_changed_source` — mock subprocess git log
- `test_get_stale_docs_current_doc` — no change → empty result
- `test_lint_doc_content_passes_valid_technical`
- `test_lint_doc_content_missing_purpose_section`
- `test_lint_doc_content_forbidden_phrase`
- `test_lint_doc_content_missing_frontmatter`
- `test_trigger_doc_regeneration_auto_trigger_disabled` — returns []
- `test_trigger_doc_regeneration_creates_jobs` — mock git diff, assert jobs created
- `test_docs_check_stale_exits_0_when_current` — CliRunner
- `test_docs_check_stale_exits_1_when_stale` — CliRunner

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — pass
2. `make quality` — pass

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "Backend",
  "work_item": "F-00013",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/models.py",
    "orch/db/migrations/versions/{ts}_add_doc_lint_warnings.py",
    "orch/doc_service.py",
    "orch/daemon/batch_merge_hooks.py",
    "orch/cli/doc_commands.py",
    "tests/unit/test_doc_automation.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
