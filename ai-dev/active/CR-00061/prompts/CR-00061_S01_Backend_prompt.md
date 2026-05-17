# CR-00061_S01_Backend_prompt

**Work Item**: CR-00061 -- Flaky test quarantine workflow (P2-CR-C)
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

Standard policy. The two new make targets re-use the existing testcontainer fixtures; no `docker compose up/down`, no `docker rm/stop`, no `docker volume *`.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This CR adds **no** migrations.

## Input Files

- **Runtime step state**: `uv run iw item-status CR-00061 --json`.
- `ai-dev/active/CR-00061/CR-00061_CR_Design.md` -- **source of truth**. Read FIRST. ACs 1–9. Especially: the 5-rule list (rules 1–5 in "Desired Behavior" / Notes); the `--reruns 1` requirement; the addopts exact form `-m 'not browser and not quarantine'`.
- `ai-dev/active/CR-00061/CR-00061_Functional.md`
- `pyproject.toml` — `[dependency-groups] dev` (lines 76–104), `[tool.pytest.ini_options]` (around lines 145–165): markers list at lines 158–164, addopts at line 156.
- `Makefile` — `.PHONY` lines 5–13; existing `make smoke` recipe at lines 107–108 for the model of "marker-filtered pytest invocation".
- `tests/CLAUDE.md` — existing "Quarantine policy" sub-section (added by CR-00055 for `order_dependent`); your new "Quarantine workflow" sub-section sits alongside it.
- `docs/IW_AI_Core_Testing_Strategy.md` — §3, §5 gate table, §9 row "Flaky/quarantine workflow".
- `skills/iw-ai-core-testing/SKILL.md` — add quarantine sub-section.
- `skills/iw-new-incident/SKILL.md` — the incident-filing flow your new rule references.
- `ai-dev/work/TESTS_ENHANCEMENT.md` — §6 item 2.3 + §11.
- `tests/unit/test_smoke.py` — the test file you'll *temporarily* mark with `@pytest.mark.quarantine` for the smoke test in deliverable (h)/(i) (REVERT before completing).
- `CLAUDE.md` for project-wide rules.

## Output Files

- `ai-dev/active/CR-00061/reports/CR-00061_S01_Backend_report.md` -- must include BOTH SMOKE TEST captures (marker deselection + aggregator-on-fabricated-logs).
- `tests/unit/test_quarantine_marker_setup.py` (RED-first guard)
- `scripts/flake_detect_aggregate.py` (≤120 SLoC, stdlib-only)
- `pyproject.toml`, `uv.lock`, `Makefile` — patched
- `docs/IW_AI_Core_Testing_Strategy.md`, `tests/CLAUDE.md` — patched
- `skills/iw-ai-core-testing/SKILL.md` + `.claude/skills/iw-ai-core-testing/SKILL.md` — patched + synced
- `ai-dev/work/TESTS_ENHANCEMENT.md` — patched §6 + §11

## Context

You are implementing **CR-00061 — Flaky test quarantine workflow (P2-CR-C)**, the **third and final Phase-2 CR**. **Read the design doc first.** "Desired Behavior" names the marker prose, the addopts change, the 5-rule list, the Makefile recipes' exact shape, the aggregator script's behaviour. ACs 1–9 are mandatory.

## Requirements

### 0. RED — write the guard test FIRST

Create `tests/unit/test_quarantine_marker_setup.py`:

