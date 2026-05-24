# I00108_S04_CodeReview_prompt

**Work Item**: I-00108 -- `iw doc-update` new-doc without `--tier`/`--editorial-category` should be exit 2 usage error, not exit 3 TypeError
**Step Being Reviewed**: S03 (tests-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits

You MUST NOT change Docker container/volume/network state. Testcontainer fixtures in pytest are exempt. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This item adds no migration. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00108 --json`.
- `ai-dev/active/I-00108/I-00108_Issue_Design.md` -- Design document.
- `ai-dev/active/I-00108/reports/I-00108_S03_Tests_report.md` -- S03 report.
- `tests/integration/cli/test_doc_update_contract.py` -- the only file S03 should have touched.
- `skills/iw-ai-core-testing/SKILL.md` -- mandatory reading: assertion-strength rules, the red-flag checklist (incl. tautology / shape-only / mock-only).

## Output Files

- `ai-dev/active/I-00108/reports/I-00108_S04_CodeReview_report.md` -- Review report.

## Context

S03 removed the `@pytest.mark.xfail(strict=True)` marker from `test_doc_update_new_doc_without_tier_is_clean_usage_error` (the reproduction test, now GREEN post-S01) and added two regression tests pinning the optional/required asymmetry: update-path stays optional, new-doc-happy-path still works. Verify the changes are correct, semantically strong, and don't pull in scope creep.

## Read the Design Document FIRST

- `## Acceptance Criteria` — AC2 lists the exact tests that must be green.
- `## TDD Approach` — the rationale for two regression tests (preserve update path, preserve new-doc happy path).

## Pre-Review Lint + Assertion-Scanner Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
make test-assertions
```

If `make test-assertions` flags either new test as tautology / shape-only / mock-only / bare `pytest.raises`, that is a **CRITICAL** finding — the assertion scanner is the merge gate.

## Review Checklist

### 1. xfail marker removed

- The `@pytest.mark.xfail(strict=True, reason=...)` decorator on `test_doc_update_new_doc_without_tier_is_clean_usage_error` is GONE.
- The function body and its assertions are UNCHANGED (the same `assert result.exit_code == 2` and `assert "tier" in (result.stderr or "").lower()` from CR-00073 still pin the contract).
- If the marker is still present, CRITICAL: the test cannot record as GREEN with the marker in place.

### 2. `test_doc_update_existing_doc_update_without_tier_succeeds` correctness

- The test **seeds an existing ProjectDoc** before issuing the second (update) call. Without a prior create, the second call would hit the new pre-check and fail — verify the seeding is real and the precondition is asserted (e.g. `assert first.exit_code == 0`).
- The second call **omits `--tier` and `--editorial-category`** — that's the whole point of this test. If the test passes those flags, it does NOT pin the update-path-stays-optional contract (HIGH).
- Assertions check **specific values**, not just shape: title equals the updated title, content contains the v2 substring, exit code is 0. Generic `assert doc is not None` or `assert "title" in data` are MEDIUM_FIXABLE (assertion-scanner risk).
- The test does NOT depend on `WorkItem` rows — `ProjectDoc` is independent of `WorkItem`. If the test seeds a `WorkItem`, flag it as MEDIUM_SUGGESTION (over-seeding).

### 3. `test_doc_update_new_doc_with_tier_and_category_succeeds` correctness

- The test uses a **fresh doc id** (no collision with the other tests). Doc ids like `F-00201` or similar — flag any clash with seeds in the same file.
- It passes **all four flags** (`--doc-type`, `--title`, `--tier`, `--editorial-category`, plus `--content`). Missing any → the test would no longer pin the happy path.
- Assertions check **specific values**: `doc_id == "F-00201"`, `tier.value == "human_authored"`, `editorial_category.value == "technical"`. Generic checks (`assert doc.tier is not None`) are MEDIUM_FIXABLE.
- The JSON output is parsed and checked for at least one specific field (e.g. `data["doc_id"]`).

### 4. In-process vs subprocess

Both new tests should be **in-process** via Click `CliRunner` + `cli_get_session` — the existing `test_doc_update_*` tests use that pattern. Spawning a subprocess via `iw_subprocess` would be unnecessary complexity here (no env-var or process-level behaviour is under test). If S03 used `iw_subprocess` for either new test, MEDIUM_SUGGESTION.

### 5. Scope discipline

- Diff limited to `tests/integration/cli/test_doc_update_contract.py`. Any other file changed → HIGH.
- The other 5 existing tests in the file are unchanged (no rewording of their docstrings, no rename, no re-numbering of doc ids). Cosmetic touches are MEDIUM_SUGGESTION.

### 6. Project conventions

- Function names use `snake_case` and describe the contract (`test_doc_update_<scenario>_<expected_outcome>`).
- Docstrings name the contract being pinned (1-2 lines, no implementation detail).
- File-local `invoke` helper is reused; no duplicate.

### 7. TDD RED Evidence

Two regression tests pin **preserved** behaviour (no bug to RED on). `tdd_red_evidence` of "n/a — regression-guard tests pin behaviour S01 deliberately preserved" (or similar) is acceptable. Verify the report includes the RED→GREEN pytest line for the xfail-flipped reproduction test (e.g. `test_doc_update_new_doc_without_tier_is_clean_usage_error PASSED`).

## Test Verification (NON-NEGOTIABLE)

Run the targeted contract file:

```bash
uv run pytest tests/integration/cli/test_doc_update_contract.py -v --no-cov 2>&1 | tail -25
```

Expected: **8 passed, 0 xfailed, 0 failed**. Anything less → HIGH finding.

Do NOT run the full suite — that's S10/S11.

## Severity Levels

- **CRITICAL** — fix or merge will be blocked (assertion scanner trip, xfail still present, test cannot pass).
- **HIGH** — must fix before merge (wrong code path, missing assertion, broken contract).
- **MEDIUM_FIXABLE** — should fix this cycle (assertion strength, naming).
- **MEDIUM_SUGGESTION** — improvement idea, defer if tight.
- **LOW** — nit / style.

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00108",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "8 passed, 0 failed",
  "notes": ""
}
```

- `verdict`: `pass` iff zero CRITICAL + HIGH + MEDIUM_FIXABLE findings.
- `mandatory_fix_count`: count of CRITICAL + HIGH + MEDIUM_FIXABLE.
