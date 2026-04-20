# F-00056_S10_CodeReview_prompt

**Work Item**: F-00056 -- Work Item Execution Report — Retry Pattern & Pain-Point Visibility
**Step Being Reviewed**: S09 (tests-impl)
**Review Step**: S10

---

## Input Files

- `ai-dev/active/F-00056/F-00056_Feature_Design.md` -- Design document (TDD Approach, every AC, every Invariant, every Boundary Behavior row)
- `ai-dev/active/F-00056/reports/F-00056_S09_Tests_report.md`
- All test files listed in S09's `files_changed`
- The three backfilled markdown reports (F-00055 + 2 priors)

## Output Files

- `ai-dev/active/F-00056/reports/F-00056_S10_CodeReview_report.md`

## Review Checklist

### 1. AC Coverage

Map each of AC1..AC10 to at least one test. Any AC without an explicit covering test is a HIGH finding. Build a table in the review report:

| AC | Test file : test function |
|----|----------------------------|
| AC1 | ... |
| AC2 | ... |
| ... | ... |

### 2. Invariant Coverage

Map each of Invariants 1..12 to at least one test. Same structure as AC coverage. Missing invariants → HIGH.

### 3. Boundary Behavior Coverage

Every row in the Boundary Behavior table has at least one test. Missing rows → HIGH.

### 4. Test Isolation and Conventions

- NEVER connects to the live DB (port 5433). Verify no `IW_CORE_DB_*` hardcoded in tests.
- NEVER mocks the database in integration tests.
- Uses testcontainers with psycopg v3 URL replacement.
- FTS trigger SQL is applied after `create_all()` in integration tests.
- No `importlib.reload(orch.config)` calls.
- Tests are deterministic (no time-based flakes; freeze time where the code reads `datetime.now`).

### 5. Test Quality

- Each test's name clearly describes what it verifies.
- Fixtures are reused across tests where sensible (DRY without over-abstraction).
- Assertions are specific (not just `assert result`).
- No commented-out `skip` or `xfail` markers without justification.

### 6. Backfill Verification

- Three markdown files exist on disk at the resolver-determined paths (each item's `ai-dev/active/<id>/` if present, else `ai-dev/archive/<id>/`); S09's `files_changed` and `notes` must cite those actual paths, not the `ai-dev/active/<id>/...` template.
- F-00055's file contains the expected hotspot signature: "S13" × 3, "S10" × 2, "S16" × 2 (or matching actual pattern if the S13/S10/S16 numbering changed since F-00055's design).
- The two prior items' files render without crashes — even if their data is minimal, the files exist and are non-empty.
- S09 report's `notes` field names the two prior item IDs explicitly AND the resolved path (active vs archive) for each of the three items.

### 7. Snapshot Test (Invariant 7)

- Verify the snapshot-style test for existing tabs (Overview, Design Doc, Reports, Artifacts, Evidences, Logs, Fix Cycles) exists and passes; the approach (HTML byte-identical or structural equivalence) is sensible.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit`
2. `make test-integration`
3. `uv run ruff check tests/`
4. Ensure the three backfilled markdown files pass a basic grep for the required wording ("Retry Hotspots", "Step Timeline", "Fix Cycles") — sanity check.

## Review Result Contract

Standard JSON. `verdict=pass` only if zero CRITICAL + zero HIGH + zero MEDIUM_FIXABLE.
