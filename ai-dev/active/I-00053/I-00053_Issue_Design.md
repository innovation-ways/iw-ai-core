# I-00053: Batch Planner Ignores Explicit "Depends on:" / "Blocks:" Declarations in Design Documents

**Type**: Issue
**Severity**: Medium
**Created**: 2026-04-29
**Reported By**: User (discovered during BATCH-00064 creation, 2026-04-29)
**Status**: Draft

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

This incident does NOT add or modify any alembic migration. The fix touches only Python code, parsing logic, and tests. No `alembic upgrade/downgrade/stamp` calls.

## Description

The batch planner does not parse the `## Dependencies` section of design documents. When a feature/incident/CR design states `**Depends on**: F-00069`, that declaration is silently ignored — `iw register` always persists `WorkItem.depends_on=[]`, and the planner has no other code path that reads the section. As a result, batches built from items with declared dependencies get the wrong wave assignment unless a brittle file-overlap heuristic happens to catch it (and the file-overlap path itself produces false positives from prose mentions in "Out of Scope" / "Notes" sections).

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. The relevant subsystems:

- `orch/batch_planner.py` — analyzes dependencies, assigns execution groups, produces the wave plan and execution-plan markdown/drawio.
- `orch/cli/item_commands.py` — `iw register` writes new items to the DB; `WorkItem.depends_on` is currently always set to `[]`.
- `ai-dev/templates/Feature_Design_Template.md`, `Issue_Design_Template.md`, `CR_Design_Template.md` — all three already define a `## Dependencies` section with `**Depends on**:` and `**Blocks**:` fields, signalling the intended UX.

## Steps to Reproduce

1. Create design doc A (`F-XXXX_Feature_Design.md`) containing:
   ```
   ## Dependencies

   - **Depends on**: None
   - **Blocks**: F-YYYY
   ```
2. Create design doc B (`F-YYYY_Feature_Design.md`) containing:
   ```
   ## Dependencies

   - **Depends on**: F-XXXX
   - **Blocks**: None
   ```
3. Make sure neither doc references a shared source-file path (so the file-overlap heuristic doesn't fire).
4. `iw register F-XXXX ... --design-doc <doc-A>`
5. `iw register F-YYYY ... --design-doc <doc-B>`
6. Approve both, run `iw batch-create F-XXXX F-YYYY`.
7. Run `iw batch-status BATCH-NNNNN`.

**Expected**: F-XXXX in execution group 0, F-YYYY in execution group 1.

**Actual**: Both items in execution group 0. The declared dependency is silently dropped.

### Concrete reproduction (BATCH-00064, 2026-04-29)

The user's actual case: F-00073 design doc contained `**Depends on**: F-00069 (provides make test-parallel, the coverage threshold floor, ...)`. The F-00073 manifest had `"depends_on": ["F-00069"]` at the top level. Both were ignored. After registration, `WorkItem(F-00073).depends_on == []`. The planner then inferred a *wrong-direction* dependency from a spurious file-overlap (F-00069's "Out of Scope" section literally named `tests/unit/test_logging.py`, which F-00073 owns), placing F-00069 alone in group 1 — the inverse of the declared intent. Recovery required manual DB edits and a design-doc rewrite.

## Root Cause Analysis

Two intertwined defects in `orch/batch_planner.py` and `orch/cli/item_commands.py`:

### Defect 1 — Dependency declaration never persisted (`orch/cli/item_commands.py:361`)

```python
work_item = WorkItem(
    project_id=project_id,
    id=item_id,
    type=_ITEM_TYPE_MAP[item_type],
    title=title,
    design_doc_path=design_doc,
    design_doc_content=design_doc_content,
    ...
    depends_on=[],     # ← always empty, even though design_doc_content is right there
    blocks=[],         # ← same
)
```

`iw register` reads the design doc into `design_doc_content` but never extracts the dependency section. `depends_on` and `blocks` are hardcoded to empty lists. There is no separate CLI to populate them after the fact (`grep -rn "depends_on" orch/cli/` returns only this initialization plus two read-sites in `batch_commands.py`). So the user's declared dependencies have no path into the database.

