# Guide to Claude Code Workflow Orchestration

**Purpose**: Comprehensive reference for automating multi-agent development workflows in Claude Code — from design to commit.
**Audience**: Engineers designing automated AI-driven development pipelines using Claude Code.
**Last Updated**: 2026-03-15

---

## 1) The Orchestration Problem

Modern AI-assisted development workflows involve multiple specialized agents executing in sequence: an implementer writes code, a reviewer checks it, a fixer addresses issues, and a validator runs quality gates. Manually launching each agent, checking outputs, and deciding the next step is tedious and error-prone.

**Orchestration** automates this chain: an orchestrator agent reads a workflow definition, launches specialist agents in order, evaluates their outputs, handles fix cycles, and only stops when the workflow is complete or a human decision is needed.

### What Orchestration Solves

| Manual Pain Point                      | Orchestration Solution |
|----------------------------------------|----------------------|
| Remembering which agent to launch next | Orchestrator skill reads step sequence from manifest |
| Copy-pasting prompt file paths         | Orchestrator discovers and loads prompts automatically |
| Deciding pass/fail after reviews       | Orchestrator parses review reports for severity |
| Launching fix cycles manually          | Orchestrator triggers fix agents when review finds issues |
| Tracking which steps are done          | Orchestrator maintains state in workflow-manifest.json |
| Running quality gates by hand          | Orchestrator runs gates and evaluates results |

### Claude Code vs OpenCode Orchestration at a Glance

| Concept | OpenCode | Claude Code |
|---------|----------|-------------|
| Subagent delegation | Task tool | Agent tool |
| Agent definition | `.opencode/agents/*.md` | `.claude/agents/*.md` |
| User commands | `.opencode/commands/*.md` | `.claude/skills/*/SKILL.md` |
| Event hooks | Plugins (TypeScript) | Hooks (shell commands / JSON) |
| Headless execution | `opencode run --agent ...` | `claude -p --agent ...` |
| Permission model | YAML frontmatter (`permission:`) | YAML frontmatter (`tools:`, `disallowedTools:`) + `settings.json` |
| Worktree isolation | Not native | `isolation: worktree` in agent frontmatter |
| Agent teams | Not available | Experimental (peer-to-peer coordination) |

---

## 2) Claude Code Primitives for Orchestration

Claude Code provides five building blocks that combine to enable workflow automation:

### 2.1 The Agent Tool (Subagent Delegation)

The **Agent tool** is how a parent Claude session spawns child agents. When Claude invokes a subagent:

1. A new child session is created with the subagent's own system prompt
2. The subagent runs in its own context window (optionally with a different model)
3. The subagent has its own tool set and permission configuration
4. Results are returned to the parent session when the subagent completes
5. The subagent's full transcript is preserved for potential resumption

**Key parameters of the Agent tool:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `prompt` | string | The task for the subagent to perform |
| `description` | string | Short (3-5 word) summary of what the agent will do |
| `subagent_type` | string | Which agent definition to use (built-in or custom) |
| `model` | string | Model override (`sonnet`, `opus`, `haiku`) |
| `run_in_background` | boolean | Run asynchronously; parent continues working |
| `isolation` | `"worktree"` | Run in isolated git worktree copy |
| `resume` | string | Agent ID from previous invocation to continue |

**Built-in subagent types:**

| Name | Model | Tools | Purpose |
|------|-------|-------|---------|
| `general-purpose` | Inherited | All | Complex multi-step tasks |
| `Explore` | Haiku | Read-only | Fast codebase exploration |
| `Plan` | Inherited | Read-only | Architecture and planning |
| `Bash` | Inherited | Bash only | Terminal commands in separate context |

### 2.2 Custom Subagents (Agent Definitions)

Custom subagents are Markdown files with YAML frontmatter. This is the Claude Code equivalent of OpenCode's agent definitions.

**Storage locations (priority order):**

| Location | Scope |
|----------|-------|
| `--agents` CLI flag (inline JSON) | Current session only |
| `.claude/agents/<name>.md` | Current project |
| `~/.claude/agents/<name>.md` | All projects |
| Plugin's `agents/` directory | Where plugin is enabled |

**Full frontmatter schema:**

```yaml
---
name: backend-impl              # required, lowercase + hyphens, max 64 chars
description: >                  # required, Claude uses this to decide when to delegate
  Backend implementation specialist for InnoForge.
  Implements repository, service, and schema layers using TDD.
tools: Read, Grep, Glob, Edit, Write, Bash  # tool allowlist (inherits all if omitted)
disallowedTools: Agent, WebFetch             # tool denylist (applied after allowlist)
model: sonnet                   # sonnet | opus | haiku | full-model-id
permissionMode: default         # default | acceptEdits | dontAsk | bypassPermissions
maxTurns: 50                    # max agentic turns before stopping
background: false               # true = always run as background task
isolation: worktree             # worktree = run in isolated git worktree
skills:                         # preload skill content at startup
  - iw-workflow
  - innoforge-conventions
mcpServers:                     # MCP servers available to this agent
  - playwright:
      type: stdio
      command: npx
      args: ["-y", "@playwright/mcp@latest"]
  - github                     # reference existing server by name
hooks:                          # hooks scoped to this subagent's lifetime
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "./scripts/validate-command.sh"
memory: project                 # user | project | local — cross-session learning
---

Your agent system prompt / instructions here.
```

**Restricting which subagents an agent can spawn:**

Use `Agent(type)` syntax in the `tools` field to allowlist specific subagent types:

```yaml
# Only these subagents can be spawned by this agent
tools: Agent(backend-impl, frontend-impl, code-review-impl), Read, Grep, Glob, Bash
```

To block specific agents while allowing all others, use `disallowedTools`:

```yaml
disallowedTools: Agent(Explore), Agent(general-purpose)
```

### 2.3 Skills (User-Triggered Workflows)

Skills are the Claude Code equivalent of OpenCode's commands — user-invoked prompt shortcuts (`/skill-name`) that can contain orchestration logic.

**File structure:**

```
.claude/skills/execute/
├── SKILL.md           # Required: frontmatter + instructions
├── reference.md       # Optional: detailed docs loaded on demand
└── scripts/
    └── helper.sh      # Optional: scripts Claude can execute
```

**Frontmatter schema:**

```yaml
---
name: execute
description: >
  Execute the workflow for a work item. Use when the user
  types /execute followed by a work item ID.
argument-hint: "[work-item-ID]"
disable-model-invocation: true  # only user can invoke, not auto-triggered
allowed-tools: Read, Grep, Glob, Bash, Agent
model: opus                     # model override when this skill is active
context: fork                   # fork = run in isolated subagent context
agent: orchestrator             # which subagent to use when context:fork
---

Skill instructions here in Markdown.
```

