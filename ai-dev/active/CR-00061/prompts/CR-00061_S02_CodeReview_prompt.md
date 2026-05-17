# CR-00061_S02_CodeReview_prompt

**Work Item**: CR-00061 -- Flaky test quarantine workflow (P2-CR-C)
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

Standard policy. No `docker compose` / `docker rm` / `docker volume *`. Testcontainer fixtures (used indirectly by the integration test suite) are allowed.

## ⛔ Migrations: agents generate, daemon applies

No migrations.

## Input Files

- `uv run iw item-status CR-00061 --json`
- `ai-dev/active/CR-00061/CR-00061_CR_Design.md` (source of truth; ACs 1–9)
- `ai-dev/active/CR-00061/reports/CR-00061_S01_Backend_report.md` (must contain BOTH smoke-test captures)
- All files in S01's `files_changed`

## Output Files

- `ai-dev/active/CR-00061/reports/CR-00061_S02_CodeReview_report.md`

## Context

Reviewing S01's implementation. Five biggest CRITICAL risks: (1) `addopts` duplicates `-m` instead of merging into one filter — pytest only honours the LAST `-m`, silently breaking either the browser deselection or the quarantine deselection; (2) `--reruns 1` got bumped to `--reruns 3` "to be helpful" — masks flakes; (3) the smoke-test temporary marker on `tests/unit/test_smoke.py` was NOT reverted (a stray `@pytest.mark.quarantine` ships); (4) the aggregator script imports pytest or other non-stdlib deps; (5) the 5-rule list in `tests/CLAUDE.md` is paraphrased or shortened (the workflow rule becomes unenforceable).

## Pre-Review Lint Gate

```bash
make lint
make format-check
```

NEW violations = CRITICAL.

## Review Checklist

### 1. Dependency + marker registration

```bash
grep -n 'pytest-rerunfailures' pyproject.toml
uv run python -c "import pytest_rerunfailures; print(pytest_rerunfailures.__version__)"
uv run pytest --markers 2>&1 | grep -A 1 quarantine
```

- `pytest-rerunfailures>=14.0,<16` in `[dependency-groups] dev` (AC1). Different pin = HIGH.
- `import pytest_rerunfailures` succeeds. Failure = CRITICAL.
- `pytest --markers` lists `quarantine` with a description matching the design's prose (key phrases: "intermittently failing", "excluded from the merge gate", "tracked via an Incident", "passes consistently in `make test-quarantine` for >=3 consecutive runs"). Paraphrased = HIGH; missing rule references = CRITICAL.

### 2. addopts mutation correctness (highest CRITICAL risk)

```bash
python -c "import tomllib; ao = tomllib.load(open('pyproject.toml','rb'))['tool']['pytest']['ini_options']['addopts']; print(repr(ao)); print('count -m:', ao.count('-m '))"
```

- Contains `not browser and not quarantine` exactly once (AC2). Missing = CRITICAL.
- Does NOT contain a separate `-m 'not browser'` clause (the old fragment must be replaced, not appended). Duplicate `-m` = CRITICAL — pytest takes the last one, silently breaking deselection.
- Contains `--strict-markers`. Missing = CRITICAL (strict-markers is what enforces the marker registry contract).
- Exactly one `-m ` substring. Two or more = CRITICAL.

### 3. Makefile recipes — exact form

```bash
make -n test-quarantine
make -n test-flake-detect | head -30
grep -E "^\.PHONY|test-quarantine|test-flake-detect" Makefile | head -5
```

- `test-quarantine` invokes `pytest -m quarantine --reruns 1 --reruns-delay 1` (AC3). `--reruns 3` or `--reruns 5` = CRITICAL (masks flakes — defeats the purpose).
- `test-flake-detect` loops `pytest` 3× into `tests/output/flake-detect-*.log` then runs `scripts/flake_detect_aggregate.py` with the three log paths. Different number of runs = HIGH (CR-00061 specifies 3); missing aggregator invocation = CRITICAL.
- `test-flake-detect` invokes pytest with `-v` (per-test line emission). If it uses `-q` or omits `-v`, the aggregator regex cannot match the log lines and the detector silently reports "No flakes" for any input = CRITICAL (the detector is a no-op).
- Both targets in `.PHONY` line. Missing = HIGH (cosmetic but `.PHONY` contract).

### 4. Aggregator script — purity + behaviour

```bash
wc -l scripts/flake_detect_aggregate.py
grep -nE '^import |^from ' scripts/flake_detect_aggregate.py
python3 -c "import ast; ast.parse(open('scripts/flake_detect_aggregate.py').read())"
```

- ≤120 SLoC (AC4). >150 = HIGH (over-engineered).
- Only stdlib imports (`re`, `sys`, `pathlib`, `collections`, `__future__`, etc.). Any third-party (`import pytest`, `import requests`, `import httpx`) = CRITICAL — the script must run standalone after pytest has finished.
- Valid Python (parses without error). Syntax error = CRITICAL.

Independently verify behaviour using the same fabricated-log approach S01 used in deliverable 8:

```bash
mkdir -p /tmp/cr-00061-s02-fake
cat > /tmp/cr-00061-s02-fake/run1.log <<'EOF'
tests/unit/test_fake.py::test_a PASSED                                    [ 50%]
tests/unit/test_fake.py::test_b PASSED                                    [100%]
EOF
cat > /tmp/cr-00061-s02-fake/run2.log <<'EOF'
tests/unit/test_fake.py::test_a FAILED                                    [ 50%]
tests/unit/test_fake.py::test_b PASSED                                    [100%]
EOF
cp /tmp/cr-00061-s02-fake/run1.log /tmp/cr-00061-s02-fake/run3.log

uv run python scripts/flake_detect_aggregate.py /tmp/cr-00061-s02-fake/run{1,2,3}.log; echo "exit=$?"
rm -rf /tmp/cr-00061-s02-fake
```

- Reports `test_a` as flaky and exits 1. Different = HIGH (parsing is off).

### 5. The two SMOKE TEST captures are in the step report

Open `ai-dev/active/CR-00061/reports/CR-00061_S01_Backend_report.md` and verify TWO sub-sections (AC5):

- `### Smoke test: marker deselection` — contains both the default-run output (deselected test absent) AND the `-m quarantine` output (deselected test present).
- `### Smoke test: aggregator behaviour` — contains both the "fabricated flake → exit 1" run AND the "all-agree → exit 0" run.

Either missing = HIGH (we can't verify the workflow really works without these captures).

### 6. CRITICAL: smoke-test marker REVERTED

```bash
git diff tests/unit/test_smoke.py
```

Output MUST be empty (S01 added `@pytest.mark.quarantine(reason="smoke-test-cr-00061")` temporarily; if it's still there, that test will be deselected from the merge gate every run from now on). Non-empty diff = **CRITICAL** — request immediate revert + re-verify.

Also: scan the broader diff for stray markers:

```bash
git diff origin/main..HEAD | grep -E "^\+.*@pytest\.mark\.quarantine"
```

The ONLY allowed match should be in the marker registration (`pyproject.toml`), the guard test (`tests/unit/test_quarantine_marker_setup.py` may reference the string), the docs, and the skill. Any match in actual test files = CRITICAL.

### 7. tests/CLAUDE.md 5-rule list verbatim

Read the new "Quarantine workflow" sub-section. Verify all 5 rules are present, in order, with the design's wording:

1. Before adding the marker → file an Incident via `/iw-new-incident`.
2. Marker `reason` MUST carry `"I-NNNNN: <one-liner>"` form.
3. Incident's Description names the test(s) verbatim.
4. Removal requires 3 consecutive passes in `make test-quarantine` OR 7 calendar days.
5. `@pytest.mark.order_dependent` is a narrower flavour; both excluded from merge gate; new entries default to `quarantine`.

Missing any rule = CRITICAL (the workflow becomes ambiguous). Paraphrased = HIGH.

### 8. Strategy doc / skill consistency

- `docs/IW_AI_Core_Testing_Strategy.md` §3 has "Flaky/quarantine workflow" sub-section. Missing = HIGH.
- §5 has 2 new rows (AC6). Missing either = HIGH.
- §9 row flipped to ✅ with `CR-00061` named. Still ❌ = CRITICAL.
- `skills/iw-ai-core-testing/SKILL.md` has the same 5-rule sub-section.
- `diff skills/iw-ai-core-testing/SKILL.md .claude/skills/iw-ai-core-testing/SKILL.md` → empty. Drift = HIGH.

### 9. Plan + changelog

- `ai-dev/work/TESTS_ENHANCEMENT.md` §6 item 2.3: `DONE — CR-00061 (YYYY-MM-DD)`. Still `TODO` = CRITICAL.
- §11 dated entry includes: marker registration; addopts change; 3 targets; file-an-incident rule; order_dependent reconciliation. Missing any = HIGH.

### 10. Scope-creep audit

```bash
git diff --name-only origin/main..HEAD | sort
```

Subset of `Impacted Paths` from the design. Specifically forbidden:

- Any file under `orch/`, `dashboard/`, `executor/`. CRITICAL.
- Any new daemon QV gate in `skills/iw-workflow/SKILL.md`. CRITICAL (operator decision — quarantine gate NOT a CI step).
- Any GH workflow change. CRITICAL.
- Any Alembic migration. CRITICAL.
- Any test-body change (no test under `tests/` should differ except the new `test_quarantine_marker_setup.py`). The smoke-test temp marker must NOT persist.

### 11. RED-first contract integrity

- `tests/unit/test_quarantine_marker_setup.py` in `files_changed`. Missing = CRITICAL.
- `tdd_red_evidence` quotes a real test id + a real failure line (any of the 5 in the guard test). `"n/a"` = CRITICAL.

## Review Report Format

Sections: **Verdict**, **Per-checklist findings** (1–11), **addopts before/after diff** (show the exact `-m` clause before and after to prove the merge worked), **Smoke-test capture summary** (one-paragraph summary of each of the two captures with their key lines), **Aggregator independent re-verification** (your own run on fabricated logs), **Scope diff** (file-list with PASS/FAIL).

Finish with the JSON contract block.