### Defect 2 — Planner relies on file overlap as the only fallback (`orch/batch_planner.py:146-220`)

`analyze_dependencies()` builds the dependency graph in five phases:

- **Phase 1** (lines 165-178): reads `WorkItem.depends_on` from the DB. Always empty due to Defect 1.
- **Phase 2** (lines 181-187): adds sequential edges between items with Database-impl steps (an unrelated heuristic).
- **Phase 3** (lines 190-200): walks `item_ids` pairwise, computes `extract_affected_files()` per item, and adds `analysis[id_b].depends_on.append(id_a)` whenever `files_a & files_b` is non-empty AND `a` precedes `b` in iteration order.
- **Phase 4** (line 216): breaks cycles.
- **Phase 5** (line 219): assigns groups via topological levelling.

With Defect 1 leaving Phase 1 empty, Phase 3 is the only signal — and it has its own problems:

1. **Direction depends on argument order to `iw batch-create`.** Phase 3 only adds `b.depends_on.append(a)` for `a < b` in iteration order. So if the user passes items in arbitrary order, the inferred direction can be wrong even when overlap detection is correct.

2. **`extract_affected_files()` is over-eager.** The regex `_FILE_PATH_RE` at `orch/batch_planner.py:98-103` matches any source-file path mentioned anywhere in the design doc — including paths in `## Out of Scope`, `## Notes`, prose comments, or "see also" lists. The regex doesn't distinguish "this item modifies X" from "X is owned by another item". One sentence in the wrong section can flip a wave assignment.

### Why the design-doc parser is the right fix

The templates explicitly model declared dependencies via the `## Dependencies` section. Users follow the template (the BATCH-00064 case proves it). The parser-and-persist path is the only one that:

- Honors the declared intent.
- Survives later edits (re-run `iw deps refresh` to re-parse, with explicit user action).
- Surfaces in `iw item-status` and `WorkItem.depends_on` so debugging tools work.
- Preserves the existing file-overlap heuristic as a *secondary*, *advisory* signal (still useful for catching unintended overlaps that the user forgot to declare).

## Affected Components

| Component | File:Line | Impact |
|-----------|-----------|--------|
| `iw register` | `orch/cli/item_commands.py:361` | Silently drops declared dependencies — never writes them to the DB |
| Batch planner Phase 1 | `orch/batch_planner.py:170` | Reads `depends_on` from DB; gets `[]` for every newly-registered item |
| Batch planner Phase 3 | `orch/batch_planner.py:190-200` | Falls back to file overlap as the only signal; introduces order-sensitivity and false-positive bugs |
| `extract_affected_files()` | `orch/batch_planner.py:114-128` | Picks up paths from "Out of Scope" / "Notes" prose, treating them as modifications |
| Templates | `ai-dev/templates/{Feature,Issue,CR}_Design_Template.md` | Define `## Dependencies` section that users fill out, but which is never parsed — silent UX failure |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Create `orch/design_doc_parser.py` (parser + section-aware file extractor); wire into `iw register` to populate `depends_on` / `blocks`; refactor `extract_affected_files()` in `batch_planner.py` to skip "Out of Scope" / "Notes" sections; **do NOT add a CLI** for after-the-fact mutation (out of scope) | — |
| S02 | code-review-impl | Review S01 (parser + register integration + extract_affected_files refactor) | — |
| S03 | tests-impl | Parser unit tests; planner regression tests for the BATCH-00064 scenario and the `Blocks:` inversion; smoke tests for section-aware extraction | — |
| S04 | code-review-impl | Review S03 | — |
| S05 | code-review-final-impl | Cross-cutting global review | — |
| S06 | qv-gate | `make lint` | — |
| S07 | qv-gate | `make format` | — |
| S08 | qv-gate | `make typecheck` | — |
| S09 | qv-gate | `make test-unit` | — |
| S10 | qv-gate | `make allure-integration` | — |

