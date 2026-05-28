# CR-00093_S01_Backend_prompt

**Work Item**: CR-00093 -- Register all test-enhancement Makefile suites as launchable dashboard cards
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY docker commands that change container/volume/network state. Testcontainers from pytest fixtures and read-only introspection (`docker ps`, `docker inspect`, `docker logs`) are the only exceptions. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This step adds NO migration. Do NOT run alembic. Do NOT touch `orch/db/migrations/versions/**`.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00093 --json`.
- `ai-dev/active/CR-00093/CR-00093_CR_Design.md` — Design document (read AC1–AC7 — every one is exercised here).
- `.iw-orch.json` — the file you will edit (test_config.categories + quality_config.categories blocks).
- `Makefile` — to verify every referenced target exists.
- `orch/daemon/project_registry.py` — to confirm the sync code path you will dry-run.
- `dashboard/routers/tests.py` — for the `e2e_stack` semantics + the `_get_test_config()` reader.
- `dashboard/routers/_run_helpers.py` — for `build_category_cards()` (which `group` / `bundle` fields it consumes).
- `ai-dev/work/TESTS_ENHANCEMENT.md` — §8 row to add + §11 changelog entry to prepend.

## Output Files

- `ai-dev/work/CR-00093/reports/CR-00093_S01_Backend_report.md`.
- Edits to `.iw-orch.json` and `ai-dev/work/TESTS_ENHANCEMENT.md`.

## Context

You are wiring 21 new test suites + 9 new quality gates into the dashboard launcher by extending two JSON blocks in `.iw-orch.json`. The dashboard route handlers + the `build_category_cards()` helper are already registry-driven — no Python edit is required. After this CR merges and an operator runs `./ai-core.sh daemon reload`, `project_registry.py:_read_iw_orch_json()` reloads the file and `project.config['test_config']` / `quality_config` in the `iw-ai-core` row gain the new entries.

## Requirements

### 1. Read the design + verify the wiring landscape

Read `ai-dev/active/CR-00093/CR-00093_CR_Design.md` end-to-end, especially AC1–AC7 and the Impact-Analysis tables.

Open `.iw-orch.json` and locate the existing `test_config.categories` (3 entries: unit, integration, all) and `quality_config.categories` (4 entries: lint, format, typecheck, all-quality) blocks. Note the exact key ordering of an existing entry (`label`, `command`, `description`, `group`, optional `bundle`) — match that ordering in every new entry for clean diffs.

Open `dashboard/routers/_run_helpers.py` and confirm `build_category_cards()` reads `cat.get("bundle", False)` and tolerates arbitrary `group` strings. Open `dashboard/routers/tests.py` and read `_find_running_e2e_stack_test()` to confirm it iterates every category with `e2e_stack=true` (the mutual-exclusion check scales to ≥2 categories).

### 2. Edit `.iw-orch.json` — extend `test_config.categories`

Add the following 21 NEW entries to the existing block. Place them in the order given (groups together, alphabetical within group, for diff readability). DO NOT remove or reorder the existing 3 entries.

**Group `backend`** (11 entries):

```json
"smoke": {
  "label": "Smoke (≤15 tests, <60 s SLA)",
  "command": "make smoke",
  "description": "Curated critical-path smoke suite. 5 paths: daemon worktree start, dashboard main pages, iw next-id, item queue, /healthz. CR-00052.",
  "group": "backend"
},
"properties": {
  "label": "Property Tests (Hypothesis, ci profile)",
  "command": "make test-properties",
  "description": "Hypothesis state-machine + @given properties on work-item / batch / fix-cycle / doc-diff / id-allocation. ci profile (20 examples, ~1.5 s). CR-00060.",
  "group": "backend"
},
"properties-deep": {
  "label": "Property Tests (Hypothesis, deep profile)",
  "command": "make test-properties-deep",
  "description": "Hypothesis deep profile — more examples, longer deadlines. ~minutes. CR-00060.",
  "group": "backend"
},
"quarantine": {
  "label": "Quarantine / Flaky (with reruns)",
  "command": "make test-quarantine",
  "description": "Run tests marked @pytest.mark.quarantine with rerunfailures. Informational — does NOT block. CR-00061.",
  "group": "backend"
},
"flake-detect": {
  "label": "Flake Detection (3-run aggregator)",
  "command": "make test-flake-detect",
  "description": "Run the full suite 3× and aggregate flakes. ~3× wall-clock of test-integration. CR-00061.",
  "group": "backend"
},
"cli-contract": {
  "label": "iw CLI Contract",
  "command": "make test-cli-contract",
  "description": "Per-command exit-code / stdout / DB-effect tests for the 6 priority iw commands + bidirectional spec-conformance check. CR-00073.",
  "group": "backend"
},
"isolation": {
  "label": "Cross-Project Isolation Matrix",
  "command": "make test-isolation",
  "description": "Dual-project matrix proving no leakage across routes / iw commands / per-worktree DB boundary. CR-00074.",
  "group": "backend"
},
"security-module": {
  "label": "Security Test Module",
  "command": "make test-security-module",
  "description": "Live-DB write guard + authz negative paths + doc-render SSRF / path-traversal + agent-context env handling. CR-00075.",
  "group": "backend"
},
"data-layer": {
  "label": "Data Layer (FTS + migration round-trip + DB-identity)",
  "command": "make data-layer-check",
  "description": "FTS-trigger invariants + migration revision-skew regression (pins I-00075/76) + DB-identity. CR-00076.",
  "group": "backend"
},
"route-sweep": {
  "label": "Dashboard Route Sweep (no-5xx)",
  "command": "make test-route-sweep",
  "description": "Every dashboard GET/HEAD route asserted < 500 against a seeded TestClient. CR-00072.",
  "group": "backend"
},
"contract-fuzz": {
  "label": "Schemathesis JSON API Fuzz",
  "command": "make test-contract-fuzz",
  "description": "schemathesis property-fuzz of JSON endpoints against OpenAPI schema. Nightly-class — non-blocking. CR-00072.",
  "group": "backend"
},
```

**Group `quality`** (1 entry):

```json
"test-assertions": {
  "label": "Assertion Scanner",
  "command": "make test-assertions",
  "description": "AST scanner for no-assert / tautology / mock-only / broad pytest.raises. Frozen baseline at tests/assertion_free_baseline.txt. CR-00046.",
  "group": "quality"
},
```

**Group `e2e`** (2 entries — BOTH carry `e2e_stack: true`):

```json
"e2e-smoke": {
  "label": "E2E Browser Smoke (2 journeys, blocking)",
  "command": "make test-e2e-smoke",
  "description": "Subset of the E2E browser-journey matrix — home-navigation + queue-to-merge. Blocking on PR. F-00088.",
  "group": "e2e",
  "e2e_stack": true
},
"e2e": {
  "label": "E2E Browser Full (6 journeys)",
  "command": "make test-e2e",
  "description": "Full 6-journey browser-journey matrix — home, queue→merge, code-QA SSE, docs export, jobs filters, htmx fragments. ~minutes. F-00088.",
  "group": "e2e",
  "e2e_stack": true
},
```

**Group `perf`** (4 entries):

```json
"perf": {
  "label": "Performance Budgets (all)",
  "command": "make test-perf",
  "description": "pytest-benchmark assertions on daemon poll-loop, RAG query, dashboard routes. Regression alerts at +25% vs baselines. CR-00083.",
  "group": "perf"
},
"perf-daemon": {
  "label": "Performance — Daemon Poll Loop",
  "command": "make test-perf-daemon",
  "description": "One Daemon._poll_cycle() iteration vs seeded testcontainer DB. CR-00083.",
  "group": "perf"
},
"perf-rag": {
  "label": "Performance — RAG Query",
  "command": "make test-perf-rag",
  "description": "One CodeQA.answer_stream call vs in-memory LanceDB + stub embedding. CR-00083.",
  "group": "perf"
},
"perf-routes": {
  "label": "Performance — Dashboard Routes",
  "command": "make test-perf-routes",
  "description": "p50 latency across home + queue + batches + jobs + code routes. CR-00083.",
  "group": "perf"
},
```

**Group `chaos`** (2 entries):

```json
"daemon-chaos-smoke": {
  "label": "Daemon Chaos Smoke (2 scenarios)",
  "command": "make daemon-chaos-smoke",
  "description": "Deterministic chaos: worktree-setup-mid-fail + fix-cycle-cap. PR-blocking. F-00089.",
  "group": "chaos"
},
"daemon-chaos-full": {
  "label": "Daemon Chaos Full (~minutes, 5-scenario matrix)",
  "command": "make daemon-chaos-full",
  "description": "Full chaos matrix: worktree-setup-mid-fail, fix-cycle-cap, agent-stall, squash-merge-conflict, migration-rebase-fail. ~minutes. Nightly-class. F-00089.",
  "group": "chaos"
},
```

**Group `visual`** (1 entry):

```json
"visual-regression": {
  "label": "Visual Regression (HTML + PDF baselines)",
  "command": "make visual-regression",
  "description": "pixelmatch vs committed baselines — 4 PDFs + 4 HTML pages. Nightly + path-filtered PR. CR-00082.",
  "group": "visual"
}
```

After insertion, the `test_config.categories` block contains exactly 24 entries (3 existing + 21 new). Confirm by running:

```bash
python -c "import json; d = json.load(open('.iw-orch.json')); print(len(d['test_config']['categories']))"
# Expected: 24
```

### 3. Edit `.iw-orch.json` — extend `quality_config.categories`

Add the following 9 NEW entries to the existing block (existing 4 stay untouched).

**Group `docs`** (1 entry):

```json
"check-column-docs": {
  "label": "DB Column Doc Scanner",
  "command": "make check-column-docs",
  "description": "Walks Base.registry.mappers and flags Column declarations lacking doc=. Becomes blocking after CR-00092 baseline scrub. CR-00085.",
  "group": "docs"
},
```

**Group `security`** (3 entries):

```json
"security-secrets": {
  "label": "Secret Scan (gitleaks)",
  "command": "make security-secrets",
  "description": "gitleaks against working tree + history. Blocking. CR-00050.",
  "group": "security"
},
"security-sast": {
  "label": "SAST (Semgrep)",
  "command": "make security-sast",
  "description": "Semgrep with p/python + p/owasp-top-ten + p/security-audit rulesets. Blocking. CR-00050 + CR-00051.",
  "group": "security"
},
"security-deps": {
  "label": "Dependency Audit (bandit + pip-audit)",
  "command": "make security-deps",
  "description": "bandit (Python-specific SAST) + pip-audit (CVE lookup against PyPI advisory DB).",
  "group": "security"
},
```

**Group `coverage`** (3 entries):

```json
"diff-coverage": {
  "label": "Diff Coverage (≥90% on PR-changed lines)",
  "command": "make diff-coverage",
  "description": "diff-cover vs origin/main. Builds combined unit+integration coverage internally. Blocking on PR. CR-00047.",
  "group": "coverage"
},
"mutation-check": {
  "label": "Mutation Check (changed files)",
  "command": "make mutation-check",
  "description": "mutmut on changed-files only, cache-warmed from main. On-demand today (CR-00080 viability guard fired M=0%, K=55).",
  "group": "coverage"
},
"mutation-audit": {
  "label": "Mutation Audit (~1h, full orch/)",
  "command": "make mutation-audit",
  "description": "Full mutmut audit over all of orch/. ~1h wall-clock. Intended for nightly CI; ad-hoc launch only when investigating mutation score. CR-00059 + CR-00080.",
  "group": "coverage"
},
```

**Group `hygiene`** (2 entries):

```json
"dead-code": {
  "label": "Dead Code (vulture)",
  "command": "make dead-code",
  "description": "vulture with min_confidence=70 over orch + dashboard + executor + scripts. Warn-only today. CR-00048.",
  "group": "hygiene"
},
"dep-check": {
  "label": "Dependency Hygiene (deptry)",
  "command": "make dep-check",
  "description": "deptry — unused, missing, transitive, misplaced deps. Warn-only today. CR-00048.",
  "group": "hygiene"
}
```

After insertion, the `quality_config.categories` block contains exactly 13 entries (4 existing + 9 new). Confirm:

```bash
python -c "import json; d = json.load(open('.iw-orch.json')); print(len(d['quality_config']['categories']))"
# Expected: 13
```

### 4. Verify every referenced Makefile target exists

For each of the 30 new `command` strings, confirm the target exists:

```bash
for target in smoke test-properties test-properties-deep test-quarantine test-flake-detect test-cli-contract test-isolation test-security-module data-layer-check test-route-sweep test-contract-fuzz test-assertions test-e2e-smoke test-e2e test-perf test-perf-daemon test-perf-rag test-perf-routes daemon-chaos-smoke daemon-chaos-full visual-regression check-column-docs security-secrets security-sast security-deps diff-coverage mutation-check mutation-audit dead-code dep-check; do
  grep -qE "^${target}:" Makefile || echo "MISSING: $target"
