# CR-00083_S03_Backend_prompt

**Work Item**: CR-00083 -- Performance-budget test layer — pytest-benchmark assertions with regression-alert baselines
**Step**: S03
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

Standard policy. This step touches no containers.

## ⛔ Migrations: agents generate, daemon applies

This CR adds **no** migrations.

## Input Files

- `uv run iw item-status CR-00083 --json` — runtime step state.
- `ai-dev/work/CR-00083/CR-00083_CR_Design.md` — design document.
- `ai-dev/work/CR-00083/reports/CR-00083_S01_Backend_report.md` — initial daemon measurement + budget recorded here.
- `ai-dev/work/CR-00083/reports/CR-00083_S02_Backend_report.md` — initial RAG + routes measurements + budgets recorded here.
- `.github/workflows/e2e.yml` and `.github/workflows/test-quality.yml` — existing workflow patterns to mirror (uv setup, artifact upload, PR-comment mechanisms).
- `docs/IW_AI_Core_Testing_Strategy.md` — strategy doc to update (§2, §5, §9, §11).
- `skills/iw-ai-core-testing/SKILL.md` — skill to update (§4).
- `.claude/skills/iw-ai-core-testing/SKILL.md` — sync target.
- `ai-dev/work/TESTS_ENHANCEMENT.md` — tracker (§8 row 4.2, v1.3 header → v1.4, §11 changelog).

## Output Files

- `ai-dev/work/CR-00083/reports/CR-00083_S03_Backend_report.md` — step report.

## Context

You are implementing **S03** of CR-00083 — the nightly CI workflow, strategy doc, skill doc, and tracker updates. This step ties the deliverables of S01 and S02 into the project's documented test-layer story.

## Requirements

### 1. Create `.github/workflows/perf-budgets.yml`

Triggers:
- `schedule: - cron: '17 3 * * *'` (nightly 03:17 UTC — offset from sibling workflows).
- `workflow_dispatch:` (manual trigger for operator-on-demand runs).
- **NO `pull_request` trigger** — per intake, per-PR perf measurement is too noisy.

Job structure (single `perf-budgets` job on `ubuntu-latest`):

1. `actions/checkout@v4`
2. Install `uv` (mirror the pattern in `e2e.yml` or `test-quality.yml`).
3. `uv sync --all-extras --dev`
4. `make test-perf` (main step — produces baseline-compare output and fails on regression > 25%).
5. `actions/upload-artifact@v4` with `if: always()` uploading `.benchmarks/**` and `tests/perf/baselines/**` (the latter for diff context).
6. Final step `if: failure()` — append a one-line entry to a "Perf regression follow-ups" subsection in `ai-dev/work/TESTS_ENHANCEMENT.md` referencing the workflow run URL. Use the same PR-creation pattern as existing workflows that append to tracker files (look at `e2e.yml` / `test-quality.yml` for the `peter-evans/create-pull-request` or `gh pr create` pattern). The entry format:

   ```
   - YYYY-MM-DD — Perf regression detected (nightly run): <workflow-run-url>. See artifact `perf-benchmarks` for diff. Investigate and either fix the regression or, if intentional, file a CR to update the baseline.
   ```

Match the GitHub Actions permissions model used in `e2e.yml` (probably `contents: write`, `pull-requests: write`).

### 2. Update `docs/IW_AI_Core_Testing_Strategy.md`

Four surgical edits:

**§2 (Test layers)** — append a new subsection AFTER the existing Layer 7 entry:

```markdown
### Layer 8 — Performance budgets (`tests/perf/` — CR-00083, 2026-05-24)

Three modules under `tests/perf/` measure wall-clock latency against committed baselines:

- `test_daemon_poll_loop.py` — one `Daemon._poll_cycle()` iteration against a seeded testcontainer DB.
- `test_rag_query.py` — one `CodeQA.answer_stream` invocation against an in-memory LanceDB fixture with a deterministic stub embedding (no Ollama dependency — opposite stance to `tests/integration/rag/`'s skip hook).
- `test_dashboard_routes.py` — p50 over ≥10 runs (parametrized) for `/`, `/project/{id}/queue`, `/project/{id}/batches`, `/project/{id}/jobs`, `/project/{id}/code`.

**Budget methodology**: each module declares a module-level constant set to `initial_measurement × 1.5` (50% headroom). Default to `mean`; switch to `min` only when initial σ/μ > 0.3 (record the ratio in the module docstring). The pytest-benchmark `--benchmark-compare-fail=mean:25%` regression threshold is the START value — operators may ratchet it down as baselines stabilise, NEVER silently relax it.

**Baseline-update policy**: baselines live under `tests/perf/baselines/` and are committed. `make test-perf-update-baseline` regenerates them locally; committing the regenerated baselines requires a CR review (no automated baseline updates from CI). This prevents a regression from being silently absorbed into the new baseline.

**Run targets**: `make test-perf-daemon` / `make test-perf-rag` / `make test-perf-routes` for individual modules; `make test-perf` for the umbrella. Excluded from `make test-unit` / `make test-integration` via the `perf` marker + `addopts` filter.

**CI surface**: nightly only via `.github/workflows/perf-budgets.yml` (`schedule` + `workflow_dispatch`); NOT on PR per intake (runner variance makes per-PR perf measurement too noisy). On regression, the workflow appends a follow-up entry to this tracker.
```