No frontend / browser verification (backend-only).

### Database Changes

- **New tables**: None
- **Modified tables**: None — `WorkItem.depends_on` and `blocks` columns already exist (`orch/db/models.py:426`).
- **Migration notes**: None.

### Code Changes

- **Files to modify**:
  - `orch/cli/item_commands.py` — call new parser at register time; persist `depends_on` and `blocks`.
  - `orch/batch_planner.py` — refactor `extract_affected_files()` to skip designated sections.
- **Files to create**:
  - `orch/design_doc_parser.py` — pure functions: `parse_dependencies(content) -> Deps`, `strip_excluded_sections(content) -> str` (used by both the parser and the file extractor).
- **Nature of change**:
  - Add a parser; wire it; reduce false positives.
  - Backwards-compatible: existing items keep their (empty) `depends_on`. Users who want to retrofit can edit the DB manually or wait for a future `iw deps refresh` CR.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `ai-dev/active/I-00053/I-00053_Issue_Design.md` | Design | This document |
| `ai-dev/active/I-00053/workflow-manifest.json` | Manifest | Step definitions |
| `ai-dev/active/I-00053/prompts/I-00053_S01_Backend_prompt.md` | Prompt | S01 fix |
| `ai-dev/active/I-00053/prompts/I-00053_S02_CodeReview_prompt.md` | Prompt | Review of S01 |
| `ai-dev/active/I-00053/prompts/I-00053_S03_Tests_prompt.md` | Prompt | Tests |
| `ai-dev/active/I-00053/prompts/I-00053_S04_CodeReview_Tests_prompt.md` | Prompt | Review of S03 |
| `ai-dev/active/I-00053/prompts/I-00053_S05_CodeReview_Final_prompt.md` | Prompt | Final review |
| `orch/design_doc_parser.py` | New | `parse_dependencies()` + `strip_excluded_sections()` |
| `orch/cli/item_commands.py` | Modified | Wire parser into `iw register` |
| `orch/batch_planner.py` | Modified | Refactor `extract_affected_files()` to use `strip_excluded_sections()` |
| `tests/unit/test_design_doc_parser.py` | New | Parser unit tests |
| `tests/unit/test_batch_planner_dependencies.py` | New | Planner regression tests for declared deps + section-aware extraction |
| `tests/integration/test_register_persists_dependencies.py` | New | End-to-end test: register populates DB depends_on |

## Test to Reproduce

The bug surfaces in two distinct places — write one test for each:

```python
# tests/unit/test_batch_planner_dependencies.py

def test_declared_depends_on_drives_wave_assignment():
    """Reproduces I-00053: declared `Depends on:` must put the dependent item in a later group."""
    items = [
        {
            "id": "F-A",
            "title": "A",
            "type": "feature",
            "depends_on": [],          # comes from DB after register; bug == always empty
            "design_doc_content": (
                "## Dependencies\n\n"
                "- **Depends on**: None\n"
                "- **Blocks**: F-B\n"
            ),
            "steps": [],
        },
        {
            "id": "F-B",
            "title": "B",
            "type": "feature",
            "depends_on": [],          # comes from DB after register; bug == always empty
            "design_doc_content": (
                "## Dependencies\n\n"
                "- **Depends on**: F-A\n"
                "- **Blocks**: None\n"
            ),
            "steps": [],
        },
    ]
    analysis = analyze_dependencies(items)
    assert analysis["F-A"].group == 0, "F-A has no deps; should be group 0"
    assert analysis["F-B"].group == 1, "F-B declares Depends on F-A; should be group 1"
    # Pre-fix: BOTH end up in group 0 because Phase 1 reads empty depends_on
    # and there's no file overlap to fall back on.
```

