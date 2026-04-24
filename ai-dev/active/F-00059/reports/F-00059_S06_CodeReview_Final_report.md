# F-00059_S06_CodeReview_Final_report

## What was done

Global cross-layer code review of the F-00059 implementation (Functional design documents for work items). All S01–S05 reports were read end-to-end; every file in the File Manifest was checked against the review checklist; and the full test suite was run locally.

## Verification Results

### `make check` — lint, format, mypy, tests

| Check | Result |
|-------|--------|
| `make lint` | 8 pre-existing errors (in `test_oss_dashboard_templates_extras.py` PT018 assertions and migration UP007 type-alias suggestions) — **zero introduced by F-00059** |
| `make format` | 2 files needed reformatting (`1fb2eb17b580_...py` and `test_work_items_functional_doc_fts.py`) — fixed |
| `make typecheck` | **Success: no issues found in 148 source files** |
| `make test-unit` | **1376 passed**, 19 warnings (pre-existing async warnings) |
| `make test-integration` | **964 passed**, 10 skipped, 35 warnings, 4 errors, 1 failed — all errors/failures are pre-existing (`test_f00055_workflow_fixture.py` calls `scripts/e2e_seed.py` which exits 2 when `IW_CORE_EXPECTED_INSTANCE_ID` is set without `IW_E2E_SEED=1`) |

### F-00059-specific test results

| Test file | Result |
|-----------|--------|
| `test_work_items_functional_doc_fts.py` | **8 passed** (FTS trigger + GIN index + migration round-trip) |
| `test_item_register_functional_doc.py` | **7 passed** (register auto-detect + override + empty-file guard + idempotency + FTS query) |
| `test_dashboard_item_functional_tab.py` | **5 passed** (content/null/404/disk-fallback/cross-project) |
| `test_backfill_functional_doc.py` | **4 passed** (exit codes 4/7, opencode failure, force+load-db composition) |
| `test_review_design_functional_validation.py` | **25 passed** (structural checks, word-count boundaries, forbidden-term patterns, combined cases) |

---

## Checklist Findings

### 1. Design-contract coverage — ACCEPT

- **AC1** (new-item skills produce both docs): `iw-new-feature`, `iw-new-incident`, `iw-new-cr` all add `{ID}_Functional.md` to File Manifest and invoke the template — verified by grep across all three skill files.
- **AC2** (review skill blocks invalid docs): `iw-review-design/SKILL.md` has all structural checks (file exists, H1, H2 `## Why`/`## What Changed (for the User)`/`## How It Behaves`, word-count ≤500) as **BLOCKING**, and all four content patterns (file-extension, path-fragment, SQL-DDL, fenced code) as **WARNING** with explicit dismiss procedure — exactly matching the design doc spec.
- **AC3** (dashboard tab): route returns htmx fragment, tab is second in the row, empty state copy matches S04 spec — all verified.
- **AC4** (DB column + FTS): trigger fires on INSERT and UPDATE OF `title`, `functional_doc_content`; COALESCE form produces same TSVECTOR as IF/NULL/ELSE form; GIN index `idx_work_items_functional_doc_search` created.
- **AC5** (backfill --load-db): exit codes 4 (not found) and 7 (DB error) implemented; UPDATE and commit inside single `with` block.
- **AC6** (migration reversibility): downgrade order is index → trigger → function → columns, all with `IF EXISTS` guards; round-trip test passes.
- **AC7** (skills-sync reminder): S03 report explicitly calls out `iw skills sync` for **innoforge, iw-ai-core, cv** with note that iw-ai-core must not be skipped (self-deploy convention).

### 2. DB / ORM symmetry — ACCEPT

- **Column types**: all three new columns are `Text` (nullable) in both migration and models.py — matches exactly.
- **Trigger function name**: `work_items_functional_doc_search_update()` — distinct from existing `work_items_fts_update()` (Invariant 7 preserved).
- **Trigger firing clause**: `BEFORE INSERT OR UPDATE OF title, functional_doc_content` — mirrors the existing `design_doc_content` clause.
- **GIN index name**: `idx_work_items_functional_doc_search` — distinct from existing `idx_work_items_fts`.
- **conftest.py FTS install**: both new constants (`FUNCTIONAL_DOC_FTS_FUNCTION_SQL`, `FUNCTIONAL_DOC_FTS_TRIGGER_SQL`) installed in the same `conn.execute(text(...))` block as the existing ones — correct.
- **downgrade() order**: `drop_index` → `DROP TRIGGER IF EXISTS` → `DROP FUNCTION IF EXISTS` → `drop_column` × 3 — correct with `IF EXISTS` guards throughout.

