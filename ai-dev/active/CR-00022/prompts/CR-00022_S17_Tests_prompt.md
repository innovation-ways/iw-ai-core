# CR-00022_S17_Tests_prompt

**Work Item**: CR-00022
**Step**: S17
**Agent**: tests-impl

---

## ⛔ Docker / Migrations off-limits

Standard rules. Tests use **testcontainers** spun up by pytest fixtures (allowed exception). Never connect to live DB on port 5433 from tests.

## Input Files

- Design (§ TDD Approach + every AC)
- All implementation reports S01..S15
- `tests/CLAUDE.md` (testcontainer rules, FTS_FUNCTION_SQL/FTS_TRIGGER_SQL after create_all, psycopg URL replacement)
- All current OSS test files (`tests/{unit,integration}/test_oss_*.py`, `test_project_oss_job_migration.py`)

## Output Files

- New: `tests/unit/test_oss_catalog_completeness.py`
- New: `tests/unit/test_oss_check_catalog_loader.py`
- New: `tests/unit/test_oss_accepted_yaml.py`
- New: `tests/unit/test_oss_fix_recipes_idempotent.py`
- New: `tests/unit/test_oss_honor_accepted.py`
- Updated: `tests/integration/test_oss_migration.py`
- Updated: `tests/integration/test_project_oss_job_migration.py`
- Updated: `tests/integration/test_oss_dashboard_routes.py`
- Updated: `tests/integration/test_oss_dashboard_sse.py`
- Updated: `tests/integration/test_oss_cli.py`
- Updated: `tests/integration/test_oss_dashboard_service.py`
- Updated: `tests/integration/test_oss_persistence.py`
- Updated: `tests/integration/test_oss_scanner.py`
- Updated: `tests/integration/test_oss_dashboard_templates_extras.py`
- `ai-dev/active/CR-00022/reports/CR-00022_S17_Tests_report.md`

## Context

Every AC in the design has at least one test. New tests live with the feature; existing tests are updated where S03/S07/S09/S11 broke them.

## Requirements

### 1. New unit tests

#### `test_oss_catalog_completeness.py`

```python
"""CR-00022 AC4: every check_id has a catalog entry with non-empty mandatory fields."""
import ast
from pathlib import Path
import yaml

CHECKS_DIR = Path(__file__).parents[2] / "skills" / "iw-oss-publish" / "scripts" / "checks"
CATALOG = Path(__file__).parents[2] / "dashboard" / "services" / "oss_check_catalog.yaml"


def _ast_check_ids() -> set[str]:
    ids = set()
    for path in CHECKS_DIR.glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "Finding":
                for kw in node.keywords:
                    if kw.arg == "id" and isinstance(kw.value, ast.Constant):
                        ids.add(kw.value.value)
    return ids


def test_every_check_id_has_catalog_entry():
    catalog = yaml.safe_load(CATALOG.read_text()) or {}
    missing = sorted(_ast_check_ids() - catalog.keys())
    assert not missing, f"Catalog missing entries for: {missing}"


def test_no_orphan_catalog_entries():
    catalog = yaml.safe_load(CATALOG.read_text()) or {}
    orphans = sorted(catalog.keys() - _ast_check_ids())
    assert not orphans, f"Catalog has orphan entries (no matching check): {orphans}"


def test_catalog_entries_have_required_fields():
    catalog = yaml.safe_load(CATALOG.read_text()) or {}
    required = {"what_it_checks", "how_it_tests", "risk_if_failing", "how_to_fix"}
    for check_id, entry in catalog.items():
        for field in required:
            assert entry.get(field, "").strip(), \
                f"{check_id}: field '{field}' is missing or empty"
```

#### `test_oss_check_catalog_loader.py`

- `load_catalog()` returns `dict[str, CheckCopy]`
- Pydantic validation rejects YAML with empty mandatory fields
- Production cache: two calls return the same object identity (cached)
- Debug mode: two calls return different object identities (re-loaded) when `IW_CORE_DEBUG=true`
- `get_copy("nonexistent")` returns `None`