```python
"""Pins the quarantine workflow config so future edits don't silently drift.

Written RED-first for CR-00061 (P2-CR-C): fails before the marker/addopts/
make targets/aggregator script exist; passes after S01 lands them.
"""
import importlib
import subprocess
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_quarantine_marker_registered():
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    markers = data["tool"]["pytest"]["ini_options"]["markers"]
    assert any(m.startswith("quarantine:") for m in markers), (
        "`quarantine: ...` marker must be registered in [tool.pytest.ini_options].markers"
    )


def test_addopts_deselects_quarantine():
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    addopts = data["tool"]["pytest"]["ini_options"]["addopts"]
    assert "not browser and not quarantine" in addopts, (
        f"addopts must filter out quarantine via 'not browser and not quarantine'; got: {addopts!r}"
    )
    assert "--strict-markers" in addopts, "addopts must keep --strict-markers"
    # Defensive: the old standalone `not browser` filter must be replaced, not duplicated
    assert addopts.count("-m ") == 1, (
        f"addopts must contain exactly one -m filter; got: {addopts!r}"
    )


def test_pytest_rerunfailures_installed():
    importlib.import_module("pytest_rerunfailures")  # ImportError if missing


def test_makefile_exposes_quarantine_and_flake_detect_targets():
    for target in ("test-quarantine", "test-flake-detect"):
        result = subprocess.run(
            ["make", "-n", target],
            cwd=REPO_ROOT, capture_output=True, text=True, check=False,
        )
        assert "No rule to make target" not in result.stderr, (
            f"make -n {target}: missing — CR-00061 must land both recipes\n{result.stderr}"
        )
        assert result.returncode == 0, f"make -n {target}: parse failed\n{result.stderr}"


def test_flake_detect_aggregator_is_valid_python():
    script = REPO_ROOT / "scripts" / "flake_detect_aggregate.py"
    assert script.exists(), "scripts/flake_detect_aggregate.py missing"
    # Validate it parses
    import ast
    ast.parse(script.read_text())
    # Stdlib-only check (no third-party imports)
    src = script.read_text()
    for forbidden in ("import pytest", "import requests", "import httpx", "from pytest"):
        assert forbidden not in src, f"aggregator must be stdlib-only; found {forbidden!r}"
```

Run:

```bash
uv run pytest tests/unit/test_quarantine_marker_setup.py -v
```

All five tests MUST fail (with `KeyError`/`AssertionError`/`ModuleNotFoundError`). Capture failure lines for `tdd_red_evidence`.

### 1. Install pytest-rerunfailures

- Add `pytest-rerunfailures>=14.0,<16` to `[dependency-groups] dev`. Place alphabetically.
- `uv lock`.
- `uv sync`.
- Verify: `uv run python -c "import pytest_rerunfailures; print(pytest_rerunfailures.__version__)"` → 14.x or 15.x.

### 2. Register the marker + extend addopts

In `pyproject.toml` `[tool.pytest.ini_options].markers`, append:

```
    "quarantine: test is intermittently failing or order-dependent in a way we haven't root-caused; excluded from the merge gate; tracked via an Incident (ID in the marker reason). Recovery signal: passes consistently in `make test-quarantine` for >=3 consecutive runs.",
```

In `addopts` (line 156), change the existing fragment:

```
-m 'not browser' --strict-markers
```

to:

```
-m 'not browser and not quarantine' --strict-markers
```

**One change, one new clause** — do not duplicate `-m`. The rest of `addopts` (the long `--cov` chain) stays untouched.

### 3. Add the two Makefile targets

After existing test-quality targets (near the `diff-coverage` block):

