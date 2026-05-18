# CR-00060_S01_Backend_prompt

**Work Item**: CR-00060 -- Hypothesis property-based tests on the state machines (P2-CR-B)
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute Docker commands that change container/volume/network state. Allowed: the testcontainer fixture from `tests/integration/conftest.py` that `test_iw_next_id_atomicity_properties.py` pulls in via `pytest_plugins` — that path is OK (Ryuk teardown). No `docker compose up/down`, no `docker rm/stop`, no `docker volume *`.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This CR adds **no** migrations. If your work seems to need one, you have gone outside scope — stop and raise a blocker.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- **Runtime step state**: `uv run iw item-status CR-00060 --json`.
- `ai-dev/active/CR-00060/CR-00060_CR_Design.md` -- **source of truth**. Read FIRST. Notes "Desired Behavior", "Acceptance Criteria" (AC1–AC10), and "Notes" — especially the `compute_batch_status` extraction caveat and the `derandomize=True` requirement on the `ci` profile.
- `ai-dev/active/CR-00060/CR-00060_Functional.md` — human-facing summary.
- `iw-doc-plan/main/iw-doc-plan/tests/unit/properties/` — InnoForge precedent for the layout (adapt, don't reinvent).
- `pyproject.toml` — `[dependency-groups] dev` (lines 76–104), `[tool.pytest.ini_options]` markers list (around line 152), `[tool.deptry]` around line 213 (your `[tool.hypothesis]` insertion point comes after).
- `Makefile` — `.PHONY` lines 5–13; `make test-unit` recipe (you do NOT modify it — the conftest under `tests/unit/properties/` handles the rest); `diff-coverage` block lines 110–141 as the model for "self-contained slow target" comment style.
- `tests/integration/conftest.py` — testcontainer fixtures (`pg_container`, `db_engine`, `db_session`) the next-id property test pulls in via `pytest_plugins`.
- `tests/unit/conftest.py` — existing `pytest_plugins = ["tests.integration.conftest"]` pattern around lines 38–42 (the model to follow for the new properties conftest).
- `orch/db/models.py` — `WorkItem`, `Batch`, `FixCycle` shapes; `allocate_next_id()` around line 2151.
- `orch/daemon/batch_manager.py` — read FIRST to determine whether batch-status computation can be tested as a pure function or needs a helper extraction.
- `orch/daemon/fix_cycle.py` — `MAX_FIX_CYCLE` constant + the cap-enforcement logic the fix-cycle property test exercises.
- `orch/doc_diff.py`, `orch/doc_sections.py` — round-trip target.
- `docs/IW_AI_Core_Testing_Strategy.md` — §3 (test infrastructure), §5 (gate table), §9 (known gaps). Update all three.
- `tests/CLAUDE.md` — add a "Property tests" sub-section.
- `skills/iw-ai-core-testing/SKILL.md` — add a property-tests sub-section (and sync with `iw sync-skills --force iw-ai-core-testing`).
- `ai-dev/work/TESTS_ENHANCEMENT.md` — §6 item 2.2 (flip to DONE) + §11 (new changelog entry).
- `CLAUDE.md` for project-wide rules.

## Output Files

- `ai-dev/active/CR-00060/reports/CR-00060_S01_Backend_report.md`
- `ai-dev/active/CR-00060/evidences/pre/cr-00060-profile-wall-clock.txt` (per-profile wall-clock per file)
- `tests/unit/test_hypothesis_setup.py` (RED-first guard)
- `tests/unit/properties/__init__.py`
- `tests/unit/properties/conftest.py`
- `tests/unit/properties/test_work_item_lifecycle_properties.py`
- `tests/unit/properties/test_batch_lifecycle_properties.py`
- `tests/unit/properties/test_fix_cycle_cap_properties.py`
- `tests/unit/properties/test_doc_diff_round_trip_properties.py`
- `tests/unit/properties/test_iw_next_id_atomicity_properties.py`
- `pyproject.toml`, `uv.lock`, `.gitignore`, `Makefile` — patched
- `docs/IW_AI_Core_Testing_Strategy.md`, `tests/CLAUDE.md` — patched
- `skills/iw-ai-core-testing/SKILL.md` + `.claude/skills/iw-ai-core-testing/SKILL.md` — patched + synced
- `ai-dev/work/TESTS_ENHANCEMENT.md` — patched §6 + §11
- `orch/daemon/batch_manager.py` — ONLY if a pure helper extraction is required (see Notes in the design)

## Context

You are implementing **CR-00060 — Hypothesis property-based tests (P2-CR-B)**, Phase 2's second CR. **Read the design doc first.** "Desired Behavior" lists the five property modules and their named invariants — those names and that list are non-negotiable; deviation = scope drift. ACs 1–10 are mandatory.

## Requirements

### 0. RED — write the guard test FIRST

Create `tests/unit/test_hypothesis_setup.py`:

```python
"""Pins the Hypothesis configuration so future edits don't silently drift.

Written RED-first for CR-00060 (P2-CR-B): fails before hypothesis is installed
AND before the properties dir/conftest/marker exist; passes after S01 lands them.
"""
import importlib
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_hypothesis_is_importable():
    """The dev dep must resolve."""
    importlib.import_module("hypothesis")  # raises ImportError if missing


def test_pyproject_has_hypothesis_config_and_marker():
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    assert "hypothesis" in data["tool"], "[tool.hypothesis] block missing"
    assert "database_file" in data["tool"]["hypothesis"]
    markers = data["tool"]["pytest"]["ini_options"]["markers"]
    assert any("properties" in m for m in markers), (
        "`properties` marker must be registered in [tool.pytest.ini_options].markers"
    )


def test_properties_conftest_registers_three_profiles():
    conftest = REPO_ROOT / "tests" / "unit" / "properties" / "conftest.py"
    assert conftest.exists(), "tests/unit/properties/conftest.py missing"
    text = conftest.read_text()
    for profile in ("ci", "dev", "deep"):
        assert f'register_profile("{profile}"' in text, (
            f"profile {profile!r} must be registered in tests/unit/properties/conftest.py"
        )
```

Run:

```bash
uv run pytest tests/unit/test_hypothesis_setup.py -v
```

All three tests MUST fail (the first with `ImportError`/`ModuleNotFoundError` — acceptable RED here since the dep is genuinely absent; the second and third with `AssertionError`). Capture the test ids + failure lines for `tdd_red_evidence`.

### 1. Install hypothesis + config

- Add `hypothesis>=6.100,<7` to `[dependency-groups] dev`. Match the alphabetical ordering style.
- `uv lock`.
- Verify: `uv run python -c "import hypothesis; print(hypothesis.__version__)"` → 6.100+.
- Add to `pyproject.toml` after `[tool.deptry]`:

```toml

# Hypothesis property-based testing (CR-00060, P2-CR-B)
# Profile selection: set IW_HYPOTHESIS_PROFILE env var (ci | dev | deep).
# Defaults to `ci` when unset (merge-gate path).
[tool.hypothesis]
database_file = ".hypothesis/examples"
```

- Add `.hypothesis/` to `.gitignore` (place near the other gitignored cache dirs).
- Register the `properties` marker in `[tool.pytest.ini_options].markers`:

```
"properties: Hypothesis property-based tests (CR-00060, P2-CR-B); auto-applied to tests/unit/properties/",
```

### 2. Create the property layout

Create `tests/unit/properties/__init__.py` (empty).

Create `tests/unit/properties/conftest.py`:

```python
"""Hypothesis profile registration + marker auto-apply for tests/unit/properties/.

Three profiles: ci (merge-gate, fast, derandomized), dev (local default), deep (on-demand).
Profile is selected via $IW_HYPOTHESIS_PROFILE, defaulting to "ci".
"""
import os

import pytest
from hypothesis import HealthCheck, settings

# Pull in the testcontainer fixtures for the DB-backed property test in this dir.
pytest_plugins = ["tests.integration.conftest"]

settings.register_profile(
    "ci",
    max_examples=20,
    deadline=2000,
    derandomize=True,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.register_profile(
    "dev",
    max_examples=200,
    deadline=5000,
)
settings.register_profile(
    "deep",
    max_examples=1000,
    deadline=None,
    derandomize=False,
)
settings.load_profile(os.environ.get("IW_HYPOTHESIS_PROFILE", "ci"))


def pytest_collection_modifyitems(config, items):  # noqa: ARG001
    """Auto-apply the `properties` marker to every test in this dir."""
    for item in items:
        if "/tests/unit/properties/" in str(item.fspath):
            item.add_marker(pytest.mark.properties)
```

### 3. Write the five property modules

Each module is independent; design doc "Desired Behavior" names the invariants per module. Quick recipe per module:

- **`test_work_item_lifecycle_properties.py`** — `RuleBasedStateMachine` modelling a single `WorkItem`. Rules: `register`, `approve`, `claim`, `complete_step`, `fail_step`, `merge`, `cancel`. Bundles: `items` (use Hypothesis's `Bundle` to track allocated IDs). Invariants (each `@invariant` returns silently or raises):
  1. No transition out of `merged`.
  2. `fix_cycle_count ≤ MAX_FIX_CYCLE`.
  3. Terminal items (`merged`, `failed`, `cancelled`) cannot be re-claimed.
  4. `current_step_index` monotonic within a single run.

  Model the `WorkItem` as a pure Python `dataclass` or `dict`; do NOT touch the DB (this property test is logic-only).

- **`test_batch_lifecycle_properties.py`** — pure-function via `@given(lists(tuples(integers(min_value=1), sampled_from(list(ItemStatus)))))`. Assert the 5 properties from the design. If `compute_batch_status` doesn't exist yet, extract it (see Notes below).

- **`test_fix_cycle_cap_properties.py`** — `RuleBasedStateMachine` with `@rule(record_pass)` and `@rule(record_fail)`. Invariant: cycle count never exceeds cap; termination state correct.

- **`test_doc_diff_round_trip_properties.py`** — two `@given` properties: `parse(serialise(d)) == d` (start from a `composite()` strategy that builds a doc structure) and `serialise(parse(s)) == s` (start from a `from_regex()`-shaped text strategy). Use `assume()` to skip pathological inputs (empty docs, all-whitespace, etc.) rather than silently passing.

- **`test_iw_next_id_atomicity_properties.py`** — uses `db_session` fixture. `RuleBasedStateMachine` with N "callers" (use `concurrent.futures.ThreadPoolExecutor` inside a rule to run K parallel `allocate_next_id(prefix)` calls). Bundle: `allocated_ids`. Invariant: `len(set(allocated_ids)) == len(allocated_ids)` (no duplicate (prefix, suffix) pair). Keep K small (≤8) — the test must finish quickly under the `ci` profile.

### 4. The pure-helper extraction (only if needed)

Read `orch/daemon/batch_manager.py` first. If `compute_batch_status(items)` already exists as a pure function on `(item_id, item_status)` tuples (or list of `WorkItem` rows), import it directly and don't touch `batch_manager.py`.

Otherwise: extract a minimal pure helper. Move only the classification logic, NOT the SQL that loads the items. Route the existing call-site through the new helper. The existing tests (`tests/integration/test_cli_batches.py` and any `test_batch_manager_*.py`) must pass identically before and after — confirm by running them locally.

If the extraction is too entangled to do cleanly within this step, **raise a blocker** and file `P2-CR-B-followup-batch-helper-extraction`. Do not ship a half-extraction.

### 5. Two Makefile targets

After the `diff-coverage` block:

```make
# Property-based tests (CR-00060, P2-CR-B) — runs tests/unit/properties/
# at the selected Hypothesis profile (ci | dev | deep).
# The `ci` profile runs as part of `make test-unit` automatically
# (the properties conftest defaults to ci); this target is just the
# explicit invocation.
test-properties:
	IW_HYPOTHESIS_PROFILE=ci uv run pytest tests/unit/properties/ -v --no-cov

# Deep property-test sweep — on-demand only, NOT a CI gate yet.
# Runs each @given/RuleBasedStateMachine with max_examples=1000 and
# full shrinking. Use to find bugs the ci profile misses (e.g. before
# a release, after a refactor of any of the 5 state-machine targets).
test-properties-deep:
	IW_HYPOTHESIS_PROFILE=deep uv run pytest tests/unit/properties/ -v --no-cov
```

Add `test-properties test-properties-deep` to the `.PHONY` line.

### 6. Run the tests + capture wall-clock

```bash
time make test-properties 2>&1 | tee evidences/pre/cr-00060-ci-run.log
time IW_HYPOTHESIS_PROFILE=dev uv run pytest tests/unit/properties/ -v --no-cov 2>&1 | tee evidences/pre/cr-00060-dev-run.log
```

Both MUST exit 0. Capture into `ai-dev/active/CR-00060/evidences/pre/cr-00060-profile-wall-clock.txt`:

```
CR-00060 — Hypothesis profile wall-clock (P2-CR-B)
Date: <YYYY-MM-DD>
Machine: <one-liner — e.g. WSL2 on Linux 6.8.0, 16-core>

| Profile | Total wall-clock | Per-module breakdown                        |
|---------|------------------|---------------------------------------------|
| ci      | <m:ss>           | work_item: <s>; batch: <s>; fix_cycle: <s>; doc_diff: <s>; next_id: <s> |
| dev     | <m:ss>           | (same shape, larger numbers)                |

Notes:
- ci profile total MUST be <30s (gates make test-unit) — currently <m:ss>
- dev profile total is informational
- deep profile NOT measured here (S03 measures it as part of cross-agent review)
```

If `ci` total wall-clock ≥30s, treat as a blocker — `make test-unit` would balloon. Trim `max_examples` in the `ci` profile (e.g. 20 → 10) OR identify the offending property and use `assume()` to narrow its input.

### 7. Re-run RED → GREEN

```bash
uv run pytest tests/unit/test_hypothesis_setup.py -v
```

All three tests pass GREEN.

### 8. Update docs + skill + plan

- `docs/IW_AI_Core_Testing_Strategy.md` §3: add "Property-based tests" sub-section (5 modules; 3 profiles; env-var selector; `properties` marker auto-applied).
- `docs/IW_AI_Core_Testing_Strategy.md` §5 gate table: 2 new rows:
  - `Property tests (ci profile) | hypothesis | included in make test-unit via tests/unit/properties/ conftest default | --strict-markers via pyproject.toml; deterministic via derandomize=True`
  - `Property tests (deep profile) | hypothesis | NOT in CI; on-demand | make test-properties-deep`
- `docs/IW_AI_Core_Testing_Strategy.md` §9 row "Property-based tests": `❌ (2.2)` → `✅ (CR-00060, 2026-MM-DD) — five modules under tests/unit/properties/; ci profile in make test-unit; deep profile on-demand`.
- `tests/CLAUDE.md`: add "Property tests" sub-section (when to add a new property test; how to choose between RuleBasedStateMachine and `@given`; use `assume()` for shaping not silent-pass; the marker auto-applies via conftest hook).
- `skills/iw-ai-core-testing/SKILL.md`: add a property-tests sub-section in conventions.
- Run `iw sync-skills --force iw-ai-core-testing` to mirror to `.claude/skills/iw-ai-core-testing/SKILL.md`.
- `ai-dev/work/TESTS_ENHANCEMENT.md` §6 item 2.2: `TODO` → `DONE — CR-00060 (2026-MM-DD)`.
- `ai-dev/work/TESTS_ENHANCEMENT.md` §11: new dated entry listing the 5 modules, 3 profiles, 2 Makefile targets, marker, wall-clock measurement (ci/dev), notes on any pure-helper extraction.

## Verification

### Pre-flight (mandatory)

```bash
make format       # auto-fixes drift
make typecheck    # zero errors on touched files
make lint         # zero errors
```

## Test Verification (NON-NEGOTIABLE)

Targeted only:

1. `uv run pytest tests/unit/test_hypothesis_setup.py -v` → 3 passes.
2. `make test-properties` → exits 0.
3. `IW_HYPOTHESIS_PROFILE=dev uv run pytest tests/unit/properties/ -v --no-cov` → exits 0.
4. `uv run pytest tests/unit/properties/ --collect-only -m properties` → lists all 5 files' tests.
5. `uv run pytest tests/unit/properties/ --collect-only -m "not properties"` → 0 results (auto-apply hook works).

Do NOT run `make check` / full suites — S04–S11 own those.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "CR-00060",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "pyproject.toml",
    "uv.lock",
    ".gitignore",
    "Makefile",
    "tests/unit/test_hypothesis_setup.py",
    "tests/unit/properties/__init__.py",
    "tests/unit/properties/conftest.py",
    "tests/unit/properties/test_work_item_lifecycle_properties.py",
    "tests/unit/properties/test_batch_lifecycle_properties.py",
    "tests/unit/properties/test_fix_cycle_cap_properties.py",
    "tests/unit/properties/test_doc_diff_round_trip_properties.py",
    "tests/unit/properties/test_iw_next_id_atomicity_properties.py",
    "docs/IW_AI_Core_Testing_Strategy.md",
    "tests/CLAUDE.md",
    "skills/iw-ai-core-testing/SKILL.md",
    ".claude/skills/iw-ai-core-testing/SKILL.md",
    "ai-dev/work/TESTS_ENHANCEMENT.md"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "test_hypothesis_setup.py 3/3 pass. make test-properties: <m:ss>. dev profile: <m:ss>. All 5 modules collect under -m properties; 0 stragglers under -m 'not properties'.",
  "tdd_red_evidence": "tests/unit/test_hypothesis_setup.py::test_hypothesis_is_importable FAILED (pre-patch): ModuleNotFoundError: No module named 'hypothesis'. Also test_pyproject_has_hypothesis_config_and_marker FAILED: KeyError: 'hypothesis'. Captured at ai-dev/active/CR-00060/evidences/pre/cr-00060-red-evidence.txt (optional).",
  "blockers": [],
  "notes": "Phase-2 2nd CR. 5 property modules + 3 profiles. ci wall-clock <m:ss>, dev <m:ss>. batch_manager.py extraction: <NEEDED — moved compute_batch_status to a pure helper; existing tests pass identically | NOT NEEDED — helper already pure>. Surprising findings during S01: <none | one-liner about any property that initially failed and informed an implementation/test tightening>."
}
```

- `tdd_red_evidence`: MUST quote real test ids + failure lines. Do not write `"n/a"`.
- `completion_status`:
  - `complete` if all 8 deliverables done; ci wall-clock <30s; all property tests pass under both ci and dev profiles.
  - `partial` if ≤1 of the 5 property modules has an invariant that doesn't hold yet (NOT due to a real bug, but because the invariant statement needs refinement) — file a follow-up and leave that module's failing property as `@pytest.mark.xfail(strict=True)` with a tracking comment.
  - `blocked` if (a) hypothesis won't install, (b) the ci wall-clock can't be brought under 30s without removing a critical invariant, (c) the batch helper extraction is too entangled, (d) a property test finds a real production bug that's load-bearing for the suite (file as a separate incident, raise blocker).
