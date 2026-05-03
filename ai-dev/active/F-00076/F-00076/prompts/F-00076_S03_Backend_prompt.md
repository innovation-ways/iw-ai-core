# F-00076_S03_Backend_prompt

**Work Item**: F-00076 -- Cross-batch file-conflict gate
**Step**: S03
**Agent**: backend-impl

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

(Same constraints as the design document — read `docs/IW_AI_Core_Agent_Constraints.md`.)

## Input Files

- `uv run iw item-status F-00076 --json`
- `ai-dev/active/F-00076/F-00076_Feature_Design.md` (sections: Description, Scope/In Scope items 4-7, AC3/AC4, Boundary Behavior, Invariants 2)
- `ai-dev/active/F-00076/reports/F-00076_S01_Database_report.md` (column shape, migration revision id)
- `orch/design_doc_parser.py` — current parser module (extend it)
- `orch/cli/item_commands.py:212-460` — `register()` command (insertion point around line 350 where `parse_dependencies` is called)
- `orch/batch_planner.py:90-219` — current `extract_affected_files()` and `analyze_dependencies()`
- `ai-dev/templates/Feature_Design_Template.md`, `Issue_Design_Template.md`, `CR_Design_Template.md` (active copies)
- `templates/design/` — master copies that must stay in sync

## Output Files

- `ai-dev/active/F-00076/reports/F-00076_S03_Backend_report.md`
- `orch/design_doc_parser.py` — extended with `parse_impacted_paths()`
- `orch/cli/item_commands.py` — `register()` populates `impacted_paths` + `config["scope_extraction"]`
- `orch/batch_planner.py` — `analyze_dependencies()` reads from item dict's `impacted_paths` (not regex)
- All six design templates updated with the new "## Impacted Paths" section
- Tests under `tests/unit/` and `tests/integration/`

## Context

You are wiring the design-doc → DB plumbing for `WorkItem.impacted_paths`. The column exists (S01). Your job:

1. Add a `## Impacted Paths` section to the design templates.
2. Write a parser that extracts globs from that section, validating them.
3. Hook the parser into `iw register` so registration populates the column AND records provenance in `config["scope_extraction"]`.
4. Update `batch_planner.analyze_dependencies()` to consume the column instead of re-running the regex.

S04 runs in parallel — it depends on this column being readable from `WorkItem.impacted_paths`. Coordinate via the design doc; do NOT change the column shape.

Read `orch/CLAUDE.md` first.

## Requirements

### 1. Design templates — add "Impacted Paths" section

In ALL SIX template files (`ai-dev/templates/{Feature,Issue,CR}_Design_Template.md` and the master copies under `templates/design/`), insert a new H2 section AFTER `## Scope` and BEFORE `## Implementation Plan`:

```markdown
## Impacted Paths

Globs declared here populate `WorkItem.impacted_paths` and are mirrored to `workflow-manifest.json:scope.allowed_paths`. The cross-batch launch-time gate uses this list to detect overlap with in-flight items in the same project (F-00076). The merge-time scope gate uses the manifest mirror to enforce the allow-list when files are actually committed.

Parser rules:
- One glob per bullet line, OR globs inside a fenced code block.
- gitignore-style globs: `dir/**`, `*.py`, `path/to/file.py`.
- No absolute paths (must NOT start with `/`).
- No `..` segments.
- No whitespace in the glob itself.
- Test paths (`**/tests/**`, `**/__tests__/**`, `**/conftest*`, `*.test.*`, `*.spec.*`) are stored but ignored by the cross-batch gate — do NOT omit them.

Example:

- `orch/foo.py`
- `orch/bar/**`
- `dashboard/templates/components/**`
- `tests/integration/test_foo.py`

If you omit this section, `iw register` falls back to a regex sweep over the prose and stamps `WorkItem.config["scope_extraction"]["source"]="regex_fallback"`.
```

Master copies (`templates/design/*.md`) and active copies (`ai-dev/templates/*.md`) must be byte-identical for this section. Sync via direct edit; do not invoke the sync skill.

### 2. Parser

Add to `orch/design_doc_parser.py`:

```python
@dataclass(frozen=True)
class ImpactedPathsResult:
    paths: list[str]      # validated, deduped, original order preserved
    found: bool           # True if the section existed (even if empty)


def parse_impacted_paths(content: str | None) -> ImpactedPathsResult:
    """Extract glob patterns from the '## Impacted Paths' section.

    Accepts BOTH markdown bullet lists (`- glob`, `* glob`) AND fenced code
    blocks. Validates each glob (raises ValueError on absolute paths, '..',
    whitespace inside the glob, or empty strings). Returns ImpactedPathsResult
    with `found=False` and `paths=[]` when the section is absent.
    """
```

Validation rules (each violation raises `ValueError` with a precise message):
- Empty/whitespace-only strings.
- Absolute paths (starts with `/`).
- Contains `..` as a path segment (use `Path(glob).parts` to check).
- Contains internal whitespace (the glob itself, not surrounding markdown whitespace).

Place the new function alongside `parse_dependencies()` in `orch/design_doc_parser.py`. Reuse `_iter_section_ranges()` and `_SECTION_HEADING_RE` to find the section.

### 3. Hook into `iw register`

In `orch/cli/item_commands.py:register()` (around line 350 where `parse_dependencies` is called), add AFTER the existing `parse_dependencies` block:

```python
# F-00076: populate impacted_paths from declared section, fallback to regex.
from datetime import UTC, datetime
from orch.batch_planner import extract_affected_files
from orch.design_doc_parser import parse_impacted_paths

scope_result = parse_impacted_paths(design_doc_content)
if scope_result.found:
    impacted_paths = scope_result.paths
    scope_extraction = {"source": "declared"}
else:
    impacted_paths = extract_affected_files(design_doc_content)
    scope_extraction = {
        "source": "regex_fallback" if impacted_paths else "none",
    }
    if impacted_paths:
        scope_extraction["warned_at"] = datetime.now(UTC).isoformat()
        click.echo(
            f"Warning: {item_id}: scope auto-extracted, please verify — "
            "no '## Impacted Paths' section in design doc",
            err=True,
        )
```

Then, when constructing the `WorkItem(...)` row (around line 359-372), add:

```python
impacted_paths=impacted_paths,
config={"scope_extraction": scope_extraction},
```

Replace the existing `config={}` literal. If `iw register` is called against an item whose design doc fails parser validation (e.g., contains `../../etc/passwd`), it MUST exit non-zero with the parser's ValueError text on stderr — DO NOT swallow the error and continue.

### 4. Update `batch_planner.analyze_dependencies`

In `orch/batch_planner.py:analyze_dependencies()` (around line 172), replace:

```python
affected = extract_affected_files(d.get("design_doc_content"))
```

with:

```python
affected = list(d.get("impacted_paths") or [])
if not affected:
    # Defensive fallback for items registered before F-00076 backfill ran.
    affected = extract_affected_files(d.get("design_doc_content"))
```

Then update the docstring's `items_data` field list to include `impacted_paths` and update the caller in `orch/cli/batch_commands.py` (search for `analyze_dependencies`) to include `impacted_paths` in the dicts it builds. Filter out test-path entries before computing intra-batch overlap (consistent with current behavior — call `_is_test_path()`).

The cross-batch overlap detection at lines 206-219 should similarly read `impacted_paths` from `active_items_data` dicts.

### 5. Tests

- `tests/unit/test_design_doc_parser.py` — add cases for `parse_impacted_paths`:
  - Bullet-list happy path.
  - Fenced code block happy path.
  - Section absent → `found=False, paths=[]`.
  - Section present but empty → `found=True, paths=[]`.
  - Validation errors: absolute path, `..`, whitespace, empty string. Each raises `ValueError`.
  - Globs with special chars (`*`, `**`, `[abc]`, `?`).
  - Dedup: `["orch/foo.py", "orch/foo.py"]` collapses but order preserved.

- `tests/integration/cli/test_register_impacted_paths.py` — register an item with:
  - A design doc containing the declared section → `WorkItem.impacted_paths` matches; `config["scope_extraction"]["source"] == "declared"`; no `warned_at`.
  - A design doc without the section but with prose mentions → fallback populates; `source == "regex_fallback"`; `warned_at` ISO-8601; stderr contains `scope auto-extracted, please verify`.
  - A design doc with NO file paths anywhere → `impacted_paths == []`; `source == "none"`; no warning.
  - A design doc containing `../etc/passwd` → `iw register` exits non-zero, no `WorkItem` row created.

- `tests/unit/test_batch_planner.py` (or extend existing) — verify `analyze_dependencies` reads from `impacted_paths` keys, falls back to regex when missing.

## Project Conventions

`orch/CLAUDE.md` — SQLAlchemy 2.0, psycopg v3, Click 8.1+, dataclasses with `frozen=True` for value objects.

## TDD Requirement

Tests before implementation, in this order: parser unit tests → parser → register integration tests → register hook → batch_planner unit tests → batch_planner refactor.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck` — zero errors on touched files
3. `make lint`

## Test Verification

1. `make test-unit`
2. `make test-integration`
3. Do NOT report `tests_passed: true` unless all pass.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "backend-impl",
  "work_item": "F-00076",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/design_doc_parser.py",
    "orch/cli/item_commands.py",
    "orch/cli/batch_commands.py",
    "orch/batch_planner.py",
    "ai-dev/templates/Feature_Design_Template.md",
    "ai-dev/templates/Issue_Design_Template.md",
    "ai-dev/templates/CR_Design_Template.md",
    "templates/design/Feature_Design_Template.md",
    "templates/design/Issue_Design_Template.md",
    "templates/design/CR_Design_Template.md",
    "tests/unit/test_design_doc_parser.py",
    "tests/integration/cli/test_register_impacted_paths.py",
    "tests/unit/test_batch_planner.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
