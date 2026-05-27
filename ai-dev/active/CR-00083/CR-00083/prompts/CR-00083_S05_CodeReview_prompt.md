# CR-00083_S05_CodeReview_prompt

**Work Item**: CR-00083 -- Performance-budget test layer — pytest-benchmark assertions with regression-alert baselines
**Step Being Reviewed**: S01 (backend-impl) + S02 (backend-impl) + S03 (backend-impl) together
**Review Step**: S05
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

This CR adds no migrations. If you see one in the diff, flag it CRITICAL.

## Input Files

- `uv run iw item-status CR-00083 --json` — runtime step state.
- `ai-dev/work/CR-00083/CR-00083_CR_Design.md` — design.
- `ai-dev/work/CR-00083/reports/CR-00083_S01_Backend_report.md` — S01 report (pytest-benchmark dep + marker).
- `ai-dev/work/CR-00083/reports/CR-00083_S02_Backend_report.md` — S02 report (perf package + daemon module).
- `ai-dev/work/CR-00083/reports/CR-00083_S03_Backend_report.md` — S03 report (RAG + dashboard modules + umbrella Makefile).
- All files listed in those reports' `files_changed`.

## Output Files

- `ai-dev/work/CR-00083/reports/CR-00083_S05_CodeReview_report.md` — review report.

## Context

You are reviewing S01, S02, and S03 together — the `pytest-benchmark` dep + `perf` marker (S01), the perf-package skeleton + `seeded_orch_db` fixture + daemon perf module + daemon baseline + first Makefile target (S02), and the RAG + dashboard perf modules + their baselines + umbrella/operator Makefile targets (S03). S04 (CI workflow + docs) is reviewed by S06.

## Read the Design Document FIRST

Read `CR-00083_CR_Design.md` end-to-end before opening any code. Specifically:

- AC1 (pytest-benchmark dep), AC2 (daemon module), AC3 (RAG module), AC4 (dashboard routes module), AC5 (Makefile umbrella + per-module + operator-only targets), AC6 (baseline regression detection) — every one is a check item.
- The Notes section's "Budget choice methodology", "Mean vs min", "LanceDB fixture", "TestClient warmup", and especially **"Test-only scope discipline"** rules.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

On any NEW violation in the changed files, file CRITICAL with category `conventions`.

## Review Checklist

### 1. Dependency + marker wiring

- `pyproject.toml` `[dependency-groups] dev` contains `"pytest-benchmark>=4.0,<5"`.
- `uv.lock` is regenerated cleanly (no manual edit — only the resolver output).
- `pyproject.toml` `[tool.pytest.ini_options].markers` registers `perf` with a clear description.
- `pyproject.toml` `[tool.pytest.ini_options].addopts` excludes `perf` via `and not perf`. Verify by running `uv run pytest --collect-only tests/perf/ 2>&1 | head -20` — it should report tests deselected by the marker filter on a default invocation, and collected when `-m perf` is added.

### 2. tests/perf/conftest.py

- Auto-applies `@pytest.mark.perf` to every test in the package (via `pytest_collection_modifyitems` or a module-level `pytestmark`).
- `seeded_orch_db` fixture is `scope="session"` (perf tests cannot afford per-test container spin-up).
- Replaces `postgresql+psycopg2://` with `postgresql+psycopg://` in the testcontainer URL (CRITICAL rule from CLAUDE.md).
- Runs `Base.metadata.create_all()` AND `FTS_FUNCTION_SQL` AND `FTS_TRIGGER_SQL` (the FTS pair is mandatory — CR-00026 / I-00039 history).
- Seeds 1 project + 3 work items + 1 batch + 1 worktree-stub row.
- Does NOT point at the live DB on port 5433 (live-DB write guard — would be CRITICAL).

### 3. Each perf module

For `test_daemon_poll_loop.py`, `test_rag_query.py`, `test_dashboard_routes.py`:

- Module docstring records initial measurement value, σ/μ ratio, and mean-vs-min rationale.
- BUDGET constant(s) is/are module-level, frozen, and chosen as `initial_mean × 1.5`.
- Assertion is `assert <stat> < BUDGET_<X>` against the **specific constant** — NOT just `--benchmark-compare-fail` alone (which is a regression gate, not an absolute upper bound).
- Forbidden assertions (would be MEDIUM_FIXABLE — assertion scanner would also catch them in S07):
  - `assert mean > 0`
  - `assert min < float('inf')`
  - `assert ratio >= 0`
  - `assert isinstance(result, dict)` alone
  - `mock.assert_called*` as the sole assertion
