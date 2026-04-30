#!/usr/bin/env bash
# =============================================================================
# IW AI Core — Step Executor Library
# =============================================================================
#
# Shared functions for step execution. Sourced by step_executor.sh.
#
# Provides:
#   - iw CLI wrappers (step-start, step-done, step-fail)
#   - Agent type mapping and label extraction
#   - Review verdict parsing (grep-based, no LLM)
#   - Fix prompt generation (heredoc template)
#   - Quality gate runner (bash-driven)
#
# All state operations go through the iw CLI — no manifest files are
# read or written.
#
# Caller must set WORKTREE_PATH before sourcing this file.
# =============================================================================

# ---------------------------------------------------------------------------
# Configuration — override via environment variables
# ---------------------------------------------------------------------------
MAX_FIX_CYCLES="${MAX_FIX_CYCLES:-5}"
MAX_STEP_TIMEOUT="${MAX_STEP_TIMEOUT:-3600}"
MAX_QV_FIX_CYCLES="${MAX_QV_FIX_CYCLES:-3}"

# Dynamic timeouts by step type (seconds)
MAX_STEP_TIMEOUT_IMPL="${MAX_STEP_TIMEOUT_IMPL:-2700}"        # 45 min
MAX_STEP_TIMEOUT_REVIEW="${MAX_STEP_TIMEOUT_REVIEW:-1800}"    # 30 min
MAX_STEP_TIMEOUT_FIX="${MAX_STEP_TIMEOUT_FIX:-2700}"          # 45 min
MAX_STEP_TIMEOUT_QV="${MAX_STEP_TIMEOUT_QV:-1200}"            # 20 min — qv-gate uses claude whose bash tool allows up to 870 s
MAX_STEP_TIMEOUT_BROWSER="${MAX_STEP_TIMEOUT_BROWSER:-1800}"  # 30 min

# Caller must set WORKTREE_PATH before sourcing
: "${WORKTREE_PATH:?WORKTREE_PATH must be set before sourcing step_executor_lib.sh}"

# ---------------------------------------------------------------------------
# Logging (uses LOG_FILE from caller if set, otherwise stderr only)
# ---------------------------------------------------------------------------
_lib_log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "$msg" >&2
    if [[ -n "${LOG_FILE:-}" ]]; then
        echo "$msg" >> "$LOG_FILE"
    fi
}

_lib_log_error() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1"
    echo "$msg" >&2
    if [[ -n "${LOG_FILE:-}" ]]; then
        echo "$msg" >> "$LOG_FILE"
    fi
}

# =============================================================================
# iw CLI Wrappers
# =============================================================================
# These replace the manifest I/O functions from the old step_executor_lib.sh.
# All state transitions go through the iw CLI → PostgreSQL.
# =============================================================================

# Mark a step as started.
iw_step_start() {
    local item_id="$1"
    local step_id="$2"
    iw step-start "$item_id" --step "$step_id" 2>&1 | while IFS= read -r line; do
        _lib_log "  [iw step-start] $line"
    done || true
}

# Mark a step as completed successfully.
# Usage: iw_step_done <item_id> <step_id> [<report_file>]
iw_step_done() {
    local item_id="$1"
    local step_id="$2"
    local report_file="${3:-}"

    local args=("step-done" "$item_id" "--step" "$step_id")
    if [[ -n "$report_file" ]]; then
        args+=("--report" "$report_file")
    fi

    iw "${args[@]}" 2>&1 | while IFS= read -r line; do
        _lib_log "  [iw step-done] $line"
    done
}

# Mark a step as failed.
# Usage: iw_step_fail <item_id> <step_id> <reason>
iw_step_fail() {
    local item_id="$1"
    local step_id="$2"
    local reason="$3"

    iw step-fail "$item_id" --step "$step_id" --reason "$reason" 2>&1 | \
        while IFS= read -r line; do
            _lib_log "  [iw step-fail] $line"
        done
}

# =============================================================================
# Agent Type Mapping
# =============================================================================

# Determine the step type from the agent name or step_type string.
# Returns: "implementation" | "review" | "fix" | "qv" | "qv-gate" | "browser"
get_step_type() {
    local agent="$1"
    case "$agent" in
        code-review-fix-final*|code_review_fix_final)
            echo "fix" ;;
        code-review-fix*|code_review_fix)
            echo "fix" ;;
        code-review-final*|code_review_final)
            echo "review" ;;
        code-review*|code_review)
            echo "review" ;;
        quality-validation*|quality_validation)
            echo "qv" ;;
        qv-gate|qv_gate)
            echo "qv-gate" ;;
        qv-fix|qv_fix)
            echo "fix" ;;
        browser-verification*|browser_verification*)
            echo "browser" ;;
        qv-browser|qv_browser)
            echo "browser" ;;
        *)
            echo "implementation" ;;
    esac
}

