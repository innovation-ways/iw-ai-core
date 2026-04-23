# F-00059: Functional design documents for work items

**Type**: Feature
**Priority**: High
**Created**: 2026-04-22
**Status**: Draft

---

## Description

Every work item (Feature, Incident, Change Request) currently has one design document that is written for an AI agent to implement against — step-by-step prompts, file paths, schema changes, TDD instructions. It is long, implementation-heavy, and poor retrieval context for human-facing questions. This feature adds a second, complementary **Functional Design Document** per work item: a short, plain-English markdown that captures the *why* behind the work, what the user actually observes, and how the system behaves — with NO implementation detail. It is auto-drafted by the `iw-new-*` skills, human-validated and editable during the design phase, gated by `iw-review-design`, surfaced as a new dashboard tab on the item detail view, and snapshotted into three new `work_items` columns with an FTS index that parallels the existing `design_doc_search`. This is a prerequisite for F-00060 (Hybrid Code Q&A retrieval), which will consume these functional docs as high-signal retrieval context.

## Project Context

Read the project's `CLAUDE.md`, `orch/CLAUDE.md`, `dashboard/CLAUDE.md`, and `tests/CLAUDE.md` for architecture, testcontainer rules, htmx patterns, and the skills-sync / templates-sync conventions.

## Scope

### In Scope

- Three new columns on `work_items`: `functional_doc_path`, `functional_doc_content`, `functional_doc_search` (TSVECTOR).
- Trigger-maintained FTS column with its own GIN index, mirroring the existing `design_doc_search` pattern exactly.
- Alembic migration (up + down) and update to `tests/integration/conftest.py` so testcontainers install the new trigger alongside the existing ones.
- `iw register` auto-detects a sibling `<ID>_Functional.md` file next to the technical design doc and loads its content into `functional_doc_content`. Explicit `--functional-doc PATH` flag as an override.
- Backfill script `scripts/backfill_functional_doc.py` gains a `--load-db` flag to UPDATE `functional_doc_path` and `functional_doc_content` for an existing registered work item.
- New template `ai-dev/templates/Functional_Design_Template.md` defining the fixed section structure and word-count expectation.
- Updates to four skill masters under `skills/`: `iw-new-feature`, `iw-new-incident`, `iw-new-cr` produce a `<ID>_Functional.md` file during the design phase; `iw-review-design` validates it.
- New dashboard route `GET /project/{project_id}/item/{item_id}/tab/functional-doc` + fragment `item_functional_doc.html` + new tab button in `pages/project/item_detail.html`.
- Integration + unit tests covering: FTS trigger on insert/update, register-time loader, review-skill validation, backfill `--load-db`, dashboard route + empty-state fragment.

### Out of Scope

