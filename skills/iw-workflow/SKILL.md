---
name: iw-workflow
version: "2.3.0"
description: IW AI Core workflow orchestration rules, manifest schema, and agent contract definitions. Use when executing work item workflows, parsing agent results, managing fix cycles, or understanding the automated development pipeline.
allowed-tools: Bash
---

# IW Workflow Orchestration Rules

This skill defines the rules for automated workflow execution in the IW AI Core development pipeline.

## Global agent constraints

All step agents MUST respect the rules in `docs/IW_AI_Core_Agent_Constraints.md`.
The orchestrator MUST surface these rules when enumerating constraints for a
step prompt if it is possible to do so programmatically. At minimum: the
"⛔ Docker is off-limits" rule applies to every agent without exception.

Summary of the Docker rule (full text in the policy doc):
- No docker kill / stop / rm / restart
- No docker compose up / down / restart (and the docker-compose v1 variants)
- No docker volume rm / prune
- No docker system / container / image prune
- Exceptions: testcontainers (pytest fixtures), read-only introspection
  (docker ps / inspect / logs), invoking ./ai-core.sh or make targets.

## Platform Architecture

Work items flow through these phases:
1. **Design** — `/iw-new-incident`, `/iw-new-feature`, or `/iw-new-cr` creates design docs + manifest
2. **Register** — `iw register {ID} "title" --type {type} --steps-from workflow-manifest.json`
3. **Approve** — `iw approve {ID}` (human reviews design, then approves)
4. **Batch** — `iw batch-create {ID}` → `iw batch-approve BATCH-001` (daemon picks up)
5. **Execute** — Daemon creates worktree, launches agents per step
6. **Merge** — Daemon squash-merges to main after all steps pass
7. **Archive** — `iw archive {ID}` (design doc → DB, files compressed to .tar.zst)

## workflow-manifest.json Schema

Every work item folder contains a manifest file at `ai-dev/active/{ID}/workflow-manifest.json`:

```json
{
  "id": "F123",
  "type": "Feature|Issue|ChangeRequest",
  "title": "Human-readable title",
  "browser_verification": false,
  "steps": [
    {
      "step": "S01",
      "agent": "backend-impl",
      "description": "Implement backend service and repository",
      "prompt": "prompts/F123_S01_Backend_prompt.md"
    },
    {
      "step": "S02",
      "agent": "qv-gate",
      "gate": "lint",
      "command": "make lint",
      "description": "QV: Linting"
    }
  ]
}
```

**Note**: The manifest defines WHAT to run. The DB tracks state (status, runs, fix cycles).

## Step Granularity Rule (Canonical)

An implementation step MUST target **one cohesive concern** — roughly one module or one closely-related file group. Work spanning several unrelated concerns is split across multiple steps. **Many small steps are preferred over one large step**; a single step bundling unrelated work is the primary failure mode that step-granularity guidance prevents. Documentation, skill, or plan updates that ride along with a code change get **their own step** rather than a tail bolted onto an implementation step.

> **Why this matters**: CR-00076 S01 accumulated tool output across ~6 unrelated deliverables (3 test modules, a Makefile target, 3 documentation/skill/plan updates, quality gates) in one agent session — exceeding the runtime context budget and failing. The fix is to split work into single-concern steps so per-step agent context stays bounded. Small steps can run in parallel; one monolith cannot.

## Agent Mapping

**CRITICAL**: The `"agent"` field in steps MUST use the slug from this table:

| Agent Label (for filenames) | `"agent"` value (in manifest) |
|-----------------------------|-------------------------------|
| Database | `database-impl` |
| Backend | `backend-impl` |
| API | `api-impl` |
| Frontend | `frontend-impl` |
| Tests | `tests-impl` |
| Pipeline | `pipeline-impl` |
| Template | `template-impl` |
| SelfAssess | `self-assess-impl` |
| CodeReview_{X} | `code-review-impl` |
| CodeReview_Final | `code-review-final-impl` |
| CodeReview_FIX_{X} | `code-review-fix-impl` |
| CodeReview_FIX_Final | `code-review-fix-final-impl` |
| QV gate | `qv-gate` (with `gate` + `command` fields) |
| QV browser | `qv-browser` (with `prompt` field) |

**`self-assess-impl` is a soft step.** Failures never block batch_item progression to `merging` — the daemon coerces a `failed` self_assess step to `completed` for batch progression while preserving the actual run status on the StepRun row. No fix cycles are launched for self_assess failures. The step is opt-in per project via `projects.toml`'s `self_assess = true` flag and is injected automatically by the design skills (`/iw-new-feature`, `/iw-new-cr`, `/iw-new-incident`).

## iw CLI State Reporting

During execution (daemon or manual), agents report state via `iw` CLI:

```bash
# Before starting a step:
iw step-start S01 --item F123

# After step completes successfully — ALWAYS include --report:
REPORT_FILE="ai-dev/active/F123/reports/F123_S01_{AgentLabel}_report.md"
mkdir -p "ai-dev/active/F123/reports"
# Write a markdown report to $REPORT_FILE (files changed, test results, notes), then:
iw step-done S01 --item F123 --report $REPORT_FILE

# After step fails:
iw step-fail S01 --item F123 --reason "Code review failed: missing error handling"
```