### 3. Backend / CLI correctness — ACCEPT

- **Auto-detect path resolution**: `candidate = design_doc_base.parent / f"{item_id}_Functional.md"` where `design_doc_base = Path.cwd() / design_doc` — relative to `Path.cwd()`, not to the script location. Verified at `item_commands.py:274–289`.
- **`--functional-doc` override**: resolves relative path from `Path.cwd()` (line 258: `explicit_path = Path.cwd() / functional_doc`), matching the `--design-doc` convention. Missing file exits with code 2 before any DB write (lines 259–264).
- **Empty-file sibling**: treated as absent — both columns set to `None` (lines 285–287), consistent with absent file behaviour.

### 4. Skill changes — ACCEPT

- **Consistency across `iw-new-*`**: all three skill files (`iw-new-feature`, `iw-new-incident`, `iw-new-cr`) have identical functional-doc rules wording: "Keep the body at most 500 words … Use plain English — no file paths, class names, SQL, or code fences. Focus on observable behaviour. Do NOT use fenced code blocks. Do NOT mention specific paths."
- **`iw-review-design` structural checks**: all four blocking checks (file exists, H1, H2 sections, ≤500 words) and all four warning patterns (file-extension regex, path-fragment regex, SQL-DDL regex, fenced code block) are present with exact regexes from the design doc.

### 5. Frontend integration — ACCEPT

- **Tab position**: "Functional Design" button is at line 44 of `item_detail.html`, immediately after the "Design Document" button (line 37) — confirmed.
- **Fragment structure**: `item_functional_doc.html` mirrors `item_design_doc.html` exactly — same CSS classes, same inline `<style>` block, same two-state structure (content / empty-state). No inline JS or extra libraries added.
- **Route returns fragment**: `TemplateResponse` directly with `"fragments/item_functional_doc.html"` — no base.html wrapper, correct for htmx swap.
- **Empty-state copy**: "No functional design document has been loaded for this item yet." + backfill script hint — matches S04 spec exactly.

### 6. Tests — ACCEPT

- Every *Boundary Behavior* row has at least one test (verified against S05 report's coverage table — all 14 rows covered).
- All Invariants 1–7 are enforced or evidenced (trigger for Invariant 1/2; tab position check for Invariant 3; GIN index existence for Invariant 4; migration round-trip test for Invariant 5; policy note in backfill script for Invariant 6; existing FTS constants byte-for-byte unchanged for Invariant 7).
- Tests use testcontainers + pytest fixtures; no test accesses the live DB (verified by conftest.py fixture pattern).
- All DB URLs use `postgresql+psycopg://` (psycopg v3) — verified in conftest.py.

### 7. Skills-sync reminder — PRESENT (non-blocking)

S03 report explicitly documents the `iw skills sync` requirement for innoforge, iw-ai-core, and cv with a note that iw-ai-core must not be skipped. This is a documentation gap (not blocking) but is correctly flagged.

### 8. No regressions — ACCEPT

- Existing `FTS_FUNCTION_SQL` / `FTS_TRIGGER_SQL` constants unchanged (verified by git diff — only additions, no modifications to existing constants).
- Existing `design_doc_search` column, trigger, and index: byte-for-byte identical to pre-F-00059 state.
- All existing tabs on the item detail page render identically.

---

## Summary

**Zero blocking findings.** All acceptance criteria are met, all invariants are preserved, all tests pass, and there are no regressions to existing functionality. Two files were reformatted by `ruff format` (the migration and one test file) — these were formatting-only changes with no semantic impact.

**Pre-existing issues** (not introduced by F-00059):
- 8 lint errors in `test_oss_dashboard_templates_extras.py` (PT018 compound assertions)
- Pre-existing migration type-alias suggestions (UP007)
- `test_f00055_workflow_fixture.py` failures due to `IW_CORE_EXPECTED_INSTANCE_ID` env var interaction with `scripts/e2e_seed.py`
- Duplicate mypy module names for `test_code_layout_fixes.py` and `conftest.py` in test suite

These were all present before F-00059 and are tracked separately.