```python
# tests/unit/test_batch_planner_dependencies.py

def test_paths_in_out_of_scope_section_do_not_create_overlap():
    """Reproduces the BATCH-00064 false-positive: `tests/unit/test_logging.py` mentioned in
    F-A's Out of Scope (because it's owned by F-B) must NOT count as a modification.
    """
    a = (
        "## File Manifest\n\n"
        "| File | Type |\n|---|---|\n"
        "| `dashboard/foo.py` | Modified |\n\n"
        "## Out of Scope\n\n"
        "- `tests/unit/test_logging.py` — owned by F-B\n"
    )
    b = (
        "## File Manifest\n\n"
        "| File | Type |\n|---|---|\n"
        "| `tests/unit/test_logging.py` | New |\n"
    )
    files_a = set(extract_affected_files(a))
    files_b = set(extract_affected_files(b))
    assert "tests/unit/test_logging.py" not in files_a, (
        "Out-of-Scope mentions must NOT be treated as modifications"
    )
    assert "tests/unit/test_logging.py" in files_b
    assert files_a & files_b == set(), "No spurious overlap"
```

These tests fail against the pre-fix code and pass against the fixed code.

## Acceptance Criteria

### AC1: Bug is fixed — declared dependencies drive wave assignment

```
Given a design doc that contains a `## Dependencies` section with `**Depends on**: F-XXXX`
When the design doc is registered via `iw register`
Then `WorkItem.depends_on` in the DB contains `["F-XXXX"]`
And running `iw batch-create` against this item plus its declared dependency produces a wave plan where F-XXXX is in an earlier group than the dependent item
```

### AC2: Bug is fixed — declared `Blocks:` works equivalently

```
Given F-A's design doc declares `**Blocks**: F-B`
When both items are registered
Then F-B's `WorkItem.depends_on` contains `F-A`
And the wave assignment is identical to the case where F-B declared `**Depends on**: F-A` instead
```

### AC3: Regression tests exist

```
Given the fix is applied
When `make test-unit` runs
Then tests/unit/test_design_doc_parser.py passes
And tests/unit/test_batch_planner_dependencies.py passes
And the BATCH-00064 reproduction test passes
And the file-overlap section-skip test passes
```

### AC4: Spurious file-overlap eliminated

```
Given a design doc mentions a path in its `## Out of Scope` or `## Notes` section
When `extract_affected_files()` is called on the doc
Then that path is NOT included in the returned list
And the planner does NOT create a dependency edge based on it
```

### AC5: Backwards compatibility

```
Given an existing WorkItem with `depends_on = []` and no `## Dependencies` section in its design doc
When the planner runs
Then behavior is unchanged from pre-fix (file-overlap heuristic remains the fallback)
And no existing tests fail
```

### AC6: Explicit out-of-scope items are NOT shipped

```
Given the fix as scoped
When the implementation lands
Then no new CLI command (e.g. `iw deps refresh`) is added — out of scope per design
And no Markdown-section parsing beyond `## Dependencies`, `## Out of Scope`, `## Notes`
And no changes to the executor, daemon, dashboard, or workflow runtime
```

## Boundary Behavior

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| `Depends on: None` | Literal "None" | Empty list returned |
| `Depends on: —` | Em-dash | Empty list |
| `Depends on:` (empty) | Trailing colon, nothing else | Empty list |
| `Depends on: F-00069, I-00042, CR-99025` | Comma-separated | `["F-00069", "I-00042", "CR-99025"]` |
| `Depends on: F-00069 (provides ...)` | Parenthetical commentary | `["F-00069"]` (commentary stripped) |
| `Depends on: F-00069 - reason` | Dash-separated reason | `["F-00069"]` |
| Section absent | No `## Dependencies` heading | Empty list (no error) |
| Section present, fields absent | Heading exists, no `**Depends on**:` line | Empty list |
| Mixed case heading | `## dependencies` | Recognised (case-insensitive heading match) |
| Item declares dep on unregistered ID | `Depends on: F-99999` (doesn't exist) | Persist as-is; planner's existing `if dep in selected_ids` filter handles non-batch members. Log a WARNING at register time |
| Self-dependency | `F-A` declares `Depends on: F-A` | Skip with WARNING log; do not persist |
| `Blocks` references unregistered ID | `Blocks: F-99999` (doesn't exist yet) | Defer; store on F-A's `blocks` field but don't try to mutate the missing item. Log a WARNING |
| Re-register same ID | `iw register` called twice on same ID | Use existing collision behavior (raise or update — match current code path); if updating, refresh `depends_on` from new design doc |
| Path inside Out of Scope | `- tests/foo.py` under `## Out of Scope` | NOT included in `extract_affected_files()` |
| Path inside Notes | `- See dashboard/bar.py` under `## Notes` | NOT included |
| Path inside File Manifest table | `| dashboard/baz.py | Modified |` | INCLUDED (canonical source) |
| Path inside Description prose | `dashboard/qux.py is involved` in `## Description` | INCLUDED (preserves current behavior unless we tighten further; keep this for now) |

## Invariants

1. `WorkItem.depends_on` and `blocks` MUST be populated at register time when the design doc contains a non-empty `## Dependencies` section.
2. `parse_dependencies()` MUST never raise on malformed input; return empty lists with a logged warning instead.
3. `extract_affected_files()` MUST NOT include paths mentioned exclusively inside `## Out of Scope` or `## Notes` sections.
4. The change MUST be backwards-compatible: existing items in the DB with empty `depends_on` continue to work; pre-existing tests pass.
5. The fix MUST NOT add a public CLI for mutating `depends_on` after registration (out of scope per the incident design).
6. The fix MUST NOT touch the executor, daemon, dashboard, or workflow runtime.
7. `Blocks:` declarations MUST produce the same wave assignment as the equivalent `Depends on:` declared in the inverse direction.

## Regression Prevention

The Tests step (S03) writes:

1. **Parser unit tests** covering the boundary table above.
2. **Planner regression test for the BATCH-00064 scenario** — two items, declared dependency, no file overlap, asserts correct wave assignment regardless of argument order to `analyze_dependencies()`.
3. **Planner regression test for `Blocks:` inversion** — declared `Blocks` produces the same wave plan as the equivalent declared `Depends on`.
4. **`extract_affected_files()` section-skip test** — paths inside `## Out of Scope` / `## Notes` do not count as modifications.
5. **Register integration test** — `iw register` on a design doc with a populated `## Dependencies` section persists the IDs into `WorkItem.depends_on` and `blocks`. Tests use the existing testcontainer fixture.

These tests are the regression net — together they prove I-00053 cannot recur in either of its two forms (silent declaration drop, false-positive file overlap).

## Dependencies

- **Depends on**: None
- **Blocks**: None

## TDD Approach

- **Reproducing tests**: the two snippets in "Test to Reproduce" above. Each MUST be written RED first (verified failing against pre-fix code) before the implementation lands.
- **Unit tests** (`tests/unit/test_design_doc_parser.py`): cover every row of the Boundary Behavior table.
- **Unit tests** (`tests/unit/test_batch_planner_dependencies.py`): planner-level assertions on declared deps, Blocks inversion, section-aware extraction.
- **Integration tests** (`tests/integration/test_register_persists_dependencies.py`): exercise `iw register` end-to-end against a testcontainer.

## Notes

- The existing file-overlap heuristic (`extract_affected_files()` + Phase 3 of the planner) stays as a *secondary* fallback. It catches cases where two items genuinely modify the same file and the user forgot to declare it. Combined with the new declared-dependency parser, the planner now has both signals: explicit-and-authoritative (parser) and implicit-and-advisory (overlap).
- The parser is a pure function with no I/O — easy to test, easy to call from anywhere. Putting it in a new `orch/design_doc_parser.py` module keeps `batch_planner.py` from growing further.
- A future CR could add `iw deps show <id>` and `iw deps refresh <id>` for inspecting and re-syncing after a design-doc edit. Out of scope for I-00053.
- This incident is the cause behind one of the F-00069..F-00073 batch issues from 2026-04-29; once I-00053 is fixed, future batches with declared dependencies "just work" without DB hand-edits.