**The `--report` flag is MANDATORY for every `step-done` call.** Reports are stored in the dashboard so developers can review what each agent did. A step completed without a report is invisible to reviewers.

## Fix Cycle Protocol

When a code review step fails:
1. `iw step-fail S02 --item F123 --reason "Review FAIL: ..."`
2. Daemon creates a fix cycle in DB
3. The implementation step is re-queued (up to `fix_cycle_max` times)
4. After max fix cycles: item moves to `failed` status

**Browser-verification fix cycles can hit a wall the fix-cycle agent cannot climb.** If a `qv-browser` step reports a `code_defect` whose root cause is a file *outside* the item's `scope.allowed_paths` — e.g. a latent crash in a shared template that the item's new fixture data is the first to exercise (see I-00075: `step_pipeline.html` was broken since CR-00039 but only 500-ed once a fixture seeded workflow steps with non-NULL durations) — the fix-cycle agent will burn every cycle and never fix it, because (a) it can't edit the file and (b) the design doc usually says "no production code change needed". When a `qv-browser` failure repeats the same out-of-scope `file:line` across ≥2 fix cycles: stop the loop. File a follow-up incident scoped to that file, and either widen the current item's `scope.allowed_paths` (if the fix is small and clearly in-bounds) or block the current item on the follow-up — don't let it grind to `failed` after 5 wasted cycles.

## QV Gate Steps

QV gates run as shell commands (no LLM):

```json
{"step": "S10", "agent": "qv-gate", "gate": "lint", "command": "make lint", "description": "QV: Linting"},
{"step": "S11", "agent": "qv-gate", "gate": "assertions", "command": "make test-assertions", "description": "QV: Assertion scanner (forbid new vacuous tests)"},
{"step": "S12", "agent": "qv-gate", "gate": "format", "command": "make format-check", "description": "QV: Formatting"},
{"step": "S13", "agent": "qv-gate", "gate": "typecheck", "command": "make type-check", "description": "QV: Type checking"},
{"step": "S14", "agent": "qv-gate", "gate": "unit-tests", "command": "make test-unit", "description": "QV: Unit tests"},
{"step": "S15", "agent": "qv-gate", "gate": "integration-tests", "command": "make test-integration", "description": "QV: Integration tests", "timeout": 1800},
{"step": "S16", "agent": "qv-gate", "gate": "diff-coverage", "command": "make diff-coverage", "description": "QV: Diff coverage (new/changed lines must be well-covered)", "timeout": 1800},
{"step": "S17", "agent": "qv-gate", "gate": "daemon-chaos-smoke", "command": "make daemon-chaos-smoke", "description": "QV: Daemon chaos smoke (S02 + S03 from F-00089)", "timeout": 900}
```

The canonical QV gate chain (in order):

1. `lint` — ruff + `lint-js` + `lint-templates`
2. `assertions` — `scripts/check_test_assertions.py` against `tests/assertion_free_baseline.txt` (CR-00046)
3. `format` — `make format-check` (ruff-format)
4. `typecheck` — `make type-check` (mypy)
5. `unit-tests` — `make test-unit`
6. `integration-tests` — `make test-integration` (was `make allure-integration` — a no-op `.PHONY` stub — until 2026-05-14; see TESTS_ENHANCEMENT.md §10)
7. `diff-coverage` — `make diff-coverage` (CR-00047)
8. `security-secrets` — `make security-secrets` (gitleaks, CR-00050)
9. `daemon-chaos-smoke` — `make daemon-chaos-smoke` (deterministic fault-injection smoke: worktree-setup-mid-failure + fix-cycle-cap-exhaustion; F-00089)

The `assertions` gate (added by CR-00046, Phase-1 P1-CR-A) runs `scripts/check_test_assertions.py` against the committed baseline at `tests/assertion_free_baseline.txt` and fails on **new** vacuous tests (no-assert / tautology / mock-only / `pytest.raises(Exception)` without `match=`). The `diff-coverage` gate (added by CR-00047, Phase-1 P1-CR-B) runs `make diff-coverage` — a self-contained run that builds its own combined unit+integration coverage, then `diff-cover --compare-branch=origin/main --fail-under≈90` so new/changed Python lines must be well-covered; it gets a generous (1800s) timeout because it re-runs the unit + integration + dashboard suites. The `security-secrets` gate (added by CR-00050, Phase-1 P1-CR-D) runs `make security-secrets` — a gitleaks scan against the working tree using the project's `.gitleaks.toml` allowlist; it is the blocking secret-scanning gate on every PR.

The `daemon-chaos-smoke` gate (added by F-00089) runs `make daemon-chaos-smoke`, which executes the two highest-signal daemon fault-injection scenarios (S02 worktree-setup-mid-failure and S03 fix-cycle-cap-exhaustion). It provides a fast, repeatable regression check for core daemon recovery behavior on every future workflow.

QV gate failure → item moves to `failed` status (no fix cycles for QV gates).

## Monitoring

```bash
iw item-status F123          # Single item status
iw item-status F123 --json   # JSON output for scripting
iw batch-status BATCH-001    # Batch status
```

Dashboard: http://localhost:9900
- Running Tasks page: real-time step progress
- Project dashboard: queue, history, analytics