**§5 (Quality gates)** — append a new row to the gates table:

```
| `perf-budgets` (nightly) | `make test-perf` | `tests/perf/**` | nightly + dispatch | regression > 25% mean fails | CR-00083 |
```

(Match the table's existing column layout — adjust columns to fit.)

**§9 (Known gaps & roadmap)** — flip the row for item 4.2:

Before:
```
| 4.2 | Performance budgets | TODO |
```

After:
```
| 4.2 | Performance budgets | ✅ DONE — CR-00083 (2026-05-24) |
```

(Match the actual table format in the doc.)

**§11 (Changelog)** — append a new dated entry at the END of the section:

```markdown
### 2026-05-24 — Layer 8 performance budgets shipped (CR-00083)

Phase 4 first item. `tests/perf/` package with 3 modules (daemon poll-loop, RAG query, dashboard routes); committed baselines per module under `tests/perf/baselines/`; 5 Makefile targets (`test-perf-daemon`, `test-perf-rag`, `test-perf-routes`, `test-perf`, `test-perf-update-baseline`); nightly `.github/workflows/perf-budgets.yml` (cron + `workflow_dispatch`, NOT on PR). Regression threshold `mean:25%` — start value, ratchetable. Test-only, no production code change.
```

### 3. Update `skills/iw-ai-core-testing/SKILL.md`

Add a new subsection in §4 (after the existing "Property-based tests" subsection or wherever §4's structure best accommodates it):

```markdown
### Performance budgets (CR-00083, Phase 4 item 4.2)

When adding a perf test for a new hot path:

1. **Where**: `tests/perf/test_<area>.py`. The package is marker-isolated (`perf`) and excluded from default unit/integration runs.
2. **Budget choice**: measure 10 times in a quiet environment, set `BUDGET = initial_mean × 1.5` as a module-level constant. Document the σ/μ ratio in the module docstring. Default to asserting `mean < BUDGET`; switch to `min < BUDGET` only when σ/μ > 0.3 (and explain why in the docstring).
3. **Assertion strength**: a perf test must assert against the specific BUDGET constant — NOT against `pytest-benchmark`'s `--benchmark-compare-fail` flag alone. The flag is a regression gate; the explicit `assert <stat> < BUDGET` is the absolute upper bound. Forbidden: `assert mean > 0`, `assert min < float('inf')`, `assert ratio >= 0` — these are tautologies the assertion scanner will flag.
4. **Baselines**: committed under `tests/perf/baselines/` per module. Operator-only regeneration via `make test-perf-update-baseline`; committing a regenerated baseline requires a CR review (no silent re-baselining of regressions).
5. **External deps**: a perf test must NOT depend on a live external service (Ollama, GH API, etc.) — stub it deterministically. The RAG perf test takes the opposite stance to `tests/integration/rag/`'s skip-when-no-Ollama hook precisely so it ALWAYS runs.
6. **CI**: nightly only via `.github/workflows/perf-budgets.yml`. Do NOT add perf tests to PR-blocking gates — runner variance makes per-PR signal too noisy.
```

Then run:

```bash
uv run iw sync-skills --force iw-ai-core-testing
diff skills/iw-ai-core-testing/SKILL.md .claude/skills/iw-ai-core-testing/SKILL.md
```

Verify the diff is empty (byte-identical mirror).

### 4. Update `ai-dev/work/TESTS_ENHANCEMENT.md`

Three surgical edits:

**§8 row 4.2** — flip from:
```
| 4.2 | Performance budgets | ... | ... | CR | TODO | |
```
to:
```
| 4.2 | Performance budgets | ... | ... | CR | ✅ DONE — CR-00083 (2026-05-24): Layer 8 (`tests/perf/`) with 3 modules + nightly workflow + threshold 25% start | CR-00083 |
```

(Match the existing row's column structure.)

**v1.3 header status block** — bump to v1.4. The current header begins "Current status (2026-05-24): Phases 0, 1, 2, and 3 are all complete...". Insert a sentence into the "Next pickup" section noting **Phase 4 first item shipped (CR-00083 — perf budgets, 2026-05-24)**; the remaining Phase 4 items (4.3 chaos, 4.8 mutmut blocking, etc.) stay TODO. Keep the prose tight — one sentence added, header version bumped from v1.3 to v1.4 at the top.

**§11 (Changelog)** — prepend a new dated entry at the top (newest first, matching the file's existing order):

```markdown
- **2026-05-24** — **CR-00083 shipped (Phase 4 item 4.2 — Performance-budget test layer).** New package `tests/perf/` with three modules: `test_daemon_poll_loop.py` (one `Daemon._poll_cycle()` iteration vs seeded testcontainer DB), `test_rag_query.py` (one `CodeQA.answer_stream` vs in-memory LanceDB + deterministic stub embedding — no Ollama dependency), `test_dashboard_routes.py` (p50 over ≥10 runs across `/`, `/project/{id}/queue`, `/project/{id}/batches`, `/project/{id}/jobs`, `/project/{id}/code`). Committed baselines under `tests/perf/baselines/` per module. 5 Makefile targets: `test-perf-daemon`, `test-perf-rag`, `test-perf-routes`, `test-perf` (umbrella), `test-perf-update-baseline` (operator-only — committing regenerated baselines requires CR review). Nightly `.github/workflows/perf-budgets.yml` (cron `17 3 * * *` + `workflow_dispatch`; NOT on PR per intake). Regression threshold `mean:25%` — start value, ratchetable. `pytest-benchmark>=4.0,<5` added to `[dependency-groups] dev`; `perf` marker registered + excluded from default runs via `addopts`. Strategy doc §2 grows new Layer 8, §5 grows nightly perf-budgets gate row, §9 row 4.2 flips ✅, §11 changelog updated. Skill `iw-ai-core-testing` §4 grows new "Performance budgets" subsection; `iw sync-skills` makes `.claude/skills/` byte-identical. **Test-only, NO production code change** — the precedent that genuine regressions surface as Incidents (not in-CR fixes) applies; budgets are observation-only.
```

## Project Conventions

Read CLAUDE.md for the skill-sync rules (`iw sync-skills`) and the strategy-doc conventions. The §2/§5/§9/§11 quadruple edit is the standard pattern from CR-00072/73/74/75/76 — mirror their cross-surface consistency exactly (same date, same CR-ID, same one-line summary across all four surfaces).

## TDD Requirement

This step is doc + workflow YAML + skill sync. Use:

> `tdd_red_evidence: "n/a — docs/CI/skill/tracker updates only; no production logic added"`

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format` — auto-fix on touched files (the workflow YAML and markdown have their own formatting rules — verify lint doesn't trip on them).
2. `make typecheck` — N/A for this step's files; should pass.
3. `make lint` — must pass; the new workflow YAML may trigger YAML-lint via the templates check — fix if so.

## Test Verification

No targeted tests for this step. Skill sync verification:

```bash
diff skills/iw-ai-core-testing/SKILL.md .claude/skills/iw-ai-core-testing/SKILL.md  # must be empty
```

Workflow YAML syntax verification (if `actionlint` or similar is in the project):

```bash
# inspect .github/workflows/perf-budgets.yml manually — confirm cron + workflow_dispatch + no pull_request triggers
grep -E "^(on:|  schedule:|  workflow_dispatch:|  pull_request:)" .github/workflows/perf-budgets.yml
# expected output:
# on:
#   schedule:
#   workflow_dispatch:
# (no pull_request line should appear)
```

## Scope discipline

Files you are permitted to touch:
- `.github/workflows/perf-budgets.yml` (new)
- `docs/IW_AI_Core_Testing_Strategy.md`
- `skills/iw-ai-core-testing/SKILL.md`
- `.claude/skills/iw-ai-core-testing/SKILL.md` (regenerated by `iw sync-skills`)
- `ai-dev/work/TESTS_ENHANCEMENT.md`

NO `orch/`, `dashboard/`, `executor/`, `scripts/`, `bin/`, `templates/`, `tests/**`, `pyproject.toml`, `uv.lock`, `Makefile` — those are S01/S02 deliverables and must NOT be re-edited in S03.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "backend-impl",
  "work_item": "CR-00083",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    ".github/workflows/perf-budgets.yml",
    "docs/IW_AI_Core_Testing_Strategy.md",
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
  "test_summary": "n/a — docs/CI/skill/tracker only",
  "tdd_red_evidence": "n/a — docs/CI/skill/tracker updates only; no production logic added",
  "blockers": [],
  "notes": "Skill sync diff verified empty. Workflow YAML has cron + workflow_dispatch only (no pull_request). Strategy doc + skill + tracker all carry 2026-05-24 + CR-00083 + same one-line summary."
}
```