done
# Expected: no MISSING lines printed.
```

If any target is missing, STOP — the design's premise is wrong and the operator needs to know which suite was assumed but doesn't exist.

### 5. Dry-run the registry sync

Confirm `project_registry.py` can still parse `.iw-orch.json` after your edits:

```bash
python -c "
from pathlib import Path
import json
data = json.load(open('.iw-orch.json'))
assert 'test_config' in data and 'categories' in data['test_config']
assert 'quality_config' in data and 'categories' in data['quality_config']
t = data['test_config']['categories']
q = data['quality_config']['categories']
print(f'test_config.categories = {len(t)} entries: {sorted(t.keys())}')
print(f'quality_config.categories = {len(q)} entries: {sorted(q.keys())}')
# every test category has the required fields
for name, cfg in t.items():
    assert 'label' in cfg, f'{name}: missing label'
    assert 'command' in cfg, f'{name}: missing command'
    assert 'group' in cfg, f'{name}: missing group'
# e2e_stack scoped correctly
e2e = [n for n, c in t.items() if c.get('e2e_stack')]
assert set(e2e) == {'e2e', 'e2e-smoke'}, f'unexpected e2e_stack scope: {e2e}'
print('OK')
"
```

This proves the file parses, every required field is present, and `e2e_stack=true` is scoped to exactly the two E2E categories. Capture the output verbatim in your report.

Then exercise the real `project_registry.py` code path against the edited file (read-only — no SIGHUP, no DB write):

```bash
python -c "
from orch.daemon.project_registry import _read_iw_orch_json
data = _read_iw_orch_json('/home/sergiog/dev/iw-doc-plan/main/iw-ai-core')
print(f\"test categories: {sorted(data['test_config']['categories'].keys())}\")
print(f\"quality categories: {sorted(data['quality_config']['categories'].keys())}\")
"
```

### 6. Update `ai-dev/work/TESTS_ENHANCEMENT.md`

Append a new row to §8 (Phase 4 table) at the end:

```markdown
| 4.9 | Dashboard launcher surface | The 21 new test suites + 9 new quality gates added by Phases 0–4 were Makefile / CI only — invisible to the dashboard Tests / Quality launcher | Extend `.iw-orch.json` `test_config.categories` and `quality_config.categories` with all suites grouped by area (backend, e2e, perf, chaos, visual, docs, security, coverage, hygiene); render via the existing registry-driven cards (zero Python change). Sibling projects out of scope. | CR | ✅ DONE 2026-05-28 (CR-00093) | CR-00093 |
```

Add a new top entry to §11 (Changelog):

```markdown
- **2026-05-28** — **CR-00093 shipped (Phase-4 item 4.9 — dashboard launcher surface).** Extended `iw-ai-core`'s `.iw-orch.json` with 21 new `test_config.categories` entries (smoke, properties, properties-deep, quarantine, flake-detect, cli-contract, isolation, security-module, data-layer, route-sweep, contract-fuzz, test-assertions, e2e-smoke, e2e, perf, perf-daemon, perf-rag, perf-routes, daemon-chaos-smoke, daemon-chaos-full, visual-regression — grouped under backend / quality / e2e / perf / chaos / visual) and 9 new `quality_config.categories` entries (check-column-docs, security-secrets, security-sast, security-deps, diff-coverage, mutation-check, mutation-audit, dead-code, dep-check — grouped under docs / security / coverage / hygiene). `e2e_stack=true` on `e2e` + `e2e-smoke` only (mutual-exclusion via shared docker ports). Heavy suites carry wall-clock hints in their description. Zero Python change — the dashboard's `build_category_cards()` is registry-driven. Browser-verified at S11 (qv-browser): all 24 test cards + 13 quality cards render under their groups; clicking a new card produces a TestRun row. Sibling projects (IW-AI-DEV, InnoForge, podforger, cv) out of scope — they own their own `.iw-orch.json` and can copy the pattern when ready. Operator step post-merge: `./ai-core.sh daemon reload` to refresh the production daemon's `project.config`.
```

Bump the header version line `> **Status**: living plan — v1.8 (2026-05-28)` → `v1.9 (2026-05-28)` and adjust the "Current status" paragraph to mention the launcher-gap closure.

### 7. Targeted test verification

Run the dashboard-route-contract sweep (which exercises the Tests / Quality launch pages) — this proves no regression in the pages that will render the new cards:

```bash
uv run pytest tests/dashboard/test_route_contract_sweep.py -v --no-cov
```

All tests must pass. Do NOT run the full `make test-integration` — that's S08's QV gate.

## Project Conventions

Read the project's `CLAUDE.md` and `dashboard/CLAUDE.md` for context. Key invariants:
- `.iw-orch.json` is JSON, not TOML — match existing key ordering exactly.
- The dashboard is registry-driven; do NOT add Python code to render the new cards.

## Pre-flight Quality Gates — same as every step

1. `make format` 2. `make typecheck` 3. `make lint`

## TDD Requirement

```
"tdd_red_evidence": "n/a — config-only registry edit; no new behavioural tests. The existing tests/dashboard/test_route_contract_sweep.py covers the Tests / Quality launch pages."
```

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "CR-00093",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    ".iw-orch.json",
    "ai-dev/work/TESTS_ENHANCEMENT.md"
  ],
  "preflight": {"format": "...", "typecheck": "...", "lint": "..."},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed (tests/dashboard/test_route_contract_sweep.py)",
  "tdd_red_evidence": "n/a — config-only registry edit; no new behavioural tests",
  "test_categories_total": 24,
  "quality_categories_total": 13,
  "new_test_categories": 21,
  "new_quality_categories": 9,
  "e2e_stack_categories": ["e2e", "e2e-smoke"],
  "missing_makefile_targets": [],
  "blockers": [],
  "notes": "All 30 new categories added; every Makefile target exists; e2e_stack scoped to exactly 2 entries; registry sync code path dry-run output captured in report."
}
```