- Semantic embedding of functional docs into LanceDB and wiring them into Code Q&A — that is F-00060.
- Versioning of functional docs in `project_doc_versions` (explicit user decision: functional docs are immutable after item completion; git is the only history).
- An in-dashboard markdown editor for functional docs — the dashboard view is read-only; edits happen in the `.md` file during the design phase only.
- Backfilling the database column for every existing item in one migration — a separate operator task runs `backfill_functional_doc.py --load-db` per item.
- Changing the existing `design_doc_search` column, trigger, or FTS semantics.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | database-impl | Add `functional_doc_path/content/search` columns to `WorkItem`; add `FUNCTIONAL_DOC_FTS_FUNCTION_SQL` / `FUNCTIONAL_DOC_FTS_TRIGGER_SQL` constants; generate Alembic migration with trigger function + trigger + GIN index and matching downgrade; extend `tests/integration/conftest.py` to install the new trigger | — |
| S02 | backend-impl | Update `orch/cli/item_commands.py` register command: auto-detect `<ID>_Functional.md` adjacent to design-doc path, add `--functional-doc PATH` override, populate `functional_doc_path` + `functional_doc_content` on INSERT. Add `--load-db` flag to `scripts/backfill_functional_doc.py` that UPDATEs the two columns after opencode writes the file | — (after S01) |
| S03 | template-impl | Create `ai-dev/templates/Functional_Design_Template.md` (and mirror to `templates/design/`). Update `skills/iw-new-feature/SKILL.md`, `iw-new-incident/SKILL.md`, `iw-new-cr/SKILL.md` to generate `<ID>_Functional.md` as part of the design package and to pass the path to `iw register`. Update `skills/iw-review-design/SKILL.md` with the validation checklist (required H2 sections, word-count, forbidden-term regex) | S02, S04 |
| S04 | frontend-impl | Add route `GET /project/{project_id}/item/{item_id}/tab/functional-doc` in `dashboard/routers/items.py`; create fragment `dashboard/templates/fragments/item_functional_doc.html`; add "Functional Design" tab button in `dashboard/templates/pages/project/item_detail.html` (placed immediately after Design Document tab) | S02, S03 |
| S05 | tests-impl | Integration tests (testcontainer): FTS trigger populates `functional_doc_search` on INSERT and UPDATE; trigger is scoped correctly; GIN index query returns matching items. Register-command loader reads adjacent file into DB. Backfill `--load-db` round-trip writes file + DB. Dashboard route renders fragment with content and the empty-state for null content. Unit tests: `iw-review-design` validator positive/negative cases (valid doc passes; missing sections, >500 words, forbidden terms each fail appropriately) | — (after S01–S04) |
| S06 | code-review-final-impl | Global cross-layer review: DB → Backend → Template → Frontend coherence; AC coverage; no regressions to sibling tabs; FTS trigger symmetry with `design_doc_search`; migration reversibility | — |
| S07 | qv-gate | `make lint` | — |
| S08 | qv-gate | `uv run ruff format --check .` | — |
| S09 | qv-gate | `make typecheck` | — |
| S10 | qv-gate | `make test-unit` | — |
| S11 | qv-gate | `make test-integration` | — |
| S12 | qv-browser | End-to-end: open an item with populated `functional_doc_content`, switch to the "Functional Design" tab, verify rendered markdown; open an item without content, verify friendly empty state; verify Design Document tab still works unchanged; no console errors across item detail tabs | — |

### Database Changes

- **New tables**: None.
- **Modified tables**: `work_items` — three new nullable columns.
- **Migration notes**: Single Alembic revision. `upgrade()` adds three columns, creates trigger function `work_items_functional_doc_search_update()`, creates trigger `work_items_functional_doc_search_trg` (BEFORE INSERT OR UPDATE OF `title`, `functional_doc_content`), creates GIN index `idx_work_items_functional_doc_search`. `downgrade()` drops index, trigger, function, then the three columns — verified reversible on a populated DB.

The new trigger is functionally equivalent to the existing `design_doc_search` trigger but uses the `COALESCE` form (matching `PROJECT_DOCS_FTS_FUNCTION_SQL` style) for clarity: `to_tsvector('english', COALESCE(NEW.title, '') || ' ' || COALESCE(NEW.functional_doc_content, ''))`. The existing `FTS_FUNCTION_SQL` uses an `IF NEW.design_doc_content IS NOT NULL THEN ... ELSE ... END IF` shape; it is **not** modified (Invariant 7). The two forms produce identical TSVECTORs for all inputs.

### API Changes

- **New endpoints**:
  - `GET /project/{project_id}/item/{item_id}/tab/functional-doc` → htmx fragment; returns rendered markdown or empty-state.
- **Modified endpoints**: None.

### Frontend Changes

- **New templates**: `dashboard/templates/fragments/item_functional_doc.html` (render markdown content or empty state).
- **Modified templates**: `dashboard/templates/pages/project/item_detail.html` (one additional tab button, keyed to the new endpoint).
- No changes to sibling tabs.

## File Manifest

All design-package files live under `ai-dev/active/F-00059/`:

| File | Type | Purpose |
|------|------|---------|
| `ai-dev/active/F-00059/F-00059_Feature_Design.md` | Design | This document |
| `ai-dev/active/F-00059/workflow-manifest.json` | Manifest | Step definitions |
| `ai-dev/active/F-00059/prompts/F-00059_S01_Database_prompt.md` | Prompt | S01 |
| `ai-dev/active/F-00059/prompts/F-00059_S02_Backend_prompt.md` | Prompt | S02 |
| `ai-dev/active/F-00059/prompts/F-00059_S03_Template_prompt.md` | Prompt | S03 |
| `ai-dev/active/F-00059/prompts/F-00059_S04_Frontend_prompt.md` | Prompt | S04 |
| `ai-dev/active/F-00059/prompts/F-00059_S05_Tests_prompt.md` | Prompt | S05 |
| `ai-dev/active/F-00059/prompts/F-00059_S06_CodeReview_Final_prompt.md` | Prompt | S06 |
| `ai-dev/active/F-00059/prompts/F-00059_S12_BrowserVerification_prompt.md` | Prompt | S12 |