# Map agent name to a human-readable label for report filenames.
get_agent_label() {
    local agent="$1"
    case "$agent" in
        frontend-impl)                echo "Frontend" ;;
        backend-impl)                 echo "Backend" ;;
        api-impl)                     echo "API" ;;
        database-impl)                echo "Database" ;;
        tests-impl)                   echo "Tests" ;;
        pipeline-impl)                echo "Pipeline" ;;
        template-impl)                echo "Template" ;;
        code-review-impl)             echo "CodeReview" ;;
        code-review-final-impl)       echo "CodeReview_Final" ;;
        code-review-fix-impl)         echo "CodeReview_FIX" ;;
        code-review-fix-final-impl)   echo "CodeReview_FIX_Final" ;;
        quality-validation-impl)      echo "QualityValidation" ;;
        qv-gate)                      echo "QV_Gate" ;;
        qv-browser)                   echo "QV_Browser" ;;
        *)                            echo "$agent" ;;
    esac
}

# Determine the appropriate timeout for a step.
get_step_timeout() {
    local step_type="$1"
    local is_fix="${2:-false}"

    if [[ "$is_fix" == "true" ]]; then
        echo "$MAX_STEP_TIMEOUT_FIX"
        return
    fi

    case "$step_type" in
        implementation)  echo "$MAX_STEP_TIMEOUT_IMPL" ;;
        review)          echo "$MAX_STEP_TIMEOUT_REVIEW" ;;
        fix)             echo "$MAX_STEP_TIMEOUT_FIX" ;;
        qv|qv-gate)      echo "$MAX_STEP_TIMEOUT_QV" ;;
        browser)         echo "$MAX_STEP_TIMEOUT_BROWSER" ;;
        *)               echo "$MAX_STEP_TIMEOUT" ;;
    esac
}

# Determine the fix agent for a given review agent.
get_fix_agent_for_review() {
    local review_agent="$1"
    case "$review_agent" in
        code-review-final-impl)       echo "code-review-fix-final-impl" ;;
        *)                            echo "code-review-fix-impl" ;;
    esac
}

# =============================================================================
# Review Verdict Parsing
# =============================================================================
# Parses structured report files produced by review agents.
# Three strategies tried in order: JSON contract → markdown → fallback.
# =============================================================================

# Parse the review verdict from a report file.
# Returns: "PASS" | "NEEDS_FIX" | "FAIL" | "UNKNOWN" | "MISSING_REPORT"
parse_review_verdict() {
    local report_file="$1"

    if [[ ! -f "$report_file" ]]; then
        echo "MISSING_REPORT"
        return
    fi

    local verdict=""

    # Strategy 1: JSON result contract — "verdict": "PASS" or "verdict": "NEEDS_FIX"
    verdict=$(grep -oP '"verdict"\s*:\s*"\K[^"]+' "$report_file" 2>/dev/null | tail -1)

    if [[ -n "$verdict" ]]; then
        case "$verdict" in
            PASS|pass|PASS_WITH_NOTES)    echo "PASS" ;;
            NEEDS_FIX|"NEEDS FIX"|FAIL|fail|GATES_FAILED) echo "NEEDS_FIX" ;;
            *)                            echo "$verdict" ;;
        esac
        return
    fi

    # Strategy 2: Markdown — **Result**: PASS or **Result**: NEEDS FIX
    local md_result
    md_result=$(grep -oP '\*\*Result\*\*:\s*\*{0,2}\K[A-Z_\s]+' "$report_file" 2>/dev/null | tail -1 | xargs)

    if [[ -n "$md_result" ]]; then
        case "$md_result" in
            PASS|"PASS")                  echo "PASS" ;;
            NEEDS*|FAIL*)                 echo "NEEDS_FIX" ;;
            *)                            echo "UNKNOWN" ;;
        esac
        return
    fi

    echo "UNKNOWN"
}

# Parse the mandatory fix count from a review report.
# Returns an integer (0 if no mandatory fixes found).
parse_mandatory_fix_count() {
    local report_file="$1"

    if [[ ! -f "$report_file" ]]; then
        echo "0"
        return
    fi

    # Strategy 1: JSON contract — "mandatory_fix_count": N
    local json_count
    json_count=$(grep -oP '"mandatory_fix_count"\s*:\s*\K\d+' "$report_file" 2>/dev/null | tail -1)
    if [[ -n "$json_count" ]]; then
        echo "$json_count"
        return
    fi

    # Strategy 2: Count ### headings with mandatory severity keywords
    local finding_count
    finding_count=$(grep -cP '^###\s+.*(CRITICAL|HIGH|MEDIUM\s*\(fixable\))' "$report_file" 2>/dev/null || true)
    echo "${finding_count:-0}"
}