**Key frontmatter fields:**

| Field | Effect |
|-------|--------|
| `disable-model-invocation: true` | Only user can trigger via `/skill-name`; Claude won't auto-invoke |
| `user-invocable: false` | Hidden from `/` menu; only Claude can invoke programmatically |
| `context: fork` | Run in isolated subagent context (fresh context window) |
| `agent: <name>` | Which subagent to use when `context: fork` is set |
| `allowed-tools` | Tools auto-approved without permission prompt during this skill |

**Variable substitution in skills:**

| Variable | Replaced With |
|----------|---------------|
| `$ARGUMENTS` | All arguments passed when invoking |
| `$1`, `$2`, etc. | Positional arguments |
| `${CLAUDE_SESSION_ID}` | Current session UUID |
| `${CLAUDE_SKILL_DIR}` | Absolute path to the skill's directory |

**Dynamic context injection** with `!` backtick syntax runs shell commands during skill preprocessing:

```markdown
## Work Item Context

Design document:
!`ls ai-dev/active/$1/*_Design.md 2>/dev/null || ls ai-dev/work/$1/*_Design.md 2>/dev/null || echo "Not found"`

All prompt files:
!`ls -1 ai-dev/active/$1/prompts/*_prompt.md 2>/dev/null || ls -1 ai-dev/work/$1/prompts/*_prompt.md 2>/dev/null || echo "No prompts"`

Manifest:
!`cat ai-dev/active/$1/workflow-manifest.json 2>/dev/null || cat ai-dev/work/$1/workflow-manifest.json 2>/dev/null || echo "No manifest"`
```

Shell commands run first; their output replaces the placeholder. Claude only receives the rendered result.

### 2.4 Hooks (Event-Driven Automation)

Hooks are shell commands that execute in response to Claude Code lifecycle events. They live in `settings.json` under the `hooks` key and provide event-driven orchestration capabilities.

**Configuration in settings.json:**

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "/path/to/validate-command.sh",
            "timeout": 10,
            "statusMessage": "Validating command..."
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/path/to/on-stop.sh"
          }
        ]
      }
    ]
  }
}
```

**Hook handler types:**

| Type | Description | Key Fields |
|------|-------------|------------|
| `command` | Shell command execution | `command`, `timeout`, `async` |
| `http` | HTTP webhook call | `url`, `headers`, `allowedEnvVars` |
| `prompt` | Inject prompt text | `prompt`, `model` |
| `agent` | Spawn agent | `prompt`, `model` |

**All supported hook events:**

| Event | Fires When | Can Block? | Matcher |
|-------|-----------|------------|---------|
| `SessionStart` | Session begins | No | `startup`, `resume`, `clear`, `compact` |
| `InstructionsLoaded` | CLAUDE.md loaded | No | None |
| `UserPromptSubmit` | User submits input | Yes | None |
| `PreToolUse` | Before any tool runs | Yes | Tool name (regex) |
| `PermissionRequest` | Permission needed | Yes | Tool name |
| `PostToolUse` | After tool succeeds | No | Tool name |
| `PostToolUseFailure` | After tool fails | No | Tool name |
| `Notification` | UI notification | No | `permission_prompt`, `idle_prompt` |
| `SubagentStart` | Subagent spawned | No | Agent type name |
| `SubagentStop` | Subagent finishes | Yes | Agent type name |
| `Stop` | Claude finishes turn | Yes | None |
| `TeammateIdle` | Agent team member idle | Yes | None |
| `TaskCompleted` | Task marked complete | Yes | None |
| `PreCompact` | Before context compaction | No | `manual`, `auto` |
| `PostCompact` | After context compaction | No | `manual`, `auto` |
| `WorktreeCreate` | Worktree created | Yes | None |
| `WorktreeRemove` | Worktree removed | No | None |
| `SessionEnd` | Session exits | No | `clear`, `logout`, `other` |

**Stdin data passed to hook scripts:**

Every hook receives JSON on stdin with common fields:

```json
{
  "session_id": "abc123",
  "transcript_path": "/path/to/transcript.jsonl",
  "cwd": "/current/working/directory",
  "permission_mode": "default",
  "hook_event_name": "PreToolUse",
  "agent_id": "optional_subagent_id",
  "agent_type": "optional_agent_name"
}
```

For tool events, additional fields:

```json
{
  "tool_name": "Bash",
  "tool_use_id": "toolu_01ABC123",
  "tool_input": {
    "command": "npm test",
    "timeout": 120000
  }
}
```

**Exit code communication:**

| Exit Code | Meaning | JSON Processed? |
|-----------|---------|-----------------|
| 0 | Success | Yes, stdout parsed |
| 2 | Blocking error | No; stderr fed to Claude as error |
| Any other | Non-blocking error | No; stderr shown in verbose mode |

**Stdout JSON response format (exit 0):**

```json
{
  "continue": true,
  "suppressOutput": false,
  "systemMessage": "optional warning shown to user",
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow|deny|ask",
    "permissionDecisionReason": "explanation",
    "updatedInput": { "command": "modified command" },
    "additionalContext": "context for claude"
  }
}
```

**PreToolUse blocking capabilities:**

- **Allow**: exit 0, `permissionDecision: "allow"`
- **Deny**: exit 0 with `permissionDecision: "deny"` + reason, OR exit 2 with stderr
- **Modify inputs**: exit 0 with `updatedInput` containing new values
- **Pass extra context**: exit 0 with `additionalContext`

**Hooks in subagent definitions:**

Subagents can define their own scoped hooks:

```yaml
---
name: orchestrator
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "./scripts/block-destructive-git.sh"
  SubagentStop:
    - matcher: ".*-impl"
      hooks:
        - type: command
          command: "./scripts/on-subagent-complete.sh"
---
```

### 2.5 The CLI (`claude -p`) for Headless Execution

The `claude -p` (print) mode runs Claude Code non-interactively: sends a prompt, runs to completion, prints the response, and exits. This is the foundation of all bash-driven orchestration.

**Complete CLI flag reference for orchestration:**

| Flag | Description | Example |
|------|-------------|---------|
| `-p` / `--print` | Non-interactive mode | `claude -p "query"` |
| `--output-format` | `text`, `json`, `stream-json` | `--output-format json` |
| `--json-schema` | Validate output against JSON Schema | `--json-schema '{"type":"object",...}'` |
| `--allowedTools` | Tools that auto-execute (no permission prompt) | `"Bash(git log *)" "Read"` |
| `--disallowedTools` | Tools removed entirely | `"Edit" "WebFetch"` |
| `--tools` | Restrict which tools are available (allowlist) | `--tools "Bash,Read,Edit"` |
| `--model` | Model alias or full ID | `--model claude-sonnet-4-6` |
| `--max-turns` | Limit agentic turns (print mode only) | `--max-turns 10` |
| `--continue` / `-c` | Continue most recent conversation | `--continue` |
| `--resume` / `-r` | Resume session by ID or name | `--resume "auth-work"` |
| `--fork-session` | When resuming, create new session ID | `--resume abc --fork-session` |
| `--system-prompt` | Replace the entire system prompt | `--system-prompt "You are..."` |
| `--system-prompt-file` | Replace system prompt from file | `--system-prompt-file ./prompt.txt` |
| `--append-system-prompt` | Append to default system prompt | `--append-system-prompt "Always use TS"` |
| `--append-system-prompt-file` | Append from file | `--append-system-prompt-file rules.txt` |
| `--agents` | Define subagents as inline JSON | `--agents '{"name":{...}}'` |
| `--agent` | Set the agent for this session | `--agent orchestrator` |
| `--max-budget-usd` | Max dollar spend before stopping | `--max-budget-usd 5.00` |
| `--no-session-persistence` | Don't save session to disk | `--no-session-persistence` |
| `--worktree` / `-w` | Start in isolated git worktree | `claude -w feature-auth` |
| `--add-dir` | Add additional working directories | `--add-dir ../apps ../lib` |
| `--name` / `-n` | Name this session for later resume | `claude -n "my-feature"` |
| `--permission-mode` | Start in specified permission mode | `--permission-mode bypassPermissions` |
| `--dangerously-skip-permissions` | Skip all permission prompts | Headless CI/CD only |
| `--mcp-config` | Load MCP servers from JSON | `--mcp-config ./mcp.json` |
| `--settings` | Load settings from file/JSON | `--settings ./settings.json` |
| `--effort` | Effort level: `low`, `medium`, `high`, `max` | `--effort high` |
| `--verbose` | Show full turn-by-turn output | `--verbose` |

**JSON output format:**

```json
{
  "result": "Claude's text response",
  "session_id": "uuid-string",
  "structured_output": { },
  "usage": { "input_tokens": 123, "output_tokens": 456 }
}
```

**Piping input:**

```bash
# Pipe file content
cat prompt.md | claude -p "Execute this implementation prompt"

# Pipe diff for review
git diff | claude -p "Review these changes for issues"

# Heredoc for multi-file context
claude -p "Analyze these files" << 'EOF'
$(cat src/service.py)
$(cat src/repository.py)
EOF
```

---

## 3) Orchestration Patterns

### 3.1 Pattern A: Orchestrator Skill with Forked Agent (Recommended)

A dedicated **skill** delegates to an **orchestrator agent** that coordinates all work. The orchestrator never writes code — it only reads files, evaluates outputs, and dispatches tasks to subagents.

```
User → /execute F122
       ↓
Skill (context: fork, agent: orchestrator)
  ↓
Orchestrator agent (read-only, spawns subagents)
  ├→ Agent(backend-impl) → implements S01
  ├→ Evaluates S01 output
  ├→ Agent(code-review-impl) → reviews S01
  ├→ Evaluates review: PASS? → next step / FAIL? → Agent(code-review-fix-impl)
  ├→ Agent(frontend-impl) → implements S03
  ├→ ...continues through all steps...
  └→ Agent(quality-validation-impl) → runs gates
```

**Why this is recommended:**
- `context: fork` gives the orchestrator a fresh context window
- The orchestrator uses the Agent tool to spawn specialist subagents
- Each subagent gets its own fresh context (no pollution between tasks)
- The orchestrator's read-only tool set prevents accidental code modification
- The skill's `!` backtick syntax pre-loads manifest data before the orchestrator starts

### 3.2 Pattern B: Direct Skill Orchestration

For simpler workflows, the skill itself contains the orchestration logic (no separate orchestrator agent):

```markdown
---
name: execute
description: Execute workflow for a work item
argument-hint: "[ID]"
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Bash, Agent
model: opus
---

# Execute Work Item Workflow

Work item: **$1**

## Manifest
!`cat ai-dev/work/$1/workflow-manifest.json 2>/dev/null || cat ai-dev/active/$1/workflow-manifest.json 2>/dev/null`

## Instructions

1. Read the manifest above
2. Find the first step with status "pending" or "needs_fix"
3. Read the prompt file for that step
4. Delegate to the appropriate specialist agent using the Agent tool
5. Evaluate the result
6. Update the manifest (mark step complete or trigger fix cycle)
7. Repeat until all steps are complete
```

**Pros**: Simpler setup (no separate orchestrator agent definition).
**Cons**: Runs in the main conversation context (uses context window budget), no isolation.

### 3.3 Pattern C: External Bash Script Orchestration

For maximum control, a bash script drives Claude Code headlessly:

```bash
#!/bin/bash
set -euo pipefail

WORK_ITEM="$1"  # e.g., F122
WORK_DIR="ai-dev/work/${WORK_ITEM}"
MANIFEST="${WORK_DIR}/workflow-manifest.json"

# Validate
if [ ! -f "$MANIFEST" ]; then
    echo "ERROR: Manifest not found at $MANIFEST"
    exit 1
fi

# Read step configuration from manifest
STEPS=$(jq -c '.steps[] | select(.status == "pending")' "$MANIFEST")

while IFS= read -r STEP; do
    STEP_NUM=$(echo "$STEP" | jq -r '.step_number')
    AGENT_LABEL=$(echo "$STEP" | jq -r '.agent_label')
    PROMPT_FILE=$(echo "$STEP" | jq -r '.prompt_file')
    AGENT_TYPE=$(echo "$STEP" | jq -r '.opencode_agent')

    # Map opencode agent names to claude code agent names
    CC_AGENT="${AGENT_TYPE}"  # Same names if agents are ported

    echo "=== Step S$(printf '%02d' $STEP_NUM) — ${AGENT_LABEL} ==="

    PROMPT_PATH="${WORK_DIR}/${PROMPT_FILE}"
    REPORT_DIR="${WORK_DIR}/reports"
    mkdir -p "$REPORT_DIR"

    # Execute step with Claude Code
    RESULT=$(cat "$PROMPT_PATH" | claude -p \
        --agent "$CC_AGENT" \
        --output-format json \
        --max-turns 50 \
        --max-budget-usd 3.00 \
        "Execute the implementation prompt provided via stdin. \
         Save your report to ${REPORT_DIR}/${WORK_ITEM}_S$(printf '%02d' $STEP_NUM)_${AGENT_LABEL}_report.md")

    # Check if report was created
    REPORT="${REPORT_DIR}/${WORK_ITEM}_S$(printf '%02d' $STEP_NUM)_${AGENT_LABEL}_report.md"
    if [ ! -f "$REPORT" ]; then
        echo "ERROR: Report not generated for S${STEP_NUM}. Aborting."
        exit 1
    fi

    # Update manifest step status
    jq --arg sn "$STEP_NUM" \
       '.steps |= map(if .step_number == ($sn | tonumber) then .status = "completed" else . end)' \
       "$MANIFEST" > "${MANIFEST}.tmp" && mv "${MANIFEST}.tmp" "$MANIFEST"

    echo "=== Step S$(printf '%02d' $STEP_NUM) COMPLETE ==="

done <<< "$STEPS"

echo "=== Workflow complete for $WORK_ITEM ==="
```

**Pros**: Full control, easy to debug, works with CI/CD, budget caps per step.
**Cons**: No AI-driven decision-making between steps, limited error recovery, no fix cycle automation.

### 3.4 Pattern D: Parallel Execution with Worktrees

When steps can run in parallel (same step number), use worktree isolation:

```
Orchestrator
  ├→ Agent(backend-impl, isolation: worktree) → S03 backend work
  ├→ Agent(frontend-impl, isolation: worktree) → S03 frontend work
  │   (both run simultaneously in separate git worktrees)
  ├→ Wait for both to complete
  └→ Evaluate both outputs
```

Each agent works in an isolated copy of the repository, preventing file conflicts. Worktrees are cleaned up automatically if no changes are made.

**Bash script parallel equivalent:**

```bash
# Find parallel steps (same step number)
S03_PROMPTS=($(ls ai-dev/work/F122/prompts/F122_S03_*_prompt.md))

# Launch in parallel with worktrees
PIDS=()
for PROMPT in "${S03_PROMPTS[@]}"; do
    AGENT=$(echo "$PROMPT" | grep -oP 'S\d+_\K[^_]+')
    claude -p \
        --agent "${AGENT,,}-impl" \
        --worktree "f122-s03-${AGENT,,}" \
        --output-format json \
        "Execute: $(cat $PROMPT)" > "/tmp/f122-s03-${AGENT,,}.json" &
    PIDS+=($!)
done

# Wait for all
for PID in "${PIDS[@]}"; do
    wait "$PID"
done
```

### 3.5 Pattern E: Session Continuity for Long Workflows

For workflows that may exceed context limits or get interrupted:

```bash
# Start workflow with named session
SESSION_NAME="${WORK_ITEM}-workflow"
claude -p \
    --agent orchestrator \
    --name "$SESSION_NAME" \
    --output-format json \
    "Execute workflow for $WORK_ITEM starting from step 1"

# Resume if interrupted
claude -p \
    --resume "$SESSION_NAME" \
    --output-format json \
    "Continue the workflow from where you left off"
```

---

## 4) Designing the Orchestrator Agent

### 4.1 Agent Definition

Create `.claude/agents/orchestrator.md`:

```markdown
---
name: orchestrator
description: >
  Orchestrates IW development workflows by reading prompt files,
  delegating to specialist agents, evaluating outputs, and managing
  fix cycles. Use for executing complete feature/incident/CR workflows.
model: opus
maxTurns: 100
tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Agent(backend-impl, frontend-impl, database-impl, api-impl,
          pipeline-impl, template-impl, tests-impl,
          code-review-impl, code-review-fix-impl,
          code-review-final-impl, code-review-fix-final-impl,
          quality-validation-impl)
disallowedTools:
  - Edit
  - Write
  - WebFetch
  - WebSearch
permissionMode: default
skills:
  - iw-workflow
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: ".claude/scripts/orchestrator-bash-guard.sh"
          timeout: 5
          statusMessage: "Validating command..."
---

# Orchestrator Agent

You are the IW Workflow Orchestrator. You coordinate the execution of
development workflows by delegating ALL implementation and review work
to specialist subagents.

## Core Principle

You NEVER write, edit, or create code. You ONLY:
1. Read workflow definitions (manifest, prompt files, design docs)
2. Determine execution order from the manifest
3. Delegate work to specialist subagents via the Agent tool
4. Evaluate subagent outputs (reports, review findings)
5. Decide: proceed, trigger fix cycle, or escalate to human
6. Update the workflow-manifest.json to track state

## Workflow Execution Protocol

### Phase 1: Discovery

When given a work item ID (e.g., F122, I005, CR003):

1. Check for folder at `ai-dev/work/{ID}/` (resume) or `ai-dev/active/{ID}/` (new)
2. Read `workflow-manifest.json` from the found folder
3. If in active/ and status is "approved": move to work/ and set status to "in_progress"
4. Determine which steps are pending (status != "completed")

### Phase 2: Step Execution Loop

For each pending step:

1. **Read the prompt file** at the path specified in the manifest
2. **Determine the target agent** from the manifest's `opencode_agent` field
   (note: field name retained for compatibility; maps to Claude Code agents)
3. **Delegate**: Send the full prompt content to the target subagent via Agent tool
4. **Evaluate**: Parse the subagent's result contract JSON block
5. **Update manifest**: Mark step completed or needs_fix

### Phase 3: Review Evaluation

After a CodeReview step completes:

1. Parse the result contract for `verdict` and `findings`
2. Count mandatory findings: CRITICAL + HIGH + MEDIUM (fixable)
3. **Decision logic**:
   - mandatory_count = 0 → **PASS** → proceed to next step
   - mandatory_count > 0 and fix_cycles < 5 → trigger fix cycle
   - mandatory_count > 0 and fix_cycles >= 5 → **ESCALATE** to human

### Phase 4: Fix Cycle Management

When a review fails:

1. Read the current fix cycle count from the manifest
2. Construct fix prompt with: original requirements + review findings
3. Delegate to the appropriate fix agent (code-review-fix-impl or
   code-review-fix-final-impl)
4. After fix: re-run the review step
5. Increment fix cycle count in manifest

### Phase 5: Completion

When all steps are complete:
1. Update manifest status to "completed"
2. Summarize the entire workflow execution
3. List all reports generated
4. Report: "All steps complete. Ready to commit and move files to done/."

## Output Format

After each step, report:

```
=== Step S{NN} — {Agent} ===
Status: PASS | FAIL | ESCALATED
Agent: {agent-name}
Report: ai-dev/work/{ID}/reports/{ID}_S{NN}_{Agent}_report.md
Findings: {N} CRITICAL, {N} HIGH, {N} MEDIUM, {N} LOW
Fix Cycles: {N}/5
Next: {next step description}
```

## Hard Constraints

- NEVER implement code directly — always delegate
- NEVER skip CodeReview steps
- NEVER exceed 5 fix cycles per review
- NEVER proceed past a step with CRITICAL findings
- ALWAYS read the prompt file before delegating
- ALWAYS verify report files exist after each subagent completes
- NEVER run git commit, git push, git reset, or git checkout
- If a subagent fails to complete, report the error and stop
```

### 4.2 Bash Guard Script

Create `.claude/scripts/orchestrator-bash-guard.sh` to enforce read-only bash:

```bash
#!/bin/bash
# Reads hook JSON from stdin, blocks destructive commands

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""')

# Block destructive git commands
if echo "$COMMAND" | grep -qE '^git (push|reset|checkout|commit|add|stash|rebase|merge|cherry-pick)'; then
    echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Orchestrator cannot run destructive git commands"}}'
    exit 0
fi

# Block file modification commands
if echo "$COMMAND" | grep -qE '^(rm |mv |cp |chmod |chown |sed |awk )'; then
    # Allow mv only for active/ → work/ folder move
    if echo "$COMMAND" | grep -qE '^mv ai-dev/active/.* ai-dev/work/'; then
        exit 0
    fi
    echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Orchestrator cannot modify files via bash"}}'
    exit 0
fi

# Allow everything else (ls, cat, head, tail, grep, wc, jq, etc.)
exit 0
```

### 4.3 Permission Architecture

The trust model ensures separation of concerns:

| Agent | Read | Write/Edit | Bash | Subagent Delegation |
|-------|------|------------|------|---------------------|
| orchestrator | Yes | No | Read-only (hook-enforced) | Yes (all specialists) |
| backend-impl | Yes | Yes | Sandboxed (no git push/reset) | No |
| frontend-impl | Yes | Yes | Sandboxed (no git push/reset) | No |
| code-review-impl | Yes | No | Read-only (git diff/log/status) | No |
| quality-validation-impl | Yes | No (write: report only) | Yes (make, pytest, ruff, mypy) | No |

This prevents:
- Orchestrator from accidentally modifying code
- Implementers from spawning other agents or skipping reviews
- Reviewers from "fixing" code they're supposed to review
- Quality validators from modifying code to pass gates

---

## 5) The Entry Skill

Create `.claude/skills/execute/SKILL.md`:

```markdown
---
name: execute
description: >
  Execute all pending steps for a work item (F/I/CR number).
  Triggers on /execute followed by a work item ID.
argument-hint: "[work-item-ID, e.g., F122, I006, CR002]"
disable-model-invocation: true
context: fork
agent: orchestrator
---

# Execute Work Item Workflow

Execute the complete development workflow for work item **$1**.

## Pre-Flight

Work item folder:
!`ls -d ai-dev/active/$1 ai-dev/work/$1 2>/dev/null || echo "NOT_FOUND"`

Manifest status:
!`jq -r '.status' ai-dev/active/$1/workflow-manifest.json 2>/dev/null || jq -r '.status' ai-dev/work/$1/workflow-manifest.json 2>/dev/null || echo "NO_MANIFEST"`

## Work Item Context

Design document:
!`ls ai-dev/active/$1/*_Design.md ai-dev/work/$1/*_Design.md 2>/dev/null || echo "No design document found"`

All prompt files (execution order):
!`ls -1 ai-dev/active/$1/prompts/*_prompt.md ai-dev/work/$1/prompts/*_prompt.md 2>/dev/null | sort || echo "No prompts found"`

Existing reports (completed steps):
!`ls -1 ai-dev/work/$1/reports/*_report*.md 2>/dev/null | sort || echo "No reports yet"`

## Instructions

1. If the folder is in `ai-dev/active/$1/`:
   - Verify manifest status is "approved" — if not, report error and stop
   - Move the folder: `mv ai-dev/active/$1/ ai-dev/work/$1/`
   - Update manifest status to "in_progress"

2. If the folder is in `ai-dev/work/$1/`:
   - Read manifest to find current state
   - Resume from first step with status "pending" or "needs_fix"

3. Execute each pending step:
   - Read the prompt file
   - Delegate to the appropriate specialist agent
   - Evaluate the result contract
   - Update the manifest

4. Handle fix cycles for failed reviews (max 5 per review)

5. Run quality validation as the final step

6. Report completion status when done

Start executing now. Proceed autonomously through all steps.
```

### Alternative: Single-Step Skill

For more control, execute one step at a time:

```markdown
---
name: step
description: Execute a single workflow step
argument-hint: "[work-item-ID] [step-number, e.g., S03]"
disable-model-invocation: true
context: fork
agent: orchestrator
---

Execute step **$2** for work item **$1**.

Prompt file:
!`cat ai-dev/work/$1/prompts/$1_$2_*_prompt.md 2>/dev/null || echo "Step not found"`

Previous reports for context:
!`ls -1 ai-dev/work/$1/reports/*_report*.md 2>/dev/null | sort`
```

Usage: `/step F123 S03`

---

## 6) Specialist Subagent Configuration

Each specialist agent needs proper configuration for autonomous execution. Create these in `.claude/agents/`.

### 6.1 Implementation Agent Pattern

Example: `.claude/agents/backend-impl.md`

```markdown
---
name: backend-impl
description: >
  Implement InnoForge Backend scope from ai-dev prompts using strict TDD.
  Handles repository, service, and schema layers.
model: sonnet
maxTurns: 35
tools:
  - Read
  - Grep
  - Glob
  - Edit
  - Write
  - Bash
disallowedTools:
  - Agent
  - WebFetch
  - WebSearch
permissionMode: acceptEdits
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: ".claude/scripts/impl-bash-guard.sh"
---

# Backend Implementation Agent

You are a backend implementation specialist. When invoked:

1. Read the prompt content provided to you (contains all requirements)
2. Read referenced architecture and design files
3. Follow TDD strictly: RED → GREEN → REFACTOR
4. Implement only in-scope requirements
5. Run quality checks on your changes
6. Write a concise report to the specified report file path

## Report Format

Write your report as markdown with these sections:
- **Summary**: What was implemented
- **Files Changed**: List of files created/modified
- **Test Results**: pytest output summary
- **Decisions**: Key technical decisions made
- **Issues**: Any unresolved problems or concerns

## Result Contract

End your response with this exact JSON block:

```json
{
  "completion_status": "complete|partial|blocked",
  "files_changed": ["list", "of", "files"],
  "tests_passed": true,
  "test_summary": "X passed, Y failed",
  "coverage": "N%",
  "blockers": [],
  "notes": ""
}
```
```

### 6.2 Code Review Agent Pattern

Example: `.claude/agents/code-review-impl.md`

```markdown
---
name: code-review-impl
description: >
  Review InnoForge code changes against design requirements
  and coding standards. Read-only — cannot modify code.
model: opus
maxTurns: 25
tools:
  - Read
  - Grep
  - Glob
  - Bash
disallowedTools:
  - Edit
  - Write
  - Agent
  - WebFetch
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: ".claude/scripts/review-bash-guard.sh"
---

# Code Review Agent

You are a code review specialist. When invoked:

1. Read the review prompt provided (contains checklist and files to review)
2. Read the implementation report from the previous step
3. Review each file against the checklist
4. Classify findings by severity: CRITICAL, HIGH, MEDIUM (fixable),
   MEDIUM (suggestion), LOW

## Result Contract

End your response with this exact JSON block:

```json
{
  "verdict": "PASS|NEEDS_FIX",
  "findings": {
    "critical": 0,
    "high": 0,
    "medium_fixable": 0,
    "medium_suggestion": 0,
    "low": 0
  },
  "mandatory_fix_count": 0,
  "finding_details": [
    {
      "id": "F1",
      "severity": "HIGH",
      "category": "fixable",
      "file": "src/service.py",
      "line": 42,
      "description": "Missing tenant_id filter",
      "fix": "Add .filter(Model.tenant_id == tenant_id)"
    }
  ]
}
```
```

### 6.3 Quality Validation Agent Pattern

Example: `.claude/agents/quality-validation-impl.md`

```markdown
---
name: quality-validation-impl
description: >
  Run InnoForge quality gates: lint, type-check, tests,
  security, and architecture validation.
model: sonnet
maxTurns: 20
tools:
  - Read
  - Grep
  - Glob
  - Write
  - Bash
disallowedTools:
  - Edit
  - Agent
  - WebFetch
---

# Quality Validation Agent

Execute all quality gates and report results:

1. Run each gate from the provided prompt
2. Record pass/fail for each
3. If any gate fails: attempt one auto-fix cycle (ruff format, etc.)
4. Report final results

## Result Contract

```json
{
  "gates": {
    "lint": { "status": "PASS|FAIL", "errors": 0 },
    "format": { "status": "PASS|FAIL", "diffs": 0 },
    "type_check": { "status": "PASS|FAIL", "errors": 0 },
    "unit_tests": { "status": "PASS|FAIL", "passed": 0, "failed": 0 },
    "integration_tests": { "status": "PASS|FAIL", "passed": 0, "failed": 0 },
    "coverage": { "status": "PASS|FAIL", "percentage": 0 },
    "security": { "status": "PASS|FAIL", "findings": 0 },
    "architecture": { "status": "PASS|FAIL", "violations": 0 }
  },
  "overall": "ALL_GATES_PASSED|GATES_FAILED",
  "evidence_files": []
}
```
```

---

## 7) State Management Strategies

### 7.1 Manifest-Based State (Recommended)

Use the `workflow-manifest.json` as the single source of truth. The orchestrator reads the manifest at startup, updates it after every step transition, and uses it to determine what to do next.

This is identical to the OpenCode approach and is fully tool-agnostic — the same manifest works with both OpenCode and Claude Code orchestrators.

**Manifest status transitions:**

```
draft → approved (human) → in_progress (/execute) → completed
                         → paused (escalation)    → in_progress (resume)
                         → failed (unrecoverable)
```

**Step status transitions:**

```
pending → in_progress → completed (success)
pending → in_progress → needs_fix (review issues) → in_progress (fix) → completed
needs_fix → in_progress → failed (5 cycles exhausted)
```

### 7.2 File-Based State (Fallback)

If the orchestrator cannot update the manifest (e.g., read-only mode without bash `jq`), it can infer state by comparing prompts to reports:

```
Prompt exists + Report exists → Step COMPLETE
Prompt exists + No report    → Step PENDING
```

This is idempotent — if the orchestrator crashes and restarts, it resumes from the last completed step.

### 7.3 Session Continuity

For long workflows, use Claude Code's session persistence:

```bash
# Start workflow with named session
claude -p --agent orchestrator --name "F122-workflow" \
    "Execute /execute F122"

# Resume if interrupted
claude -p --resume "F122-workflow" \
    "Continue the workflow from where you left off"
```

The `--resume` flag restores the full conversation context, including all previous tool calls and agent results. If context was auto-compacted, the essential state survives via the manifest on disk.

---

## 8) Parallel Execution

When prompt files share the same step number, they can run in parallel.

### 8.1 In-Agent Parallelism

The orchestrator can launch multiple subagents simultaneously by making multiple Agent tool calls in a single turn:

```
Orchestrator identifies S03 has both Backend and Frontend prompts
  → Launches Agent(backend-impl, run_in_background: true) for S03 Backend
  → Launches Agent(frontend-impl, run_in_background: true) for S03 Frontend
  → Both run concurrently
  → Orchestrator receives both results
  → Evaluates both before proceeding to S04
```

With `isolation: worktree`, each agent works in a separate copy of the repository, preventing file conflicts.

### 8.2 External Script Parallelism

```bash
# Find parallel steps (same step number)
S03_PROMPTS=($(ls ai-dev/work/F122/prompts/F122_S03_*_prompt.md))

# Launch in parallel with worktrees
PIDS=()
for PROMPT in "${S03_PROMPTS[@]}"; do
    AGENT_LABEL=$(echo "$PROMPT" | grep -oP 'S\d+_\K[^_]+(?=_prompt)')
    CC_AGENT="${AGENT_LABEL,,}-impl"

    claude -p \
        --agent "$CC_AGENT" \
        --worktree "f122-s03-${AGENT_LABEL,,}" \
        --output-format json \
        --max-budget-usd 3.00 \
        "Execute this prompt: $(cat $PROMPT)" > "/tmp/f122-s03-${AGENT_LABEL,,}.json" &
    PIDS+=($!)
done

# Wait for all
for PID in "${PIDS[@]}"; do
    wait "$PID"
done
```

---

## 9) Error Handling and Recovery

### 9.1 Subagent Failure

If a subagent fails to complete (hits `maxTurns`, budget cap, or error):
- The orchestrator receives an incomplete response or error
- Action: Log the error, update manifest step status to "failed", report to user, and STOP
- Never retry a failed subagent automatically — the failure may indicate a systemic issue

### 9.2 Review Failure (Fix Cycle)

```
Review finds CRITICAL/HIGH/MEDIUM (fixable) issues
  → Fix cycle 1: delegate to fix agent with findings
  → Re-run review
  → If still failing: Fix cycle 2
  → ...
  → If still failing after cycle 5: ESCALATE to human (manifest status: paused)
```

Maximum 5 fix cycles prevents infinite loops. The orchestrator tracks the cycle count per review step in the manifest.

### 9.3 Quality Gate Failure

If quality validation fails:
- Auto-fixable issues (formatting): the QV agent attempts one fix
- Non-auto-fixable issues (type errors, test failures): report to user
- Never modify code to bypass quality gates

### 9.4 Context Window Exhaustion

Long workflows may exhaust the orchestrator's context window. Mitigation strategies:
- Use `context: fork` on the `/execute` skill to give the orchestrator a fresh context
- Each subagent gets its own fresh context (no pollution)
- The manifest on disk preserves state across context compactions
- Use `--resume` to continue interrupted sessions
- Set `maxTurns: 100` or higher for complex workflows
- The orchestrator can be re-invoked with `/execute {ID}` to resume from the manifest

### 9.5 Budget Control

Use `--max-budget-usd` in headless mode to prevent runaway costs:

```bash
# Cap total workflow cost
claude -p --agent orchestrator --max-budget-usd 20.00 \
    "Execute workflow for F122"

# Or cap per-step in bash orchestration
claude -p --agent backend-impl --max-budget-usd 3.00 \
    "Execute: $(cat prompt.md)"
```

---

## 10) The IW Workflow: Claude Code Integration Design

### 10.1 Current Workflow (OpenCode)

```
Claude Code: /iw-new-feature <description>
  → Creates design + all prompts + manifest in active/{ID}/
  ↓
Claude Code: /iw-review-design {ID}
  → Validates and auto-fixes the design package
  ↓
Human: Approves by setting manifest status to "approved"
  ↓
OpenCode: /execute {ID}
  → Orchestrator delegates to specialist subagents
  → Fix cycles, quality validation, etc.
  ↓
Human: Reviews, commits, moves to done/
```

### 10.2 Claude Code Workflow (New)

```
Claude Code: /iw-new-feature <description>
  → Creates design + all prompts + manifest in active/{ID}/
  ↓
Claude Code: /iw-review-design {ID}
  → Validates and auto-fixes the design package
  ↓
Human: Approves by setting manifest status to "approved"
  ↓
Claude Code: /execute {ID}              ← NEW: same command, different orchestrator
  → Orchestrator agent (context:fork) delegates to specialist subagents
  → Fix cycles, quality validation, etc.
  ↓
Human: Reviews, commits, moves to done/
```

The design phase (steps 1-3) is **unchanged** — the same skills create the same artifacts. Only the execution phase changes: instead of OpenCode's `/execute`, Claude Code's `/execute` triggers the orchestrator agent via the skill's `context: fork` + `agent: orchestrator` mechanism.

### 10.3 Required Artifacts

| Artifact | Type | File | Purpose |
|----------|------|------|---------|
| Orchestrator agent | Agent | `.claude/agents/orchestrator.md` | Coordinates workflow |
| Execute skill | Skill | `.claude/skills/execute/SKILL.md` | Entry point (`/execute F122`) |
| Step skill | Skill | `.claude/skills/step/SKILL.md` | Single step (`/step F122 S03`) |
| Bash guard (orchestrator) | Script | `.claude/scripts/orchestrator-bash-guard.sh` | Enforce read-only bash |
| Bash guard (impl) | Script | `.claude/scripts/impl-bash-guard.sh` | Block destructive git ops |
| Bash guard (review) | Script | `.claude/scripts/review-bash-guard.sh` | Allow only git diff/log/status |
| Backend impl agent | Agent | `.claude/agents/backend-impl.md` | Backend implementation |
| Frontend impl agent | Agent | `.claude/agents/frontend-impl.md` | Frontend implementation |
| Database impl agent | Agent | `.claude/agents/database-impl.md` | Database implementation |
| API impl agent | Agent | `.claude/agents/api-impl.md` | API implementation |
| Pipeline impl agent | Agent | `.claude/agents/pipeline-impl.md` | Pipeline implementation |
| Template impl agent | Agent | `.claude/agents/template-impl.md` | Template implementation |
| Tests impl agent | Agent | `.claude/agents/tests-impl.md` | Test implementation |
| Code review agent | Agent | `.claude/agents/code-review-impl.md` | Per-agent code review |
| Code review fix agent | Agent | `.claude/agents/code-review-fix-impl.md` | Fix review issues |
| Code review final agent | Agent | `.claude/agents/code-review-final-impl.md` | Global review |
| Code review fix final agent | Agent | `.claude/agents/code-review-fix-final-impl.md` | Fix global review |
| Quality validation agent | Agent | `.claude/agents/quality-validation-impl.md` | Quality gates |

### 10.4 Mapping OpenCode Agents to Claude Code Agents

The agent mapping is 1:1. The manifest's `opencode_agent` field values map directly to Claude Code agent names:

| Manifest `opencode_agent` | Claude Code Agent File | `subagent_type` |
|---------------------------|----------------------|-----------------|
| `database-impl` | `.claude/agents/database-impl.md` | `database-impl` |
| `backend-impl` | `.claude/agents/backend-impl.md` | `backend-impl` |
| `api-impl` | `.claude/agents/api-impl.md` | `api-impl` |
| `frontend-impl` | `.claude/agents/frontend-impl.md` | `frontend-impl` |
| `tests-impl` | `.claude/agents/tests-impl.md` | `tests-impl` |
| `pipeline-impl` | `.claude/agents/pipeline-impl.md` | `pipeline-impl` |
| `template-impl` | `.claude/agents/template-impl.md` | `template-impl` |
| `code-review-impl` | `.claude/agents/code-review-impl.md` | `code-review-impl` |
| `code-review-fix-impl` | `.claude/agents/code-review-fix-impl.md` | `code-review-fix-impl` |
| `code-review-final-impl` | `.claude/agents/code-review-final-impl.md` | `code-review-final-impl` |
| `code-review-fix-final-impl` | `.claude/agents/code-review-fix-final-impl.md` | `code-review-fix-final-impl` |
| `quality-validation-impl` | `.claude/agents/quality-validation-impl.md` | `quality-validation-impl` |

### 10.5 Shared vs Tool-Specific Artifacts

| Artifact | Shared (Both Tools) | OpenCode Only | Claude Code Only |
|----------|-------------------|---------------|-----------------|
| Design documents | Yes | — | — |
| Prompt files | Yes | — | — |
| Report files | Yes | — | — |
| Workflow manifest | Yes | — | — |
| Tracking files | Yes | — | — |
| Templates | Yes | — | — |
| Agent definitions | — | `.opencode/agents/` | `.claude/agents/` |
| Entry command/skill | — | `.opencode/commands/execute.md` | `.claude/skills/execute/SKILL.md` |
| Bash guard scripts | — | — | `.claude/scripts/*.sh` |
| Plugin hooks | — | `.opencode/plugins/*.ts` | `settings.json` hooks |

### 10.6 Workflow Execution State Machine

```
IDLE → DISCOVERING → EXECUTING_STEP → EVALUATING
                                          ↓
                                    ┌─ PASS → next step or COMPLETE
                                    └─ FAIL → FIX_CYCLE (max 5)
                                                  ↓
                                            RE_EVALUATING
                                                  ↓
                                    ┌─ PASS → next step
                                    └─ FAIL → FIX_CYCLE or ESCALATED
```

---

## 11) Advanced Patterns

### 11.1 Multi-Model Orchestration

Use different models for different roles to optimize cost and get diverse perspectives:

```yaml
# orchestrator.md — needs strong reasoning and coordination
model: opus

# backend-impl.md — needs good code generation
model: sonnet

# code-review-impl.md — needs thorough analysis
model: opus

# quality-validation-impl.md — just runs commands
model: haiku
```

### 11.2 Structured Output with JSON Schema

Use `--json-schema` for machine-parseable subagent results:

```bash
SCHEMA='{"type":"object","properties":{"verdict":{"type":"string","enum":["PASS","NEEDS_FIX"]},"findings":{"type":"object"}},"required":["verdict","findings"]}'

claude -p --agent code-review-impl \
    --output-format json \
    --json-schema "$SCHEMA" \
    "Review: $(cat review-prompt.md)" | jq '.structured_output'
```

### 11.3 Hook-Based Workflow Automation

Use hooks for cross-cutting workflow concerns:

```json
{
  "hooks": {
    "SubagentStop": [
      {
        "matcher": ".*-impl",
        "hooks": [
          {
            "type": "command",
            "command": ".claude/scripts/on-impl-complete.sh",
            "statusMessage": "Processing implementation result..."
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": ".claude/scripts/update-manifest-on-stop.sh"
          }
        ]
      }
    ]
  }
}
```

The `SubagentStop` hook fires when any `-impl` subagent completes, allowing you to:
- Validate that report files were created
- Parse result contracts
- Update the manifest automatically
- Trigger notifications

### 11.4 Fresh Context per Task

Each subagent invocation creates a **new session** with a fresh context window. This prevents context pollution between tasks and avoids the "long conversation" degradation problem. The orchestrator passes only the current task's prompt to each subagent — previous task details stay in the orchestrator's context, not the subagent's.

### 11.5 Convergence Detection for Reviews

If a reviewer returns identical findings on consecutive fix cycles, the orchestrator should escalate to human instead of running another fix cycle. Compare current review findings with previous cycle findings — if they're substantially the same, further fix cycles won't help.

### 11.6 Audit Trail

Every orchestrator decision should be logged. The manifest's `runs[]` and `fix_cycles[]` arrays serve as the audit trail:

```json
{
  "runs": [
    {
      "run_number": 1,
      "started_at": "2026-03-15T09:00:00Z",
      "completed_at": "2026-03-15T09:15:00Z",
      "report_file": "reports/F122_S01_Backend_report.md",
      "result_contract": { "completion_status": "complete", ... }
    }
  ],
  "fix_cycles": [
    {
      "cycle_number": 1,
      "triggered_by": "S02_CodeReview_Backend",
      "findings_count": 3,
      "fix_report": "reports/F122_S02_CodeReview_FIX_Backend_report_run_2.md"
    }
  ]
}
```

---

## 12) Anti-Patterns to Avoid

| Anti-Pattern | Why It's Bad | Instead |
|--------------|--------------|---------|
| **Orchestrator that writes code** | Loses separation of concerns, can't review its own work | Make orchestrator read-only via `disallowedTools` + hooks |
| **Infinite fix cycles** | Burns tokens, rarely converges after 5 cycles | Hard cap at 5 cycles, then escalate |
| **Skipping review steps** | Defeats the purpose of the workflow | Orchestrator must enforce review after every implementation |
| **No structured output** | Orchestrator can't parse natural language reliably | Define explicit result contracts for subagents |
| **Auto-committing** | Risky without human review | Orchestrator reports completion, human commits |
| **Same model for reviewer and implementer** | Similar blind spots | Use different models for independent perspectives |
| **No audit trail** | Can't debug workflow failures | Log every delegation, evaluation, and decision in manifest |
| **Running orchestrator in main context** | Wastes the user's conversation budget | Use `context: fork` to give orchestrator its own context |
| **Hardcoded agent names in skill** | Breaks when agents are renamed | Read agent name from manifest's `opencode_agent` field |
| **Ignoring budget caps** | Runaway costs on long workflows | Use `--max-budget-usd` in headless mode |

---

## 13) Implementation Roadmap

### Phase 1: Foundation (Day 1)

- Create orchestrator agent (`.claude/agents/orchestrator.md`)
- Create `/execute` skill (`.claude/skills/execute/SKILL.md`)
- Create bash guard scripts (`.claude/scripts/*.sh`)
- Port one implementation agent (e.g., `backend-impl`) as proof of concept
- Port one review agent (`code-review-impl`)
- Test with a simple 2-step workflow (implement + review)

### Phase 2: Full Agent Suite (Day 2-3)

- Port all implementation agents to `.claude/agents/`
- Port all review and fix agents
- Port quality validation agent
- Add fix cycle logic to orchestrator
- Test with a complete feature workflow

### Phase 3: Refinement (Day 4-5)

- Add parallel step detection and worktree isolation
- Add hook-based workflow automation (SubagentStop, etc.)
- Add convergence detection for reviews
- Test with incident and change request workflows
- Fine-tune `maxTurns` and model selection per agent
- Add budget caps per agent type

### Phase 4: Bash Script Driver (Optional)

- Create external bash script for CI/CD integration
- Add structured output validation with `--json-schema`
- Add notification system (webhook hooks)
- Session continuity for very long workflows

---

## 14) What's Coming in the Future

This section documents announced or hinted features that may enhance orchestration capabilities. These are **not available today** — they are listed here for awareness and follow-up.

| Feature | Status | Relevance |
|---------|--------|-----------|
| **Agent Teams (stable)** | Experimental as of March 2026 | Peer-to-peer agent coordination without a central orchestrator; could enable reviewer-implementer debate loops |
| **A2A Protocol** | Under discussion (GitHub Issue #3023 in OpenCode; Anthropic tracking) | Inter-agent communication protocol for cross-tool coordination (Claude Code ↔ OpenCode) |
| **Plugin system** | Hinted in Claude Code docs (`--plugin-dir` flag exists) | TypeScript plugins similar to OpenCode's plugin system for deeper lifecycle integration |
| **MCP tool interception in hooks** | Not supported today | Would allow hooks to fire on MCP tool calls, enabling Playwright/GitHub automation gating |
| **Shared task list persistence** | Available in Agent Teams (experimental) | File-locked task claiming at `~/.claude/tasks/{team-name}/` for multi-agent coordination |
| **Custom model routing** | Available via `model` field | Future: dynamic model selection based on task complexity or budget remaining |

**Recommendation**: Start with the agent-based orchestrator pattern (Section 4) today. Monitor Agent Teams stabilization for potential migration to a more collaborative model later.

---

**Document Version**: 1.0
**Author**: AI Development Team
**Sources**: Claude Code official docs (code.claude.com/docs), community patterns, existing IW workflow implementation
