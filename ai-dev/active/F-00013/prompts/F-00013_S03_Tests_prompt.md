# F-00013_S03_Tests_prompt

**Work Item**: F-00013 — Project-Level Documentation System — Automation (Phase 3)
**Step**: S03
**Agent**: Tests

---

## Input Files

- `ai-dev/active/F-00013/F-00013_Feature_Design.md` — Design document (Acceptance Criteria + Boundary Behavior)
- All S01–S02 implementation reports
- `tests/CLAUDE.md` — Read first
- `tests/conftest.py`

## Output Files

- `tests/integration/test_doc_automation.py` — Integration tests
- `ai-dev/work/F-00013/reports/F-00013_S03_Tests_report.md` — Step report

## Context

Integration tests for **F-00013: Documentation Automation**. Key challenge: testing the post-merge hook requires a real git repository. Use `tmp_path` + `git init` to create a minimal repo fixture with staged commits. Test the hook by calling the function directly with a mock `Batch` object (with known pre/post merge SHAs), then asserting jobs were created.

**CRITICAL**: NEVER connect to live DB. NEVER mock DB. Testcontainers only.

## Requirements

### 1. Post-Merge Hook Tests (`tests/integration/test_doc_automation.py`)

**`test_merge_hook_creates_jobs_for_matching_docs`**
```
Setup:
  - git init repo in tmp_path
  - Create docs/auth.md, commit as "base" (HEAD~1)
  - Modify docs/auth.md, commit as "change" (HEAD — simulates squash merge landing)
  - Create ProjectDoc with source_paths=["docs/auth.md"]
  - project.repo_root = tmp_path

Execute: trigger_doc_regeneration_on_merge(session, mock_batch_item, project)
  # The hook runs git diff HEAD^..HEAD --name-only in project.repo_root

Assert:
  - 1 DocGenerationJob created
  - trigger_reason contains batch_item.batch_id and batch_item.work_item_id
  - status = queued
```

**`test_merge_hook_no_jobs_when_auto_trigger_disabled`**
```
Project.config["doc_generation"]["auto_trigger_on_merge"] = False
Execute: trigger_doc_regeneration_on_merge(...)
Assert: 0 jobs created
```

**`test_merge_hook_no_jobs_when_source_not_changed`**
```
Setup: HEAD commit changed only README.md (not docs/auth.md)
ProjectDoc has source_paths=["docs/auth.md"]
Assert: 0 jobs created
```

**`test_merge_hook_glob_path_matching`**
```
Setup: HEAD commit changed "docs/auth/middleware/token.py"
ProjectDoc has source_paths=["docs/auth/**/*.py"]
Assert: 1 job created (glob match)
```

### 2. Staleness Tests

**`test_get_stale_docs_detects_changed_source`** — git fixture, modify source after generated_at  
**`test_get_stale_docs_returns_empty_for_current`** — source older than generated_at → empty  
**`test_docs_check_stale_cli_exits_1`** — CliRunner with stale doc → exit 1  
**`test_docs_check_stale_cli_exits_0`** — no stale docs → exit 0  

### 3. Lint Gate Tests

**`test_lint_gate_runs_after_job_completion`**
```
Create job, write content missing "## Purpose", complete job
Assert: DocGenerationJob.lint_warnings contains warning about missing section
Assert: DocStatus unchanged (still draft)
```

**`test_lint_gate_passes_valid_content`** — valid technical doc → empty lint_warnings  
**`test_lint_gate_forbidden_phrase`** — content with "cutting-edge" → warning  
**`test_lint_warnings_route`** — GET /api/project/{id}/docs/{doc_id}/lint-warnings → 200 with warnings HTML  

### 4. Config Panel Tests

**`test_config_panel_saves_auto_trigger_setting`**
```
POST /api/project/{id}/docs/config with auto_trigger_on_merge=true
Assert: Project.config["doc_generation"]["auto_trigger_on_merge"] == True
GET /api/project/{id}/docs/config → assert toggle shows enabled
```

**`test_config_panel_saves_forbidden_phrases`**  
**`test_regenerate_stale_creates_jobs`** — POST /api/project/{id}/docs/regenerate-stale with stale docs → N jobs created  
**`test_stale_summary_route`** — GET /api/project/{id}/docs/stale → 200 with banner HTML  

### 5. Boundary Tests

- `test_merge_hook_high_volume_queues_within_limit` — 10 docs match → max 2 start, 8 remain queued
- `test_get_stale_docs_skips_archived` — archived docs not returned
- `test_lint_doc_no_content_skipped` — doc with null content → lint not called
- `test_config_defaults_when_not_set` — no doc_generation key in config → defaults apply

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — pass
2. `make test-integration` — pass
3. `make quality` — pass

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "Tests",
  "work_item": "F-00013",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/integration/test_doc_automation.py"
  ],
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