```make
# =============================================================================
# QUARANTINE & FLAKE DETECTION (CR-00061, P2-CR-C) — on-demand, NOT a CI gate
# =============================================================================
# The `quarantine` marker is auto-deselected by `addopts` on the merge path
# (see pyproject.toml). These targets are for inspecting/recovering quarantined
# tests and for detecting NEW flakes that should be quarantined.

# Run ONLY quarantined tests; --reruns 1 lets a genuine flake recover.
# DELIBERATELY --reruns 1 (not 3): we want to surface flakes, not mask them.
test-quarantine:
	uv run pytest tests/ -m quarantine --reruns 1 --reruns-delay 1 -v --no-cov

# Run the FULL suite 3x and aggregate per-test outcomes; any test that
# disagreed across runs is a flake. Operator-on-demand or nightly cron.
# Wall-clock budget: ~30+ minutes (3x full integration suite).
# IMPORTANT: use `-v` (not `-q`) so each test emits a `<test_id> <OUTCOME>`
# line that the aggregator's regex can match. `-q` only prints dots, and
# the default failure summary uses `<OUTCOME> <test_id>` order which the
# aggregator does NOT match — `-v` is the version that actually works.
test-flake-detect:
	@mkdir -p tests/output
	@rm -f tests/output/flake-detect-*.log
	@for i in 1 2 3; do \
		echo "=== flake-detect run $$i/3 ==="; \
		uv run pytest tests/unit tests/integration tests/dashboard --ignore=tests/dashboard/browser \
			--no-cov -v --tb=no 2>&1 | tee tests/output/flake-detect-$$i.log || true; \
	done
	@echo ""
	@echo "=== aggregating ==="
	@uv run python scripts/flake_detect_aggregate.py tests/output/flake-detect-1.log tests/output/flake-detect-2.log tests/output/flake-detect-3.log
```

Add `test-quarantine test-flake-detect` to the `.PHONY` line near the other test-* targets.

### 4. Write scripts/flake_detect_aggregate.py

Constraints: ≤120 SLoC, stdlib-only, exits 1 on flakes detected, 0 otherwise. Skeleton:

