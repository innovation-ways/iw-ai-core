# CR-00084 S02 Backend Report

**Step**: S02 (backend-impl)
**Work Item**: CR-00084 — LLM-as-judge test review (spike)
**Agent**: backend-impl
**Date**: 2026-05-25

---

## What was done

Implemented the conditional advisory hook in `code-review-impl.md` for both the `claude` and `opencode` agent variants. The hook form was selected based on S01's `calibration_verdict`.

### Calibration verdict read from S01

`calibration_verdict: "DEFERRED"` — S01 reported that live calibration could not run because `ANTHROPIC_API_KEY` is not available in agent worktrees at this time. The judge infrastructure is complete and verified (35 unit tests green), but the formal calibration run was deferred.

### Hook form: DORMANT

Because the verdict is DEFERRED (not MET), the hook was shipped in its **dormant** form in both agent specs. The section `### 6. (Advisory) LLM-as-judge test-quality signal` was added immediately before the `## Severity Levels` / `## Output` boundary in each file:

- **`agents/claude/code-review-impl.md`** — inserted between `### 5. Produce Findings` and `## Severity Levels`
- **`agents/opencode/code-review-impl.md`** — inserted between `### 5. Produce Findings` and `## Output`

The dormant form tells the agent:
1. The judge utility exists (with path `scripts/llm_judge_test_review.py`)
2. The calibration bar was DEFERRED, per `ai-dev/active/CR-00084/evidences/pre/cr-00084-judge-calibration.txt`
3. **DO NOT invoke the judge in this review**
4. Forward-link to the evidence file
5. One-line re-enablement instruction: "To re-enable, file a small follow-up CR that re-runs `make llm-judge-calibrate` and flips this section to the LIVE form."

### Mirror sync

Both `.claude/agents/code-review-impl.md` and `.opencode/agents/code-review-impl.md` were copied from their respective masters and verified byte-identical via `diff -q`.

---

## Pre-flight quality gates

| Gate | Result |
|------|--------|
| `make format` | `895 files already formatted` — ok |
| `make typecheck` | `Success: no issues found in 276 source files` — ok |
| `make lint` | `All checks passed!` — ok |

---

## Files changed

```
agents/claude/code-review-impl.md          (edited — DORMANT hook section added)
agents/opencode/code-review-impl.md        (edited — DORMANT hook section added)
.claude/agents/code-review-impl.md         (synced from master)
.opencode/agents/code-review-impl.md       (synced from master)
```

---

## Notes

- **TDD**: No new behavioural Python code was written in this step. `tdd_red_evidence` is `"n/a — agent-spec markdown edits only, no production logic"`.
- **No other agent specs touched** — `agents/pi/code-review-impl.md` was intentionally not edited (out of scope for CR-00084 S02).
- **Hook form**: DORMANT because S01 reported `calibration_verdict: "DEFERRED"`. When an API key becomes available and `make llm-judge-calibrate` produces a MET or NOT_MET verdict, a small follow-up CR should flip the section to the LIVE form.
- The LIVE form is fully documented in the step instructions; it was not written in this run because the verdict was DEFERRED, but it is ready to be copied in when re-calibration succeeds.