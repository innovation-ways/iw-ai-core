# I00108_S03_Tests_prompt

**Work Item**: I-00108 -- `iw doc-update` new-doc without `--tier`/`--editorial-category` should be exit 2 usage error, not exit 3 TypeError
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

You MUST NOT change Docker container/volume/network state. Testcontainer fixtures in pytest are exempt. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This item adds no migration. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00108 --json`.
- `ai-dev/active/I-00108/I-00108_Issue_Design.md` -- Design document (read §Acceptance Criteria, §TDD Approach).
- `ai-dev/active/I-00108/reports/I-00108_S01_Backend_report.md` -- S01 report (notes the post-fix `XPASS(strict)`).
- `ai-dev/active/I-00108/reports/I-00108_S02_CodeReview_report.md` -- S02 review.
- `tests/integration/cli/test_doc_update_contract.py` -- The file you'll modify (drop xfail marker, add 2 regression tests).
- `tests/integration/conftest.py` -- Read-only: fixtures `db_session`, `db_engine`, `test_project`, `cli_get_session`.
- `tests/integration/cli/conftest.py` -- Read-only: the `iw_subprocess` fixture (you will NOT need it for these tests — they are in-process via `CliRunner`).

## Output Files

- `ai-dev/active/I-00108/reports/I-00108_S03_Tests_report.md` -- Step report.

## Context

S01 added the pre-check that makes `iw doc-update` exit cleanly with code 2 when a new-doc call omits `--tier`/`--editorial-category`. The reproduction test (`test_doc_update_new_doc_without_tier_is_clean_usage_error`, authored by CR-00073 as a strict `xfail`) is currently reporting `XPASS(strict)` — the unexpected pass is the RED→GREEN proof. Your job is to:

1. Remove the `@pytest.mark.xfail(strict=True)` marker so the test records as a normal `passed`.
2. Add **two** regression tests pinning the asymmetry the fix preserves:
   - The update path (existing doc) MUST still accept calls without `--tier`/`--editorial-category`.
   - The new-doc happy path (with both flags supplied) MUST still succeed and create the row.

## Requirements

### 1. Remove the strict-xfail marker

In `tests/integration/cli/test_doc_update_contract.py`, remove the `@pytest.mark.xfail(strict=True, reason=...)` decorator from `test_doc_update_new_doc_without_tier_is_clean_usage_error`. Keep the function body and its assertions unchanged — those assertions now hold post-fix and pin the desired contract directly. The function is the reproduction test; without the marker, any future regression that reintroduces the exit-3 `TypeError` will fail the test directly.

If S01 unexpectedly **left** the bug in (the test is still `xfailed`, not `XPASSed`), STOP and raise a blocker — do NOT remove the marker yet, because doing so would convert a current `xfail` into a hard `failed`. Verify S01's fix landed by running the targeted file (see Test Verification below) before removing the marker.

### 2. Add `test_doc_update_existing_doc_update_without_tier_succeeds`

A new in-process `CliRunner` test:

```python
def test_doc_update_existing_doc_update_without_tier_succeeds(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """An update to an existing doc may omit --tier and --editorial-category —
    they are required only when creating a brand-new doc, per upsert semantics.

    Pins the "update path stays optional" side of I-00108: making --tier /
    --editorial-category required at the Click layer would have broken this
    path; the pre-check in doc_commands.py must fire only when no existing doc
    is found.
    """
    # Seed an existing ProjectDoc by running doc-update with all required flags first.
    first = runner.invoke(... full create call with --tier/--editorial-category ...)
    assert first.exit_code == 0  # precondition: the doc now exists

    # Now do an UPDATE without --tier/--editorial-category — must succeed.
    second = invoke(
        runner,
        ["doc-update", "<same-doc-id>", "--title", "Updated title", "--content", "v2"],
        cli_get_session,
    )
    assert second.exit_code == 0, f"stderr: {second.stderr}\nstdout: {second.output}"

    # Semantic check: the row was updated, not crashed/recreated.
    doc = db_session.execute(
        select(ProjectDoc).where(
            ProjectDoc.project_id == test_project.id,
            ProjectDoc.id == "<same-doc-id>",
        )
    ).scalar_one()
    assert doc.title == "Updated title"
    assert "v2" in (doc.content or "")
```

(Pseudocode — fill in the actual `ProjectDoc` import and the seeding call. Use a fresh doc id like `F-00200`. Match the style of the existing `test_doc_update_*` tests in the file.)

### 3. Add `test_doc_update_new_doc_with_tier_and_category_succeeds`

A new in-process `CliRunner` test pinning the new-doc happy path:

```python
def test_doc_update_new_doc_with_tier_and_category_succeeds(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """A new-doc upsert with all required flags creates the ProjectDoc row
    cleanly — the pre-check added for I-00108 must not fire when both
    --tier and --editorial-category are supplied.
    """
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--project", test_project.id, "--json",
            "doc-update", "F-00201",
            "--doc-type", "module",
            "--title", "New module doc",
            "--tier", "human_authored",
            "--editorial-category", "technical",
            "--content", "# New doc body",
        ],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )
    assert result.exit_code == 0, f"stderr: {result.stderr}\nstdout: {result.output}"
    data = json.loads(result.output)
    assert data["doc_id"] == "F-00201"
    assert data["project_id"] == test_project.id

    doc = db_session.execute(
        select(ProjectDoc).where(
            ProjectDoc.project_id == test_project.id,
            ProjectDoc.id == "F-00201",
        )
    ).scalar_one()
    assert doc.tier.value == "human_authored"
    assert doc.editorial_category.value == "technical"
