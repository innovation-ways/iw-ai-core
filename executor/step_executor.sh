#!/usr/bin/env bash
# =============================================================================
# IW AI Core — Step Executor
# =============================================================================
#
# Executes a single workflow step for a work item by launching an LLM agent.
# Reports completion via the iw CLI (step-done / step-fail).
#
# In normal daemon operation, the daemon launches agents directly via
# subprocess.Popen. This script is for manual execution and testing.
#
# Usage:
#   executor/step_executor.sh <item_id> <step_id> <worktree_path> \
#       [<cli_tool>] [<project_repo_root>]
#
# Arguments:
#   item_id           Work item ID (e.g. I001)
#   step_id           Step ID to execute (e.g. S01, S03)
#   worktree_path     Absolute path to the git worktree
#   cli_tool          Agent CLI: "opencode" or "claude" (default: opencode)
#   project_repo_root Absolute path to the project repo (optional, for context)
#
# Exit codes:
#   0 — step completed successfully (iw step-done called)
#   1 — step failed (iw step-fail called)
#   2 — setup error (wrong args, worktree missing, etc.)
#
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Arguments
# ---------------------------------------------------------------------------
ITEM_ID="${1:?Usage: step_executor.sh <item_id> <step_id> <worktree_path> [<cli_tool>] [<project_repo_root>]}"
STEP_ID="${2:?step_id is required}"
WORKTREE_PATH="${3:?worktree_path is required}"
CLI_TOOL="${4:-opencode}"
PROJECT_REPO_ROOT="${5:-}"

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source the shared library (sets WORKTREE_PATH requirement)
# shellcheck source=step_executor_lib.sh
source "$SCRIPT_DIR/step_executor_lib.sh"

# Validate worktree exists
if [[ ! -d "$WORKTREE_PATH" ]] || [[ ! -f "$WORKTREE_PATH/.git" ]]; then
    echo "ERROR: Worktree not found or invalid: $WORKTREE_PATH" >&2
    exit 2
fi

# Create working directories
mkdir -p "$WORKTREE_PATH/.tmp"
mkdir -p "$WORKTREE_PATH/ai-dev/work/$ITEM_ID/reports"
mkdir -p "$WORKTREE_PATH/ai-dev/work/$ITEM_ID/logs"

# ---------------------------------------------------------------------------
# Log file
# ---------------------------------------------------------------------------
LOG_DIR="$WORKTREE_PATH/ai-dev/work/$ITEM_ID/logs"
LOG_FILE="$LOG_DIR/${ITEM_ID}_${STEP_ID}_manual.log"
mkdir -p "$LOG_DIR"

_lib_log "=== Step Executor: $ITEM_ID $STEP_ID ==="
_lib_log "  Worktree: $WORKTREE_PATH"
_lib_log "  CLI tool: $CLI_TOOL"

# ---------------------------------------------------------------------------
# Read step info from DB via iw CLI
# ---------------------------------------------------------------------------
cd "$WORKTREE_PATH"

ITEM_JSON=$(iw item-status "$ITEM_ID" --json 2>/dev/null) || {
    _lib_log_error "Could not get item status for $ITEM_ID"
    exit 2
}

# Find this step in the steps array
STEP_JSON=$(echo "$ITEM_JSON" | jq --arg sid "$STEP_ID" '.steps[] | select(.step_id == $sid)' 2>/dev/null || echo "")

if [[ -z "$STEP_JSON" ]]; then
    _lib_log_error "Step $STEP_ID not found in item $ITEM_ID"
    exit 2
fi

STEP_TYPE=$(echo "$STEP_JSON" | jq -r '.type // "implementation"')
STEP_LABEL=$(echo "$STEP_JSON" | jq -r '.label // "'"$STEP_ID"'"')
STEP_STATUS=$(echo "$STEP_JSON" | jq -r '.status // "unknown"')

_lib_log "  Step: $STEP_ID ($STEP_LABEL) type=$STEP_TYPE status=$STEP_STATUS"

# Check step is in a launchable state
if [[ "$STEP_STATUS" != "pending" ]] && [[ "$STEP_STATUS" != "in_progress" ]]; then
    _lib_log_error "Step $STEP_ID is in status '$STEP_STATUS' — cannot execute"
    exit 2
fi

# Determine timeout
TIMEOUT=$(get_step_timeout "$STEP_TYPE")
_lib_log "  Timeout: ${TIMEOUT}s"

# ---------------------------------------------------------------------------
# Mark step as started
# ---------------------------------------------------------------------------
if [[ "$STEP_STATUS" == "pending" ]]; then
    iw_step_start "$ITEM_ID" "$STEP_ID"
fi

# ---------------------------------------------------------------------------
# Build agent instruction
# ---------------------------------------------------------------------------
# The /execute skill in the worktree knows how to read execution_brief.json
# and execute the step. We pass the item_id and step_id as arguments.
INSTRUCTION="/execute ${ITEM_ID} ${STEP_ID}"

# ---------------------------------------------------------------------------
# Launch the agent
# ---------------------------------------------------------------------------
_lib_log "  Launching $CLI_TOOL for $STEP_ID..."

STEP_LOG="$LOG_DIR/${ITEM_ID}_${STEP_ID}_run.log"
EXIT_CODE=0

