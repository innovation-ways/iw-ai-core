---
name: iw-workflow
version: "2.1.0"
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
| CodeReview_{X} | `code-review-impl` |
| CodeReview_Final | `code-review-final-impl` |
| CodeReview_FIX_{X} | `code-review-fix-impl` |
| CodeReview_FIX_Final | `code-review-fix-final-impl` |
| QV gate | `qv-gate` (with `gate` + `command` fields) |
| QV browser | `qv-browser` (with `prompt` field) |

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

## QV Gate Steps

QV gates run as shell commands (no LLM):

```json
{"step": "S10", "agent": "qv-gate", "gate": "lint", "command": "make lint", "description": "QV: Linting"},
{"step": "S11", "agent": "qv-gate", "gate": "format", "command": "make format-check", "description": "QV: Formatting"},
{"step": "S12", "agent": "qv-gate", "gate": "typecheck", "command": "make type-check", "description": "QV: Type checking"},
{"step": "S13", "agent": "qv-gate", "gate": "unit-tests", "command": "make test-unit", "description": "QV: Unit tests"},
{"step": "S14", "agent": "qv-gate", "gate": "integration-tests", "command": "make allure-integration", "description": "QV: Integration tests", "timeout": 900}
```

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
