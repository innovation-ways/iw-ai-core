# CR-00083_S03_Backend_prompt

**Work Item**: CR-00083 -- Performance-budget test layer — pytest-benchmark assertions with regression-alert baselines
**Step**: S03
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Allowed exceptions:
  1. Testcontainers spun up by pytest fixtures (Ryuk-managed).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This CR adds **no** migrations.

## Input Files

- `uv run iw item-status CR-00083 --json` — runtime step state.
- `ai-dev/work/CR-00083/CR-00083_CR_Design.md` — design document.
- `ai-dev/work/CR-00083/reports/CR-00083_S02_Backend_report.md` — S02 report (uses its `seeded_orch_db` fixture).
- `orch/rag/qa.py` — `CodeQA.answer_stream` (the RAG entry point you measure).
- `dashboard/app.py` + `dashboard/routers/project_dashboard.py` + `dashboard/routers/items.py` + `dashboard/routers/batches.py` + `dashboard/routers/jobs_ui.py` + `dashboard/routers/code.py` — the 5 routes you measure.
- `tests/integration/rag/conftest.py` — the existing Ollama-skip pattern; you take the OPPOSITE stance (stub embeddings, always run).
- `tests/dashboard/conftest.py` — existing FastAPI `TestClient` patterns.

## Output Files

- `ai-dev/work/CR-00083/reports/CR-00083_S03_Backend_report.md` — step report.

## Context

You are implementing **S03** of CR-00083 — the RAG query perf module, the dashboard routes perf module, and the umbrella + per-module + operator-only baseline Makefile targets.

S01 has already shipped the `pytest-benchmark` dep + the `perf` marker. S02 has shipped the perf package skeleton + the `seeded_orch_db` testcontainer fixture + the daemon perf module + the first Makefile target. Reuse the fixture verbatim.

## Requirements

### 1. Create `tests/perf/test_rag_query.py`

Build a deterministic `tmp_path`-backed LanceDB index fixture (10 documents) and STUB the embedding model. The RAG perf test must run unconditionally — opposite stance to `tests/integration/rag/`'s skip-when-no-Ollama hook. Goal: measure retrieval + ranking + result-assembly cost, NOT model latency.

> **LanceDB note**: LanceDB has no true in-memory backend — it always persists to a directory. Use `tmp_path` (or `tmp_path_factory` for session scope) so the index lives in pytest's tempdir, which is RAM-backed on most CI systems. The fixture's lifecycle handles cleanup automatically.

```python
"""RAG query performance budget.

Methodology: measures one full `CodeQA.answer_stream` invocation against a
tmp_path-backed LanceDB index fixture (10 documents) with a deterministic stub
embedding (hash-to-fixed-dim vector — NO Ollama dependency, opposite stance to
tests/integration/rag/'s skip-when-no-Ollama hook).

Initial measurement (2026-05-24, S03 run): mean = <X> s, σ/μ = <Y>.
Mean-vs-min: <mean|min> (σ/μ <0.3 = mean, ≥0.3 = min — record rationale).
"""
import pytest
# ...

BUDGET_S = <ceil(initial_mean * 1.5 * 100) / 100>  # frozen 2026-05-24


def test_rag_query_within_budget(benchmark, tmp_path_rag_index):
    result = benchmark.pedantic(
        _run_one_rag_query,  # drains the async generator into a list
        args=(tmp_path_rag_index, "What does the daemon do?"),
        rounds=10,
        warmup_rounds=5,
    )
    assert benchmark.stats.stats.mean < BUDGET_S, (
        f"RAG query mean {benchmark.stats.stats.mean:.3f} s exceeds budget {BUDGET_S} s"
    )
```