**Source files created / modified**:

- `orch/db/models.py` (modified — new columns on `WorkItem` + `FUNCTIONAL_DOC_FTS_FUNCTION_SQL` / `FUNCTIONAL_DOC_FTS_TRIGGER_SQL` constants)
- `orch/db/migrations/versions/{hash}_add_functional_doc_columns.py` (new)
- `tests/integration/conftest.py` (modified — install new FTS trigger)
- `orch/cli/item_commands.py` (modified — `register` auto-detects and loads functional doc)
- `scripts/backfill_functional_doc.py` (modified — `--load-db` flag)
- `ai-dev/templates/Functional_Design_Template.md` (new)
- `templates/design/Functional_Design_Template.md` (new — mirror of above)
- `skills/iw-new-feature/SKILL.md` (modified)
- `skills/iw-new-incident/SKILL.md` (modified)
- `skills/iw-new-cr/SKILL.md` (modified)
- `skills/iw-review-design/SKILL.md` (modified)
- `dashboard/routers/items.py` (modified — new tab route)
- `dashboard/templates/fragments/item_functional_doc.html` (new)
- `dashboard/templates/pages/project/item_detail.html` (modified — tab button)
- `tests/integration/test_work_items_functional_doc_fts.py` (new)
- `tests/integration/test_item_register_functional_doc.py` (new)
- `tests/integration/test_dashboard_item_functional_tab.py` (new)
- `tests/unit/test_backfill_functional_doc.py` (new)
- `tests/unit/test_review_design_functional_validation.py` (new)

Reports are created during execution in `ai-dev/active/F-00059/reports/`.

## Acceptance Criteria

### AC1: New-item skills produce both design docs

```
Given   a clean project worktree and the /iw-new-feature skill invoked with a feature request
When    the skill finishes Step 6 (file creation) and reaches the "register in platform" step
Then    both ai-dev/active/<ID>/<ID>_Feature_Design.md AND ai-dev/active/<ID>/<ID>_Functional.md exist
And     the functional doc contains the fixed H2 sections (## Why, ## What Changed (for the User), ## How It Behaves; ## Out of Scope optional)
And     the functional doc is at most 500 words (≤500 passes, >500 is rejected by the review skill)
And     the same behaviour holds for /iw-new-incident (producing <ID>_Functional.md) and /iw-new-cr
```

### AC2: Review skill blocks invalid functional docs

```
Given   a design package where ai-dev/active/<ID>/<ID>_Functional.md is missing, OR is empty, OR has more than 500 words (inclusive boundary: 500 passes, 501+ fails), OR lacks one of the required H2 sections
When    /iw-review-design runs
Then    the review reports a blocking error that names the specific failure (missing file, missing section, word count)
And     the review does NOT approve the package
Given   a design package where the functional doc contains a forbidden term (file extension like .py/.md/.sql, path fragment like orch/ or dashboard/, an SQL DDL keyword, or a fenced code block)
When    /iw-review-design runs
Then    the review reports a warning citing the offending term(s)
And     approval requires either an edit removing the term OR an explicit human override
```

### AC3: Dashboard item detail view surfaces the functional doc

```
Given   an approved work item with functional_doc_content populated
When    a user loads /project/<project>/item/<ID> and clicks the "Functional Design" tab
Then    the tab fragment renders the markdown via the existing markdown helper
And     the tab appears immediately after the "Design Document" tab in the tab row
And     switching back to "Design Document" still works and shows the technical design unchanged
Given   a work item with functional_doc_content = NULL
When    the user clicks the "Functional Design" tab
Then    a friendly empty-state fragment renders (e.g., "No functional design document has been loaded for this item yet.") without any server error
```

### AC4: DB column populated at register time and FTS-queryable

```
Given   a repo containing ai-dev/active/<ID>/<ID>_Functional.md next to the technical design doc
When    an operator runs `iw register <ID> "title" --type feature --design-doc <technical>.md --steps-from <manifest>`
Then    the inserted work_items row has functional_doc_path set to the relative path and functional_doc_content set to the file content
And     the functional_doc_search TSVECTOR is non-NULL and contains lexemes from the title + functional content
And     a query `SELECT id FROM work_items WHERE functional_doc_search @@ to_tsquery('english', <term>)` returns the row for any term present in the content
Given   the same repo WITHOUT <ID>_Functional.md on disk
When    `iw register` runs
Then    functional_doc_path and functional_doc_content are NULL
And     the INSERT still succeeds (no blocking failure)
And     functional_doc_search TSVECTOR contains only lexemes from the title (mirroring design_doc_search behaviour for null content)
```