```python
#!/usr/bin/env python3
"""Aggregate pytest log files from `make test-flake-detect` and report flakes.

A flake is a test whose outcome (PASSED/FAILED) differs across the supplied
log files. Exit 1 if any flake is detected so a nightly cron can alert.

Usage:
    flake_detect_aggregate.py run1.log run2.log run3.log [...]
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

# pytest line format (default -v output): "tests/foo.py::test_bar PASSED [ 12%]"
# With -q (the flake-detect recipe uses -q --tb=no), pytest prints dots; we instead
# pull the per-test outcome from the failure/short-test-summary section. Be permissive.
_TEST_LINE_RE = re.compile(
    r"^(?P<test_id>[\w./:\[\]\-\,]+?::[\w\[\]\-]+)\s+(?P<outcome>PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS)\b"
)


def parse_log(path: Path) -> dict[str, str]:
    """Return {test_id: outcome} for tests with a definitive PASSED/FAILED line."""
    outcomes: dict[str, str] = {}
    for line in path.read_text(errors="replace").splitlines():
        m = _TEST_LINE_RE.match(line.strip())
        if m:
            tid = m.group("test_id")
            outcome = m.group("outcome")
            # Last-write-wins is fine — pytest reports each test once per run
            outcomes[tid] = outcome
    return outcomes


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print("Usage: flake_detect_aggregate.py run1.log run2.log [run3.log ...]", file=sys.stderr)
        return 2

    logs = [Path(p) for p in argv[1:]]
    for log in logs:
        if not log.exists():
            print(f"ERROR: log file not found: {log}", file=sys.stderr)
            return 2

    per_run: list[dict[str, str]] = [parse_log(p) for p in logs]

    # Union of all test ids seen
    all_ids: set[str] = set()
    for run in per_run:
        all_ids.update(run)

    flakes: dict[str, list[str]] = defaultdict(list)
    for tid in sorted(all_ids):
        outcomes = [run.get(tid, "ABSENT") for run in per_run]
        # A flake is a test with both PASSED and FAILED outcomes across runs
        distinct = {o for o in outcomes if o in ("PASSED", "FAILED")}
        if len(distinct) > 1:
            flakes[tid] = outcomes

    n_runs = len(logs)
    print(f"Flake detection over {n_runs} runs of the full suite")
    print()
    if not flakes:
        print("No flakes detected.")
        return 0

    print(f"Found {len(flakes)} flaky test(s):")
    for tid, outcomes in flakes.items():
        print(f"  {tid}")
        for i, outcome in enumerate(outcomes, start=1):
            print(f"    run {i}: {outcome}")
    print()
    print("Recommendation: file an incident, add `@pytest.mark.quarantine(reason=\"I-NNNNN: ...\")`, exclude from merge gate.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

Make it executable: `chmod +x scripts/flake_detect_aggregate.py` (the Makefile uses `uv run python ...`, so the shebang is cosmetic — but executable is good hygiene).

### 5. Confirm no pre-existing usage

```bash
grep -rn "@pytest.mark.quarantine" tests/ scripts/ orch/ dashboard/ executor/ 2>/dev/null
```

Should return **nothing**. If anything matches, raise a blocker — it means someone has been using the marker name already and the addopts deselection could silently break their workflow.

### 6. Re-run RED → GREEN

```bash
uv run pytest tests/unit/test_quarantine_marker_setup.py -v
```

All five tests MUST pass.

### 7. SMOKE TEST — marker deselection actually works

Pick the FIRST `def test_` in `tests/unit/test_smoke.py`. Temporarily add `@pytest.mark.quarantine(reason="smoke-test-cr-00061")` directly above its `def`.

```bash
# Capture default-run output (the marked test should be deselected)
uv run pytest tests/unit/test_smoke.py -v --no-cov 2>&1 | tee /tmp/cr-00061-smoke-default.log | head -40

# Capture -m quarantine output (the marked test should be the ONLY one)
uv run pytest tests/unit/test_smoke.py -m quarantine -v --no-cov 2>&1 | tee /tmp/cr-00061-smoke-quarantine.log | head -20
```

Embed BOTH outputs in the step report (`### Smoke test: marker deselection` sub-section).

**REVERT the temporary marker** before completing S01:

```bash
git checkout tests/unit/test_smoke.py
git status tests/unit/test_smoke.py  # should be clean
```

The diff at S01 completion MUST NOT include any change to `tests/unit/test_smoke.py`.

### 8. SMOKE TEST — aggregator on fabricated logs

Create three temp logs that simulate a flake:

```bash
mkdir -p /tmp/cr-00061-fake
cat > /tmp/cr-00061-fake/run1.log <<'EOF'
tests/unit/test_fake.py::test_a PASSED                                    [ 50%]
tests/unit/test_fake.py::test_b PASSED                                    [100%]
EOF
cat > /tmp/cr-00061-fake/run2.log <<'EOF'
tests/unit/test_fake.py::test_a FAILED                                    [ 50%]
tests/unit/test_fake.py::test_b PASSED                                    [100%]
EOF
cat > /tmp/cr-00061-fake/run3.log <<'EOF'
tests/unit/test_fake.py::test_a PASSED                                    [ 50%]
tests/unit/test_fake.py::test_b PASSED                                    [100%]
EOF

uv run python scripts/flake_detect_aggregate.py /tmp/cr-00061-fake/run1.log /tmp/cr-00061-fake/run2.log /tmp/cr-00061-fake/run3.log; echo "exit=$?"
```

Expected output: one flake (`test_a`) reported with `run 1: PASSED  run 2: FAILED  run 3: PASSED`, exit 1.

Run again with all 3 logs identical (copy run1 three times):

```bash
cp /tmp/cr-00061-fake/run1.log /tmp/cr-00061-fake/run2.log
cp /tmp/cr-00061-fake/run1.log /tmp/cr-00061-fake/run3.log
uv run python scripts/flake_detect_aggregate.py /tmp/cr-00061-fake/run1.log /tmp/cr-00061-fake/run2.log /tmp/cr-00061-fake/run3.log; echo "exit=$?"
```

Expected: `No flakes detected.`, exit 0.

Embed both outputs in the step report (`### Smoke test: aggregator behaviour` sub-section).

Clean up the temp dir: `rm -rf /tmp/cr-00061-fake`.

### 9. Update docs + skill + plan

- `docs/IW_AI_Core_Testing_Strategy.md` §3: new "Flaky/quarantine workflow" sub-section (the marker; the 3 surfaces — merge gate deselection, `make test-quarantine` for inspection, `make test-flake-detect` for detection; the file-an-incident rule).
- `docs/IW_AI_Core_Testing_Strategy.md` §5 gate table: 2 new rows.
- `docs/IW_AI_Core_Testing_Strategy.md` §9 row "Flaky/quarantine workflow": `❌ (2.3)` → `✅ (CR-00061, 2026-MM-DD) — quarantine marker; addopts deselection; make test-quarantine / make test-flake-detect; quarantining requires filing an Incident (rule in tests/CLAUDE.md)`.
- `tests/CLAUDE.md`: new "Quarantine workflow" sub-section with the 5-rule list verbatim from the design.
- `skills/iw-ai-core-testing/SKILL.md`: add a "Quarantine" sub-section in conventions (same 5 rules).
- Run `iw sync-skills --force iw-ai-core-testing` and verify the `.claude/skills/...` copy.
- `ai-dev/work/TESTS_ENHANCEMENT.md` §6 item 2.3: `TODO` → `DONE — CR-00061 (2026-MM-DD)`.
- `ai-dev/work/TESTS_ENHANCEMENT.md` §11: dated entry summarising marker + addopts + 3 targets + the rule + the relationship to existing `order_dependent`.

## Verification

### Pre-flight (mandatory)

```bash
make format
make typecheck
make lint
```

## Test Verification (NON-NEGOTIABLE)

1. `uv run pytest tests/unit/test_quarantine_marker_setup.py -v` → 5 passes.
2. `make -n test-quarantine` and `make -n test-flake-detect` → both parse.
3. `pytest --markers | grep quarantine` → lists the new marker.
4. The two SMOKE TEST captures from deliverables 7 + 8 are in the step report.
5. `git diff tests/unit/test_smoke.py` → empty (smoke-test marker reverted).

Do NOT run `make check` / `make test-flake-detect` against the full suite.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "CR-00061",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "pyproject.toml",
    "uv.lock",
    "Makefile",
    "scripts/flake_detect_aggregate.py",
    "tests/unit/test_quarantine_marker_setup.py",
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
  "test_summary": "test_quarantine_marker_setup.py 5/5 pass. Smoke test 1: marker on test_smoke.py first test → deselected from default run, present under -m quarantine; reverted. Smoke test 2: aggregator on fabricated logs → flake reported & exit 1; on agreeing logs → 'No flakes', exit 0.",
  "tdd_red_evidence": "tests/unit/test_quarantine_marker_setup.py::test_quarantine_marker_registered FAILED (pre-patch): AssertionError at line <L> — `quarantine: ...` marker not found in [tool.pytest.ini_options].markers. test_pytest_rerunfailures_installed FAILED: ModuleNotFoundError: No module named 'pytest_rerunfailures'.",
  "blockers": [],
  "notes": "Phase-2 closes with this CR (items 2.1+2.2+2.3 all DONE). Marker registered + addopts deselects. 3 new make targets (test-quarantine, test-flake-detect, plus the aggregator script). 5 existing order_dependent quarantines untouched per design. No pre-existing @pytest.mark.quarantine in the codebase (verified). Smoke-test temporary marker reverted (diff clean)."
}
```

- `tdd_red_evidence`: real test id + real failure line. Not `"n/a"`.
- `completion_status`:
  - `complete` if all 9 deliverables done, both smoke-test captures in the report, `git diff` clean on `tests/unit/test_smoke.py`.
  - `partial` if doc updates done but a smoke-test capture is missing (file a follow-up note); the CR is still functionally complete.
  - `blocked` if (a) pytest-rerunfailures won't install, (b) the addopts change breaks unit-test collection in some unforeseen way (verify with `uv run pytest tests/unit/ --collect-only 2>&1 | tail -5` before declaring complete), (c) pre-existing `@pytest.mark.quarantine` is found (operator escalation).