```

### 4. Semantic correctness — non-negotiable

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

Tests that check API response SHAPE (key exists, is a list, is non-empty) and pass can mask a still-broken fix. Tests MUST verify SPECIFIC VALUES:

- BAD: `assert "doc_id" in data` (shape only)
- GOOD: `assert data["doc_id"] == "F-00201"` (semantic — verifies the specific expected value)
- BAD: `assert result.stderr` (just truthy)
- GOOD: `assert "tier" in result.stderr.lower()` (semantic — verifies the missing-flag name surfaces)
- BAD: `assert doc is not None` (only checks existence)
- GOOD: `assert doc.title == "Updated title"` (verifies the actual field that changed)

Every assertion in both new tests MUST be one that would fail if the production code regressed.

### 5. Scope discipline

You may modify ONLY `tests/integration/cli/test_doc_update_contract.py`. Do NOT touch `orch/cli/doc_commands.py` (that was S01's job) or any other test file.

### 6. Test verification (targeted only)

Run **only** the doc-update contract file from this step:

```bash
uv run pytest tests/integration/cli/test_doc_update_contract.py -v --no-cov 2>&1 | tail -25
```

Expected after S01 + your changes: **8 passed, 0 xfailed, 0 failed** (the original 6 tests with the xfail flipped to a normal pass + your 2 new tests).

Do NOT run `make test-unit`, `make test-integration`, or `make test-cli-contract` — those are S10/S11 QV gates and including them blows the step's timeout budget (lesson from CR-00073 / I-00073).

### 7. TDD evidence

The reproduction test is now GREEN (no marker, real `passed`) — that's the documented RED→GREEN evidence. Cite the pytest one-liner showing `test_doc_update_new_doc_without_tier_is_clean_usage_error PASSED` in your report.

The two new regression tests are GREEN-from-the-start (they pin behaviour S01 preserves). Per `tests/CLAUDE.md` "TDD = RED → GREEN → REFACTOR", agent-authored tests are normally written failing-first. For pure regression-guard tests of *preserved* behaviour (where there is no bug to RED on), record `tdd_red_evidence` as `"n/a — regression-guard tests pin behaviour that S01 deliberately preserved (update path stays optional; new-doc happy path still works). The bug-reproducing test is the renamed-from-xfail test_doc_update_new_doc_without_tier_is_clean_usage_error which is now GREEN."`.

## Project Conventions

Read `tests/CLAUDE.md` for: live-DB guard, testcontainer rules, the assertion-strength scanner (`make test-assertions` — DO NOT trip it; your assertions must be specific-value, not shape-only). Read `skills/iw-ai-core-testing/SKILL.md` for assertion-strength rules and the test red-flag checklist.

Match the existing `test_doc_update_*_contract.py` style (file-local `invoke` helper, `seed_work_item` helper if needed for fixtures — though these tests do NOT need a work item; ProjectDoc rows are independent of WorkItem).

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`, run:

1. **`make format`** — auto-fixes formatting drift.
2. **`make lint`** — zero errors in the test file.
3. **`make test-assertions`** — your two new tests MUST NOT trip the scanner.

Do NOT run `make typecheck` for this step (mypy doesn't cover `tests/`).

## Test Verification (NON-NEGOTIABLE)

Targeted only — see Requirement 6. Expected: 8 passed.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00108",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["tests/integration/cli/test_doc_update_contract.py"],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "lint": "ok|skipped:<reason>",
    "test-assertions": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "8 passed, 0 failed (doc-update contract suite — xfail marker removed; 2 regression tests added)",
  "tdd_red_evidence": "n/a — regression-guard tests pin behaviour S01 deliberately preserved (update path stays optional; new-doc happy path still works). The bug-reproducing test is the renamed-from-xfail test_doc_update_new_doc_without_tier_is_clean_usage_error which is now GREEN.",
  "blockers": [],
  "notes": ""
}
```
