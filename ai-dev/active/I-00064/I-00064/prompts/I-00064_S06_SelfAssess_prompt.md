# I-00064_S06_SelfAssess_prompt

**Work Item**: I-00064 -- Job detail "View document" link 404s with double project_id prefix
**Step**: S06
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

(Standard policy. Allowed exceptions: testcontainer fixtures, read-only
introspection, `./ai-core.sh` / `make` targets. Full policy:
`docs/IW_AI_Core_Agent_Constraints.md`.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This step does NOT modify the database — it analyzes.)

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (canonical source set by the executor).
- **Worktree logs** — `.worktrees/I-00064/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/active/I-00064/reports/` — existing step reports (secondary evidence).

## Output Files

- `ai-dev/active/I-00064/reports/I-00064_self_assess_report.md` — Human-readable narrative analysis.
- `ai-dev/active/I-00064/reports/I-00064_self_assess_findings.json` — Structured findings JSON.

## Context

You are running the self-assessment step for work item **I-00064**.

This step invokes the `iw-item-analyze` skill to analyze the
just-completed item's execution history and surface process improvement
findings. This step is **soft** — failure does NOT block the item from
merging. Produce the best report you can even if the analysis is
partial.

**Use the `iw-item-analyze` skill** to perform the analysis. The skill
is auto-discovered by both Claude Code (via
`.claude/skills/iw-item-analyze/SKILL.md`) and OpenCode (which reads the
same path). In Claude Code, invoke it via the `Skill` tool with
`skill: "iw-item-analyze"`. In OpenCode, the skill is loaded by default
for the agent and you can reference it by name in your reasoning. Do
NOT re-implement the analysis procedure inline — the skill is the
source of truth for the output contract (two files:
`_self_assess_report.md` + `_self_assess_findings.json`).

For this incident specifically, look for:

- Whether the agents had to re-discover the same composite-PK convention
  (e.g., did multiple steps grep for `:` in IDs or re-read
  `orch/db/models.py:1281-1289`?). If yes, consider proposing a
  CLAUDE.md addendum documenting the FK-vs-inner-id convention.
- Whether any step burned a fix cycle on the same lint/format/typecheck
  issue, suggesting a pre-flight gap.
- Whether the test fixture wiring (testcontainer, FastAPI client) was
  redundantly re-derived rather than reused from
  `tests/integration/test_i00059_*` — if so, suggest extracting a
  helper.

## Soft-Step Semantics

This step's failure does NOT block merge — but produce a usable report
anyway. If the analysis can't complete, write a stub report explaining
why and a `findings: []` JSON.

## Subagent Result Contract

```json
{
  "step": "S06",
  "agent": "self-assess-impl",
  "work_item": "I-00064",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/I-00064/reports/I-00064_self_assess_report.md",
    "ai-dev/active/I-00064/reports/I-00064_self_assess_findings.json"
  ],
  "preflight": {
    "format": "ok|skipped:no-code-changes",
    "typecheck": "ok|skipped:no-code-changes",
    "lint": "ok|skipped:no-code-changes"
  },
  "tests_passed": true,
  "test_summary": "skipped: no tests for analysis step",
  "blockers": [],
  "notes": "Analysis completed; findings written to two output files."
}
```