### AC5: Backfill script --load-db round-trip

```
Given   a completed work item F-00055 already registered (functional_doc_content is NULL) and a running orchestration DB
When    the operator runs `uv run python scripts/backfill_functional_doc.py F-00055 --load-db`
Then    the script produces ai-dev/active/F-00055/F-00055_Functional.md via opencode (MiniMax-M2.7)
And     after the file is written, the script UPDATEs work_items SET functional_doc_path = ?, functional_doc_content = ? WHERE project_id = ? AND id = 'F-00055'
And     the FTS trigger re-generates functional_doc_search on that UPDATE
And     the next dashboard load of the item detail page shows the new Functional Design tab content
Given   `--load-db` is passed but the work item is not found in the DB
When    the script runs
Then    it exits with code 4 (work item not found) and does not modify the filesystem
```

### AC6: Migration is cleanly reversible

```
Given   a populated orchestration DB with functional_doc_* columns and trigger installed
When    an operator runs `alembic downgrade -1`
Then    the three columns, the GIN index, the trigger, and the trigger function are all dropped
And     `alembic upgrade head` immediately afterwards re-creates them successfully
And     no stale database objects (orphan indexes, orphan trigger functions) remain after either direction
```

### AC7: Skills-sync and templates-sync propagate changes

```
Given   the master edits from S03 have landed in skills/ and ai-dev/templates/ in iw-ai-core
When    an operator runs `iw skills sync` against every project in projects.toml (innoforge, iw-ai-core, cv — iw-ai-core is itself a managed project and must be synced so its own .claude/skills/ reflects the new masters)
Then    the updated SKILL.md files and the new Functional_Design_Template.md appear in each target project's .claude/skills/ and ai-dev/templates/ respectively
And     subsequent /iw-new-feature runs in those projects produce <ID>_Functional.md
```

## Boundary Behavior

Every row becomes a mandatory test case.

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| New item registered without a functional doc file | `<ID>_Functional.md` not on disk | `functional_doc_path` = NULL, `functional_doc_content` = NULL; INSERT succeeds; trigger populates search vector from title only |
| New item registered with sibling functional doc | File present next to technical design | Both columns populated from file; trigger populates search vector from title + content |
| Register with explicit `--functional-doc PATH` override | Path points to file outside the `ai-dev/active/<ID>/` directory | Loader reads from the given path and stores that path verbatim in `functional_doc_path` (relative to repo root) |
| Register with `--functional-doc PATH` pointing to a non-existent file | Path given but file missing | Register fails with a clear error message naming the missing path; no partial INSERT |
| Functional doc exceeds 500 words | Long file | `iw register` still loads it (trusts the design phase); `iw-review-design` blocks earlier |
| Functional doc contains forbidden term | `orch/` fragment in the markdown | `iw-review-design` surfaces a warning; approval requires manual override or edit |
| Functional doc content updated after approval (DB UPDATE) | Row updated via backfill `--load-db` | Trigger regenerates `functional_doc_search`; app-policy (not DB policy) is that approved items should not be updated post-completion — the operator is accountable |
| Dashboard tab for item with NULL content | Tab opened | Empty-state fragment renders; no server error |
| Dashboard tab after functional content added via backfill | Tab re-opened | Rendered markdown appears; no page reload needed (htmx swap) |
| Backfill `--load-db` when the item does not exist | Item ID not in DB | Exit code 4; filesystem untouched |
| Backfill `--load-db` when opencode fails | Subprocess non-zero exit | Exit with opencode's return code; DB not touched |
| Downgrade when rows have non-NULL `functional_doc_content` | Populated DB | Downgrade succeeds; data loss is acceptable (the markdown file in git remains the source of truth) |

## Invariants

