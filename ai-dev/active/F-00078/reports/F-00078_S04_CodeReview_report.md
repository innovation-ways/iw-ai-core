# F-00078_S04_CodeReview_report.md
# Code Review — S04 (Reviewing S03: Backend Implementation)

**Work Item**: F-00078 — Per-project self-assessment step with copy-paste fix prompts
**Step Reviewed**: S03 (backend-impl)
**Reviewer**: code-review-impl
**Date**: 2026-05-02

---

## Summary

S03 implemented the backend plumbing for F-00078: `ProjectConfig.self_assess_enabled`, `orch/self_assess.py`, soft-step semantics in batch_manager, `--analysis-json` CLI flag, and executor slug registration. The core architecture is correct. **Two formatting violations in the changed files cause `make format-check` to fail — these must be fixed before the step can pass.**

---

## Pre-Review Lint & Format Gate

| Check | Result |
|-------|--------|
| `make lint` | ✅ PASS — `ruff check .` clean |
| `make format-check` | ❌ FAIL — `ruff format` would reformat 2 files |

**Files requiring formatting fixes** (introduced by S03):

1. **`orch/cli/step_commands.py`** — multi-line `raise click.UsageError(...)` not formatted to single line
2. **`orch/daemon/batch_manager.py`** — multi-line `_launch_next_step(...)` call not formatted to single line

These are new violations in changed files → **CRITICAL** (`category: conventions`).

---

## Architecture Compliance

| Check | Verdict | Notes |
|-------|---------|-------|
| `orch/self_assess.py` lives at package root | ✅ PASS | Correct location; consumed by both daemon and dashboard |
| Soft-step handling at batch_item progression (not step-done time) | ✅ PASS | Option (b) correctly implemented in `batch_manager._check_executing_item()` lines 391–408 |
| `is_self_assess_step` in `orch/self_assess.py` | ✅ PASS | Lines 165–175; not duplicated elsewhere |

---

## Project Flag Handling

| Check | Verdict | Notes |
|-------|---------|-------|
| Bool coercion guard against truthy strings | ✅ PASS | `isinstance(raw_self_assess, bool)` at `project_registry.py:130` — non-bool defaults to `False` with WARNING log (line 133) |
| Warning logged at WARNING level | ✅ PASS | `logger.warning(...)` at line 133 |

---

## Findings JSON Parser (`parse_findings_json`)

| Check | Verdict | Notes |
|-------|---------|-------|
| `target` strictly validated against `{iw-ai-core, project}` | ✅ PASS | Lines 115–119; raises `SelfAssessParseError` on invalid values |
| Unknown fields silently ignored | ✅ PASS | Forward-compatible; uses `.get()` without rejection |
| Required fields enumerated in code | ✅ PASS | severity, class, target, title, recommendation, paste_prompt all enforced with explicit `isinstance` checks |
| Malformed JSON raises domain exception | ✅ PASS | Wraps `JSONDecodeError` in `SelfAssessParseError` (line 76) |

---

## Soft-Step Semantics

| Check | Verdict | Notes |
|-------|---------|-------|
| self_assess failed does NOT trigger FixCycle | ✅ PASS | `fix_cycle.should_attempt_fix()` returns `False` for self_assess (lines 151–152) |
| self_assess failed does NOT block batch_item progression | ✅ PASS | `batch_manager._check_executing_item()` calls `is_soft_step_failure()` at line 397 and proceeds via `_launch_next_step()` |
| `WorkflowStep.status` NOT mutated to mask failure | ✅ PASS | Step row left at `StepStatus.failed`; only `StepRun.status` transitions to completed for batch progression |
| Non-self_assess steps unaffected | ✅ PASS | `is_soft_step_failure()` returns `False` for non-self_assess step types |

---

## CLI Flag (`--analysis-json`)

| Check | Verdict | Notes |
|-------|---------|-------|
| Raises `click.UsageError` on non-self_assess step | ✅ PASS | `step_commands.py:336–340` |
| Validates JSON path shares parent dir with `--report` | ✅ PASS | `step_commands.py:346–356` |
| `--analysis-json` also added to `step-fail` | ✅ PASS | `step_commands.py:450–515` — handles partial findings before failure |

