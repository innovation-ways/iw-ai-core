# I-00108: `iw doc-update` new-doc without `--tier`/`--editorial-category` crashes with raw TypeError (exit 3) instead of a clean usage error (exit 2)

**Type**: Issue
**Severity**: Low
**Created**: 2026-05-22
**Reported By**: CR-00073 contract test (xfail strict, `TODO(file-incident)`)
**Status**: Draft

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. **This item adds no migration and no schema change.**)

## Description

`iw doc-update <new-doc-id>` accepts a flag combination it can't fulfill: when the target ProjectDoc does not yet exist and the caller omits `--tier`/`--editorial-category`, the command crashes with a raw `TypeError` from `DocService.create_doc()` surfaced as `exit 3 "Database error: ... missing 2 required positional arguments: 'tier' and 'editorial_category'"`. The expected behavior is a clean exit-2 usage error that names the missing options. Pinned by a strict `xfail` contract test in CR-00073.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Key facts for this item: `iw` is the agent-to-DB bridge; `doc-update` upserts a `ProjectDoc` and is intentionally an **upsert** (not just create) — so its Click options for `--tier`/`--editorial-category`/`--doc-type` are deliberately optional in the CLI signature (an update of an existing doc may legitimately change only content). The required-args constraint lives one layer below, in `DocService.create_doc()`, and only applies to the *new-doc* code path.

## Steps to Reproduce

1. Have a project registered (`test-proj` or any valid project) with no existing `ProjectDoc` for some id (e.g. `F-NEW`).
2. Run: `uv run iw --project test-proj doc-update F-NEW --doc-type module --title T`.
3. Observe the exit code and stderr.

**Expected**: exit 2 with a usage-style error such as `Error: --tier and --editorial-category are required when creating a new doc (no existing ProjectDoc 'F-NEW' to update)`.

**Actual**: exit 3 with `Error: Database error: DocService.create_doc() missing 2 required positional arguments: 'tier' and 'editorial_category'` — a `TypeError` mislabeled as a "Database error".

## Root Cause Analysis

`orch/cli/doc_commands.py::doc_update` builds `kwargs` from optional Click options, then unconditionally calls `svc.upsert_doc(project_id, doc_id, **kwargs)`. The `upsert_doc` flow:

* If the doc **already exists** → `update_doc()` is called; the kwargs are partial-update fields, all optional. ✓
* If the doc **does not exist** → `create_doc()` is called; `create_doc()` requires `tier` and `editorial_category` as positional/keyword arguments. Missing kwargs raise `TypeError`. ✗

The TypeError is caught by the broad `try / except Exception` at the end of `doc_update` (around `orch/cli/doc_commands.py` line ~256) and converted to `output_error(ctx, f"Database error: {exc}", 3)`. Two problems with the current shape:

1. The error label is **misleading** — there is no database error; it is a usage error (the caller forgot two flags).
2. The **exit code is wrong** — exit 3 is reserved for configuration / database errors, not for missing required input. A Click-style usage error would exit 2.

Making the options Click-`required=True` is not a fix: it would break the update use case (where the flags are optional). The fix has to be a runtime branch: when the doc doesn't exist, require `tier` and `editorial_category` *before* calling `upsert_doc`.

## Affected Components

| Component | Impact |
|-----------|--------|
| `orch/cli/doc_commands.py` (`doc_update` callback) | Surfaces `TypeError` as exit 3 "Database error" instead of clean exit 2 usage error |
| `tests/integration/cli/test_doc_update_contract.py` | `test_doc_update_new_doc_without_tier_is_clean_usage_error` is `@pytest.mark.xfail(strict=True)` — once the fix lands the strict xfail becomes xpass and the marker must be removed |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Add a pre-check in `doc_update`: when `svc.get_doc(project_id, doc_id) is None` AND (`tier is None` OR `editorial_category is None`) → `output_error(ctx, "...", 2)` with a clear message naming the two missing flags. The update path stays untouched. | — |
| S02 | code-review-impl | Per-agent review of S01 | — |
| S03 | tests-impl | Remove the `@pytest.mark.xfail(strict=True)` marker from `test_doc_update_new_doc_without_tier_is_clean_usage_error` (the test already encodes the desired contract — it now passes GREEN); add regression tests that pin: (a) update of an existing doc still works without `--tier`/`--editorial-category` (the optional case must be preserved), (b) new-doc with both flags still succeeds | — |
| S04 | code-review-impl | Per-agent review of S03 | — |
| S05 | code-review-final-impl | Global cross-agent review of S01..S04 | — |
| S06..S13 | qv-gate | lint, assertions, format, typecheck, unit-tests, integration-tests, diff-coverage, security-secrets | — |
| S14 | self-assess-impl | Self-assessment via `iw-item-analyze` | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None (no schema change)

### Code Changes

