# I00109_S14_SelfAssess_prompt

**Work Item**: I-00109 -- `GET /project/{project_id}/docs/{doc_id}/pdf` raises unhandled `PermissionError` → HTTP 500 when on-disk PDF cache dir is not writable
**Step**: S14
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

Standard policy. You are analyzing logs and reports, not modifying infra. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You are NOT modifying the database. No alembic commands. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (canonical).
- **Worktree logs** — `.worktrees/I-00109/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/active/I-00109/reports/` — existing step reports (secondary evidence).

## Output Files

- `ai-dev/active/I-00109/reports/I-00109_self_assess_report.md` — human-readable narrative analysis.
- `ai-dev/active/I-00109/reports/I-00109_self_assess_findings.json` — structured findings JSON.

## Context

You are running the self-assessment step for **I-00109**. This is the **last** step in the manifest (after all QV gates), so the execution history is complete: any retries triggered by `lint` / `assertions` / `format-check` / `type-check` / `unit-tests` / `integration-tests` / `diff-coverage` / `security-secrets` are now visible to you.

Use the `iw-item-analyze` skill to perform the analysis. The skill is auto-discovered by both Claude Code (`.claude/skills/iw-item-analyze/SKILL.md`) and OpenCode. In Claude Code, invoke it via the `Skill` tool with `skill: "iw-item-analyze"`. Do NOT re-implement the analysis procedure inline — the skill is the source of truth for the output contract.

## What to look for in this item specifically

I-00109 is a small, narrowly-scoped dashboard router fix surfaced by the CR-00072 contract-route-sweep test layer (merged 2026-05-22). The fix is a defensive `try/except` mirror of an existing sibling-handler guard, plus a dedicated regression test and the removal of one `EXPECTED_5XX` entry. Self-assessment is mostly a baseline run for the workflow analytics. Things worth flagging if they occurred:

- **xfail-marker handoff between S01 and S03.** The `EXPECTED_5XX` entry in `tests/dashboard/test_route_contract_sweep.py:142` parametrizes the docs-pdf case with `pytest.mark.xfail(strict=True)`. S01's fix flips it to `XPASS(strict)` → reported as FAIL by pytest. S03 removes the entry so the case records as a normal pass. If S02 review missed the `XPASS(strict)` and treated it as a regression — or if S03 failed to remove the entry (or removed the surrounding `EXPECTED_5XX` declaration too) — note the cycle. The strict-xfail-to-allowlist-removed handoff is the same pattern used in I-00108 and earlier operator-follow-up incidents; future incidents from CR-00072 / CR-00073 will repeat it, so any prompt-clarity gaps that tripped agents here are worth capturing.
- **Mirror drift between `docs_pdf` and `docs_pdf_view`.** S01's value is structural symmetry with the sibling handler's guard at lines 256-266 (same comment, same `import logging` placement, same `.warning(...)` format string). If S01 was rejected by S02 or S05 for deviating from the sibling pattern (different exception, different log level, hoisted import, refactored to a helper), flag it as a prompt-clarity issue — the S01 prompt explicitly calls for verbatim mirroring, and any agent that "improved" on the existing pattern points to a gap in how the rule is communicated.
- **Scope creep — refactoring the two handlers into a shared helper.** Both the design doc and the S01 prompt explicitly say "if you want to consolidate, file a follow-up CR." If an agent retried extracting a `_safe_write_pdf_cache()` helper or rewriting `docs_pdf_view` to delegate, note it — the temptation to consolidate visible duplication is strong and the prompt may need stronger wording.
- **Test placement under `tests/dashboard/`.** The new test file MUST live under `tests/dashboard/` because the `client` fixture is registered only there (I-00067 lesson). If an agent placed the test under `tests/unit/` or `tests/integration/` and was caught at collection time with `fixture 'client' not found`, note the cycle — the rule is documented in `tests/CLAUDE.md` and the S03 prompt, but the lesson keeps recurring.
- **`ProjectDoc` constructor mismatch.** S03's test seeds a `ProjectDoc` row. If S03 omitted a NOT NULL column the live model added since 2026-05-24 and the test failed at fixture-build time, note it — the design doc lists the columns the test needs to set, but column drift in `orch/db/models.py` can outpace prompt updates.
- **`render_pdf_chromium` patch path.** S03's test patches `dashboard.routers.docs.render_pdf_chromium`. If the actual import in `dashboard/routers/docs.py` is from a helper module (e.g. re-exported from `orch/render_pdf.py`) and the patch path was wrong, the test would silently invoke the real Chromium and pass on dev machines but fail in CI. If a fix cycle traced back to this, note it — the S03 prompt warns about it but the failure mode is subtle.
- **Assertion-scanner trip on the new regression test.** S03's assertions are all specific-value semantic checks (exact status code, exact content type, PDF magic bytes prefix, `pdf_path is None` after the failed write). If `make test-assertions` flagged any as shape-only or tautology, note the cycle — the S03 and S04 prompts both warn extensively about this with the I003 lesson quoted verbatim.
- **`make test-integration` runtime.** The integration-tests QV gate (S11, 1800 s budget) runs the full integration suite. If this step needed multiple fix cycles for unrelated reasons (other items' tests, testcontainer flakiness), note the cycle — it is a noise signal for the workflow's QV-gate budget tuning, not an I-00109 issue.

## Soft-Step Semantics

This step's failure does NOT block merge — but produce a usable report anyway. If the analysis cannot complete, write a stub report explaining why and a `findings: []` JSON.

## TDD RED Evidence (behaviour-implementing steps only)

For each behaviour-implementing step whose report claims new behavioural tests:

- **S01 (backend-impl)** is expected to cite the `XPASS(strict)` line from the route-sweep case (`test_route_returns_no_5xx[GET /project/{project_id}/docs/{doc_id}/pdf]`) as its `tdd_red_evidence` — that is the RED→GREEN signal for this fix. An empty `tdd_red_evidence` or a generic "n/a" is a documentation-clarity issue (LOW); flag it only if the fix coverage is actually missing.
- **S03 (tests-impl)** is exempt from the RED-run requirement (it adds the dedicated regression test after the fix lands). The new test pins the fixed behaviour and passes by construction; the `EXPECTED_5XX` removal converts the sweep case from `XPASS(strict)` → normal pass. S03's `tdd_red_evidence` is expected to be `"n/a — Tests step adds regression coverage after S01's fix..."` plus a pytest GREEN line for the sweep case post-removal.

## Subagent Result Contract

```json
{
  "step": "S14",
  "agent": "self-assess-impl",
  "work_item": "I-00109",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/I-00109/reports/I-00109_self_assess_report.md",
    "ai-dev/active/I-00109/reports/I-00109_self_assess_findings.json"
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
