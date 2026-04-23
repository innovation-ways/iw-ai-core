# F-00059_S06_CodeReview_Final_prompt

**Work Item**: F-00059 — Functional design documents for work items
**Step**: S06
**Agent**: code-review-final-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute any docker container/volume/network mutation command.
See S01 banner. Read-only `docker ps | inspect | logs` is fine for
investigation.

---

## Input Files

- `ai-dev/active/F-00059/F-00059_Feature_Design.md` — the single source of truth
- All S01..S05 reports
- Every file in the *File Manifest* (Source files created / modified)

## Output Files

- `ai-dev/active/F-00059/reports/F-00059_S06_CodeReview_Final_report.md` (new)

## Context

This is the global cross-layer review. S01..S05 each had their own review;
this step checks that the seams between layers are tight and that the feature
actually satisfies every Acceptance Criterion and Invariant in the design.

## Review Checklist

### 1. Design-contract coverage

For each AC1..AC7 in the design doc, verify that implementation + tests
exist and are wired end-to-end. For each Invariant 1..7, verify that at
least one test enforces it OR that the mechanism (trigger, migration) makes
violation impossible. Flag any missing coverage as a blocking finding.

### 2. DB / ORM symmetry

Compare the new `functional_doc_*` trio (columns, constants, trigger, index,
downgrade) with the existing `design_doc_*` trio line-by-line in
`orch/db/models.py` and the migration file. Any asymmetry that is not
deliberate and documented in the feature design is a finding. Specifically
check:

- Column types, nullability, and `comment=` strings.
- Trigger function name, trigger name, and trigger firing clause
  (`BEFORE INSERT OR UPDATE OF ...`).
- GIN index name and `postgresql_using`.
- `tests/integration/conftest.py` installs both new trigger constants
  alongside the old ones, in the same `conn.execute(text(...))` block.
- `downgrade()` drops index → trigger → function → columns, in that order,
  with `IF EXISTS` guards.

### 3. Backend / CLI correctness

Read `orch/cli/item_commands.py` `register` diff:

- Auto-detect path resolution is relative to `design_doc_path.parent`, not
  to `Path.cwd()` (so registering from any cwd works).
- `--functional-doc` override respects the `Path.cwd()` convention for
  relative paths (same as `--design-doc`).
- Missing override file raises a clear error before any DB write.
- Empty-content sibling file is treated consistently with empty-content
  `design_doc` behaviour.

Read `scripts/backfill_functional_doc.py` diff:

- `--load-db` is opt-in; default behaviour is unchanged.
- Exit codes match the documented table (4 for missing item, 7 for DB
  error).
- Session scope: the UPDATE and commit happen inside a single `with`
  block; no connection leaks on exception paths.

### 4. Skill changes

`skills/iw-new-feature/SKILL.md`, `iw-new-incident/SKILL.md`, and
`iw-new-cr/SKILL.md` all tell their author AI to produce
`<ID>_Functional.md` and include it in the File Manifest table. The wording
is consistent across the three skills — drift in this area is a finding.

`skills/iw-review-design/SKILL.md` enumerates the structural (blocking) and
content (warning) checks exactly as in the design doc's
*Notes / Forbidden-term regex* subsection. Any missing pattern in the skill
body is a blocking finding.

### 5. Frontend integration

- The new tab button is immediately after "Design Document" in
  `item_detail.html` — not first, not last.
- The new fragment file structurally mirrors `item_design_doc.html` —
  inline JS or added libraries would be a finding.
- The route returns a fragment (not a full page template) — htmx swap
  requires this.
- Empty-state copy matches the S04 spec.

### 6. Tests

- Every row of the design's *Boundary Behavior* table has at least one
  test.
- Every Invariant 1..7 is enforced or evidenced.
- Tests isolate state via testcontainers + pytest fixtures; no test
  accesses the live DB (would be a blocking finding).
- `psycopg` v3 used throughout (`postgresql+psycopg://`, not
  `+psycopg2://`).

### 7. Skills-sync and templates-sync reminders

The S03 report explicitly flags that an operator must run `iw skills sync`
for `innoforge` and `cv` after merge. If that reminder is missing, file a
finding (not blocking — it's a documentation gap, but important).

### 8. No regressions

- Existing `design_doc_search` column, trigger, index: byte-for-byte
  unchanged (diff-check `orch/db/models.py` around the existing constants).
- Existing tabs on the item detail page render identically.
- Existing tests still pass.

## Procedure

1. Read the design doc and every step report end-to-end.
2. Check out each file in the File Manifest and cross-reference against the
   checklist.
3. Run the full test suite locally inside the worktree: `make check`.
4. Write the report with findings grouped by *Blocking* and *Non-blocking*.
5. If any finding is blocking, call `iw step-fail` with a reason; otherwise
   call `iw step-done`.

## Test Verification (NON-NEGOTIABLE)

1. `make check` — pass (this is lint + format-check + mypy + unit + integration).
2. Zero blocking findings in the report.

## Subagent Result Contract

Standard JSON with `step: "S06"`, `agent: "code-review-final-impl"`, `work_item: "F-00059"`.
