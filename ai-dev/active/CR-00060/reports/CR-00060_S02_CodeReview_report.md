# CR-00060 S02 Code Review Report — Hypothesis property-based tests (P2-CR-B)

**Reviewing agent**: S01 (backend-impl)
**Reviewer**: code-review-impl
**Work Item**: CR-00060
**Step**: S02

---

## Verdict

**NEEDS_FIX**

---

## 1. Dep + config + marker

| Check | Result | Detail |
|-------|--------|--------|
| `hypothesis>=6.100,<7` in `[dependency-groups] dev` | ✅ PASS | v6.152.7 confirmed |
| `uv run python -c "import hypothesis; print(hypothesis.__version__)"` | ✅ PASS | 6.152.7 |
| `[tool.hypothesis]` block in `pyproject.toml` | ✅ PASS | `database_file = ".hypothesis/examples"` present |
| `.hypothesis/` in `.gitignore` | ✅ PASS | `.hypothesis/` entry confirmed |
| `properties` marker registered in `pyproject.toml` | ✅ PASS | `"properties: …"` in `markers` list |

---

## 2. Conftest correctness

| Check | Result | Detail |
|-------|--------|--------|
| Three profiles: `ci`, `dev`, `deep` | ✅ PASS | All three registered in `tests/unit/properties/conftest.py` |
| `ci` has `derandomize=True` | ✅ PASS | Present at line 16 |
| `ci` has `max_examples=20` | ✅ PASS | ≤50 threshold |
| `dev` has `max_examples=200` | ✅ PASS | |
| `deep` has `max_examples=1000`, `derandomize=False` | ✅ PASS | |
| `settings.load_profile()` defaults to `"ci"` | ✅ PASS | `os.environ.get("IW_HYPOTHESIS_PROFILE", "ci")` |
| `pytest_plugins = ["tests.integration.conftest"]` | ❌ CRITICAL | **MISSING** — not present in `tests/unit/properties/conftest.py` |
| `pytest_collection_modifyitems` auto-applies marker | ✅ PASS | Hook present and confirmed working (collect-only tests all 19 marked) |
| Marker auto-apply verified | ✅ PASS | `-m properties` collects all 19 tests; `-m "not properties"` returns empty |