cd "$WORKTREE_PATH"

if [[ "$CLI_TOOL" == "opencode" ]]; then
    # Isolate opencode state per item to avoid SQLite contention
    OC_DATA_HOME="/tmp/opencode-worker-${ITEM_ID}"
    mkdir -p "$OC_DATA_HOME/opencode"
    [[ -f "${XDG_DATA_HOME:-$HOME/.local/share}/opencode/auth.json" ]] && \
        cp "${XDG_DATA_HOME:-$HOME/.local/share}/opencode/auth.json" \
           "$OC_DATA_HOME/opencode/auth.json" 2>/dev/null || true

    XDG_DATA_HOME="$OC_DATA_HOME" OPENCODE_DATA_DIR="$OC_DATA_HOME/opencode" \
    TMPDIR="$WORKTREE_PATH/.tmp" \
        setsid timeout "$TIMEOUT" \
        opencode run "$INSTRUCTION" \
        < /dev/null >> "$STEP_LOG" 2>&1 || EXIT_CODE=$?

    rm -rf "$OC_DATA_HOME"

elif [[ "$CLI_TOOL" == "claude" ]]; then
    TMPDIR="$WORKTREE_PATH/.tmp" \
        setsid timeout "$TIMEOUT" \
        claude -p "$INSTRUCTION" --permission-mode bypassPermissions \
        < /dev/null >> "$STEP_LOG" 2>&1 || EXIT_CODE=$?

else
    _lib_log_error "Unknown CLI tool: $CLI_TOOL (expected 'opencode' or 'claude')"
    iw_step_fail "$ITEM_ID" "$STEP_ID" "Unknown CLI tool: $CLI_TOOL"
    exit 1
fi

_lib_log "  Agent exited with code: $EXIT_CODE"

# ---------------------------------------------------------------------------
# Find report file (agent may have written it)
# ---------------------------------------------------------------------------
REPORT_DIR="$WORKTREE_PATH/ai-dev/work/$ITEM_ID/reports"
REPORT_FILE=""

# Look for any report matching the step ID
if [[ -d "$REPORT_DIR" ]]; then
    FOUND_REPORT=$(find "$REPORT_DIR" -name "${ITEM_ID}_${STEP_ID}_*report*.md" 2>/dev/null | sort | tail -1 || true)
    if [[ -n "$FOUND_REPORT" ]]; then
        # Return relative path from worktree
        REPORT_FILE="${FOUND_REPORT#$WORKTREE_PATH/}"
        _lib_log "  Report: $REPORT_FILE"
    fi
fi

# ---------------------------------------------------------------------------
# Determine step outcome
# ---------------------------------------------------------------------------
STEP_OUTCOME="success"
FAIL_REASON=""

if [[ $EXIT_CODE -eq 124 ]]; then
    STEP_OUTCOME="timeout"
    FAIL_REASON="Agent timed out after ${TIMEOUT}s"
    _lib_log_error "  TIMEOUT: $ITEM_ID $STEP_ID after ${TIMEOUT}s"

elif [[ $EXIT_CODE -ne 0 ]]; then
    STEP_OUTCOME="agent_failed"
    FAIL_REASON="Agent exited with code $EXIT_CODE"
    _lib_log_error "  Agent failed: exit code $EXIT_CODE"
fi

# For review steps: parse the verdict from the report file
if [[ "$STEP_OUTCOME" == "success" && "$STEP_TYPE" =~ ^(review|code_review)$ ]]; then
    if [[ -n "$REPORT_FILE" ]]; then
        VERDICT=$(parse_review_verdict "$WORKTREE_PATH/$REPORT_FILE")
        _lib_log "  Review verdict: $VERDICT"

        if [[ "$VERDICT" == "NEEDS_FIX" ]]; then
            # Review passed the execution but found issues — still mark step done
            # The daemon/fix cycle management picks up the verdict from the report
            _lib_log "  Review found issues — marking step done with verdict in report"
        elif [[ "$VERDICT" == "MISSING_REPORT" ]] || [[ "$VERDICT" == "UNKNOWN" ]]; then
            STEP_OUTCOME="agent_failed"
            FAIL_REASON="Review agent did not produce a parseable verdict (report: $REPORT_FILE)"
        fi
    else
        STEP_OUTCOME="agent_failed"
        FAIL_REASON="Review agent did not produce a report file"
    fi
fi

# For QV steps: check if all gates passed (if we ran them in lib mode)
# When the agent runs the step, it handles QV internally via the /execute skill.
# No special handling needed here beyond checking exit code.

# ---------------------------------------------------------------------------
# Report outcome to DB via iw CLI
# ---------------------------------------------------------------------------
if [[ "$STEP_OUTCOME" == "success" ]]; then
    if [[ -n "$REPORT_FILE" ]]; then
        iw_step_done "$ITEM_ID" "$STEP_ID" "$REPORT_FILE"
    else
        iw_step_done "$ITEM_ID" "$STEP_ID"
    fi
    _lib_log "=== Step $STEP_ID completed successfully ==="
    exit 0
else
    iw_step_fail "$ITEM_ID" "$STEP_ID" "$FAIL_REASON"
    _lib_log_error "=== Step $STEP_ID failed: $FAIL_REASON ==="
    exit 1
fi