- `warmup_rounds=5, rounds=10` (or equivalent — at least 5 warmup + 10 measurement) for daemon and RAG modules.
- Dashboard routes module performs ≥3 warmup hits per route OUTSIDE the benchmark loop.
- Dashboard routes module covers EXACTLY the 5 routes specified: `/`, `/project/{id}/queue`, `/project/{id}/batches`, `/project/{id}/jobs`, `/project/{id}/code`. Extra or missing routes = MEDIUM_FIXABLE (HIGH if a required one is missing).
- RAG module STUBS the embedding model deterministically. If you see an Ollama dependency (a real HTTP call, even with a fallback), file CRITICAL — the design's Notes section is explicit that the RAG perf test must ALWAYS run, NOT skip when Ollama is absent.

### 4. Baselines

- `tests/perf/baselines/daemon.json` exists, is non-empty, parseable JSON.
- `tests/perf/baselines/rag.json` exists, is non-empty, parseable JSON.
- `tests/perf/baselines/routes.json` exists, is non-empty, parseable JSON.
- Each baseline records the budget the module asserts against in a way that future runs can `--benchmark-compare=<name>` against (the `--benchmark-save=<name>` flag in S01/S02 should have produced the right filenames; if the structure is `tests/perf/baselines/Linux-CPython-<ver>-64bit/<name>.json`, that's fine — pytest-benchmark's storage convention).

### 5. Makefile targets

- `test-perf-daemon`, `test-perf-rag`, `test-perf-routes` each invoke `uv run pytest <module> ... --benchmark-compare=<name> --benchmark-compare-fail=mean:25% ... -m perf --no-cov`.
- `test-perf` is an umbrella that chains `test-perf-daemon test-perf-rag test-perf-routes` (Make's prerequisite list, not a recipe-level loop).
- `test-perf-update-baseline` is operator-only, prints the "commit requires CR review" warning to stdout BEFORE running the benchmark saves, and runs `--benchmark-save=<name>` for each module.
- All 5 targets are in `.PHONY` (the top-level aggregation list AND/OR explicit `.PHONY:` lines).

### 6. Scope discipline (CR-00083 hard rule)

Run `git diff --name-only $(git merge-base HEAD main)..HEAD` (or equivalent). The diff MUST contain ONLY:

- `pyproject.toml`
- `uv.lock`
- `tests/perf/**`
- `Makefile`

ANY file outside this list (especially `orch/**`, `dashboard/**`, `executor/**`) is a CRITICAL finding (scope violation). Even if a perf measurement uncovered a real production regression, the design's Notes section explicitly forbids in-CR production fixes — the response should be a raised budget + a filed Incident.

### 7. TDD RED evidence

- S01's `tdd_red_evidence` is `"n/a — dependency + marker configuration only; behavioural perf tests are introduced in S02 onward"` (configuration-only step, allowed). Field MUST NOT be a generic "tests pass" — the n/a justification IS the required content.
- S02's `tdd_red_evidence` records the initial-measurement → budget-set → final-green narrative for the daemon module. Field MUST NOT be `"n/a"` — perf tests are behavioural tests with explicit measurement-based RED.
- S03's `tdd_red_evidence` records the same for the RAG + 5 dashboard routes (single field covering both modules is acceptable).
- If S02 or S03 evidence is missing or generic ("tests pass"), file HIGH finding under category `testing`.

## Test Verification (NON-NEGOTIABLE)

```bash
make test-perf  # umbrella runs all three modules — must pass with no regression > 25%
uv run pytest --collect-only tests/perf/  # confirms perf tests are deselected by default
uv run pytest -m perf --collect-only tests/perf/  # confirms they're collectable with -m perf
```

Report results in the contract. Do NOT run `make check` — that's S11/S12/S13's job (renumbered QV gates).

## Severity Levels

Standard: CRITICAL / HIGH / MEDIUM_FIXABLE / MEDIUM_SUGGESTION / LOW.

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "code-review-impl",
  "work_item": "CR-00083",
  "step_reviewed": "S01,S02,S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "make test-perf: X passed (1 daemon + 1 rag + 5 routes), 0 failed",
  "notes": "Diff confirmed scope-bounded to pyproject.toml + uv.lock + tests/perf/** + Makefile."
}
```