# Extract mandatory findings from a review report for inclusion in a fix prompt.
extract_findings_for_fix() {
    local report_file="$1"

    if [[ ! -f "$report_file" ]]; then
        echo "(no findings — report file missing)"
        return
    fi

    local findings
    findings=$(awk '
        /^###/ {
            if (block != "" && block ~ /(CRITICAL|HIGH|MEDIUM.*fixable)/) {
                print block
            }
            block = $0 "\n"
            next
        }
        block != "" {
            block = block $0 "\n"
        }
        END {
            if (block != "" && block ~ /(CRITICAL|HIGH|MEDIUM.*fixable)/) {
                print block
            }
        }
    ' "$report_file")

    if [[ -n "$findings" ]]; then
        echo "$findings"
    else
        # Fallback: include everything between "## Findings" and the next section
        awk '/^## Findings/,/^## [^F]/' "$report_file" | head -100
    fi
}

# =============================================================================
# Fix Prompt Generation
# =============================================================================

# Generate a fix prompt file and return its path (relative to worktree).
generate_fix_prompt() {
    local item_id="$1"
    local review_step="$2"       # e.g., "S02"
    local agent_label="$3"       # e.g., "Frontend"
    local review_report="$4"     # path relative to worktree
    local fix_cycle="$5"         # cycle number (1-N)
    local worktree_path="$6"

    local fix_prompt_dir="$worktree_path/ai-dev/work/$item_id/prompts"
    local fix_prompt_file="${fix_prompt_dir}/${item_id}_${review_step}_CodeReview_FIX_${agent_label}_prompt.md"

    if [[ "$fix_cycle" -gt 1 ]]; then
        fix_prompt_file="${fix_prompt_dir}/${item_id}_${review_step}_CodeReview_FIX_${agent_label}_cycle_${fix_cycle}_prompt.md"
    fi

    mkdir -p "$fix_prompt_dir"

    local findings
    findings=$(extract_findings_for_fix "$worktree_path/$review_report")

    # Get work item title via iw CLI
    local title="implementation"
    if command -v iw >/dev/null 2>&1; then
        title=$(cd "$worktree_path" && iw item-status "$item_id" --json 2>/dev/null | jq -r '.title // "implementation"' 2>/dev/null || echo "implementation")
    fi

    cat > "$fix_prompt_file" << FIXEOF
# ${item_id}_${review_step}_CodeReview_FIX_${agent_label}_prompt

**Work Item**: ${item_id} — ${title}
**Step**: ${review_step}_FIX
**Fixing**: Code review findings from ${review_step}
**Agent**: CodeReview_FIX_${agent_label}
**Fix Cycle**: ${fix_cycle} of ${MAX_FIX_CYCLES} maximum

---

## Input Files

- \`ai-dev/work/${item_id}/reports/$(basename "$review_report")\` — Code review report with findings to fix
- All source files referenced in the findings below

## Output Files

- \`ai-dev/work/${item_id}/reports/${item_id}_${review_step}_CodeReview_FIX_${agent_label}_report.md\`

## Context

The code review for your **${agent_label}** implementation found issues that need to be fixed.

**Code Review Report**: \`${review_report}\`

Read the review report first to understand all findings, then fix them.

## Findings to Fix

${findings}

$(if [[ "$fix_cycle" -ge 4 ]]; then
    echo "**REDUCED SCOPE (cycle $fix_cycle)**: Fix CRITICAL findings ONLY."
elif [[ "$fix_cycle" -ge 3 ]]; then
    echo "Fix CRITICAL and HIGH findings ONLY. Skip MEDIUM (fixable), MEDIUM (suggestion), and LOW."
else
    echo "Fix CRITICAL, HIGH, and MEDIUM (fixable) findings. Skip MEDIUM (suggestion) and LOW."
fi)

## Constraints

- **ONLY** fix the issues listed above
- Do NOT refactor or improve code that was not flagged
- Do NOT change the public interface unless the review specifically requires it
- Ensure all existing tests still pass after fixes

## Subagent Result Contract

\`\`\`json
{
  "step": "${review_step}_FIX",
  "agent": "CodeReview_FIX_${agent_label}",
  "work_item": "${item_id}",
  "completion_status": "complete",
  "fix_cycle": ${fix_cycle},
  "findings_addressed": [],
  "findings_skipped": [],
  "tests_passed": true,
  "notes": ""
}
\`\`\`
FIXEOF

    echo "ai-dev/work/$item_id/prompts/$(basename "$fix_prompt_file")"
}

# =============================================================================
# Quality Gate Runner
# =============================================================================
# Runs quality gates as pure bash commands.
# Returns 0 if gate passes, 1 if it fails.
# =============================================================================

run_single_qv_gate() {
    local item_id="$1"
    local step_id="$2"
    local gate_name="$3"
    local gate_cmd="$4"
    local worktree_path="$5"
    local report_file_rel="$6"     # relative to worktree

    local abs_report="$worktree_path/$report_file_rel"
    mkdir -p "$(dirname "$abs_report")"

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

    return $exit_code
}

# Run all quality validation gates defined in project config.
# Gates are read from .iw-orch.json if present; defaults used otherwise.
# Returns 0 if all gates pass, 1 if any fail.
run_quality_validation() {
    local item_id="$1"
    local qv_step="$2"
    local worktree_path="$3"

    local report_dir="$worktree_path/ai-dev/work/$item_id/reports"
    local report_file="$report_dir/${item_id}_${qv_step}_QualityValidation_report.md"
    mkdir -p "$report_dir"

    # Get item title
    local title="implementation"
    if command -v iw >/dev/null 2>&1; then
        title=$(cd "$worktree_path" && iw item-status "$item_id" --json 2>/dev/null | jq -r '.title // "implementation"' 2>/dev/null || echo "implementation")
    fi

    # Read quality_gates from .iw-orch.json if present
    local iw_orch_file="$worktree_path/.iw-orch.json"
    local -a gates=()
    if [[ -f "$iw_orch_file" ]]; then
        # Read gates as "name:command" entries from quality_gates array
        # Expected format: ["make lint", "make type-check", ...]
        while IFS= read -r gate_cmd; do
            if [[ -n "$gate_cmd" ]]; then
                local gate_name
                gate_name=$(echo "$gate_cmd" | sed 's/[^a-zA-Z0-9]/-/g' | sed 's/--*/-/g' | sed 's/^-//' | sed 's/-$//')
                gates+=("${gate_name}:${gate_cmd}")
            fi
        done < <(jq -r '.quality_gates[]? // empty' "$iw_orch_file" 2>/dev/null || true)
    fi

    # Defaults if no gates configured
    if [[ ${#gates[@]} -eq 0 ]]; then
        gates=(
            "lint:make lint"
            "type-check:make type-check"
            "unit-tests:make test-unit"
        )
    fi

    # Initialize report
    cat > "$report_file" << HEADER
# ${item_id}_${qv_step}_QualityValidation_report

**Work Item**: ${item_id} — ${title}
**Step**: ${qv_step}
**Agent**: QualityValidation (script-driven)
**Date**: $(date '+%Y-%m-%d')

---

## Quality Gates

HEADER

    local all_passed=true
    local -a gate_names=()
    local -a gate_results=()

    for gate_entry in "${gates[@]}"; do
        local gate_name="${gate_entry%%:*}"
        local gate_cmd="${gate_entry#*:}"

        _lib_log "  QV gate: $gate_name"

        local output exit_code=0
        output=$(cd "$worktree_path" && eval "$gate_cmd" 2>&1 | tail -30) || exit_code=$?

        local result="PASS"
        if [[ $exit_code -ne 0 ]]; then
            result="FAIL"
            all_passed=false
        fi

        cat >> "$report_file" << GATEENTRY

### $gate_name

**Command**: \`$gate_cmd\`
**Result**: $result (exit code: $exit_code)

\`\`\`
$(echo "$output" | tail -20)
\`\`\`

GATEENTRY

        gate_names+=("$gate_name")
        gate_results+=("$result")
    done

    # Summary table
    cat >> "$report_file" << 'SUMMARY'

---

## Summary

| Gate | Status |
|------|--------|
SUMMARY

    for i in "${!gate_names[@]}"; do
        echo "| ${gate_names[$i]} | ${gate_results[$i]} |" >> "$report_file"
    done

    local overall="ALL_GATES_PASSED"
    if [[ "$all_passed" != "true" ]]; then
        overall="GATES_FAILED"
    fi

    cat >> "$report_file" << VERDICT

---

**Overall**: $overall

## Subagent Result Contract

\`\`\`json
{
  "step": "${qv_step}",
  "agent": "QualityValidation",
  "work_item": "${item_id}",
  "completion_status": "complete",
  "overall": "${overall}",
  "notes": "Script-driven QV — quality gates run by bash"
}
\`\`\`
VERDICT

    if [[ "$all_passed" == "true" ]]; then
        return 0
    else
        return 1
    fi
}
