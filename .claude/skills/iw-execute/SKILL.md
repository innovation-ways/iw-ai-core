---
name: iw-execute
version: "2.1.0"
description: >
  Execute the AI development workflow for a work item via the IW AI Core platform.
  Checks item status, starts steps via iw CLI, delegates to specialist subagents.
  Supports resume for interrupted workflows. Use when user says "execute", "run", "/iw-execute".
argument-hint: "[work-item-ID, e.g., F001, I006, CR002]"
allowed-tools: Read, Grep, Glob, Edit, Write, Bash
disable-model-invocation: true
context: fork
agent: orchestrator
---

# Execute Work Item Workflow

Execute the AI development workflow for work item **$ARGUMENTS**.

**Argument parsing:** `$ARGUMENTS` may contain `ITEM_ID STEP_ID` (e.g. `CR-00003 S03`) when invoked by the daemon.
- **ITEM_ID** = first token (e.g. `CR-00003`)
- **STEP_ID** = second token if present (e.g. `S03`) — use to resume from that step

## Pre-Flight Data

Current status from platform:
!`uv run iw item-status $(echo $ARGUMENTS | awk '{print $1}') --json 2>/dev/null || echo '{"error": "item not found or not registered"}'`

Work item design document location:
!`ls -d ai-dev/active/$(echo $ARGUMENTS | awk '{print $1}') 2>/dev/null || echo "NOT_FOUND: $(echo $ARGUMENTS | awk '{print $1}') not in ai-dev/active/"`

## Pre-Flight Validation

Parse `$ARGUMENTS` into `ITEM_ID` (first token) and optional `STEP_ID` (second token).
Use only `ITEM_ID` for all `iw` CLI commands below.

Before executing, validate:

1. **Item is registered** — `uv run iw item-status ITEM_ID` must succeed
2. **Item status is `approved`** — if `draft`, tell user to run `uv run iw approve ITEM_ID` first
3. **Design doc exists** — must be in `ai-dev/active/ITEM_ID/`

## If item not found:

Report error: "Work item ITEM_ID not found in database. Create a design first with /iw-new-feature, /iw-new-incident, or /iw-new-cr, then register it with `uv run iw register`."

## If item status is `draft`:

Report: "Work item ITEM_ID is in 'draft' status. Review the design, then approve with: `iw approve ITEM_ID`"

## If item status is `approved` or `in_progress`:

Begin execution. For each step in the workflow:

### Step Execution Protocol

1. Before starting each step, call:
   ```bash
   uv run iw step-start ITEM_ID --step S{NN}
   ```

2. Delegate the step to the correct specialist subagent using **path-based delegation** (pass the prompt file path)

3. After step completes successfully, write a report then call step-done:
   ```bash
   mkdir -p ai-dev/active/ITEM_ID/reports
   ```
   Write a markdown report to `ai-dev/active/ITEM_ID/reports/ITEM_ID_S{NN}_{AgentLabel}_report.md` containing:
   - Completion status and step description
   - Files changed (list)
   - Test results summary
   - Any notes or observations from the subagent

   Then:
   ```bash
   uv run iw step-done ITEM_ID --step S{NN} --report ai-dev/active/ITEM_ID/reports/ITEM_ID_S{NN}_{AgentLabel}_report.md
   ```

4. After step fails:
   ```bash
   uv run iw step-fail ITEM_ID --step S{NN} --reason "{brief reason}"
   ```

5. Output a progress status line after EVERY step

### Resuming Interrupted Workflow

If item status is `in_progress`:

1. `uv run iw item-status ITEM_ID --json` shows current step state
2. If `STEP_ID` was provided in arguments, resume from that step
3. Otherwise, find the first step not yet `completed`
4. Output: "Resuming ITEM_ID — {N} of {total} steps already completed"
5. Resume from the target step

## Worktree Isolation

For daemon-managed execution, use `iw batch-create` + `iw batch-approve` instead:
```bash
uv run iw batch-create ITEM_ID
uv run iw batch-approve BATCH-001
```

The daemon creates the worktree, launches the agent, and handles monitoring automatically.

For direct execution in the current working directory, proceed with the steps above.

## QV Gate Steps

For `qv-gate` steps, run the gate command directly:
```bash
{step.command}
```

Report pass/fail based on the exit code.

## MANDATORY: Output Requirements

After each step: output the step progress line.
On completion: output the full final summary.
On interruption: output INTERRUPTED status with resume instructions.
On error: output FAILED status with what went wrong.

**NEVER exit silently.** The operator must always see a summary of what happened.

Start executing now. Proceed autonomously through all pending steps.