Use `monkeypatch` for `IW_CORE_DEBUG` env var. Reset the `@cache` between tests via `_load_catalog_cached.cache_clear()`.

#### `test_oss_accepted_yaml.py`

- `compute_finding_hash` is deterministic across multiple calls with same inputs
- `compute_finding_hash` differs when summary differs by one char
- `compute_finding_hash` differs when evidence dict differs (order shouldn't matter — keys sorted)
- `append_accepted` creates the file on first call
- `append_accepted` is idempotent — second append of the same `(check_id, finding_hash)` is a no-op (file unchanged byte-for-byte)
- `load_accepted` returns empty `AcceptedFile` when file is missing
- `load_accepted` returns parsed entries when file exists
- `is_accepted` matches by `(check_id, finding_hash)` exactly

Use `tmp_path` fixture for repo_root.

#### `test_oss_fix_recipes_idempotent.py`

```python
"""CR-00022 idempotency contract — every recipe applying twice is a no-op."""
import pytest
from orch.oss.fix_recipes import list_recipes


@pytest.mark.parametrize("recipe", list_recipes(), ids=lambda r: r.check_id)
def test_recipe_apply_is_idempotent(recipe, tmp_path):
    # Apply once
    recipe.apply(tmp_path)
    state1 = _snapshot(tmp_path)
    # Apply twice
    recipe.apply(tmp_path)
    state2 = _snapshot(tmp_path)
    assert state1 == state2, f"{recipe.check_id} not idempotent"


def test_preview_does_not_write(recipe, tmp_path):
    state_before = _snapshot(tmp_path)
    recipe.preview(tmp_path)
    state_after = _snapshot(tmp_path)
    assert state_before == state_after, f"{recipe.check_id}.preview() wrote to disk"


def _snapshot(root):
    return {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
```

#### `test_oss_honor_accepted.py`

- Accepted entry downgrades matching SARIF result from `error` to `warning`
- Reason text is appended to message
- Non-matching results are unchanged
- Empty/missing accepted file leaves SARIF unchanged
- Hash-mismatch entries are NOT applied
- `compute_finding_hash` in `honor_accepted.py` matches `dashboard/services/oss_accepted.py:compute_finding_hash` (golden test on a known fixture)

### 2. Updated integration tests

#### `test_oss_migration.py`

- After migration:
  - `project_oss_job` no longer has `worktree_path`, `branch_name`, `commit_sha`, `files_changed_summary`
  - `project_oss_job_kind` enum values are exactly `{scan, install, fix}`
  - `ossscan_mode` enum values are exactly `{scan}`
  - `project_oss_job_status` values are exactly `{queued, running, complete, error, cancelled}`
  - `oss_finding.auto_apply_safe` exists, `BOOLEAN NOT NULL DEFAULT false`
- Pre-migration delete: insert a row with `kind='prepare'` (via raw SQL on the previous schema), run migration, verify the row is gone

#### `test_project_oss_job_migration.py`

- Mirror of above — confirm the previously-added `awaiting_review`/`discarded` are gone and the migration is forward-only (downgrade raises `NotImplementedError`)

#### `test_oss_dashboard_routes.py`

- `POST /oss/prepare` → 404
- `POST /oss/publish` → 404
- `POST /oss/fix/{check_id}` with `apply=False` → 200, returns preview JSON
- `POST /oss/fix/{check_id}` with `apply=True` → 200, returns job_id + stream_url
- `POST /oss/recheck/{check_id}` → 200
- `POST /oss/accept/{check_id}` with `{finding_hash, reason}` → 204, file appended in working tree
- `POST /oss/accept` rejects empty reason (422)
- `POST /oss/apply-all-safe/preview` → 200, returns array
- `POST /oss/apply-all-safe` with `{check_ids: [unsafe_id]}` → 422 (server defends against UI bypass)
- `POST /oss/apply-all-safe` with valid IDs → 200, working tree modified, no branch created (assert `git symbolic-ref HEAD` unchanged)

#### `test_oss_dashboard_sse.py`

- `row-update` events emitted during scan
- Event data shape matches design (check_id, domain, severity, status, summary, auto_apply_safe, auto_fix_available, finding_hash)
- `complete` event still emitted at end
- No `progress` regression

#### `test_oss_cli.py`

- `iw oss prepare` and `iw oss publish` not registered
- `iw oss fix OSS-CH-01 --project iw-ai-core` (preview) → exit 0, JSON output validates
- `iw oss fix OSS-CH-01 --project iw-ai-core --apply` → file written
- `iw oss fix OSS-CH-99 --project iw-ai-core` (unknown ID) → exit 2 with helpful message

#### `test_oss_dashboard_service.py`

- `WORKTREE_KINDS`, `_run_worktree`, `discard_job`, `_prep_branch_name` import errors (symbols removed)
- `_run_fix(project, job_id, session_factory, check_id, apply)` exists and writes to `project.repo_root` directly
- No `tempfile.mkdtemp` or `/tmp/oss-*` paths created during any service call

Use a tmp_path fixture or testcontainer-backed `Project.repo_root` to verify writes go to the expected location.

#### `test_oss_persistence.py`

- Drop assertions for `OssScanMode.make_oss` and `.publish`
- Add: `OssFinding.auto_apply_safe` persisted from Finding into the row

#### `test_oss_scanner.py`

- Drop mode parametrisation (only `scan` remains)
- Add: scanner returns Findings carrying `auto_apply_safe` flag
- `run_scan(project, "make_oss")` raises `ValueError`

#### `test_oss_dashboard_templates_extras.py`

- Remove cards-template assertions
- Add: table renders with the new column order (Group | Test | Type | Status | Details)
- Add: modal fragment renders catalog content for a given check
- Add: filter chips present with default = failing/human-required active

### 3. Coverage map

In the report, include a table:

| AC | Tests covering |
|----|----------------|
| AC1 (no branch ever) | test_oss_dashboard_service.py::test_no_worktree_paths, test_oss_dashboard_routes.py::test_apply_all_safe_no_branch_change |
| AC2 (prepare/publish removed) | test_oss_cli.py::test_prepare_not_registered, test_oss_dashboard_routes.py::test_oss_prepare_404 |
| AC3 (table + modal) | test_oss_dashboard_templates_extras.py::test_table_columns, test_modal_renders |
| AC4 (catalog complete) | test_oss_catalog_completeness.py::test_every_check_id_has_catalog_entry |
| AC5 (apply working-tree-only, idempotent) | test_oss_fix_recipes_idempotent.py |
| AC6 (accept honored by CI) | test_oss_honor_accepted.py + manual workflow run |
| AC7 (migration hard) | test_oss_migration.py |
| AC8 (SSE row updates) | test_oss_dashboard_sse.py |
| AC9 (apply-all-safe deselectable) | covered by S27 browser verification |
| AC10 (apply-all-safe never includes unsafe) | test_oss_dashboard_routes.py::test_apply_all_safe_rejects_unsafe |
| AC11 (worktree cleanup) | manual verification in S19 |
| AC12 (e2e browser) | S27 browser verification |

### 4. TDD requirement

Per `tests/CLAUDE.md`:
- Use testcontainers (Postgres + psycopg v3 URL prefix replacement).
- Run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()`.
- Never `importlib.reload(orch.config)` — use `monkeypatch.delenv()`.
- Mark slow tests with `@pytest.mark.integration` so `make test-unit` stays fast.

### 5. Verification

```bash
make test-unit
make test-integration -- tests/integration/test_oss_*
```

Expect everything green. Any failure is a CR-00022 implementation gap to flag.

## Output / Report

Report contains:
- New + updated test file paths with summary of what each covers
- Coverage map (AC → tests)
- Final test counts (unit pass/fail, integration pass/fail)
- Any tests deferred to S27 (browser-only verifications) and why

End with `iw step-done` / `iw step-fail`.
