---
name: iw-execute
version: "2.0.0"
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

## Pre-Flight Data

Current status from platform:
!`uv run iw item-status $ARGUMENTS --json 2>/dev/null || echo '{"error": "item not found or not registered"}'`

Work item design document location:
!`ls -d ai-dev/design/active/$ARGUMENTS 2>/dev/null || echo "NOT_FOUND: $ARGUMENTS not in ai-dev/design/active/"`

## Pre-Flight Validation

Before executing, validate:

1. **Item is registered** — `uv run iw item-status $ARGUMENTS` must succeed
2. **Item status is `approved`** — if `draft`, tell user to run `uv run iw approve $ARGUMENTS` first
3. **Design doc exists** — must be in `ai-dev/design/active/$ARGUMENTS/`

## If item not found:

Report error: "Work item $ARGUMENTS not found in database. Create a design first with /iw-new-feature, /iw-new-incident, or /iw-new-cr, then register it with `uv run iw register`."

## If item status is `draft`:

Report: "Work item $ARGUMENTS is in 'draft' status. Review the design, then approve with: `iw approve $ARGUMENTS`"

## If item status is `approved`:

Begin execution. For each step in the workflow:

### Step Execution Protocol

1. Before starting each step, call:
   ```bash
   uv run iw step-start $ARGUMENTS --step S{NN}
   ```

2. Delegate the step to the correct specialist subagent using **path-based delegation** (pass the prompt file path)

3. After step completes successfully:
   ```bash
   uv run iw step-done $ARGUMENTS --step S{NN}
   ```

4. After step fails:
   ```bash
   uv run iw step-fail $ARGUMENTS --step S{NN} --reason "{brief reason}"
   ```

5. Output a progress status line after EVERY step

### Resuming Interrupted Workflow

If item status is `in_progress`:

1. `uv run iw item-status $ARGUMENTS --json` shows current step state
2. Find the first step not yet `completed`
3. Output: "Resuming $ARGUMENTS — {N} of {total} steps already completed"
4. Resume from the first non-completed step

## Worktree Isolation

For daemon-managed execution, use `iw batch-create` + `iw batch-approve` instead:
```bash
uv run iw batch-create $ARGUMENTS
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
