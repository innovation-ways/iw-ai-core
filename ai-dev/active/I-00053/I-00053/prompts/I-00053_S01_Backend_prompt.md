# I-00053_S01_Backend_prompt

**Work Item**: I-00053 -- Batch Planner Ignores Explicit "Depends on:" / "Blocks:" Declarations
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

(Standard policies. Testcontainers in tests are exempt. No alembic invocations needed — `WorkItem.depends_on` and `blocks` columns already exist.)

## Input Files

- `uv run iw item-status I-00053 --json` — runtime state
- `ai-dev/active/I-00053/I-00053_Issue_Design.md` — design doc (read fully — Boundary Behavior table is the spec for the parser)
- `orch/cli/item_commands.py` — register code path (around line 361 — `depends_on=[]`)
- `orch/batch_planner.py` — planner; `extract_affected_files()` lines 114-128, `analyze_dependencies()` lines 146-220
- `orch/db/models.py` line 426 — `WorkItem.depends_on` column
- `ai-dev/templates/Feature_Design_Template.md` — section template
- `ai-dev/templates/Issue_Design_Template.md` — section template
- `ai-dev/templates/CR_Design_Template.md` — section template
- `CLAUDE.md`

## Output Files

- New: `orch/design_doc_parser.py`
- Modified: `orch/cli/item_commands.py`
- Modified: `orch/batch_planner.py`
- `ai-dev/active/I-00053/reports/I-00053_S01_Backend_report.md`

## Context

You are fixing I-00053. The bug has two intertwined defects:

1. **`iw register` never persists declared dependencies** — `depends_on=[]` is hardcoded.
2. **`extract_affected_files()` over-extracts** — picks up paths from "Out of Scope" / "Notes" prose, treating mentions as modifications.

The fix introduces a single new module (`orch/design_doc_parser.py`) and wires it into both code paths. **Tests are NOT part of this step — S03 owns them.** Reviews and QV gates come later.

## Requirements

### 1. New module: `orch/design_doc_parser.py`

Pure functions, no I/O, no logging side-effects beyond `logging.getLogger(__name__).warning(...)`.

Public API:

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Dependencies:
    depends_on: list[str]
    blocks: list[str]


def parse_dependencies(content: str | None) -> Dependencies:
    """Parse `**Depends on**:` and `**Blocks**:` lines from a design doc.

    Tolerates: missing section, "None", "—", empty, comma-separated lists,
    parenthetical commentary after IDs, dash-separated reasons. Never raises.
    Logs a WARNING for malformed lines but returns sensible defaults.
    """
    ...


def strip_excluded_sections(content: str | None) -> str:
    """Return the doc content with `## Out of Scope` and `## Notes` sections
    removed. Used by extract_affected_files() to avoid spurious overlap.
    A section runs from its `## Heading` line to the next top-level `## ` heading
    (exclusive) or end of file.
    """
    ...
```

Implementation notes:

- ID regex: `r"\b(?:F|I|CR)-\d{3,5}\b"` — covers F-00069, I-00042, CR-99025.
- Self-dependency: if the design doc IS the one being parsed, the parser doesn't know its own ID. Skip self-dep filtering at parser level — do it at the **register** integration point (which has the ID).
- Section heading match: case-insensitive, leading whitespace tolerated. Recognise `## Out of Scope`, `## Notes`. Do NOT strip "## Out of Scope" inside a code fence (skip code blocks).
- Use stdlib `re` only — no external dependencies.

### 2. Wire parser into `iw register`

In `orch/cli/item_commands.py` around line 361, replace `depends_on=[]` and `blocks=[]` with:

```python
from orch.design_doc_parser import parse_dependencies

deps = parse_dependencies(design_doc_content)

# Self-dependency guard
self_dep = item_id in deps.depends_on
self_block = item_id in deps.blocks
filtered_depends_on = [d for d in deps.depends_on if d != item_id]
filtered_blocks = [b for b in deps.blocks if b != item_id]
if self_dep or self_block:
    logger.warning(
        "Self-dependency detected in %s design doc — ignoring", item_id
    )

work_item = WorkItem(
    ...
    depends_on=filtered_depends_on,
    blocks=filtered_blocks,
)
```

