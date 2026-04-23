# F-00059_S05_Tests_prompt

**Work Item**: F-00059 — Functional design documents for work items
**Step**: S05
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute any docker container/volume/network mutation command.
See S01 banner. Testcontainers via pytest fixtures are allowed.

---

## Input Files

- `ai-dev/active/F-00059/F-00059_Feature_Design.md` — see *TDD Approach*, *Boundary Behavior*, *Invariants*
- All S01..S04 reports — confirm the shape of what each layer built
- `tests/conftest.py` and `tests/integration/conftest.py` — existing fixtures, FTS install, session factories
- `tests/CLAUDE.md` — fixture rules and anti-patterns

## Output Files

- `ai-dev/active/F-00059/reports/F-00059_S05_Tests_report.md` (new)
- `tests/integration/test_work_items_functional_doc_fts.py` (if not already created in S01; otherwise extend)
- `tests/integration/test_item_register_functional_doc.py` (if not already created in S02; otherwise extend)
- `tests/integration/test_dashboard_item_functional_tab.py` (new)
- `tests/unit/test_backfill_functional_doc.py` (if not already created in S02; otherwise extend)
- `tests/unit/test_review_design_functional_validation.py` (new)

## Context

S01..S04 implemented the feature end-to-end with their own per-step TDD. This
step adds the cross-layer and boundary-behaviour tests that prove the full
design-doc contract holds in integration, fills any per-step gaps, and closes
every row of the design's *Boundary Behavior* table.

Do NOT duplicate tests that already exist from S01..S04. Read each prior
report first and only add what is missing.

## Requirements

### 1. FTS integration tests

Complete coverage of the `work_items_functional_doc_search_trg` trigger —
extend S01's test if needed:

- Bulk insert of 10 work items with varied `title` and `functional_doc_content`
  combinations — assert every row's search vector matches expectation.
- `functional_doc_search` and `design_doc_search` are independent: updating
  one column never affects the other's vector.
- GIN index is used for a `@@` query (check via `EXPLAIN` / `plan_hash`
  assertion that the index is hit; if the testcontainer is too small for the
  planner to prefer GIN, set `enable_seqscan = off` for the test and re-run).

### 2. `iw register` integration tests

Fill AC4 and its boundary rows — extend S02's test if needed:

- Register with sibling `<ID>_Functional.md` present → both columns set; FTS
  returns the row on a content-specific term.
- Register without sibling file → columns NULL; FTS returns the row on a
  title-specific term only.
- Register with `--functional-doc PATH` pointing at a file outside
  `ai-dev/active/<ID>/` → `functional_doc_path` stores the verbatim
  (relative-to-repo-root) path; content loaded from that file.
- Register with `--functional-doc PATH` pointing at a missing file → command
  exits non-zero; no row inserted; DB state unchanged.
- Register twice with the same ID: the first succeeds; the second fails (or
  no-ops, matching existing register-command idempotency behaviour) — this
  is a regression check, not a new behaviour.

### 3. Backfill script unit tests

Fill every boundary branch — extend S02's test if needed:

- `--load-db` + opencode produces file + WorkItem exists → DB UPDATE happens
  with the expected payload; session committed.
- `--load-db` + opencode produces file + WorkItem missing → exit 4; DB not
  touched; file remains on disk.
- `--load-db` + opencode exits non-zero → early exit with opencode's code;
  no DB path reached.
- `--load-db` + DB raises `SQLAlchemyError` → exit 7; the message is printed
  to stderr; file remains on disk.
- No `--load-db` flag → no DB calls whatsoever (mock `SessionLocal`,
  assert `MagicMock.assert_not_called()`).
- `--force` semantics unchanged (overwrites file); verify `--force` and
  `--load-db` compose correctly.

### 4. Review-skill validation unit tests

Create `tests/unit/test_review_design_functional_validation.py`. The review
skill's validation logic must be callable as a pure function (if S03 did
not extract one, request the refactor; do not copy-paste regexes here).
Cover:

- Happy path: a 200-word doc with all three required H2 sections, no
  forbidden terms → `violations == []`, `blocking == []`.
- Missing file → blocking error "functional doc not found".
- Missing one of the required H2 sections (parameterise on each of the three)
  → blocking error naming the section.
- Word count boundaries: 499 → pass, 500 → pass (inclusive), 501 → blocking
  error naming the count.
- File-extension match → warning; each of `.py .md .sql .js .ts .tsx .html .json .toml .yaml .yml` triggers.
- Path-fragment match → warning; each of `orch/ dashboard/ scripts/ ai-dev/ tests/ skills/ templates/ executor/` triggers.
- SQL-DDL match → warning; each of the listed patterns triggers (test with
  both upper and lower case inputs to confirm case-insensitivity).
- Code-fence match → warning.
- A doc with structural issues AND content issues → both are reported
  simultaneously; blocking status is driven by the structural issues only.

### 5. Dashboard route integration tests

Create `tests/integration/test_dashboard_item_functional_tab.py`:

- Request the route for an item with non-NULL `functional_doc_content` →
  200; the fragment contains the rendered markdown (assert on a unique word
  from the seeded content).
- Same item after clearing `functional_doc_content` → 200; fragment contains
  the empty-state copy defined in S04.
- Request for an unknown item ID → 404.
- Request for a valid item with `functional_doc_content` NULL but
  `functional_doc_path` pointing at an on-disk file (simulate via a
  `tmp_path` fixture) → 200; fragment contains the file's content (fallback
  path).
- Request with the wrong project in the URL path → 404 (cross-project
  leakage check).

## Project Conventions

Read `tests/CLAUDE.md`. Postgres testcontainer fixtures only — never connect
to the live DB. Use `psycopg` (v3), not `psycopg2`. FTS function + trigger
SQL install happens in the `db_engine` fixture (already wired by S01).

## TDD Requirement

This step is test-only; there is no RED-GREEN cycle to perform here beyond
verifying that every test added now **passes** against the S01..S04
implementation. Any test that fails means the prior step did not honour the
design — report it as a blocker rather than patching the test to green.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — pass, zero failures.
2. `make test-integration` — pass, zero failures.
3. `make lint` — pass.
4. `make type-check` — pass.

## Subagent Result Contract

Standard JSON with `step: "S05"`, `agent: "tests-impl"`, `work_item: "F-00059"`. Include counts of new tests added per file in `notes`.