The `tmp_path_rag_index` fixture seeds 10 small synthetic documents into a `tmp_path`-backed LanceDB and patches the embedding-model factory to return a deterministic stub (`hashlib.blake2b(query.encode()).digest()` reshaped/padded to the model's expected dim, e.g., 768). Use a `monkeypatch.setattr` against the embedding factory's import site in `orch/rag/qa.py`.

Save baseline via:

```bash
uv run pytest tests/perf/test_rag_query.py -v --benchmark-save=rag --benchmark-storage=file://tests/perf/baselines -m perf --no-cov
```

The concrete file pytest-benchmark produces is `tests/perf/baselines/<machine-id>/NNNN_rag.json` (e.g. `tests/perf/baselines/Linux-CPython-3.13-64bit/0001_rag.json`). Commit the whole subtree.

### 2. Create `tests/perf/test_dashboard_routes.py`

Parametrize over exactly these 5 routes:

1. `/`
2. `/project/{project_id}/queue`
3. `/project/{project_id}/batches`
4. `/project/{project_id}/jobs`
5. `/project/{project_id}/code`

```python
"""Dashboard routes performance budget (p50 over ≥10 runs).

Methodology: p50 latency of each route via FastAPI `TestClient` against the
session-scoped `seeded_orch_db` fixture from `tests/perf/conftest.py`. ≥3
warmup hits per route (excluded from measurement). pytest-benchmark
`warmup_rounds=3, rounds=10`.

Initial measurements (2026-05-24, S03 run):
  /                          mean = <Xa> ms, σ/μ = <Ya>
  /project/{id}/queue        mean = <Xb> ms, σ/μ = <Yb>
  /project/{id}/batches      mean = <Xc> ms, σ/μ = <Yc>
  /project/{id}/jobs         mean = <Xd> ms, σ/μ = <Yd>
  /project/{id}/code         mean = <Xe> ms, σ/μ = <Ye>
"""
import pytest

BUDGET_MS_HOME = <ceil(Xa * 1.5)>
BUDGET_MS_QUEUE = <ceil(Xb * 1.5)>
BUDGET_MS_BATCHES = <ceil(Xc * 1.5)>
BUDGET_MS_JOBS = <ceil(Xd * 1.5)>
BUDGET_MS_CODE = <ceil(Xe * 1.5)>

ROUTES = [
    ("/", BUDGET_MS_HOME, "home"),
    ("/project/{project_id}/queue", BUDGET_MS_QUEUE, "queue"),
    ("/project/{project_id}/batches", BUDGET_MS_BATCHES, "batches"),
    ("/project/{project_id}/jobs", BUDGET_MS_JOBS, "jobs"),
    ("/project/{project_id}/code", BUDGET_MS_CODE, "code"),
]


@pytest.mark.parametrize("route_template,budget_ms,label", ROUTES, ids=[r[2] for r in ROUTES])
def test_dashboard_route_p50_within_budget(benchmark, dashboard_test_client, project_id, route_template, budget_ms, label):
    url = route_template.format(project_id=project_id)
    # warmup outside benchmark
    for _ in range(3):
        dashboard_test_client.get(url)
    benchmark.pedantic(
        lambda: dashboard_test_client.get(url),
        rounds=10,
        warmup_rounds=0,  # already warmed above
    )
    p50_ms = benchmark.stats.stats.median * 1000
    assert p50_ms < budget_ms, (
        f"{label} route p50 {p50_ms:.1f} ms exceeds budget {budget_ms} ms"
    )
```

`dashboard_test_client` fixture builds the FastAPI app against the `seeded_orch_db` session-scoped fixture; `project_id` returns the seeded project's ID.

Save baseline:

```bash
uv run pytest tests/perf/test_dashboard_routes.py -v --benchmark-save=routes --benchmark-storage=file://tests/perf/baselines -m perf --no-cov
```

The concrete file is `tests/perf/baselines/<machine-id>/NNNN_routes.json` (e.g. `tests/perf/baselines/Linux-CPython-3.13-64bit/0001_routes.json`). Commit the whole subtree.

### 3. Add Makefile targets

All in `.PHONY`:

```makefile
.PHONY: test-perf test-perf-rag test-perf-routes test-perf-update-baseline

test-perf-rag:  ## Run RAG query performance budget test
	uv run pytest tests/perf/test_rag_query.py -v --benchmark-compare=rag --benchmark-compare-fail=mean:25% --benchmark-storage=file://tests/perf/baselines -m perf --no-cov

test-perf-routes:  ## Run dashboard routes performance budget tests (5 routes)
	uv run pytest tests/perf/test_dashboard_routes.py -v --benchmark-compare=routes --benchmark-compare-fail=mean:25% --benchmark-storage=file://tests/perf/baselines -m perf --no-cov

test-perf: test-perf-daemon test-perf-rag test-perf-routes  ## Run all performance budget tests (umbrella)

test-perf-update-baseline:  ## OPERATOR-ONLY: regenerate committed perf baselines (requires CR review before commit per CR-00083)
	@echo ">>> WARNING: Baseline updated locally — commit requires CR review per CR-00083 Notes section"
	uv run pytest tests/perf/test_daemon_poll_loop.py -v --benchmark-save=daemon --benchmark-storage=file://tests/perf/baselines -m perf --no-cov
	uv run pytest tests/perf/test_rag_query.py -v --benchmark-save=rag --benchmark-storage=file://tests/perf/baselines -m perf --no-cov
	uv run pytest tests/perf/test_dashboard_routes.py -v --benchmark-save=routes --benchmark-storage=file://tests/perf/baselines -m perf --no-cov
```

Add all four targets to the top-level `.PHONY` aggregation list.

### 4. RED-first evidence

`tdd_red_evidence` must record initial measurements + budgets + final-green pass for BOTH modules in the same field, e.g.:

> `RAG query initial mean = <X> s (σ/μ = <Y>) → BUDGET_S = <Z>; final mean = <W> < Z. Dashboard routes initial p50 = {home: <Xa>, queue: <Xb>, batches: <Xc>, jobs: <Xd>, code: <Xe>} ms → BUDGETs = {<Za>, <Zb>, <Zc>, <Zd>, <Ze>}; all 5 routes pass.`

## Project Conventions

Read CLAUDE.md and `docs/IW_AI_Core_Testing_Strategy.md`. Reuse the `seeded_orch_db` session-scoped fixture from S02's `tests/perf/conftest.py`. Do NOT spin up a new testcontainer per test — that destroys perf budget validity.

## TDD Requirement

Same as S02 — the perf tests ARE the RED-first behavioural artefacts. The initial-measurement → budget-set → final-green narrative is your RED evidence.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format` — auto-fix on touched files.
2. `make typecheck` — zero errors on touched files.
3. `make lint` — zero errors on touched files.

## Test Verification (NON-NEGOTIABLE)

Run ONLY:

```bash
uv run pytest tests/perf/test_rag_query.py tests/perf/test_dashboard_routes.py -v --benchmark-storage=file://tests/perf/baselines -m perf --no-cov
make test-perf  # confirm umbrella target chains correctly
```

Do NOT run `make test-unit`, `make test-integration`, or `make check`.

## Scope discipline (CR-00083 hard rule)

NO production code changes under `orch/`, `dashboard/`, `executor/`, `scripts/`, `bin/`, `templates/`. If your work suggests a production-code change, STOP and raise a blocker.

Files you are permitted to touch:
- `tests/perf/test_rag_query.py` (new)
- `tests/perf/test_dashboard_routes.py` (new)
- `tests/perf/baselines/<machine-id>/NNNN_rag.json` (new — generated by pytest-benchmark)
- `tests/perf/baselines/<machine-id>/NNNN_routes.json` (new — generated by pytest-benchmark)
- `Makefile`

Files you may READ from S01/S02's deliverables (do NOT modify):
- `tests/perf/__init__.py`
- `tests/perf/conftest.py`
- `tests/perf/test_daemon_poll_loop.py`
- `tests/perf/baselines/<machine-id>/NNNN_daemon.json`
- `pyproject.toml`
- `uv.lock`

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "backend-impl",
  "work_item": "CR-00083",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/perf/test_rag_query.py",
    "tests/perf/test_dashboard_routes.py",
    "tests/perf/baselines/<machine-id>/NNNN_rag.json",
    "tests/perf/baselines/<machine-id>/NNNN_routes.json",
    "Makefile"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "6 passed (1 rag + 5 parametrized routes), 0 failed",
  "tdd_red_evidence": "RAG initial mean = <X> s, BUDGET_S = <Z>, final pass at <W>. Routes initial p50s = {...}, BUDGETs = {...}, all 5 pass.",
  "blockers": [],
  "notes": "RAG embedding stubbed deterministically (tmp_path LanceDB); dashboard routes warmed up x3 outside measurement; umbrella `make test-perf` verified chains all 3 modules. Baseline files: <full paths>."
}
```
