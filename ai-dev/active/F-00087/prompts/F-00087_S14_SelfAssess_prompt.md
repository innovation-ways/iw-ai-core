# F-00087_S14_SelfAssess_prompt

**Work Item**: F-00087 -- Pi runtime + per-tab runtime selection in AI Assistant chat
**Step**: S14
**Agent**: self-assess-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute any docker command that changes container/volume/network state. Read-only introspection is allowed.

## ⛔ Migrations: agents generate, daemon applies

Your job is to ANALYZE the item's execution, not to modify the database.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (canonical source).
- **Worktree logs** — `.worktrees/F-00087/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/active/F-00087/reports/` — every step report from S01..S13, plus any fix-cycle reports.

## Output Files

- `ai-dev/active/F-00087/reports/F-00087_self_assess_report.md` — human-readable narrative analysis
- `ai-dev/active/F-00087/reports/F-00087_self_assess_findings.json` — structured findings JSON

## Context

You are running the self-assessment step for F-00087 (Pi runtime + per-tab runtime selection in AI Assistant chat). This step uses the `iw-item-analyze` skill to surface recurring process issues across the just-completed workflow — agent thrashing, repeated tool failures, prompt gaps, manifest issues, redundant env/install steps.

**You analyze the EXECUTION HISTORY, not the generated code.** Look at retry counts, fix cycles, gate failures, agent thrash patterns. Do NOT review the Pi runtime feature itself for correctness — that's S02/S06's job.

This step is **soft** — failure does NOT block the item from merging. Produce the best report you can even if analysis is partial.

**Use the `iw-item-analyze` skill** to perform the analysis. In Claude Code, invoke via the `Skill` tool with `skill: "iw-item-analyze"`. In OpenCode, reference the skill by name.

## Soft-Step Semantics

This step's failure does NOT block merge — but produce a usable report anyway. If analysis can't complete, write a stub report explaining why and a `findings: []` JSON.

## Particular things to watch for in F-00087

The feature spans 1 backend step (large), 1 frontend step, 1 tests step, 2 review cycles, 5 QV gates, and 1 browser verification. Areas with elevated risk for thrash/retry:

- **S01 Backend (large)** — the LF-only JSONL reader is the single highest-risk piece per the design's §Notes. If reviewers (S02/S06) had to flag built-in-line-iterator regressions across multiple fix cycles, that's a prompt-fix opportunity (S01 prompt may need more aggressive guard rails — e.g., a literal "do not import io.IOBase.readline" check). Surface as a finding for future Pi-shaped work.
- **TypeScript extension uncertainty** — Pi's exact extension manifest shape isn't pinned in R-00072. If S01/S05 retried because the stub Pi binary couldn't load the extension, document the lookup pattern that worked.
- **Stub `pi` binary pattern** — CR-00062 established the stub pattern; F-00087 reuses it. If S05 retried because the stub script wasn't on PATH or wasn't executable, document the pre-flight check that catches it sooner.
- **Subprocess lifecycle bugs** — async-subprocess management is intrinsically tricky. If S01/S02 had multiple fix cycles around event-loop leaks, zombie subprocesses, or test flakiness from subprocess teardown timing, surface as patterns for future runtime-subpackage work.
- **Frontend dropdown wiring** — the F-00086 dropdown control shape is the contract. If S04 had to retry because the F-00086 implementation differed from this Feature's assumption (e.g., F-00086 used radio buttons instead of select), document the discovery and propose a cross-Feature design pattern.
- **S12 (integration tests)** — Pi subprocess tests are intrinsically slower than mocked OpenCode tests. If the test wall-clock pushed close to the 1800s timeout, recommend adjusting the timeout or splitting the test file.
- **S13 (browser verification)** — V6 (approval modal) depends on a real Pi binary in the test stack. Document whether the stack supported it; if not, recommend stack provisioning changes.

## TDD RED Evidence (cross-step check)

For each behaviour-implementing step (notably S01 Backend), confirm the report contains plausible `tdd_red_evidence`:

- S01: expected to cite `tests/unit/chat/test_pi_jsonl_reader.py::test_unicode_separators_in_json_string_do_not_split` (or `test_pi_runtime_lru_eviction.py::test_seventh_tab_evicts_lru`) with `ImportError` snippet from the RED run (the module doesn't exist pre-S01).

If S01's `tdd_red_evidence` is missing, `n/a` without justification, or shows a non-plausible failure shape, surface as a finding.

`tests-impl` (S05) is exempt — it's a dedicated coverage step.

## Subagent Result Contract

```json
{
  "step": "S14",
  "agent": "self-assess-impl",
  "work_item": "F-00087",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/F-00087/reports/F-00087_self_assess_report.md",
    "ai-dev/active/F-00087/reports/F-00087_self_assess_findings.json"
  ],
  "preflight": {
    "format": "skipped:no-code-changes",
    "typecheck": "skipped:no-code-changes",
    "lint": "skipped:no-code-changes"
  },
  "tests_passed": true,
  "test_summary": "skipped: no tests for analysis step",
  "blockers": [],
  "notes": "Analysis completed; findings written to two output files."
}
```
