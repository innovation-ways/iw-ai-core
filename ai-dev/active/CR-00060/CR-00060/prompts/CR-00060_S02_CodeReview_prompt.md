# CR-00060_S02_CodeReview_prompt

**Work Item**: CR-00060 -- Hypothesis property-based tests on the state machines (P2-CR-B)
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

Standard policy. Allowed: testcontainer fixtures (the next-id property test uses `db_session`). No `docker compose` / `docker rm` / `docker volume *`.

## ⛔ Migrations: agents generate, daemon applies

This CR adds **no** migrations. Any migration in `files_changed` = CRITICAL.

## Input Files

- `uv run iw item-status CR-00060 --json` — runtime step state.
- `ai-dev/active/CR-00060/CR-00060_CR_Design.md` (source of truth; AC1–AC10)
- `ai-dev/active/CR-00060/reports/CR-00060_S01_Backend_report.md`
- `ai-dev/active/CR-00060/evidences/pre/cr-00060-profile-wall-clock.txt`
- All files in S01's `files_changed`
- `iw-doc-plan/main/iw-doc-plan/tests/unit/properties/` — InnoForge precedent

## Output Files

- `ai-dev/active/CR-00060/reports/CR-00060_S02_CodeReview_report.md`

## Context

You are reviewing S01's implementation of **CR-00060 — Hypothesis property-based tests (P2-CR-B)**. The biggest risks are: (1) property tests that look thorough but actually exercise a tiny portion of input space (e.g. `sampled_from([single_value])`, or every `@given` shrunk by overly-tight `assume()`); (2) `RuleBasedStateMachine` modules with rules but no `@invariant` — passing trivially; (3) the next-id atomicity test using a mocked engine instead of the real testcontainer (defeating the entire purpose); (4) `ci` profile wall-clock too slow for `make test-unit`; (5) silent behaviour change in `orch/daemon/batch_manager.py` if the pure-helper extraction is dirty.

## Pre-Review Lint Gate

```bash
make lint
make format-check
```

NEW violations = CRITICAL.

## Review Checklist

### 1. Dep + config + marker

- `hypothesis>=6.100,<7` in `[dependency-groups] dev`. Other version pin = HIGH.
- `uv run python -c "import hypothesis; print(hypothesis.__version__)"` prints 6.100+. Failure = CRITICAL.
- `[tool.hypothesis]` block present with `database_file = ".hypothesis/examples"`. Missing = CRITICAL.
- `.hypothesis/` in `.gitignore`. Missing = HIGH.
- `properties` marker registered in `[tool.pytest.ini_options].markers`. Missing = CRITICAL (`--strict-markers` would fail the suite).

### 2. Conftest correctness

Read `tests/unit/properties/conftest.py`:

- Three profiles registered with EXACT names `ci`, `dev`, `deep`. Wrong names = CRITICAL.
- `ci` has `derandomize=True` (merge-gate determinism). Missing = HIGH.
- `ci` has `max_examples=20` (or thereabouts; ≤50). `>100` = HIGH (will blow ci wall-clock).
- `dev` has `max_examples=200` (or thereabouts; 100–500).
- `deep` has `max_examples=1000` (or thereabouts; ≥500) and `derandomize=False` (or absent — default is False).
- `settings.load_profile()` honours `$IW_HYPOTHESIS_PROFILE` with default `"ci"`. Different default = CRITICAL (merge gate would run unintended profile).
- `pytest_plugins = ["tests.integration.conftest"]` line present (so the next-id test can use `db_session`). Missing = CRITICAL (next-id test will fail to collect).
- `pytest_collection_modifyitems` hook auto-applies `pytest.mark.properties` to every test under `tests/unit/properties/`. Missing = HIGH (marker is registered but never applied → `pytest -m properties` returns nothing).

Verify the hook actually fires:

```bash
uv run pytest tests/unit/properties/ --collect-only -m properties 2>&1 | grep -E "(::|<Function)" | head -20
uv run pytest tests/unit/properties/ --collect-only -m "not properties" 2>&1 | grep -E "(::|<Function)" | head -20
```

First should list tests; second should be empty (or only deselection messages). Any test under the dir not marked = HIGH.

### 3. Five property modules — invariants + content

For EACH of the 5 files (`test_{work_item_lifecycle,batch_lifecycle,fix_cycle_cap,doc_diff_round_trip,iw_next_id_atomicity}_properties.py`):

- File exists. Missing = CRITICAL (the design names them by name).
- At least one of: `@given`, `RuleBasedStateMachine` subclass with `@rule`. Both absent = CRITICAL (file is empty / not a property test).

For the `RuleBasedStateMachine` modules (work-item, fix-cycle, next-id):

- At least 1 `@invariant` decorator (the WHOLE POINT of state-machine tests). Missing = CRITICAL.
- At least 2 `@rule` decorators. Less = HIGH (no interesting state space explored).

For `test_work_item_lifecycle_properties.py`:

- Invariants asserted match the 4 named in the design's "Desired Behavior":
  1. No transition out of `merged`.
  2. `fix_cycle_count ≤ MAX_FIX_CYCLE`.
  3. Terminal items not re-claimable.
  4. `current_step_index` monotonic.
  - Missing ≥2 of these = CRITICAL. Missing 1 = HIGH.

For `test_batch_lifecycle_properties.py`:

- All 5 named properties present (deterministic; held precedence; completed-iff; failed-iff; in_progress otherwise). Missing ≥2 = CRITICAL. Missing 1 = HIGH.
- Uses `@given(lists(tuples(...)))` or similar non-degenerate strategy. `sampled_from([single_fixed_input])` = CRITICAL (no exploration).