1. `functional_doc_search` is automatically maintained by a trigger — application code never writes to it directly.
2. Whenever `functional_doc_content` is non-NULL, `functional_doc_search` is non-NULL (enforced by trigger fired on INSERT and UPDATE OF `title`, `functional_doc_content`).
3. The "Functional Design" tab is the second tab after "Design Document" in the item detail page tab row — its position is stable across projects.
4. The `idx_work_items_functional_doc_search` index exists and uses GIN.
5. `alembic downgrade -1` from the F-00059 revision leaves zero orphan DB objects related to `functional_doc_*`.
6. No dashboard request, CLI command, or daemon step ever edits `functional_doc_content` for a work item whose status is `Done` (policy invariant; backfill `--load-db` is the single documented exception and the operator is responsible).
7. The existing `design_doc_search` column, trigger, index, and any FTS consumer behaviour are unchanged by this feature.

## Dependencies

- **Depends on**: None.
- **Blocks**: F-00060 (Hybrid Code Q&A retrieval).

## TDD Approach

**Unit tests**:
- `iw-review-design` validator: parameterised cases for missing-file, missing each H2 section, word count = 499 / 500 / 501, forbidden-term matches (file extension, path fragment, SQL DDL, code fence), happy path.
- `backfill_functional_doc.py --load-db`: mocked opencode invocation, verify DB UPDATE payload; verify exit codes for item-not-found and file-not-found paths.

**Integration tests** (Postgres testcontainer):
- FTS trigger: insert WorkItem with functional_doc_content → search vector contains expected lexemes; update content → search vector updates; update title only → search vector still updates.
- GIN-index query returns the expected row for a term in the functional doc but not in the design doc (proves the two columns are independent).
- **Migration round-trip** (enforces Invariant 5): run the F-00059 migration's `upgrade()` against a fresh testcontainer, populate a row, run `downgrade()`, and assert that the three columns, the trigger, the trigger function, and the GIN index are all gone; then run `upgrade()` again and assert it succeeds (no orphan objects block re-create). Persistent test: `test_functional_doc_migration_round_trip` in `tests/integration/test_work_items_functional_doc_fts.py`.
- `iw register` path: file present → both columns populated; file absent → both NULL, no error; `--functional-doc` override path respected.
- Dashboard route: content present → fragment contains rendered markdown; content NULL → empty-state fragment; unknown item → 404.

**Edge cases**: every Boundary Behavior row has at least one test. Cross-layer happy-path test registers an item with both docs, loads the dashboard, clicks both tabs, and asserts on both fragments.

## Notes

- **Skills sync**: edits to `skills/iw-new-feature`, `iw-new-incident`, `iw-new-cr`, `iw-review-design` under this repo's `skills/` are only the master copy. An operator must run `iw skills sync` against every project in `projects.toml` afterwards — that currently means **innoforge, iw-ai-core, and cv**. iw-ai-core is itself a managed project (per the self-deploy convention) so its own `.claude/skills/` needs the same sync; do not skip it. This is documented in the S03 prompt and referenced in AC7. The orchestration pipeline does not auto-sync across repos.
- **Templates sync**: the new `Functional_Design_Template.md` lives in `ai-dev/templates/` (canonical) and is mirrored to `templates/design/` by the same sync flow. Projects pick it up when they next run `iw skills sync` / `iw init-project`.
- **Forbidden-term regex** (implemented in S03 for the review skill, tested in S05):
  - File-extension regex: `\b[A-Za-z0-9_./-]+\.(py|md|js|ts|tsx|sql|html|json|toml|yaml|yml)\b`
  - Path-fragment regex: `\b(orch|dashboard|scripts|ai-dev|tests|skills|templates|executor)/`
  - SQL-DDL regex (case-insensitive): `\b(ALTER\s+TABLE|CREATE\s+TABLE|DROP\s+TABLE|INSERT\s+INTO|SELECT\s+\*)\b`
  - Fenced code block: three-backtick fences anywhere in the body.
  Structural checks (missing file, missing H2 section, > 500 words) are BLOCKING. Content checks (forbidden terms) are WARNINGS that block unless explicitly dismissed by the reviewer — this keeps false positives (e.g. "the dashboard" is fine, "dashboard/routers" is not) manageable.
- **Trigger naming**: the existing trigger is `work_items_fts_update` on column `design_doc_search`. The new one is `work_items_functional_doc_search_update` on column `functional_doc_search`. Kept distinct so each can be dropped independently.
- **Tier-2 archive**: this feature does not change the archive/zstd flow. Archived items' `functional_doc_content` goes with them as a TEXT column; no new archive handling needed.
- **Browser evidence pre-state**: none captured — the Functional Design tab does not exist yet. Post-state screenshots are captured by S12 into `evidences/post/`.