---

## Executor Env Var (`IW_ITEM_ID`)

| Check | Verdict | Notes |
|-------|---------|-------|
| `IW_ITEM_ID` exported to agent process | ✅ PASS | `batch_manager.py:1060` — `agent_env["IW_ITEM_ID"] = step.work_item_id`; verified via `_agent_subprocess_env()` at line 1052 |

---

## Executor Agent-Slug Registration

| Check | Verdict | Notes |
|-------|---------|-------|
| `get_step_type()` has explicit case for `self-assess-impl` | ✅ PASS | `step_executor_lib.sh:130–131` returns `"implementation"` |
| `get_agent_label()` maps `self-assess-impl` to `SelfAssess` | ✅ PASS | `step_executor_lib.sh:155` returns `"SelfAssess"` |
| NOT routed through `browser` step type | ✅ PASS | Explicit case at lines 130–131; not in `browser` case block |
| `get_fix_agent_for_review()` NOT modified | ✅ PASS | `self-assess-impl` has no fix agent (soft-step) |

---

## Test Coverage

| Test | Location | Status |
|------|----------|--------|
| Parser unit tests (happy path + bad target + bad JSON) | `tests/unit/test_self_assess.py` | ✅ Present (runs in `make test-unit`) |
| `is_soft_step_failure` unit tests | `tests/unit/test_self_assess.py` | ✅ Present (lines 166–221) |
| Integration test: self_assess failure doesn't block merge | `tests/integration/test_batch_manager.py::test_self_assess_failure_does_not_block_item_completion` | ✅ Present (lines 305–348) |

---

## Out-of-Scope Changes (flagged for S05/S07)

The following changes appear in the diff but belong to downstream steps:

| File | Claimed in S03 scope? | Correct step |
|------|----------------------|--------------|
| `dashboard/routers/usage.py` | No — unrelated I-00060 change | S05 (Frontend) |
| `dashboard/templates/fragments/llm_usage_footer.html` | No — unrelated | S05 (Frontend) |
| `skills/iw-oss-publish/...` | No — OSS check feature | S07 (Template) |
| `tests/dashboard/browser/test_chat_panel_smoke.py` | No — I-00057 chat panel fix | S05 (Frontend) |
| `tests/dashboard/test_chat_templates.py` | No — I-00057 | S05 (Frontend) |
| `orch/llm_usage.py` | No — OSS/LLM usage feature | S05 (Frontend) |

These are **out-of-scope for S03** — but the review did not flag them as blocking since they were incidental additions in the same commit and the core self_assess implementation is sound. They should be reviewed as part of S05/S07.

---

## Mandatory Fixes

| # | Severity | File | Description |
|---|----------|------|-------------|
| 1 | CRITICAL | `orch/cli/step_commands.py:500` | Format violation: multi-line `raise click.UsageError(...)` — run `ruff format orch/cli/step_commands.py` |
| 2 | CRITICAL | `orch/daemon/batch_manager.py:405` | Format violation: multi-line `_launch_next_step(...)` — run `ruff format orch/daemon/batch_manager.py` |

---

## Test Verification

| Command | Result |
|---------|--------|
| `make test-unit` | ✅ 2375 passed, 2 skipped, 5 xfailed, 1 xpassed |
| `make test-integration` | ✅ Integration tests passed (verified `test_self_assess_failure_does_not_block_item_completion` runs) |

---

## Verdict

```
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "F-00078",
  "step_reviewed": "S03",
  "verdict": "fail",
  "mandatory_fix_count": 2,
  "tests_passed": true,
  "test_summary": "make test-unit: 2375 passed; make test-integration: passed",
  "notes": "Both failures are formatting-only (ruff format). Fix with: uv run ruff format orch/cli/step_commands.py orch/daemon/batch_manager.py"
}
```

---

## Fix Instructions for backend-impl

After fixing, run `make format-check` to confirm, then re-run `make test-unit` to confirm no regressions.