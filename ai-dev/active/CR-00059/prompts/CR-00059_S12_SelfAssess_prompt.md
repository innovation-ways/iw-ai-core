# CR-00059_S12_SelfAssess_prompt

**Work Item**: CR-00059 -- Mutation testing spike + setup on `orch/daemon/` (P2-CR-A)
**Step**: S12
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived infrastructure containers are outside your scope.

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (Ryuk teardown).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets.

If your task seems to require a prohibited command, STOP and raise a blocker.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run live alembic commands. Your job is to ANALYZE the item's execution, not to modify state.

Allowed for agents: `alembic history / current / show` (read-only); testcontainer migrations inside pytest fixtures.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (canonical source).
- **Worktree logs** — `.worktrees/CR-00059/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/active/CR-00059/reports/` — existing step reports (S01–S11).
- **Spike measurement artefact** — `ai-dev/active/CR-00059/evidences/pre/cr-00059-spike-measurements.txt`.
- **Design** — `ai-dev/active/CR-00059/CR-00059_CR_Design.md`.

## Output Files

- `ai-dev/active/CR-00059/reports/CR-00059_self_assess_report.md` — Human-readable narrative analysis.
- `ai-dev/active/CR-00059/reports/CR-00059_self_assess_findings.json` — Structured findings JSON.

## Context

You are running the self-assessment step for **CR-00059 — Mutation testing spike + setup on `orch/daemon/` (P2-CR-A)** — the **first Phase-2 CR**. Findings from this assessment will shape the structure and scope of P2-CR-B (Hypothesis property tests, item 2.2) and P2-CR-C (flaky/quarantine workflow, item 2.3).

**Use the `iw-item-analyze` skill** to perform the analysis. In Claude Code: invoke via `Skill` tool with `skill: "iw-item-analyze"`. In OpenCode: skill is auto-loaded.

## Soft-Step Semantics

This step's failure does NOT block merge. Produce a usable report even if the analysis is partial.

## Additional Phase-2-specific findings to surface (beyond the generic skill rubric)

Beyond the standard `iw-item-analyze` analysis (agent thrash, fix cycles, manifest issues, prompt gaps), this Phase-2 inaugural CR has specific findings worth surfacing:

1. **Spike timeout calibration.** Did S01's 3600 s timeout hold? Was it (a) used in full, (b) used with margin, or (c) close to expiry? This informs whether Phase-2 spike steps (P2-CR-B's "first run on the work-item state machine") need shorter or longer budgets.

2. **mutmut infrastructure blockers encountered.** Read `cr-00059-spike-measurements.txt`'s "Infrastructure blockers" section. Were the predicted ones (testcontainer per-mutant cost, FTS replay, live-DB guard) actually triggered? Were any unanticipated ones surfaced? P2-CR-B (Hypothesis) runs the same pytest infrastructure — if anything tripped mutmut, it may trip Hypothesis too.

3. **Spike runtime distribution.** From S01's report, was wall-clock dominated by (a) testcontainer per-mutant startup, (b) mutmut's own overhead, (c) actual test execution, or (d) something else? This informs whether the broader-scope follow-up (`P2-CR-A-followup-mutation-block`) should batch-cache the container.

4. **Surviving-mutant queue actionability.** From S01's "Top 5 surviving mutants" — are they concentrated in one file or spread across daemon modules? Do any of them suggest a *systematic* test weakness (e.g. multiple "boundary comparison" mutants surviving → smoke that we don't test boundary conditions) versus *one-off* misses?

5. **Audit-table-as-deliverable pattern.** CR-00052 introduced this pattern (audit table for 16 smoke decorators). CR-00059 extends it (measurement table for the spike). Did S02 + S03 verify the table effectively? Was the cross-doc-triangle check (canonical artefact ↔ strategy doc ↔ changelog) caught any drift? Should the Phase-2 CR template formalise this as a standard deliverable for any CR whose output includes a measurement?

6. **Phase-2 CR shape for the next two.**
   - **P2-CR-B (item 2.2, Hypothesis property tests)**: should it follow the same spike-then-setup shape (run a small Hypothesis run on the work-item state machine, measure cost, then land the property-test module), or go straight to full setup?
   - **P2-CR-C (item 2.3, flaky/quarantine workflow)**: should it use the audit-table pattern? (E.g. "audit table classifying current intermittent failures by suspected cause".)

7. **`make quality` deptry check on the new dep.** Did `make dep-check` (deptry) flag mutmut as unused? If so, S01 mis-declared its place in the dep-groups (mutmut is a tool, belongs in `[dependency-groups] dev`, not `[project] dependencies` — and deptry needs to know that). If yes, file a finding for follow-up.

## TDD RED Evidence (behaviour-implementing steps only)

S01 is a behaviour-implementing step (introduces tooling + a guard test). Confirm:

- S01's report contains `tdd_red_evidence` with a real test id (one of the two `test_mutmut_setup.py` tests) and a real failure line (AssertionError / KeyError, NOT ImportError / SyntaxError / "n/a").
- If `tdd_red_evidence` is `"n/a"` — that's a CR-00045 contract violation and should be flagged as a CRITICAL finding.

S02 (code-review-impl) and S03 (code-review-final-impl) are review steps — no RED evidence expected.

## Subagent Result Contract

```json
{
  "step": "S12",
  "agent": "self-assess-impl",
  "work_item": "CR-00059",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/CR-00059/reports/CR-00059_self_assess_report.md",
    "ai-dev/active/CR-00059/reports/CR-00059_self_assess_findings.json"
  ],
  "preflight": {
    "format": "ok|skipped:no-code-changes",
    "typecheck": "ok|skipped:no-code-changes",
    "lint": "ok|skipped:no-code-changes"
  },
  "tests_passed": true,
  "test_summary": "skipped: no tests for analysis step",
  "blockers": [],
  "notes": "Phase-2 inaugural CR — analysis includes the 7 additional Phase-2-specific findings. Recommendations feed into P2-CR-B and P2-CR-C design."
}
```