Profile switching confirmed working (dev runs 200 examples vs ci's 20).

---

## 3. Five property modules — invariants + content

### Per-module invariant table

| Module | RuleBasedStateMachine or @given | #invariants | #rules / #properties | uses assume() | Critical concerns |
|--------|----------------------------------|-------------|----------------------|---------------|------------------|
| `test_work_item_lifecycle_properties.py` | RuleBasedStateMachine + 2 @given | 4 | 7 rules + 2 @given | N/A | Invariant 1 (`no_transition_from_terminal`) is **comment-only** — no assertion. Invariant 3 (`terminal_items_not_reclaimable`) is **comment-only** — no assertion. |
| `test_batch_lifecycle_properties.py` | @given (5 tests) | N/A | 5 properties | N/A | `compute_batch_status` returns `BatchStatus.executing` for P2 held/`awaiting_merge_approval` cases (design says `held`); returns `completed_with_errors` for P4 (design says `failed`); returns `executing` for P5 (design says `in_progress`). The implementation is internally consistent but semantically misnamed vs the design's property names. HIGH concern — the properties are asserted against the wrong enum values. |
| `test_fix_cycle_cap_properties.py` | RuleBasedStateMachine + 2 @given | 2 | 2 rules + 2 @given | N/A | Invariant 1 (`terminal_state_correct`) asserts `max_observed_count <= _DEFAULT_FIX_CYCLE_MAX` — this is the SAME invariant as `cycle_count_within_cap`. It does not assert anything about the "terminal state" being correct (step terminates at cap). Both invariants assert the cap; no assertion that the step is terminal when cap is hit. |
| `test_doc_diff_round_trip_properties.py` | @given (6 tests) | N/A | 6 properties | N (implicit via composite strategy) | No explicit `assume()` calls — inputs are shaped by composite strategies. Acceptable since the `markdown_document` composite ensures well-formed documents. HIGH concern: no explicit `assume()` means pathological inputs (empty doc, docs with no headings) are exercised but not explicitly skipped. |
| `test_iw_next_id_atomicity_properties.py` | RuleBasedStateMachine (placeholder) | 0 | 0 (placeholder) | N/A | **CRITICAL — test body is empty placeholder**. `test_concurrent_allocate_next_id_no_duplicates` has no assertions, no `ThreadPoolExecutor`, no `allocate_next_id` calls. Passes trivially with 10 examples. Does not use the real testcontainer `db_session` — uses the `MagicMock` from `tests/unit/conftest.py` (see finding CR-3 below). The invariant "no duplicate (prefix, suffix) across concurrent allocations" is **never tested**. |

### Named invariant coverage (work_item_lifecycle)

| Design invariant | Has assertion? | Notes |
|-----------------|----------------|-------|
| 1. No transition out of `merged` | ❌ NO | Comment only: `"""A WorkItem in a terminal state never transitions to any other state."""` — no `assert` |
| 2. `fix_cycle_count ≤ MAX_FIX_CYCLE` | ✅ YES | `assert self.item.fix_cycle_count <= self.item.MAX_FIX_CYCLE` |
| 3. Terminal items not re-claimable | ❌ NO | Comment only: `"""A work item in a terminal state is never re-claimable."""` — no `assert` |
| 4. `current_step_index` monotonic | ✅ YES | `assert self.item._step_history[i] >= self.item._step_history[i - 1]` |

Missing ≥2 named assertions = **CRITICAL** per review checklist.

---

## 4. Wall-clock budget

| Profile | Evidence file (s) | Observed (s) | Budget | Result |
|---------|-------------------|-------------|--------|--------|
| ci | ~1.5s total | 0.60s (test run) | <30s | ✅ PASS |
| dev | ~3.8s total | ~10.7s (all 3 modules with stats) | N/A | ✅ Informational |

Evidence file exists with real numbers (not placeholders). ci total <30s budget — ✅.

---

## 5. End-to-end exercise

```bash
make test-properties          # 18 passed, 1 skipped in 0.60s — ✅ exit 0
IW_HYPOTHESIS_PROFILE=dev …  # confirmed 200 examples vs ci's 20 — ✅ profile works
```

Dev profile statistics: `WorkItemSM.TestCase` reports 20 examples (ci) → confirmed `derandomize=True` in ci, `dev` profile uses default seed with 200 examples.

---

## 6. batch_manager.py pure-refactor verification

`orch/daemon/batch_manager.py` was **NOT modified** in this CR. `git diff origin/main..HEAD -- orch/daemon/batch_manager.py` returns nothing. ✅ No change.

The `compute_batch_status` helper lives in `test_batch_lifecycle_properties.py` (the test file itself) — it is not extracted from `batch_manager.py`. This means the batch-lifecycle property tests validate a *reimplementation* of the batch status logic, not the actual production code. This is a HIGH concern: if `batch_manager.py`'s real logic differs from the reimplementation, the property tests provide no coverage of the actual code path.

---

## 7. Doc + skill + plan consistency

| Location | Check | Result |
|----------|-------|--------|
| Strategy doc §3 | New "Property-based tests" sub-section with 5 modules + 3 profiles + env-var selector | ✅ PASS |
| Strategy doc §5 | 2 new rows (ci profile in `make test-unit`; deep profile on-demand) | ✅ PASS |
| Strategy doc §9 | Row "Property-based tests" flipped to ✅ with CR-00060 | ✅ PASS |
| `tests/CLAUDE.md` | New "Property tests" sub-section | ✅ PASS |
| `skills/iw-ai-core-testing/SKILL.md` | Property-based tests sub-section in §4 | ✅ PASS |
| `.claude/skills/iw-ai-core-testing/SKILL.md` | Byte-identical to master | ✅ PASS |
| TESTS_ENHANCEMENT.md §6 item 2.2 | `DONE — CR-00060 (2026-05-18)` | ✅ PASS |
| TESTS_ENHANCEMENT.md §11 | Dated changelog entry with 5 modules + 3 profiles + 2 Makefile targets + wall-clock | ✅ PASS |

---

## 8. Scope-creep audit

CR-00060's Impacted Paths per the design:
- `pyproject.toml` ✅ (changed — hypothesis dep + config + marker)
- `uv.lock` ✅ (changed — regenerated)
- `.gitignore` ✅ (not in diff but confirmed `.hypothesis/` entry exists in file)
- `Makefile` ✅ (changed — test-properties targets added)
- `tests/unit/properties/**` ✅ (all 5 modules + conftest + __init__ exist)
- `tests/unit/test_hypothesis_setup.py` ✅ (exists in worktree)
- `docs/IW_AI_Core_Testing_Strategy.md` ✅ (changed)
- `tests/CLAUDE.md` ✅ (not in diff vs origin/main — pre-existing in worktree)
- `skills/iw-ai-core-testing/**` ✅ (not in diff vs origin/main — pre-existing)
- `.claude/skills/iw-ai-core-testing/**` ✅ (not in diff vs origin/main — pre-existing)
- `ai-dev/work/TESTS_ENHANCEMENT.md` ✅ (changed)
- `orch/daemon/batch_manager.py` ✅ (NOT changed — confirmed clean)

**Scope**: Only CR-00060 design files affected. No production code under `orch/`, `dashboard/`, or `executor/` changed. No migrations. No new daemon QV gates in `skills/iw-workflow/SKILL.md`.

---

## 9. RED-first contract integrity

`tests/unit/test_hypothesis_setup.py` is in `files_changed` (exists in the worktree).

**CRITICAL**: The S01 report states: *"The RED-first guard was already GREEN when examined. The TDD cycle was completed by the prior S01 run."*

Per the design's TDD contract: the RED-first test **must fail** before the implementation is added. The S01 agent did not perform a RED run — it found the test already green. The `tdd_red_evidence` field in S01's contract quotes `"n/a"` (not a real failure line). This is a **CRITICAL TDD contract violation**: the RED-first step was skipped.

---

## Findings

### CRITICAL

**[CR-1] `test_concurrent_allocate_next_id_no_duplicates` — empty body, no assertions, no ThreadPoolExecutor**

**File**: `tests/unit/properties/test_iw_next_id_atomicity_properties.py`, lines 50–59

**Description**: The test body is:
```python
def test_concurrent_allocate_next_id_no_duplicates(...) -> None:
    # This uses the session from the active testcontainer fixture.
    # We access it by name so pytest resolves it from the integration conftest.
    # Placeholder — the actual implementation needs rethinking
```
No assertion. No call to `allocate_next_id`. No `ThreadPoolExecutor`. The test passes with 10 examples because a function that does nothing always succeeds. The invariant "no duplicate (prefix, suffix) across concurrent `allocate_next_id` calls" is **never tested**.

This is the most dangerous finding: the test *appears* to be a working atomicity test but is in fact a vacuous pass.

**[CR-2] `pytest_plugins` missing from `tests/unit/properties/conftest.py`**

**File**: `tests/unit/properties/conftest.py`

**Description**: The design doc (CR-00060_CR_Design.md line 89) explicitly requires:
> "The DB-backed property test conftest pulls in the testcontainer fixture explicitly via `pytest_plugins = ["tests.integration.conftest"]`"

This line is absent. As a result, `tests/unit/properties/` inherits `db_session` from `tests/unit/conftest.py` (a `MagicMock`) rather than from `tests/integration/conftest.py` (the real testcontainer session). Even if the placeholder test body were implemented with actual `allocate_next_id` calls, it would call a `MagicMock`, not the real database.

**[CR-3] TDD RED-first contract violated — `tdd_red_evidence` is `"n/a"`**

**File**: S01's result contract (implicit from report text)

**Description**: The design requires the RED-first guard to be written *before* hypothesis is installed, run, and observed to fail. The S01 report explicitly states the test was "already GREEN when examined." The `tdd_red_evidence` field does not contain a real failure line. This is a mandatory pre-condition for a behavioural step — skipping it means the TDD discipline was not followed.

**[CR-4] `no_transition_from_terminal` invariant has no assertion**

**File**: `tests/unit/properties/test_work_item_lifecycle_properties.py`, lines 105–107

**Description**: The docstring says "A WorkItem in a terminal state never transitions to any other state" but the invariant method body is empty (just the docstring). This means the core invariant the state machine is supposed to prove is silently assumed rather than asserted. The design requires this invariant (named invariant #1 in "Desired Behavior"). 2 of the 4 named invariants have no assertions — exceeds the "missing ≥2 = CRITICAL" threshold.

### HIGH

**[HIGH-1] `batch_status` semantics do not match design property names**

**File**: `tests/unit/properties/test_batch_lifecycle_properties.py`

**Description**: `compute_batch_status` returns `BatchStatus.executing` when the design's P2 says "held"; returns `BatchStatus.completed_with_errors` when P4 says "failed"; returns `BatchStatus.executing` when P5 says "in_progress". The implementation is internally consistent (the tests assert correctly against the code's behavior) but the property names in the test file do not match the design doc's named properties. If the real `batch_manager.py` logic uses the same values, the test is fine. If it uses different semantics, the tests don't cover the real code.

Additionally: `compute_batch_status` is **reimplemented in the test file** rather than imported from `orch/daemon/batch_manager.py`. The property tests validate a reimplementation, not the actual production code path. Any divergence between the reimplementation and `batch_manager.py`'s real logic is untested.

**[HIGH-2] `terminal_state_correct` invariant is a duplicate cap assertion**

**File**: `tests/unit/properties/test_fix_cycle_cap_properties.py`, lines 49–53

**Description**: `terminal_state_correct` asserts `self.max_observed_count <= _DEFAULT_FIX_CYCLE_MAX`. This is **identical** to what `cycle_count_within_cap` asserts (line 43). The design's fix-cycle invariant is: "cycle count never exceeds the configured cap regardless of any pass/fail interleaving; the step terminates in `failed` (not `in_progress`) exactly when count hits the cap and the latest record was a fail." There is no assertion that the step is `failed` at cap — only that the count never exceeds the cap.

**[HIGH-3] No explicit `assume()` in doc_diff round-trip tests**

**File**: `tests/unit/properties/test_doc_diff_round_trip_properties.py`

**Description**: While the composite `markdown_document` strategy shapes inputs to be well-formed, no explicit `assume()` call is present. The design requires "at least one `assume()` call to skip pathological inputs." Without explicit `assume()` calls, it's unclear whether degenerate inputs (empty strings, docs with no headings) are intentionally skipped or accidentally passed. Given the composite strategy mitigates this, rated HIGH rather than CRITICAL.

### Notes

- `make lint` ✅ All checks passed
- `make format-check` ✅ 755 files already formatted
- Hypothesis version 6.152.7 ✅ (≥6.100)
- ci wall-clock ~0.60s ✅ (well under 30s budget)
- Dev profile shows 200 examples vs ci's 20 ✅ (profile selection confirmed working)
- Skills are byte-identical ✅
- Docs updated ✅
- `.gitignore` has `.hypothesis/` ✅ (not in diff vs origin/main — pre-existing in worktree)
- `batch_manager.py` was NOT modified ✅
- Scope is clean — only CR-00060 design files + property test infrastructure files touched ✅

---

## Summary

The implementation is **structurally complete** (all 5 modules exist, configuration is correct, profiles work, docs are updated, wall-clock is well within budget), but it has **one severe quality flaw**: the central test of this CR — the `allocate_next_id` atomicity test — is a **vacuous placeholder**. It passes not because the invariant holds but because it asserts nothing. This is exactly the failure mode this CR was designed to prevent. The missing `pytest_plugins` means even a proper implementation of the test body would not reach the real testcontainer DB.

The work-item lifecycle module's two comment-only invariants (no transition from merged, no re-claim of terminal) and the TDD RED-first contract violation round out the critical findings.

---

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "CR-00060",
  "reviewed_agent": "backend-impl",
  "verdict": "NEEDS_FIX",
  "mandatory_fix_count": 4,
  "findings": [
    {
      "severity": "CRITICAL",
      "file": "tests/unit/properties/test_iw_next_id_atomicity_properties.py",
      "line": "50-59",
      "description": "test_concurrent_allocate_next_id_no_duplicates has an empty body (placeholder comment only). No assertion, no allocate_next_id call, no ThreadPoolExecutor. Passes vacuously with 10 examples. The atomicity invariant (no duplicate prefix,suffix across concurrent calls) is never tested.",
      "suggested_fix": "Implement the test body with ThreadPoolExecutor driving N parallel allocate_next_id(prefix) calls; assert all returned suffixes are unique within the prefix."
    },
    {
      "severity": "CRITICAL",
      "file": "tests/unit/properties/conftest.py",
      "line": "n/a",
      "description": "pytest_plugins = ['tests.integration.conftest'] is absent. Without it, db_session in tests/unit/properties/ resolves to the MagicMock from tests/unit/conftest.py, not the real testcontainer session. Even a correctly implemented next-id test body would call a mock, not the real DB.",
      "suggested_fix": "Add pytest_plugins = ['tests.integration.conftest'] to tests/unit/properties/conftest.py. This overrides the MagicMock db_session from tests/unit/conftest.py with the real testcontainer session for all tests in the properties directory."
    },
    {
      "severity": "CRITICAL",
      "file": "tests/unit/test_hypothesis_setup.py / S01 contract",
      "line": "n/a",
      "description": "tdd_red_evidence is 'n/a'. The RED-first guard test (test_hypothesis_setup.py) was already GREEN when examined — the RED step was not performed. Per CR-00060's TDD contract: the test must be written, run, and confirmed to fail BEFORE hypothesis is installed. The test was not written to fail; it was found already passing.",
      "suggested_fix": "To satisfy the TDD contract, the S01 agent should have: (1) temporarily removed hypothesis from pyproject.toml, (2) run test_hypothesis_setup.py and confirmed it failed (ImportError for missing hypothesis), (3) recorded that failure in tdd_red_evidence, (4) then re-added hypothesis. Since this step cannot be retroactively performed, the finding stands as a process violation."
    },
    {
      "severity": "CRITICAL",
      "file": "tests/unit/properties/test_work_item_lifecycle_properties.py",
      "line": "105-107",
      "description": "Invariant 'no_transition_from_terminal' has no assertion body — only a docstring. Also invariant 'terminal_items_not_reclaimable' (lines 118-120) has no assertion. The design names 4 invariants; 2 have no assertions. This exceeds the 'missing ≥2 = CRITICAL' threshold.",
      "suggested_fix": "Add assert statements to both invariants. For no_transition_from_terminal: assert that after any rule fires, status is still terminal (or assert that _is_terminal(status) at end of any state). For terminal_items_not_reclaimable: assert that _is_terminal(self.item.status) implies self.item.status cannot change after any rule."
    },
    {
      "severity": "HIGH",
      "file": "tests/unit/properties/test_batch_lifecycle_properties.py",
      "line": "56-81",
      "description": "compute_batch_status is reimplemented in the test file, not imported from orch/daemon/batch_manager.py. The property tests validate a reimplementation of batch status logic. Any divergence between this reimplementation and the actual batch_manager.py logic is untested. Additionally, the property P2/P4/P5 use BatchStatus values that do not match the design doc's named property semantics (executing instead of held/failed/in_progress).",
      "suggested_fix": "Either import compute_batch_status from batch_manager.py (if it exists or after extraction), or rename the test properties to match the actual enum values returned, and add a comment explaining the semantic mapping."
    },
    {
      "severity": "HIGH",
      "file": "tests/unit/properties/test_fix_cycle_cap_properties.py",
      "line": "49-53",
      "description": "Invariant 'terminal_state_correct' asserts max_observed_count <= cap, which is identical to what 'cycle_count_within_cap' asserts. The design's fix-cycle invariant requires an assertion that the step terminates in 'failed' (not 'in_progress') when cap is hit and the last event was a fail. This terminal-state behavior is not asserted.",
      "suggested_fix": "Add an assertion to terminal_state_correct (or a new invariant) that: when self.cycle_count == _DEFAULT_FIX_CYCLE_MAX and self.step_terminal == True, no further rules can change the state."
    },
    {
      "severity": "HIGH",
      "file": "tests/unit/properties/test_doc_diff_round_trip_properties.py",
      "line": "n/a",
      "description": "No explicit assume() calls in any of the 6 @given tests. While the composite markdown_document strategy shapes inputs to be well-formed (avoiding the worst degenerate cases), there are no explicit assume() calls as required by the design's invariant for pathological-input skipping.",
      "suggested_fix": "Add at least one assume() call in the round-trip tests to explicitly skip a known pathological case (e.g., assume(len(doc) > 0) or assume(len(sections) > 0))."
    }
  ],
  "notes": "The implementation infrastructure (hypothesis dep, profiles, Makefile targets, doc updates, skill sync, wall-clock budget) is correct and complete. The critical failures are: (1) the central next-id atomicity test has no body — it is a vacuous pass; (2) pytest_plugins is missing so the db_session would be a MagicMock even if the test were implemented; (3) the TDD RED-first contract was not followed (test was found green, not red); (4) 2 of 4 named work-item invariants are comment-only with no assertions. The S01 agent report acknowledges the next-id test is a placeholder and attributes it to a fixture-shadowing issue, which is accurate."
}
```