For `test_fix_cycle_cap_properties.py`:

- `RuleBasedStateMachine` with `record_pass` + `record_fail` rules. Invariant: cycle never exceeds cap. Missing = CRITICAL.

For `test_doc_diff_round_trip_properties.py`:

- Two round-trip properties: `parse(serialise(d)) == d` and `serialise(parse(s)) == s`. One missing = HIGH.
- At least one `assume()` call to skip pathological inputs. Zero assume calls = HIGH (strategy too loose → silent pass on degenerate input).

For `test_iw_next_id_atomicity_properties.py`:

- Uses the `db_session` fixture (NOT `MagicMock`, NOT a fake engine). Mocked = CRITICAL (defeats the entire purpose).
- Uses `ThreadPoolExecutor` or similar to drive parallel `allocate_next_id` calls. Sequential calls only = HIGH (atomicity test that doesn't test concurrency).
- Invariant: no duplicate (prefix, suffix) across concurrent allocations. Missing = CRITICAL.

### 4. Wall-clock budget

Read `ai-dev/active/CR-00060/evidences/pre/cr-00060-profile-wall-clock.txt`:

- File exists. Missing = CRITICAL.
- All numeric cells are real values. Placeholders (TBD / —) = CRITICAL.
- `ci` total wall-clock <30s. ≥30s = HIGH. ≥60s = CRITICAL (will visibly slow `make test-unit`).

### 5. End-to-end exercise

```bash
# CI profile
make test-properties
# Dev profile (more examples)
IW_HYPOTHESIS_PROFILE=dev uv run pytest tests/unit/properties/ -v --no-cov 2>&1 | tail -20
# Show statistics to verify profile actually engages
IW_HYPOTHESIS_PROFILE=dev uv run pytest tests/unit/properties/test_work_item_lifecycle_properties.py --hypothesis-show-statistics 2>&1 | grep -iE "examples|run time" | head -10
```

- All exit 0. Failure = CRITICAL.
- The dev-profile statistics show a measurably higher example count than what `ci` would (typically order-of-magnitude). If the dev profile reports the same number of examples as `ci` (≈20), the profile selection isn't working = CRITICAL.

### 6. (If batch_manager.py edited) pure-refactor verification

If `orch/daemon/batch_manager.py` is in `files_changed`:

- The diff is purely a helper extraction (new pure function `compute_batch_status` extracted; original call-site delegates to it). NOT a behaviour change. Any new conditional / SQL change / status-mapping change = CRITICAL.
- Run existing batch tests:
  ```bash
  uv run pytest tests/integration/test_cli_batches.py tests/unit/daemon/ -v 2>&1 | tail -20
  ```
- Same number of passes/skips as before. Any new failure or new skip = CRITICAL.

### 7. Doc + skill + plan consistency

- Strategy doc §3: new "Property-based tests" sub-section names all 5 modules + 3 profiles + env-var selector. Missing any = HIGH.
- Strategy doc §5: 2 new rows (ci profile in `make test-unit`; deep profile on-demand). Missing = HIGH.
- Strategy doc §9 row "Property-based tests": flipped to ✅ with `CR-00060` named. Still ❌ = CRITICAL.
- `tests/CLAUDE.md`: new "Property tests" sub-section with conventions. Missing = HIGH.
- `skills/iw-ai-core-testing/SKILL.md` AND `.claude/skills/iw-ai-core-testing/SKILL.md`: BOTH updated; byte-identical (sync via `iw sync-skills --force iw-ai-core-testing`). Drift = HIGH.
- `ai-dev/work/TESTS_ENHANCEMENT.md` §6 item 2.2: `DONE — CR-00060`. Still `TODO` = CRITICAL.
- `ai-dev/work/TESTS_ENHANCEMENT.md` §11: new dated entry with 5 modules + 3 profiles + 2 Makefile targets + wall-clock. Missing/incomplete = HIGH.

### 8. Scope-creep audit

```bash
git diff --name-only origin/main..HEAD | sort
```

Allowed files only (`Impacted Paths` from design). Specifically forbidden:

- Any file under `orch/` (other than `orch/daemon/batch_manager.py` if needed). CRITICAL on violation.
- Any file under `dashboard/`, `executor/`. CRITICAL.
- Any Alembic migration. CRITICAL.
- New daemon QV gate in `skills/iw-workflow/SKILL.md` (this CR doesn't add `make test-properties` as a gate). CRITICAL.
- New GH workflow step. CRITICAL.
- Behavioural change in `batch_manager.py` (must be pure refactor). CRITICAL.

### 9. RED-first contract integrity

- `tests/unit/test_hypothesis_setup.py` in `files_changed`. Missing = CRITICAL.
- `tdd_red_evidence` in S01's contract quotes ≥1 real test id from this file + a real failure line (ImportError/ModuleNotFoundError/AssertionError/KeyError are all acceptable RED here). `"n/a"` = CRITICAL.

## Review Report Format

Sections: **Verdict** (APPROVED / NEEDS_FIX / BLOCKED), **Per-checklist findings** (1–9 above), **Per-module invariant table** (one row per of the 5 modules: name | RuleBasedStateMachine or @given | #invariants | #rules or #properties | uses `assume()` Y/N | concerns), **Wall-clock audit** (ci vs dev numbers from the evidence file + your assessment of whether ci is sane for merge-gate inclusion), **Scope diff** (full file-list with PASS/FAIL annotations).

Finish with the JSON contract block (CR-00046 shape).