- **Files to modify**: `orch/cli/doc_commands.py` (one small pre-check branch), `tests/integration/cli/test_doc_update_contract.py` (drop one `xfail` marker, add ~2 regression tests).
- **Nature of change**: Add a usage-validation branch in the CLI callback before delegating to the service layer. No service-layer changes.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `I-00108_Issue_Design.md` | Design | This document |
| `I-00108_Functional.md` | Design | Human-facing summary |
| `workflow-manifest.json` | Manifest | Step definitions |
| `prompts/I-00108_S01_Backend_prompt.md` | Prompt | S01 backend fix |
| `prompts/I-00108_S02_CodeReview_prompt.md` | Prompt | S02 per-agent review of S01 |
| `prompts/I-00108_S03_Tests_prompt.md` | Prompt | S03 tests — remove xfail + regression |
| `prompts/I-00108_S04_CodeReview_prompt.md` | Prompt | S04 per-agent review of S03 |
| `prompts/I-00108_S05_CodeReview_Final_prompt.md` | Prompt | S05 global review |
| `prompts/I-00108_S14_SelfAssess_prompt.md` | Prompt | S14 self-assess |

## Test to Reproduce

The reproduction test already exists — CR-00073 wrote it as a strict `xfail` pinning the desired post-fix contract:

```python
# tests/integration/cli/test_doc_update_contract.py
@pytest.mark.xfail(
    strict=True,
    reason=(
        "TODO(file-incident): doc-update accepts a new-doc upsert that omits "
        "--tier/--editorial-category, then crashes with a raw TypeError from "
        "DocService.create_doc() surfaced as exit 3 'Database error'. The "
        "contract should be a clean exit 2 usage error naming the missing "
        "options. Operator follow-up: file an Incident; the orch/cli fix is "
        "out of scope for this test-only CR."
    ),
)
def test_doc_update_new_doc_without_tier_is_clean_usage_error(...):
    """A new-doc doc-update missing --tier/--editorial-category should be a clean
    exit-2 usage error — not a raw TypeError surfaced as exit 3."""
    ...
    result = invoke(
        runner,
        ["doc-update", "F-00099", "--doc-type", "module", "--title", "T"],
        cli_get_session,
    )
    assert result.exit_code == 2, f"stdout: {result.output}\nstderr: {result.stderr}"
    assert "tier" in (result.stderr or "").lower()
```

S03 removes the `@pytest.mark.xfail` marker. The fix in S01 turns this test from `xfailed` to `passed`. The `strict=True` flag means: if S01 forgets to wire up the check, this test will fail with `XPASS(strict)` only if the unchanged behavior somehow flips — but more importantly, the explicit assertions (`exit_code == 2`, `"tier" in stderr`) directly pin the new contract.

## Acceptance Criteria

### AC1: Bug is fixed

```
Given a project exists and no ProjectDoc exists for "F-NEW"
When the operator runs `iw --project test-proj doc-update F-NEW --doc-type module --title T`
  (omitting --tier and --editorial-category)
Then the command exits with code 2 (not 3)
  And stderr contains a clear usage error naming "--tier" and "--editorial-category"
  And stderr does NOT contain "TypeError" or "Database error: ... missing ... positional arguments"
  And no ProjectDoc row is created
```

### AC2: Regression test exists

```
Given the fix is applied
When `make test-cli-contract` (and `make test-integration`) runs
Then test_doc_update_new_doc_without_tier_is_clean_usage_error passes GREEN
  (the @pytest.mark.xfail(strict=True) marker has been removed by S03)
  And test_doc_update_existing_doc_update_without_tier_succeeds passes
  And test_doc_update_new_doc_with_tier_and_category_succeeds passes
```

## Regression Prevention

- The reproduction test moves from `xfail strict` to `passed`. Removing the `xfail` marker means any future regression that re-introduces the exit-3 TypeError surfacing will fail the test directly.
- The new regression tests pin **both** sides of the optional/required asymmetry: update-without-tier MUST still succeed; create-without-tier MUST fail cleanly. Together they prevent a "fix" that over-corrects by making the options mandatory at the Click layer.
- No new validation primitives are added — the fix is a single conditional in the existing CLI callback, scoped to the exact failure mode surfaced by the contract test.

## Dependencies

- **Depends on**: CR-00073 (which authored the reproduction test as a strict `xfail` and filed this incident).
- **Blocks**: None.

## Impacted Paths

- `orch/cli/doc_commands.py`
- `tests/integration/cli/test_doc_update_contract.py`

## TDD Approach

- **Reproducing test**: `test_doc_update_new_doc_without_tier_is_clean_usage_error` — already written by CR-00073 as `@pytest.mark.xfail(strict=True)`. S01 makes it pass; S03 removes the xfail marker. The xfail-then-remove pattern keeps the desired contract pinned for the entire fix cycle (a fix that misses the case keeps the test red).
- **Unit tests**: none — the change is a single conditional in a Click callback already exercised end-to-end by the contract tests.
- **Integration tests** (S03): add `test_doc_update_existing_doc_update_without_tier_succeeds` (update path still optional) and `test_doc_update_new_doc_with_tier_and_category_succeeds` (the happy path still works). Both via Click's `CliRunner` against the testcontainer `db_session` — match the patterns already in `test_doc_update_contract.py`.

## Notes

- This is a small, narrowly-scoped CLI usability fix. The orch CLI is the agent-to-DB bridge and its exit-code/stderr contract is load-bearing — exit 3 "Database error" for missing required args makes the bug invisible to a downstream caller that only checks exit codes (a "Database error" reads as transient/retryable; a missing-arg usage error reads as caller-must-fix).
- The fix MUST preserve the upsert semantics: tier/editorial-category remain optional for **updates** of existing docs. The Tests step has an explicit regression test for that side.