After `session.add(work_item)` and `session.flush()`, also process the `Blocks` inversion: for each ID in `filtered_blocks`, if that other item exists in the DB, append the current item's ID to its `depends_on` (de-duplicated). If the blocked item does not exist yet, log a WARNING ("declared blocks F-XXXX which is not registered"). Do NOT raise.

```python
for blocked_id in filtered_blocks:
    blocked = session.get(WorkItem, (project_id, blocked_id))
    if blocked is None:
        logger.warning(
            "%s blocks %s but %s is not registered — skipping inversion",
            item_id, blocked_id, blocked_id,
        )
        continue
    if item_id not in (blocked.depends_on or []):
        blocked.depends_on = [*(blocked.depends_on or []), item_id]
```

If the existing register flow already has a logger object, use it. Otherwise add `logger = logging.getLogger(__name__)` at module top.

### 3. Refactor `extract_affected_files()` to skip excluded sections

In `orch/batch_planner.py`, change `extract_affected_files()` to call `strip_excluded_sections()` from the new parser module before applying the regex:

```python
from orch.design_doc_parser import strip_excluded_sections

def extract_affected_files(design_doc: str | None) -> list[str]:
    """Extract affected file paths from a design document.

    Skips `## Out of Scope` and `## Notes` sections to avoid false-positive
    overlaps from prose mentions (I-00053).
    """
    if not design_doc:
        return []
    cleaned = strip_excluded_sections(design_doc)
    files: set[str] = set()
    for match in _FILE_PATH_RE.finditer(cleaned):
        path = match.group(0)
        if not _is_test_path(path):
            files.add(path)
    return sorted(files)
```

(The existing test-path exclusion stays. The new section-strip is additive.)

### 4. Backwards compatibility

- Existing items in the DB with `depends_on=[]` continue to work. The planner's Phase 1 reads them as before; if empty, Phase 3's overlap heuristic still runs.
- Existing tests under `tests/integration/` and `tests/unit/` MUST pass without modification. If any test fails because it depended on the old (buggy) behavior, raise it as a finding in your report — do NOT silently weaken the new behavior.

### 5. Out of scope (do NOT do these here)

- A new `iw deps refresh` / `iw deps show` CLI — explicitly out of scope per design.
- Markdown-section parsing beyond `## Dependencies`, `## Out of Scope`, `## Notes`.
- Changes to executor, daemon, dashboard, workflow runtime, or any other subsystem.
- A new alembic migration (the columns already exist).
- Tests — S03 owns them.

## Project Conventions

- Read `CLAUDE.md` and `tests/CLAUDE.md`.
- Type hints required; passes `make typecheck`.
- Use `logging.getLogger(__name__)` not `print`.
- Match existing code style in `orch/`.
- New module goes in `orch/` (not `orch/cli/`, not `dashboard/`).

## TDD Requirement

S03 writes the tests, but for S01 you MUST verify your implementation by hand:

1. Write a tiny throwaway script that constructs sample design-doc strings (one with `Depends on: F-00069`, one with `Blocks: F-00073`, one with paths inside `## Out of Scope`) and run your parser. Confirm outputs match the design's Boundary Behavior table.
2. Register a sample item via `iw register` against a fresh testcontainer (or a temp branch DB) and verify `WorkItem.depends_on` is populated. Do NOT register against the live DB.
3. Run `make test-unit` and `make test-integration` against the modified code. ZERO regressions.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format` — auto-fix and re-stage
2. `make typecheck` — zero new errors on touched files
3. `make lint` — zero errors
4. `make test-unit` — all existing tests pass
5. `make test-integration` — all existing tests pass

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "I-00053",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/design_doc_parser.py",
    "orch/cli/item_commands.py",
    "orch/batch_planner.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "Tests intentionally not written — owned by S03."
}
```
