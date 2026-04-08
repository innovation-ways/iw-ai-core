# AI Dashboard & Orchestration Enhancement — Design & Implementation Plan

**Author**: Claude Opus 4.6 (AI assistant) + Sergio (project lead)
**Date**: 2026-03-29
**Status**: Approved for implementation
**Priority**: Critical — current orchestration fails on ~60% of batch items

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Root Cause Analysis](#2-root-cause-analysis)
3. [Enhancement Overview](#3-enhancement-overview)
4. [E1: Split QV Into Individual Gate Steps](#4-e1-split-qv-into-individual-gate-steps)
5. [E2: QV Gate Fix Cycles](#5-e2-qv-gate-fix-cycles)
6. [E3: Dynamic Timeouts](#6-e3-dynamic-timeouts)
7. [E4: Fix Daemon Status Recognition](#7-e4-fix-daemon-status-recognition)
8. [E5: Per-Step Process Tracking](#8-e5-per-step-process-tracking)
9. [E6: Item-Level Restart from Dashboard](#9-e6-item-level-restart-from-dashboard)
10. [E7: Smart Fix Cycle Escalation](#10-e7-smart-fix-cycle-escalation)
11. [E8: Zombie Process Cleanup](#11-e8-zombie-process-cleanup)
12. [E9: Dashboard Real-Time Step View](#12-e9-dashboard-real-time-step-view)
13. [Implementation Order & Dependencies](#13-implementation-order--dependencies)
14. [Testing Strategy](#14-testing-strategy)
15. [Migration & Backward Compatibility](#15-migration--backward-compatibility)

---

## 1. Problem Statement

The AI orchestration system (batch dispatcher + step executor + daemon + dashboard) suffers from systemic failures that cause ~60% of batch items to fail, stall, or become orphaned. Analysis of BATCH-052, BATCH-053, and BATCH-054 (2026-03-29) shows:

| Item | Failure Mode | Root Cause |
|------|-------------|------------|
| I117 | Orphaned — daemon can't see it | Batch manifest uses `"running"` status (not recognized) |
| I118 | 4.5h in fix cycles, 2 timeouts | Fix agent can't complete work in 30-min timeout |
| I120 | 3 fix cycle timeouts, stalled | Same timeout issue; review keeps finding same issue |
| I121 | Dead on first step, zero output | 30-min timeout too short for large frontend task |
| I122 | All code gates passed, died at browser verification | Monolithic QV step; no recovery from browser failure |
| F140 | Fix cycle timeout at global review | Same timeout pattern |

**Key insight**: Every single failure falls into one of three categories:
1. **Monolithic QV step** — one failure kills everything (I117, I122)
2. **30-minute timeout too short** — for complex implementations and fix cycles (I118, I120, I121, F140)
3. **System bugs** — daemon doesn't recognize status values, no restart capability (I117)

---

## 2. Root Cause Analysis

### 2.1 Monolithic Quality Validation

**Current behavior** (`scripts/step_executor_lib.sh:568-737`): The QV step runs 9 quality gates + optional browser verification as a single atomic step. The `run_quality_validation()` function loops through all gates, and if ANY gate fails, the entire workflow fails with `set_wf_status "failed"` and `return 1`.

**Current QV step in step_executor.sh (lines 605-620)**:
```bash
qv)
    run_quality_validation "$ITEM_ID" "$step_id" \
        "$WORKTREE_PATH" "$ITEM_LOG" "$CLI_TOOL"
    local qv_exit=$?
    if [[ $qv_exit -eq 0 ]]; then
        set_step_status "$ITEM_ID" "$step_index" "completed"
    else
        set_step_status "$ITEM_ID" "$step_index" "failed"
        set_wf_status "$ITEM_ID" "failed"   # ← KILLS THE ENTIRE WORKFLOW
        return 1
    fi
```

**Problems**:
- If integration tests hang (I117), all other passed gates are lost
- If browser verification blocks (I122), the 9 passed code gates are invisible
- There is NO fix cycle for QV failures — the `QualityValidation_FIX_Prompt_Template.md` exists but is never used
- A flaky test kills the entire item

### 2.2 Static 30-Minute Timeout

**Current constants** (`scripts/step_executor_lib.sh:24-28`):
```bash
MAX_FIX_CYCLES=5
MAX_CONTINUATIONS=3
MAX_STEP_TIMEOUT=1800        # 30 min for ALL step types
MAX_STEP_TIMEOUT_QV=2400     # 40 min for QV browser only
MAX_TEST_REGRESSION_RETRIES=3
```

A fix cycle = fix agent (up to 30 min) + re-review agent (up to 30 min) = up to 60 min per cycle. Complex fix cycles (global review touching multiple files) routinely exceed 30 min, causing the fix agent to be killed mid-work. The timed-out fix produces nothing, so the re-review sees the same unfixed code and returns NEEDS_FIX again — wasting another cycle.

### 2.3 Daemon Status Mismatch

**Current state machine** (`scripts/ai_dev_daemon/state_machine.py:13-24`): `BatchStatus` enum only recognizes: `planning`, `approved`, `executing`, `paused`, `completed`, `completed_with_errors`, `blocked`, `crashed`, `archived`.

When the daemon reads a manifest with `"status": "running"`, `BatchStatus("running")` raises `ValueError`, which is caught as `False` in `can_transition_batch()`. The daemon logs a warning every 60 seconds and completely ignores the batch.

### 2.4 No Step-Level Restart

The dashboard has a `/api/item/{ID}/restart-step/{N}` endpoint that sets `step.status = "pending"` in the manifest. But the step_executor.sh process is already dead — there's no mechanism to relaunch it from step N. The manifest change is purely cosmetic.

---

## 3. Enhancement Overview

| ID | Enhancement | Impact | Effort | Priority |
|----|------------|--------|--------|----------|
| E1 | Split QV into individual gate steps | Fixes I117, I122 class failures | High | P0 |
| E2 | QV gate fix cycles | Auto-recovers from lint/type/test failures | Medium | P0 |
| E3 | Dynamic timeouts by step type | Fixes I118, I120, I121, F140 class failures | Low | P0 |
| E4 | Fix daemon status recognition | Fixes I117 orphan | Low | P0 |
| E5 | Per-step process tracking | Visibility into what's actually running | Medium | P1 |
| E6 | Item-level restart from dashboard | Manual recovery without CLI | High | P1 |
| E7 | Smart fix cycle escalation | Reduces wasted fix cycles | Medium | P2 |
| E8 | Zombie process cleanup | Prevents process table pollution | Low | P2 |
| E9 | Dashboard real-time step view | Operator visibility | High | P2 |

---

## 4. E1: Split QV Into Individual Gate Steps

### 4.1 Goal

Replace the single monolithic QV step with individual gate steps in the workflow manifest. Each gate runs independently, has its own pass/fail status, its own log, and can be individually restarted.

### 4.2 Design

#### 4.2.1 New Step Types

Add new step types to the agent type mapping in `scripts/step_executor_lib.sh`:

```bash
# In get_step_type() — add these cases:
get_step_type() {
    local agent="$1"
    case "$agent" in
        # ... existing cases ...
        qv-gate)                    echo "qv-gate" ;;
        qv-browser)                 echo "qv-browser" ;;
        *)                          echo "implementation" ;;
    esac
}
```

#### 4.2.2 New Manifest Step Structure

Instead of one QV step at the end, workflow manifests will have individual gate steps. The manifest generator (in the design/planning phase) should produce steps like:

**Before** (current):
```json
{
  "steps": [
    {"step": "S01", "agent": "frontend-impl", "status": "pending"},
    {"step": "S02", "agent": "code-review-impl", "status": "pending"},
    {"step": "S03", "agent": "code-review-final-impl", "status": "pending"},
    {"step": "S04", "agent": "quality-validation-impl", "status": "pending"}
  ]
}
```

**After** (new):
```json
{
  "steps": [
    {"step": "S01", "agent": "frontend-impl", "status": "pending"},
    {"step": "S02", "agent": "code-review-impl", "status": "pending"},
    {"step": "S03", "agent": "code-review-final-impl", "status": "pending"},
    {"step": "S04", "agent": "qv-gate", "status": "pending",
     "gate": "lint", "command": "make lint"},
    {"step": "S05", "agent": "qv-gate", "status": "pending",
     "gate": "format", "command": "make format-check"},
    {"step": "S06", "agent": "qv-gate", "status": "pending",
     "gate": "typecheck", "command": "make type-check"},
    {"step": "S07", "agent": "qv-gate", "status": "pending",
     "gate": "frontend-tsc", "command": "cd frontend && npx tsc --noEmit"},
    {"step": "S08", "agent": "qv-gate", "status": "pending",
     "gate": "arch-check", "command": "make arch-check"},
    {"step": "S09", "agent": "qv-gate", "status": "pending",
     "gate": "security-sast", "command": "make security-sast"},
    {"step": "S10", "agent": "qv-gate", "status": "pending",
     "gate": "unit-tests", "command": "make test-unit"},
    {"step": "S11", "agent": "qv-gate", "status": "pending",
     "gate": "frontend-tests", "command": "make test-frontend"},
    {"step": "S12", "agent": "qv-gate", "status": "pending",
     "gate": "integration-tests", "command": "make allure-integration"},
    {"step": "S13", "agent": "qv-browser", "status": "pending",
     "gate": "browser-verification"}
  ]
}
```

**Important**: The `qv-browser` step should only be present when `browser_verification: true` in the workflow manifest.

#### 4.2.3 Gate Execution in step_executor.sh

Add a new case to the step loop in `step_executor.sh` (after line 620):

```bash
qv-gate)
    # Read gate config from manifest
    local gate_name gate_cmd
    gate_name=$(get_step_field "$ITEM_ID" "$step_index" ".gate")
    gate_cmd=$(get_step_field "$ITEM_ID" "$step_index" ".command")

    # Run the gate (pure bash, no LLM)
    local gate_report="ai-dev/work/$ITEM_ID/reports/${ITEM_ID}_${step_id}_QV_${gate_name}_report.md"
    local gate_exit=0
    run_single_qv_gate "$item_id" "$step_id" "$gate_name" "$gate_cmd" \
        "$WORKTREE_PATH" "$gate_report" || gate_exit=$?

    if [[ $gate_exit -eq 0 ]]; then
        set_step_status "$ITEM_ID" "$step_index" "completed"
        add_step_run "$ITEM_ID" "$step_index" "$run_number" "$gate_report" "pass"
    else
        # Gate failed — trigger QV fix cycle (see E2)
        add_step_run "$ITEM_ID" "$step_index" "$run_number" "$gate_report" "gates_failed"

        handle_qv_fix_cycle "$step_index" "$step_id" "$gate_name" \
            "$gate_cmd" "$gate_report"
        local fix_result=$?

        if [[ $fix_result -ne 0 ]]; then
            set_step_status "$ITEM_ID" "$step_index" "failed"
            _lib_log_error "  $step_id ($gate_name) FAILED — QV fix exhausted"
            set_wf_status "$ITEM_ID" "failed"
            return 1
        fi
    fi
    ;;

qv-browser)
    # Browser verification — delegates to LLM (same as current browser logic)
    local qv_prompt="ai-dev/work/$ITEM_ID/prompts/${ITEM_ID}_${step_id}_BrowserVerification_prompt.md"
    local browser_report="ai-dev/work/$ITEM_ID/reports/${ITEM_ID}_${step_id}_BrowserVerification_report.md"
    local browser_log="${ITEM_LOG%.log}_${step_id}_browser.log"

    execute_single_step "$step_id" "quality-validation-impl" \
        "$qv_prompt" "$browser_report" "$browser_log" "$MAX_STEP_TIMEOUT_QV"
    local browser_exit=$?

    if [[ $browser_exit -eq 0 ]]; then
        set_step_status "$ITEM_ID" "$step_index" "completed"
        add_step_run "$ITEM_ID" "$step_index" "$run_number" "$browser_report" "pass"
    else
        set_step_status "$ITEM_ID" "$step_index" "failed"
        add_step_run "$ITEM_ID" "$step_index" "$run_number" "$browser_report" "failed"
        _lib_log_error "  $step_id (browser-verification) FAILED"
        set_wf_status "$ITEM_ID" "failed"
        return 1
    fi
    ;;
```

#### 4.2.4 New Library Function: run_single_qv_gate

Add to `scripts/step_executor_lib.sh`:

```bash
# Run a single quality gate and generate a report.
# Returns 0 if gate passes, 1 if it fails.
run_single_qv_gate() {
    local item_id="$1"
    local step_id="$2"
    local gate_name="$3"
    local gate_cmd="$4"
    local worktree_path="$5"
    local report_file_path="$6"

    local report_dir
    report_dir="$(dirname "$worktree_path/$report_file_path")"
    mkdir -p "$report_dir"

    local abs_report="$worktree_path/$report_file_path"

    _lib_log "  QV gate: $gate_name"

    local output exit_code=0
    output=$(cd "$worktree_path" && eval "$gate_cmd" 2>&1 | tail -50) || exit_code=$?

    local status="PASS"
    if [[ $exit_code -ne 0 ]]; then
        status="FAIL"
    fi

    cat > "$abs_report" << GATEEOF
# ${item_id}_${step_id}_QV_${gate_name}_report

**Work Item**: ${item_id}
**Step**: ${step_id}
**Gate**: ${gate_name}
**Command**: \`${gate_cmd}\`
**Result**: ${status} (exit code: ${exit_code})
**Date**: $(date '+%Y-%m-%d %H:%M:%S')

---

## Output

\`\`\`
${output}
\`\`\`

## Subagent Result Contract

\`\`\`json
{
  "step": "${step_id}",
  "agent": "QV_${gate_name}",
  "work_item": "${item_id}",
  "completion_status": "complete",
  "gate": "${gate_name}",
  "gate_status": "${status}",
  "exit_code": ${exit_code}
}
\`\`\`
GATEEOF

    if [[ $exit_code -eq 0 ]]; then
        return 0
    else
        return 1
    fi
}
```

#### 4.2.5 Backward Compatibility

Keep the existing `quality-validation-impl` agent type handling for old manifests that still use it. The `qv)` case in the step loop should remain but log a deprecation warning:

```bash
qv)
    _lib_log "  WARNING: Monolithic QV step detected — use qv-gate steps instead"
    # ... existing run_quality_validation logic unchanged ...
```

#### 4.2.6 Dashboard Step Labels

Update `scripts/ai_dashboard/scanner.py` to display gate steps with meaningful labels. In the step parsing logic, when `agent == "qv-gate"`, use the `gate` field for the label:

```python
# In _parse_workflow_manifest(), after extracting step fields:
if agent_label == "qv-gate" and "gate" in step_data:
    agent_label = f"QV: {step_data['gate']}"
elif agent_label == "qv-browser":
    agent_label = "QV: Browser"
```

#### 4.2.7 Gate Timeout

Individual QV gates should have a shorter timeout since they're just running a make command:

```bash
MAX_STEP_TIMEOUT_QV_GATE="${MAX_STEP_TIMEOUT_QV_GATE:-600}"  # 10 minutes
```

Integration tests may take longer, so allow per-gate override:

```json
{"step": "S12", "agent": "qv-gate", "gate": "integration-tests",
 "command": "make allure-integration", "timeout": 900}
```

Read the optional `timeout` field in the step loop:
```bash
local step_timeout
step_timeout=$(get_step_field "$ITEM_ID" "$step_index" ".timeout")
[[ -z "$step_timeout" || "$step_timeout" == "null" ]] && step_timeout="$MAX_STEP_TIMEOUT_QV_GATE"
```

### 4.3 Files to Modify

| File | Changes |
|------|---------|
| `scripts/step_executor.sh` | Add `qv-gate)` and `qv-browser)` cases in step loop (after line 620) |
| `scripts/step_executor_lib.sh` | Add `run_single_qv_gate()` function; update `get_step_type()` and `get_agent_label()`; add `MAX_STEP_TIMEOUT_QV_GATE` constant |
| `scripts/ai_dashboard/scanner.py` | Handle `qv-gate` and `qv-browser` agent labels |
| `ai-dev/templates/` | Update workflow manifest templates to emit individual gate steps |

### 4.4 Manifest Template Update

All workflow manifest templates (used by `/iw-new-feature`, `/iw-new-incident`, `/iw-new-cr`) must be updated to emit individual QV gate steps instead of a single `quality-validation-impl` step. This is done in the design generation skills.

The standard QV gate sequence is always:

```
1. lint           — make lint
2. format         — make format-check
3. typecheck      — make type-check
4. frontend-tsc   — cd frontend && npx tsc --noEmit
5. arch-check     — make arch-check
6. security-sast  — make security-sast
7. unit-tests     — make test-unit
8. frontend-tests — make test-frontend
9. integration-tests — make allure-integration
10. browser-verification (optional, only if browser_verification: true)
```

**Gate steps that only apply to backend work**: If a work item has NO frontend changes (no files under `frontend/`), the `frontend-tsc` and `frontend-tests` gates should be omitted from the manifest. The design generation skill should check `affected_files` and only include frontend gates if there are frontend files.

**Gate steps that only apply to frontend work**: If a work item has NO backend changes (no files under `src/`), the `typecheck` (mypy), `arch-check`, `security-sast`, `unit-tests`, and `integration-tests` gates can be omitted. However, to be safe and catch cross-cutting regressions, **always include all gates**. The gates are fast enough (typically < 2 min each except integration tests) that the overhead is acceptable.

---

## 5. E2: QV Gate Fix Cycles

### 5.1 Goal

When a QV gate fails (e.g., lint errors, mypy errors, test failures), automatically invoke an LLM fix agent to resolve the issue, then re-run the gate. Up to 3 fix cycles per gate.

### 5.2 Design

#### 5.2.1 New Configuration

```bash
MAX_QV_FIX_CYCLES="${MAX_QV_FIX_CYCLES:-3}"  # Max fix attempts per gate
```

#### 5.2.2 QV Fix Cycle Handler

Add to `scripts/step_executor.sh`:

```bash
# Handle QV gate fix cycles.
# Invokes an LLM agent to fix the gate failure, then re-runs the gate.
handle_qv_fix_cycle() {
    local step_index="$1"
    local step_id="$2"
    local gate_name="$3"
    local gate_cmd="$4"
    local gate_report="$5"   # report from the failed gate run

    local fix_cycle=0
    while [[ $fix_cycle -lt $MAX_QV_FIX_CYCLES ]]; do
        fix_cycle=$((fix_cycle + 1))
        _lib_log "    QV FIX CYCLE $fix_cycle/$MAX_QV_FIX_CYCLES for $gate_name"

        # 1. Generate QV fix prompt
        local fix_prompt
        fix_prompt=$(generate_qv_fix_prompt "$ITEM_ID" "$step_id" "$gate_name" \
            "$gate_cmd" "$gate_report" "$fix_cycle" "$WORKTREE_PATH")

        # 2. Determine fix agent based on gate type
        local fix_agent
        fix_agent=$(get_qv_fix_agent "$gate_name")

        # 3. Execute fix
        local fix_report="ai-dev/work/$ITEM_ID/reports/${ITEM_ID}_${step_id}_QV_FIX_${gate_name}_report.md"
        if [[ $fix_cycle -gt 1 ]]; then
            fix_report="ai-dev/work/$ITEM_ID/reports/${ITEM_ID}_${step_id}_QV_FIX_${gate_name}_report_run_${fix_cycle}.md"
        fi
        local fix_log="${ITEM_LOG%.log}_${step_id}_qvfix_${fix_cycle}.log"

        execute_single_step "${step_id}_QV_FIX" "$fix_agent" \
            "$fix_prompt" "$fix_report" "$fix_log" || true

        # 4. Re-run the gate
        local rerun_report="ai-dev/work/$ITEM_ID/reports/${ITEM_ID}_${step_id}_QV_${gate_name}_report_run_$((fix_cycle + 1)).md"
        local rerun_exit=0
        run_single_qv_gate "$ITEM_ID" "$step_id" "$gate_name" "$gate_cmd" \
            "$WORKTREE_PATH" "$rerun_report" || rerun_exit=$?

        # 5. Record fix cycle
        add_fix_cycle "$ITEM_ID" "$step_index" "$fix_cycle" \
            "$fix_prompt" "$fix_report"

        if [[ $rerun_exit -eq 0 ]]; then
            set_step_status "$ITEM_ID" "$step_index" "completed"
            _lib_log "    QV fix cycle $fix_cycle resolved $gate_name"
            return 0
        fi

        # Update report pointer for next cycle
        gate_report="$rerun_report"
    done

    _lib_log_error "    QV ESCALATION: $MAX_QV_FIX_CYCLES fix cycles exhausted for $gate_name"
    return 1
}
```

#### 5.2.3 QV Fix Agent Mapping

Different gates need different fix agents:

```bash
# Determine which fix agent to use for a QV gate failure.
get_qv_fix_agent() {
    local gate_name="$1"
    case "$gate_name" in
        lint|format)
            # Lint/format can be auto-fixed by running make format
            echo "code-review-fix-impl" ;;
        typecheck)
            # Mypy errors need a Python expert
            echo "code-review-fix-impl" ;;
        frontend-tsc|frontend-tests)
            # Frontend issues need frontend agent
            echo "code-review-fix-impl" ;;
        unit-tests|integration-tests)
            # Test failures need the test fix agent
            echo "code-review-fix-impl" ;;
        arch-check|security-sast)
            # Architecture/security violations need careful fixes
            echo "code-review-fix-impl" ;;
        *)
            echo "code-review-fix-impl" ;;
    esac
}
```

#### 5.2.4 QV Fix Prompt Generation

Add to `scripts/step_executor_lib.sh`:

```bash
# Generate a fix prompt for a failed QV gate.
generate_qv_fix_prompt() {
    local item_id="$1"
    local step_id="$2"
    local gate_name="$3"
    local gate_cmd="$4"
    local gate_report="$5"   # relative path to failed gate report
    local fix_cycle="$6"
    local worktree_path="$7"

    local prompt_dir="$worktree_path/ai-dev/work/$item_id/prompts"
    mkdir -p "$prompt_dir"

    local prompt_file="${prompt_dir}/${item_id}_${step_id}_QV_FIX_${gate_name}_prompt.md"
    if [[ "$fix_cycle" -gt 1 ]]; then
        prompt_file="${prompt_dir}/${item_id}_${step_id}_QV_FIX_${gate_name}_cycle_${fix_cycle}_prompt.md"
    fi

    # Read the gate output from the report
    local gate_output=""
    if [[ -f "$worktree_path/$gate_report" ]]; then
        gate_output=$(awk '/^## Output/,/^## /' "$worktree_path/$gate_report" | head -80)
    fi

    # For lint/format, try auto-fix first
    local auto_fix_hint=""
    case "$gate_name" in
        lint)
            auto_fix_hint="
**Quick Fix**: Try running \`make format\` first — many lint issues are auto-fixable.
After formatting, run \`make lint\` again to see remaining issues." ;;
        format)
            auto_fix_hint="
**Quick Fix**: Run \`make format\` to auto-format all files. Then verify with \`make format-check\`." ;;
    esac

    cat > "$prompt_file" << QVFIXEOF
# ${item_id}_${step_id}_QV_FIX_${gate_name}_prompt

**Work Item**: ${item_id}
**Step**: ${step_id}_QV_FIX
**Gate**: ${gate_name}
**Fix Cycle**: ${fix_cycle} of ${MAX_QV_FIX_CYCLES} maximum

---

## Context

The quality validation gate **${gate_name}** failed. You must fix the errors so the gate passes.

**Gate Command**: \`${gate_cmd}\`
${auto_fix_hint}

## Gate Output (Errors)

${gate_output}

## Instructions

1. Read the gate output above carefully
2. Fix ALL errors reported by the gate
3. Run the gate command again to verify: \`${gate_cmd}\`
4. Ensure no other gates are broken by your fixes
5. Write your report

## Constraints

- ONLY fix errors reported by this gate
- Do NOT refactor or improve unrelated code
- Do NOT change public interfaces unless required
- Ensure existing tests still pass after fixes

## Output Files

- \`ai-dev/work/${item_id}/reports/${item_id}_${step_id}_QV_FIX_${gate_name}_report.md\`

## Subagent Result Contract

\`\`\`json
{
  "step": "${step_id}_QV_FIX",
  "agent": "QV_FIX_${gate_name}",
  "work_item": "${item_id}",
  "completion_status": "complete",
  "gate": "${gate_name}",
  "fix_cycle": ${fix_cycle},
  "errors_fixed": [],
  "tests_passed": true,
  "notes": ""
}
\`\`\`
QVFIXEOF

    echo "ai-dev/work/$item_id/prompts/$(basename "$prompt_file")"
}
```

### 5.3 Special Handling: Lint/Format Auto-Fix

For lint and format gates, try an auto-fix BEFORE invoking the LLM:

```bash
# In the qv-gate) case, before calling handle_qv_fix_cycle:
if [[ "$gate_name" == "lint" || "$gate_name" == "format" ]]; then
    _lib_log "    Attempting auto-fix for $gate_name..."
    (cd "$WORKTREE_PATH" && make format 2>&1 | tail -5) || true

    # Re-run the gate
    local auto_report="ai-dev/work/$ITEM_ID/reports/${ITEM_ID}_${step_id}_QV_${gate_name}_autofix_report.md"
    local auto_exit=0
    run_single_qv_gate "$ITEM_ID" "$step_id" "$gate_name" "$gate_cmd" \
        "$WORKTREE_PATH" "$auto_report" || auto_exit=$?

    if [[ $auto_exit -eq 0 ]]; then
        set_step_status "$ITEM_ID" "$step_index" "completed"
        add_step_run "$ITEM_ID" "$step_index" "$run_number" "$auto_report" "pass"
        _lib_log "    Auto-fix resolved $gate_name"
        # Skip the case block's fallthrough — use continue or break
        break  # exit the case, step is done
    fi
fi
```

### 5.4 Files to Modify

| File | Changes |
|------|---------|
| `scripts/step_executor.sh` | Add `handle_qv_fix_cycle()` function; add auto-fix logic for lint/format in `qv-gate)` case |
| `scripts/step_executor_lib.sh` | Add `generate_qv_fix_prompt()`, `get_qv_fix_agent()`; add `MAX_QV_FIX_CYCLES` constant |

---

## 6. E3: Dynamic Timeouts

### 6.1 Goal

Replace the static 30-minute timeout with dynamic timeouts based on step type, agent type, complexity, and fix cycle context.

### 6.2 Design

#### 6.2.1 New Timeout Constants

Update `scripts/step_executor_lib.sh`:

```bash
# Base timeouts by category
MAX_STEP_TIMEOUT="${MAX_STEP_TIMEOUT:-2700}"                    # 45 min (was 30)
MAX_STEP_TIMEOUT_FRONTEND="${MAX_STEP_TIMEOUT_FRONTEND:-3600}"  # 60 min for frontend-impl
MAX_STEP_TIMEOUT_REVIEW="${MAX_STEP_TIMEOUT_REVIEW:-1800}"      # 30 min for reviews
MAX_STEP_TIMEOUT_FIX="${MAX_STEP_TIMEOUT_FIX:-2700}"            # 45 min for fix cycles
MAX_STEP_TIMEOUT_QV_GATE="${MAX_STEP_TIMEOUT_QV_GATE:-600}"     # 10 min per QV gate
MAX_STEP_TIMEOUT_QV_INTEG="${MAX_STEP_TIMEOUT_QV_INTEG:-900}"   # 15 min for integration tests
MAX_STEP_TIMEOUT_QV_BROWSER="${MAX_STEP_TIMEOUT_QV_BROWSER:-1800}"  # 30 min for browser verification
```

#### 6.2.2 Timeout Selection Function

Add to `scripts/step_executor_lib.sh`:

```bash
# Determine the appropriate timeout for a step.
# Takes into account agent type, gate name, fix cycle context, and manifest overrides.
get_step_timeout() {
    local agent="$1"
    local gate_name="${2:-}"     # Only for qv-gate steps
    local is_fix="${3:-false}"   # Whether this is a fix cycle
    local manifest_timeout="${4:-}"  # Per-step override from manifest

    # Manifest override takes highest priority
    if [[ -n "$manifest_timeout" && "$manifest_timeout" != "null" && "$manifest_timeout" != "0" ]]; then
        echo "$manifest_timeout"
        return
    fi

    # Fix cycle gets its own timeout
    if [[ "$is_fix" == "true" ]]; then
        echo "$MAX_STEP_TIMEOUT_FIX"
        return
    fi

    case "$agent" in
        frontend-impl)
            echo "$MAX_STEP_TIMEOUT_FRONTEND" ;;
        code-review-impl|code-review-final-impl)
            echo "$MAX_STEP_TIMEOUT_REVIEW" ;;
        qv-gate)
            case "$gate_name" in
                integration-tests)
                    echo "$MAX_STEP_TIMEOUT_QV_INTEG" ;;
                *)
                    echo "$MAX_STEP_TIMEOUT_QV_GATE" ;;
            esac ;;
        qv-browser|quality-validation-impl)
            echo "$MAX_STEP_TIMEOUT_QV_BROWSER" ;;
        *)
            echo "$MAX_STEP_TIMEOUT" ;;
    esac
}
```

#### 6.2.3 Integration with Step Loop

In `step_executor.sh`, before executing each step, determine the timeout:

```bash
# After reading step details (line 453), add:
local manifest_timeout
manifest_timeout=$(get_step_field "$ITEM_ID" "$step_index" ".timeout")

# Then in execute_single_step calls, replace hardcoded timeout:
local step_timeout
step_timeout=$(get_step_timeout "$step_agent" "" "false" "$manifest_timeout")
execute_single_step "$step_id" "$step_agent" \
    "$prompt_file" "$report_path" "$step_log" "$step_timeout"
```

For fix cycles in `handle_fix_cycles()`, pass the fix timeout:

```bash
# Line 370, replace:
execute_single_step "${step_id}_FIX" "$fix_agent" \
    "$fix_prompt_relative" "$fix_report" "$fix_log" "$MAX_STEP_TIMEOUT_FIX"
```

#### 6.2.4 Timeout Escalation on Retry

When a fix cycle times out and retries, increase the timeout by 50%:

```bash
# In handle_fix_cycles(), after detecting a timeout:
if [[ $fix_cycle -gt 1 ]]; then
    local escalated_timeout=$((MAX_STEP_TIMEOUT_FIX + (MAX_STEP_TIMEOUT_FIX / 2)))
    # Cap at 1 hour
    [[ $escalated_timeout -gt 3600 ]] && escalated_timeout=3600
    execute_single_step "${step_id}_FIX" "$fix_agent" \
        "$fix_prompt_relative" "$fix_report" "$fix_log" "$escalated_timeout"
fi
```

### 6.3 Files to Modify

| File | Changes |
|------|---------|
| `scripts/step_executor_lib.sh` | Add timeout constants and `get_step_timeout()` function |
| `scripts/step_executor.sh` | Use `get_step_timeout()` for all `execute_single_step` calls; pass `$MAX_STEP_TIMEOUT_FIX` to fix cycle calls |

---

## 7. E4: Fix Daemon Status Recognition

### 7.1 Goal

Make the daemon handle unrecognized batch/item status values gracefully instead of ignoring them.

### 7.2 Design

#### 7.2.1 Status Normalization

Add a normalization layer to `scripts/ai_dev_daemon/state_machine.py`:

```python
# Status aliases — maps legacy/non-standard values to canonical values
BATCH_STATUS_ALIASES: dict[str, str] = {
    "running": "executing",
    "run": "executing",
    "active": "executing",
    "done": "completed",
    "error": "completed_with_errors",
    "cancelled": "archived",
    "draft": "planning",
}

ITEM_STATUS_ALIASES: dict[str, str] = {
    "running": "executing",
    "in_progress": "executing",
    "done": "completed",
    "error": "failed",
    "timeout": "failed",
}


def normalize_batch_status(status: str) -> str:
    """Normalize a batch status string to a canonical value.

    Returns the canonical status string, or the original if not recognized.
    """
    normalized = status.lower().strip()
    if normalized in BATCH_STATUS_ALIASES:
        return BATCH_STATUS_ALIASES[normalized]
    # Check if it's already a valid status
    try:
        BatchStatus(normalized)
        return normalized
    except ValueError:
        return normalized  # Return as-is, let caller handle


def normalize_item_status(status: str) -> str:
    """Normalize an item status string to a canonical value."""
    normalized = status.lower().strip()
    if normalized in ITEM_STATUS_ALIASES:
        return ITEM_STATUS_ALIASES[normalized]
    try:
        ItemStatus(normalized)
        return normalized
    except ValueError:
        return normalized
```

#### 7.2.2 Use Normalization in Batch Manager

In `scripts/ai_dev_daemon/batch_manager.py`, wherever batch status is read from the manifest, normalize it:

```python
from .state_machine import normalize_batch_status, normalize_item_status

# In discover_batches() or _process_batch():
raw_status = manifest.get("status", "")
status = normalize_batch_status(raw_status)
if status != raw_status:
    logger.info("Normalized batch status '%s' → '%s' for %s", raw_status, status, batch_id)
    # Update the manifest with the canonical value
    update_batch_manifest(manifest_path, lambda d: d.update({"status": status}))
```

#### 7.2.3 Log Warning for Truly Unknown Statuses

If normalization still results in an unrecognized status, log a clear error with guidance:

```python
try:
    batch_status = BatchStatus(status)
except ValueError:
    logger.error(
        "UNKNOWN batch status '%s' (original: '%s') in %s — "
        "valid statuses: %s. Skipping this batch.",
        status, raw_status, batch_id,
        ", ".join(s.value for s in BatchStatus),
    )
    continue  # Skip, but don't spam warnings every poll
```

### 7.3 Files to Modify

| File | Changes |
|------|---------|
| `scripts/ai_dev_daemon/state_machine.py` | Add `BATCH_STATUS_ALIASES`, `ITEM_STATUS_ALIASES`, `normalize_batch_status()`, `normalize_item_status()` |
| `scripts/ai_dev_daemon/batch_manager.py` | Normalize status values when reading manifests; auto-fix manifests with legacy values |
| `scripts/ai_dev_daemon/manifest.py` | Apply normalization in `read_workflow_status()` for item statuses |

---

## 8. E5: Per-Step Process Tracking

### 8.1 Goal

Track the PID, start time, and timeout deadline of each step's LLM process in the workflow manifest, so the daemon and dashboard can show per-step process health.

### 8.2 Design

#### 8.2.1 Step-Level Process Fields

Add these fields to each step in the workflow manifest:

```json
{
  "step": "S01",
  "agent": "frontend-impl",
  "status": "in_progress",
  "pid": 578531,
  "started_at": "2026-03-29T19:54:43+00:00",
  "timeout_at": "2026-03-29T20:24:43+00:00",
  "completed_at": null,
  "exit_code": null
}
```

#### 8.2.2 Write PID Before Execution

In `step_executor.sh`, modify `execute_single_step()` to capture and record the PID:

```bash
execute_single_step() {
    # ... existing setup ...

    local exit_code=0
    cd "$WORKTREE_PATH"

    if [[ "$CLI_TOOL" == "opencode" ]]; then
        TMPDIR="$WORKTREE_PATH/.tmp" INNOFORGE_BATCH_MODE=1 \
            timeout "$timeout_secs" \
            opencode run "$instruction" \
            < /dev/null >> "$step_log" 2>&1 &
        local child_pid=$!

        # Record PID in workflow manifest
        update_step_process "$ITEM_ID" "$step_index" "$child_pid" "$timeout_secs"

        wait $child_pid || exit_code=$?
    # ... similar for claude ...
    fi

    # Record completion
    update_step_completion "$ITEM_ID" "$step_index" "$exit_code"

    # ... existing report check logic ...
}
```

**Note**: This changes the execution model from synchronous to background + wait. The `timeout` command must still wrap the `opencode run` — the backgrounding is just to capture the PID.

Actually, a simpler approach that doesn't change the execution model:

```bash
# Before the timeout+opencode invocation, write a pre-execution record:
set_step_process_info "$ITEM_ID" "$step_index" "$$" "$timeout_secs"

# The step_executor.sh PID ($$) is the parent — the daemon can check this.
# The actual opencode PID is a child of the timeout command, which is a child of $$.
```

#### 8.2.3 New Library Functions

Add to `scripts/step_executor_lib.sh`:

```bash
# Record process info for a step before execution starts.
set_step_process_info() {
    local item_id="$1"
    local index="$2"
    local pid="$3"
    local timeout_secs="$4"
    local mf
    mf=$(get_wf_manifest_path "$item_id") || return 1

    local started_at timeout_at
    started_at=$(date -Iseconds)
    timeout_at=$(date -Iseconds -d "+${timeout_secs} seconds" 2>/dev/null || \
                 date -v+${timeout_secs}S -Iseconds 2>/dev/null || \
                 echo "")

    local tmp="${mf}.tmp"
    jq --argjson idx "$index" \
       --argjson p "$pid" \
       --arg sa "$started_at" \
       --arg ta "$timeout_at" \
        '.steps[$idx].pid = $p |
         .steps[$idx].started_at = $sa |
         .steps[$idx].timeout_at = $ta |
         .steps[$idx].completed_at = null |
         .steps[$idx].exit_code = null' \
        "$mf" > "$tmp" && mv "$tmp" "$mf"
}

# Record step completion info.
set_step_completion_info() {
    local item_id="$1"
    local index="$2"
    local exit_code="$3"
    local mf
    mf=$(get_wf_manifest_path "$item_id") || return 1

    local completed_at
    completed_at=$(date -Iseconds)

    local tmp="${mf}.tmp"
    jq --argjson idx "$index" \
       --argjson ec "$exit_code" \
       --arg ca "$completed_at" \
        '.steps[$idx].completed_at = $ca |
         .steps[$idx].exit_code = $ec |
         .steps[$idx].pid = null' \
        "$mf" > "$tmp" && mv "$tmp" "$mf"
}
```

#### 8.2.4 Dashboard Display

Update `scripts/ai_dashboard/templates/item_detail.html` to show per-step process info:

- For `in_progress` steps: show PID, elapsed time, and time until timeout
- Show a "ZOMBIE" badge if PID exists but process is dead
- Show timeout countdown (time remaining)

### 8.3 Files to Modify

| File | Changes |
|------|---------|
| `scripts/step_executor_lib.sh` | Add `set_step_process_info()`, `set_step_completion_info()` |
| `scripts/step_executor.sh` | Call `set_step_process_info()` before each `execute_single_step`; call `set_step_completion_info()` after |
| `scripts/ai_dashboard/scanner.py` | Parse `pid`, `started_at`, `timeout_at`, `completed_at`, `exit_code` from step data |
| `scripts/ai_dashboard/templates/item_detail.html` | Display per-step process info in step pipeline |

---

## 9. E6: Item-Level Restart from Dashboard

### 9.1 Goal

Allow the dashboard operator to restart a failed/stalled item from a specific step, or restart the entire item, directly from the dashboard UI.

### 9.2 Design

#### 9.2.1 New API Endpoints

Add to `scripts/ai_dashboard/server.py`:

**POST /api/item/{ID}/restart-from/{step_number}**
- Kills any running process for the item (if PID is still alive)
- Resets steps N through end to `pending` in the workflow manifest
- Resets the item status to `executing` in the batch manifest
- Relaunches `step_executor.sh` for the item in the existing worktree
- Returns the new PID

**POST /api/item/{ID}/restart**
- Same as restart-from/S01 (restart everything)

**POST /api/item/{ID}/kill**
- Kills the step_executor.sh process (and all children)
- Marks item as `failed` in the batch manifest
- Does NOT restart — just frees the slot

#### 9.2.2 Implementation: Restart from Step N

```python
@app.route("/api/item/<item_id>/restart-from/<step_number>", methods=["POST"])
def restart_item_from_step(item_id: str, step_number: str) -> Response:
    """Restart execution of an item from a specific step."""

    # 1. Find the batch this item belongs to
    batch_id = find_batch_for_item(item_id)
    if not batch_id:
        return jsonify({"error": f"Item {item_id} not found in any active batch"}), 404

    batch_manifest_path = os.path.join(
        repo_root, "ai-dev", "work", batch_id, "batch-manifest.json"
    )
    batch_manifest = read_json(batch_manifest_path)
    item = get_item(batch_manifest, item_id)

    # 2. Kill existing process if alive
    old_pid = item.get("pid", 0)
    if old_pid > 0:
        try:
            # Kill the process group (step_executor + all children)
            os.killpg(os.getpgid(old_pid), signal.SIGTERM)
            time.sleep(2)
            # Force kill if still alive
            try:
                os.killpg(os.getpgid(old_pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
        except (ProcessLookupError, OSError):
            pass

    # 3. Reset steps from step_number onward to pending
    worktree_path = os.path.join(repo_root, ".worktrees", item_id)
    wf_manifest_path = os.path.join(
        worktree_path, "ai-dev", "work", item_id, "workflow-manifest.json"
    )

    if os.path.isfile(wf_manifest_path):
        wf = read_json(wf_manifest_path)
        step_idx = int(step_number.replace("S", "").replace("s", "")) - 1

        for i, step in enumerate(wf.get("steps", [])):
            if i >= step_idx:
                step["status"] = "pending"
                step.pop("pid", None)
                step.pop("started_at", None)
                step.pop("timeout_at", None)
                step.pop("completed_at", None)
                step.pop("exit_code", None)

        wf["status"] = "in_progress"
        wf["updated_at"] = datetime.now(timezone.utc).isoformat()
        write_json(wf_manifest_path, wf)

    # 4. Relaunch step_executor.sh
    log_dir = os.path.join(repo_root, "ai-dev", "work", batch_id, "logs")
    item_log = os.path.join(log_dir, f"{item_id}.log")
    cli_tool = batch_manifest.get("cli_tool", "opencode")
    batch_dir = os.path.join(repo_root, "ai-dev", "work", batch_id)

    proc = subprocess.Popen(
        [
            "bash", os.path.join(repo_root, "scripts", "step_executor.sh"),
            item_id, worktree_path, item_log, cli_tool, batch_dir,
        ],
        stdout=open(item_log, "a"),
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,  # detach from dashboard process
        cwd=repo_root,
    )

    # 5. Update batch manifest
    set_item_field(
        batch_manifest_path,
        item_id,
        status="executing",
        pid=proc.pid,
        stall_count=0,
        notes=f"restarted from {step_number}",
    )

    return jsonify({
        "status": "restarted",
        "item_id": item_id,
        "from_step": step_number,
        "pid": proc.pid,
    })
```

#### 9.2.3 Dashboard UI Buttons

In `scripts/ai_dashboard/templates/item_detail.html`, add restart buttons to the step pipeline:

```html
{% if item.status in ('failed', 'stalled') %}
  <div class="item-actions">
    <button onclick="restartItem('{{ item.id }}')"
            class="btn btn-warning">
      Restart Item
    </button>
    <button onclick="killItem('{{ item.id }}')"
            class="btn btn-danger">
      Kill Item
    </button>
  </div>
{% endif %}

<!-- Per-step restart buttons -->
{% for step in item.steps %}
  {% if step.status == 'failed' %}
    <button onclick="restartFromStep('{{ item.id }}', '{{ step.step_number }}')"
            class="btn btn-sm btn-outline-warning">
      Restart from {{ step.step_number }}
    </button>
  {% endif %}
{% endfor %}
```

Add JavaScript:
```javascript
async function restartFromStep(itemId, stepNumber) {
    if (!confirm(`Restart ${itemId} from step ${stepNumber}?`)) return;
    const resp = await fetch(`/api/item/${itemId}/restart-from/${stepNumber}`, {method: 'POST'});
    const data = await resp.json();
    if (resp.ok) {
        alert(`Restarted ${itemId} from ${stepNumber} (PID: ${data.pid})`);
        location.reload();
    } else {
        alert(`Error: ${data.error}`);
    }
}

async function restartItem(itemId) {
    restartFromStep(itemId, 'S01');
}

async function killItem(itemId) {
    if (!confirm(`Kill ${itemId}? This will mark it as failed.`)) return;
    const resp = await fetch(`/api/item/${itemId}/kill`, {method: 'POST'});
    const data = await resp.json();
    if (resp.ok) {
        alert(`Killed ${itemId}`);
        location.reload();
    } else {
        alert(`Error: ${data.error}`);
    }
}
```

#### 9.2.4 Worktree Verification

Before restarting, verify the worktree exists and is in a usable state:

```python
# In restart_item_from_step():
worktree_path = os.path.join(repo_root, ".worktrees", item_id)
if not os.path.isdir(worktree_path):
    return jsonify({
        "error": f"Worktree not found at {worktree_path}. "
                 f"Run 'make worktree-new ITEM={item_id}' to recreate it."
    }), 400
```

### 9.3 Files to Modify

| File | Changes |
|------|---------|
| `scripts/ai_dashboard/server.py` | Add `/api/item/{ID}/restart-from/{step}`, `/api/item/{ID}/restart`, `/api/item/{ID}/kill` endpoints |
| `scripts/ai_dashboard/templates/item_detail.html` | Add restart/kill buttons and JavaScript handlers |
| `scripts/ai_dashboard/templates/batch_detail.html` | Add per-item restart buttons in the items table |

---

## 10. E7: Smart Fix Cycle Escalation

### 10.1 Goal

When fix cycles repeatedly fail or time out, apply smarter strategies instead of blindly retrying the same approach.

### 10.2 Design

#### 10.2.1 Escalation Strategies

```
Fix Cycle 1: Normal execution (standard timeout)
Fix Cycle 2: If cycle 1 timed out → increase timeout by 50%
Fix Cycle 3: If same finding persists across 2 reviews → split into smaller fixes
Fix Cycle 4: If still failing → reduce scope (fix only CRITICAL, skip HIGH)
Fix Cycle 5: If still failing → mark as "needs human review" and continue workflow
```

#### 10.2.2 Finding Deduplication

Track which findings persist across fix cycles:

```bash
# In handle_fix_cycles(), after each re-review:
local current_findings
current_findings=$(extract_finding_ids "$WORKTREE_PATH/$rereview_report")
local previous_findings
previous_findings=$(extract_finding_ids "$WORKTREE_PATH/$review_report")

# Count recurring findings
local recurring=0
for f in $current_findings; do
    if echo "$previous_findings" | grep -q "$f"; then
        recurring=$((recurring + 1))
    fi
done

if [[ $recurring -gt 0 ]]; then
    _lib_log "    WARNING: $recurring findings recurred from previous review"
fi
```

#### 10.2.3 Graceful Skip on Cycle 5

On the last fix cycle, instead of failing the entire workflow, allow the step to pass with a warning:

```bash
# At the end of handle_fix_cycles(), when all cycles exhausted:
# Instead of immediate failure, check if findings are LOW/MEDIUM only
local remaining_critical
remaining_critical=$(grep -cP '(CRITICAL|HIGH)' "$WORKTREE_PATH/$review_report" 2>/dev/null || echo "0")

if [[ "$remaining_critical" -eq 0 ]]; then
    _lib_log "  WARNING: Fix cycles exhausted but only LOW/MEDIUM findings remain — treating as PASS"
    set_step_status "$ITEM_ID" "$step_index" "completed"
    return 0
fi

_lib_log_error "  ESCALATION: $MAX_FIX_CYCLES fix cycles exhausted — CRITICAL/HIGH findings remain"
return 1
```

### 10.3 Files to Modify

| File | Changes |
|------|---------|
| `scripts/step_executor.sh` | Modify `handle_fix_cycles()` to implement escalation strategies |
| `scripts/step_executor_lib.sh` | Add `extract_finding_ids()` helper; modify fix prompt generation to reduce scope on later cycles |

---

## 11. E8: Zombie Process Cleanup

### 11.1 Goal

Prevent zombie process accumulation by properly reaping child processes.

### 11.2 Design

#### 11.2.1 Zombie Reaper in Daemon

Add to `scripts/ai_dev_daemon/daemon.py` in the main loop:

```python
import os

def _reap_zombies(self) -> None:
    """Reap any zombie child processes to prevent accumulation."""
    try:
        while True:
            pid, status = os.waitpid(-1, os.WNOHANG)
            if pid == 0:
                break  # No more zombies
            logger.debug("Reaped zombie process %d (exit status %d)", pid, os.WEXITSTATUS(status))
    except ChildProcessError:
        pass  # No children to reap
```

Call `_reap_zombies()` at the start of each poll cycle in `_main_loop()`.

#### 11.2.2 Process Group Isolation in Step Executor

Ensure `step_executor.sh` runs each `opencode`/`claude` invocation in its own process group so that `timeout` can kill the entire group:

```bash
# In execute_single_step(), use setsid:
setsid timeout "$timeout_secs" \
    opencode run "$instruction" \
    < /dev/null >> "$step_log" 2>&1 || exit_code=$?
```

**Note**: `setsid` creates a new session, so `timeout` can kill the entire process group. This prevents orphaned pyright language servers and other child processes.

### 11.3 Files to Modify

| File | Changes |
|------|---------|
| `scripts/ai_dev_daemon/daemon.py` | Add `_reap_zombies()` method; call in main loop |
| `scripts/step_executor.sh` | Add `setsid` to `timeout` invocations in `execute_single_step()` |

---

## 12. E9: Dashboard Real-Time Step View

### 12.1 Goal

Show real-time per-step execution status in the dashboard, including PID health, elapsed time, timeout countdown, fix cycle number, and current log tail.

### 12.2 Design

#### 12.2.1 Enhanced Step Pipeline in Item Detail

Each step in the pipeline should show:

| Field | Source | Display |
|-------|--------|---------|
| Step number | `step.step_number` | Badge: S01, S02, ... |
| Agent label | `step.agent` or `step.gate` | Label: "Backend", "QV: lint" |
| Status | `step.status` | Color badge: green=completed, blue=in_progress, red=failed, gray=pending |
| PID | `step.pid` | PID number + alive/zombie indicator |
| Elapsed | `step.started_at` → now | "15m 23s" |
| Timeout | `step.timeout_at` | "14m 37s remaining" or "TIMED OUT" |
| Fix cycle | From `step.fix_cycles` array | "Fix 2/5" |
| Last log line | Read last line of step log | Truncated to 80 chars |

#### 12.2.2 Process Health Check in Scanner

Update `scripts/ai_dashboard/scanner.py` to check PID health:

```python
def check_pid_alive(pid: int) -> str:
    """Check process health. Returns 'alive', 'zombie', or 'dead'."""
    if not pid or pid <= 0:
        return "dead"
    try:
        with open(f"/proc/{pid}/status") as f:
            for line in f:
                if line.startswith("State:"):
                    if "Z" in line:
                        return "zombie"
                    return "alive"
        return "alive"
    except (FileNotFoundError, OSError):
        return "dead"
```

#### 12.2.3 Step Detail Card (Expanded View)

When a step is clicked/expanded in the pipeline:

```html
<div class="step-detail-card">
  <h4>S07 — Frontend Implementation</h4>

  <div class="step-meta">
    <span class="badge bg-primary">in_progress</span>
    <span class="badge bg-info">PID 578531 (alive)</span>
    <span>Elapsed: 15m 23s</span>
    <span>Timeout: 14m 37s remaining</span>
  </div>

  {% if step.fix_cycles %}
  <div class="fix-cycles">
    <h5>Fix Cycles</h5>
    <table>
      <tr><th>Cycle</th><th>Fix Report</th><th>Re-review Verdict</th></tr>
      {% for fc in step.fix_cycles %}
      <tr>
        <td>{{ fc.cycle_number }}/5</td>
        <td><a href="#">{{ fc.fix_report }}</a></td>
        <td>{{ fc.verdict }}</td>
      </tr>
      {% endfor %}
    </table>
  </div>
  {% endif %}

  <div class="step-actions">
    {% if step.status == 'in_progress' %}
      <button onclick="killStep('{{ item.id }}', {{ step.step_number }})">Kill Step</button>
    {% endif %}
    {% if step.status == 'failed' %}
      <button onclick="restartFromStep('{{ item.id }}', '{{ step.step_number }}')">
        Restart from Here
      </button>
    {% endif %}
  </div>

  <div class="step-log">
    <h5>Log (last 20 lines)</h5>
    <pre>{{ step.log_tail }}</pre>
  </div>
</div>
```

#### 12.2.4 Auto-Refresh

Add auto-refresh to the item detail page (every 15 seconds when the item is executing):

```javascript
{% if item.status in ('executing', 'in_progress') %}
<script>
  setTimeout(() => location.reload(), 15000);
</script>
{% endif %}
```

### 12.3 Files to Modify

| File | Changes |
|------|---------|
| `scripts/ai_dashboard/scanner.py` | Add `check_pid_alive()`; parse step-level PID, timestamps, fix cycles |
| `scripts/ai_dashboard/renderer.py` | Pass step log tails to templates; compute elapsed/remaining times |
| `scripts/ai_dashboard/templates/item_detail.html` | Redesign step pipeline with expanded detail cards; add auto-refresh |
| `scripts/ai_dashboard/static/` | Add CSS for step detail cards, timeout countdown, PID badges |

---

## 13. Implementation Order & Dependencies

### Phase 1: Critical Fixes (E3, E4) — No manifest changes needed

These are quick wins that fix existing bugs without changing the step structure.

```
E3: Dynamic Timeouts
  └─ Modify: step_executor_lib.sh (add constants + get_step_timeout)
  └─ Modify: step_executor.sh (use get_step_timeout in all execute calls)
  └─ No manifest changes, no dashboard changes
  └─ Estimated: 2 files, ~80 lines changed

E4: Fix Daemon Status Recognition
  └─ Modify: state_machine.py (add aliases + normalize functions)
  └─ Modify: batch_manager.py (normalize on read)
  └─ Modify: manifest.py (normalize item statuses)
  └─ Estimated: 3 files, ~60 lines changed
```

### Phase 2: QV Split (E1, E2) — Core orchestration change

This is the biggest change and must be done carefully.

```
E1: Split QV Into Individual Gate Steps
  └─ Modify: step_executor_lib.sh (add run_single_qv_gate, gate timeout constant, update get_step_type/get_agent_label)
  └─ Modify: step_executor.sh (add qv-gate and qv-browser cases)
  └─ Modify: scanner.py (handle new agent labels)
  └─ Keep old qv) case for backward compat
  └─ Estimated: 3 files, ~150 lines added

E2: QV Gate Fix Cycles (depends on E1)
  └─ Modify: step_executor.sh (add handle_qv_fix_cycle function)
  └─ Modify: step_executor_lib.sh (add generate_qv_fix_prompt, get_qv_fix_agent, MAX_QV_FIX_CYCLES)
  └─ Estimated: 2 files, ~120 lines added
```

### Phase 3: Process Management (E5, E8)

```
E5: Per-Step Process Tracking
  └─ Modify: step_executor_lib.sh (add set_step_process_info, set_step_completion_info)
  └─ Modify: step_executor.sh (call process tracking functions)
  └─ Modify: scanner.py (parse new step fields)
  └─ Modify: item_detail.html (display PID + timing info)
  └─ Estimated: 4 files, ~100 lines added

E8: Zombie Process Cleanup
  └─ Modify: daemon.py (add _reap_zombies method)
  └─ Modify: step_executor.sh (add setsid to timeout invocations)
  └─ Estimated: 2 files, ~20 lines added
```

### Phase 4: Dashboard Controls (E6, E9)

```
E6: Item-Level Restart
  └─ Modify: server.py (add restart-from, restart, kill endpoints)
  └─ Modify: item_detail.html (add buttons + JS)
  └─ Modify: batch_detail.html (add per-item restart buttons)
  └─ Estimated: 3 files, ~200 lines added

E9: Dashboard Real-Time Step View (depends on E5)
  └─ Modify: scanner.py (add check_pid_alive, compute timings)
  └─ Modify: renderer.py (pass step data to templates)
  └─ Modify: item_detail.html (redesign step pipeline)
  └─ Modify: static/ CSS (step detail cards)
  └─ Estimated: 4 files, ~300 lines changed
```

### Phase 5: Smart Behavior (E7)

```
E7: Smart Fix Cycle Escalation
  └─ Modify: step_executor.sh (modify handle_fix_cycles)
  └─ Modify: step_executor_lib.sh (add finding dedup, modify fix prompt for later cycles)
  └─ Estimated: 2 files, ~80 lines changed
```

### Dependency Graph

```
E3 (timeouts) ─────────────────────────────── standalone
E4 (status fix) ────────────────────────────── standalone

E1 (split QV) ─── depends on nothing
  └── E2 (QV fix cycles) ── depends on E1

E5 (step tracking) ──── depends on nothing
  └── E9 (dashboard view) ── depends on E5

E8 (zombie cleanup) ────────────────────────── standalone

E6 (restart) ───────────────────────────────── standalone

E7 (smart escalation) ─── should come after E3
```

### Recommended Work Item Breakdown

| Work Item | Enhancements | Dependencies | Scope |
|-----------|-------------|--------------|-------|
| **I-QV-SPLIT** | E1 + E2 | None | step_executor.sh, step_executor_lib.sh, scanner.py |
| **I-TIMEOUTS** | E3 | None | step_executor_lib.sh, step_executor.sh |
| **I-DAEMON-FIX** | E4 + E8 | None | state_machine.py, batch_manager.py, manifest.py, daemon.py |
| **I-STEP-TRACKING** | E5 | None | step_executor_lib.sh, step_executor.sh, scanner.py, item_detail.html |
| **I-DASHBOARD-RESTART** | E6 | None | server.py, item_detail.html, batch_detail.html |
| **I-DASHBOARD-VIEW** | E9 | E5 | scanner.py, renderer.py, item_detail.html, static/ |
| **I-SMART-ESCALATION** | E7 | E3 | step_executor.sh, step_executor_lib.sh |

---

## 14. Testing Strategy

### 14.1 Unit Tests for Bash Functions

Create test scripts in `tests/scripts/` using `bats` (Bash Automated Testing System):

```bash
# tests/scripts/test_step_executor_lib.bats

@test "get_step_type returns qv-gate for qv-gate agent" {
    source scripts/step_executor_lib.sh
    run get_step_type "qv-gate"
    [ "$output" = "qv-gate" ]
}

@test "get_step_timeout returns 600 for qv-gate" {
    source scripts/step_executor_lib.sh
    run get_step_timeout "qv-gate" "lint" "false" ""
    [ "$output" = "600" ]
}

@test "get_step_timeout returns manifest override when set" {
    source scripts/step_executor_lib.sh
    run get_step_timeout "frontend-impl" "" "false" "5400"
    [ "$output" = "5400" ]
}

@test "normalize_batch_status maps running to executing" {
    # Python test
    from scripts.ai_dev_daemon.state_machine import normalize_batch_status
    assert normalize_batch_status("running") == "executing"
}
```

### 14.2 Integration Tests

Test the full step execution flow with a mock work item:

1. Create a test workflow manifest with QV gate steps
2. Create a test worktree with intentional lint errors
3. Run `step_executor.sh` and verify:
   - Individual gates produce separate reports
   - Lint gate fails and triggers fix cycle
   - Fix cycle auto-fixes lint, re-runs gate → passes
   - Integration test gate has its own timeout
   - Browser verification step is skipped when `browser_verification: false`

### 14.3 Dashboard Tests

Test the new API endpoints:

1. POST `/api/item/{ID}/restart-from/S05` — verify step reset and process relaunch
2. POST `/api/item/{ID}/kill` — verify process termination
3. Verify the step pipeline renders correctly with QV gate steps

### 14.4 Backward Compatibility Tests

1. Run an old-format manifest (single `quality-validation-impl` step) through the step executor → must still work via the `qv)` case
2. Run a new-format manifest (individual `qv-gate` steps) → must work via the `qv-gate)` case
3. Verify daemon handles both `"running"` and `"executing"` batch statuses

---

## 15. Migration & Backward Compatibility

### 15.1 Old Manifests

Existing workflow manifests with `"agent": "quality-validation-impl"` will continue to work unchanged. The `qv)` case in the step loop is preserved. Only new manifests generated after this enhancement will use the split gate format.

### 15.2 Running Batches

These changes should NOT be applied to currently executing batches. Deploy the changes, then start new batches with the new manifest format.

### 15.3 Design Templates

The design generation skills (`/iw-new-feature`, `/iw-new-incident`, `/iw-new-cr`) must be updated to emit the new QV gate step format. This is a separate change to the skill definitions and templates in `ai-dev/templates/`.

### 15.4 Configuration

All new timeouts and limits use environment variable overrides with sensible defaults. No configuration file changes needed. Existing `MAX_STEP_TIMEOUT` and `MAX_FIX_CYCLES` environment variables continue to work.

---

## Appendix A: Current File Inventory

| File | Lines | Role |
|------|-------|------|
| `scripts/step_executor.sh` | 674 | Main step execution loop |
| `scripts/step_executor_lib.sh` | 738 | Shared library (manifest I/O, QV runner) |
| `scripts/ai_dev_daemon/daemon.py` | ~225 | Main daemon loop |
| `scripts/ai_dev_daemon/batch_manager.py` | 920 | Batch orchestration |
| `scripts/ai_dev_daemon/state_machine.py` | 125 | Status enums + transitions |
| `scripts/ai_dev_daemon/manifest.py` | ~255 | JSON I/O + fallback chains |
| `scripts/ai_dashboard/server.py` | ~600 | HTTP server + API endpoints |
| `scripts/ai_dashboard/scanner.py` | ~450 | Manifest reading + data model |
| `scripts/ai_dashboard/renderer.py` | ~413 | Jinja2 rendering |
| `scripts/ai_dashboard/templates/item_detail.html` | ~536 | Item detail page |
| `scripts/ai_dashboard/templates/batch_detail.html` | ~382 | Batch detail page |

## Appendix B: Environment Variable Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_STEP_TIMEOUT` | 2700 (was 1800) | Default step timeout in seconds |
| `MAX_STEP_TIMEOUT_FRONTEND` | 3600 | Timeout for frontend-impl steps |
| `MAX_STEP_TIMEOUT_REVIEW` | 1800 | Timeout for review steps |
| `MAX_STEP_TIMEOUT_FIX` | 2700 | Timeout for fix cycle steps |
| `MAX_STEP_TIMEOUT_QV_GATE` | 600 | Timeout for individual QV gates |
| `MAX_STEP_TIMEOUT_QV_INTEG` | 900 | Timeout for integration test gate |
| `MAX_STEP_TIMEOUT_QV_BROWSER` | 1800 | Timeout for browser verification |
| `MAX_FIX_CYCLES` | 5 | Max code review fix cycles |
| `MAX_QV_FIX_CYCLES` | 3 | Max QV gate fix cycles |
| `MAX_CONTINUATIONS` | 3 | Max continuation attempts |
| `MAX_TEST_REGRESSION_RETRIES` | 3 | Max test regression fix attempts |
