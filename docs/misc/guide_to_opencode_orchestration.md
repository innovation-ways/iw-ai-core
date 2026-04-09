# Guide to OpenCode Workflow Orchestration

**Purpose**: Comprehensive reference for automating multi-agent development workflows in OpenCode — from design to commit.
**Audience**: Engineers designing automated AI-driven development pipelines using OpenCode.
**Last Updated**: 2026-03-14

---

## 1) The Orchestration Problem

Modern AI-assisted development workflows involve multiple specialized agents executing in sequence: an implementer writes code, a reviewer checks it, a fixer addresses issues, and a validator runs quality gates. Manually launching each agent, checking outputs, and deciding the next step is tedious and error-prone.

**Orchestration** automates this chain: an orchestrator agent reads a workflow definition, launches specialist agents in order, evaluates their outputs, handles fix cycles, and only stops when the workflow is complete or a human decision is needed.

### What Orchestration Solves

| Manual Pain Point                      | Orchestration Solution |
|----------------------------------------|----------------------|
| Remembering which agent to launch next | Orchestrator reads step sequence from prompt files |
| Copy-pasting prompt file paths         | Orchestrator discovers and loads prompts automatically |
| Deciding pass/fail after reviews       | Orchestrator parses review reports for severity |
| Launching fix cycles manually          | Orchestrator triggers fix agents when review finds issues |
| Tracking which steps are done          | Orchestrator maintains state in a tracking file |
| Running quality gates by hand          | Orchestrator runs gates and evaluates results |

---

## 2) OpenCode Primitives for Orchestration

OpenCode provides four building blocks that combine to enable workflow automation:

### 2.1 The Task Tool (Subagent Delegation)

The **task tool** is how a primary agent launches subagents programmatically. When a primary agent invokes a subagent via the task tool:

1. A new child session is created with the subagent's own system prompt
2. The subagent runs in its own context window (possibly with a different LLM)
3. The subagent has its own tool and permission configuration
4. Results are returned to the parent agent when the subagent completes

**Permission control** determines which subagents can be invoked:

```yaml
# In orchestrator agent frontmatter
permission:
  task:
    "*": deny              # Block all by default
    "backend-impl": allow  # Allow specific agents
    "frontend-impl": allow
    "code-review-*": allow # Glob patterns work
```

When set to `deny`, the subagent is removed from the task tool description entirely — the model won't even attempt to invoke it.

### 2.2 Commands (User-Triggered Workflows)

Commands are user-invoked prompt shortcuts (`/command-name`) that can:
- Target a specific agent via the `agent` field
- Inject dynamic data via `$ARGUMENTS`, `$1`, `$2`
- Embed shell output via `` !`command` `` syntax
- Include file contents via `@filename` references
- Force subagent execution via `subtask: true`

A command is the **entry point** for a workflow — the user types `/execute-feature F122` and the orchestrator takes over.

### 2.3 Skills (Agent-Loadable Knowledge)

Skills are reusable instruction packs that agents load on demand via the `skill` tool. An orchestrator skill can contain:
- The workflow state machine definition
- Step validation logic
- Report parsing rules
- Fix cycle decision criteria

Skills are lazy-loaded (only `name` + `description` visible until activated), preserving context window budget.

### 2.4 The CLI `run` Command (Headless Execution)

For external automation (CI/CD, bash scripts):

```bash
opencode run --agent orchestrator "Execute F122 workflow"
opencode run --agent backend-impl --file ai-dev/prompts/active/F122_S01_Backend_prompt.md "Implement this prompt"
```

Key flags:
- `--agent <name>`: Target specific agent
- `--file <path>`: Attach file(s) to the prompt
- `--session <id>`: Resume existing session (context continuity)
- `--format json`: Machine-parseable output
- `--model <provider/model>`: Override model

---

## 3) Orchestration Patterns

### 3.1 Pattern A: Orchestrator Agent (Recommended)

A dedicated **primary agent** that delegates all real work to subagents. The orchestrator never writes code — it only reads files, evaluates outputs, and dispatches tasks.

```
User → /execute-feature F122
       ↓
Orchestrator (primary agent, read-only)
  ├→ Reads prompt files to determine step sequence
  ├→ @backend-impl (subagent) → implements S01
  ├→ Evaluates S01 output
  ├→ @code-review-impl (subagent) → reviews S01
  ├→ Evaluates review: PASS? → next step / FAIL? → @code-review-fix-impl
  ├→ @frontend-impl (subagent) → implements S03
  ├→ ...continues through all steps...
  └→ @quality-validation-impl (subagent) → runs gates
```

**Key principle**: The orchestrator NEVER does real work directly. It delegates everything to subagents, tracks state, and makes routing decisions.

### 3.2 Pattern B: Command-Driven Pipeline

A command that uses shell injection to discover workflow state and constructs the orchestration prompt dynamically:

```markdown
---
description: Execute the next step in a work item workflow
agent: orchestrator
---

## Current Work Item: $1

## Available Prompts
!`ls -1 ai-dev/prompts/active/$1_S*_prompt.md 2>/dev/null`

## Completed Reports
!`ls -1 ai-dev/reports/active/$1_S*_report.md 2>/dev/null`

## Design Document
@ai-dev/design/active/$1_Feature_Design.md

Execute the next uncompleted step for work item $1.
Compare prompts vs reports to determine which step is next.
For each step: delegate to the appropriate subagent, evaluate the output, and proceed.
```

Usage: `/execute F122`

### 3.3 Pattern C: ORCH Mode (Review Loop)

Inspired by [opencode-orch-mode](https://github.com/agents-to-go/opencode-orch-mode), this pattern uses two sub-agents in a loop until a compliance threshold is met:

```
Orchestrator
  ├→ @executor: implements the plan, writes summary
  ├→ @reviewer: scores compliance (0-100%)
  ├→ If compliance < 90%: loop back to @executor with review feedback
  └→ If compliance ≥ 90%: proceed to next step
```

Each iteration's output is saved to numbered files (`01-code.md`, `02-review.md`, `03-code.md`, etc.), providing full audit trail. Every agent reads ALL previous summaries before starting work.

### 3.4 Pattern D: External Script Orchestration

For maximum control, a bash script drives OpenCode headlessly:

```bash
#!/bin/bash
WORK_ITEM="$1"  # e.g., F122

# Discover prompt files
PROMPTS=($(ls -1 ai-dev/prompts/active/${WORK_ITEM}_S*_prompt.md | sort))

for PROMPT_FILE in "${PROMPTS[@]}"; do
    STEP=$(echo "$PROMPT_FILE" | grep -oP 'S\d+')
    AGENT_LABEL=$(echo "$PROMPT_FILE" | grep -oP 'S\d+_\K[^_]+')

    # Map label to OpenCode agent
    case "$AGENT_LABEL" in
        Backend)     AGENT="backend-impl" ;;
        Frontend)    AGENT="frontend-impl" ;;
        CodeReview)  AGENT="code-review-impl" ;;
        QualityValidation) AGENT="quality-validation-impl" ;;
        *)           AGENT="build" ;;
    esac

    echo "=== Executing $STEP with @$AGENT ==="
    opencode run --agent "$AGENT" --file "$PROMPT_FILE" \
        "Execute the implementation prompt in the attached file. Save report to ai-dev/reports/active/${WORK_ITEM}_${STEP}_${AGENT_LABEL}_report.md"

    # Check if report was created
    REPORT="ai-dev/reports/active/${WORK_ITEM}_${STEP}_${AGENT_LABEL}_report.md"
    if [ ! -f "$REPORT" ]; then
        echo "ERROR: Report not generated for $STEP. Aborting."
        exit 1
    fi
done

echo "=== Workflow complete for $WORK_ITEM ==="
```

**Pros**: Full control, easy to debug, works with CI/CD.
**Cons**: No AI-driven decision-making between steps, limited error recovery.

---

## 4) Designing the Orchestrator Agent

### 4.1 Agent Definition

Create `.opencode/agents/orchestrator.md`:

```markdown
---
description: Orchestrates IW development workflows by reading prompt files, delegating to specialist agents, evaluating outputs, and managing fix cycles. Use for executing complete feature/incident/CR workflows end-to-end.
mode: primary
temperature: 0.2
steps: 100
tools:
  write: false
  edit: false
  patch: false
permission:
  read: allow
  glob: allow
  grep: allow
  list: allow
  skill: allow
  webfetch: deny
  websearch: deny
  bash:
    "*": deny
    "ls *": allow
    "cat *": allow
    "wc *": allow
    "grep *": allow
    "head *": allow
    "tail *": allow
  task:
    "*": deny
    "backend-impl": allow
    "frontend-impl": allow
    "database-impl": allow
    "api-impl": allow
    "pipeline-impl": allow
    "template-impl": allow
    "tests-impl": allow
    "code-review-impl": allow
    "code-review-fix-impl": allow
    "code-review-final-impl": allow
    "code-review-fix-final-impl": allow
    "quality-validation-impl": allow
---

# Orchestrator Agent

You are the IW Workflow Orchestrator. You coordinate the execution of development workflows by delegating ALL implementation and review work to specialist subagents.

## Core Principle

You NEVER write, edit, or create code. You ONLY:
1. Read workflow definitions (prompt files, design docs)
2. Determine execution order
3. Delegate work to specialist subagents via the Task tool
4. Evaluate subagent outputs (reports, review findings)
5. Decide: proceed, trigger fix cycle, or escalate to human

## Workflow Execution Protocol

### Phase 1: Discovery

When given a work item ID (e.g., F122, I005, CR003):

1. Read the design document: `ai-dev/design/active/{ID}_*_Design.md`
2. List all prompt files: `ai-dev/prompts/active/{ID}_S*_prompt.md`
3. List all existing reports: `ai-dev/reports/active/{ID}_S*_report.md`
4. Determine which steps are complete (have reports) and which are pending

### Phase 2: Step Sequencing

Parse prompt filenames to determine execution order:
- Format: `{ID}_S{NN}_{Agent}_prompt.md`
- Steps with the same S-number run in PARALLEL
- Steps with different S-numbers run SEQUENTIALLY
- CodeReview steps must follow their implementation step
- QualityValidation is always the last step

### Phase 3: Execution Loop

For each pending step:

1. **Read the prompt file** completely
2. **Determine the target agent** from the filename:
   | Filename Contains | Delegate To |
   |-------------------|-------------|
   | `_Backend_` | `@backend-impl` |
   | `_Frontend_` | `@frontend-impl` |
   | `_Database_` | `@database-impl` |
   | `_API_` | `@api-impl` |
   | `_Pipeline_` | `@pipeline-impl` |
   | `_Template_` | `@template-impl` |
   | `_Tests_` | `@tests-impl` |
   | `_CodeReview_FIX_Final_` | `@code-review-fix-final-impl` |
   | `_CodeReview_FIX_` | `@code-review-fix-impl` |
   | `_CodeReview_Final_` | `@code-review-final-impl` |
   | `_CodeReview_` | `@code-review-impl` |
   | `_QualityValidation_` | `@quality-validation-impl` |

3. **Delegate**: Send the full prompt content to the target subagent via Task tool
4. **Evaluate output**: Read the subagent's response

### Phase 4: Review Evaluation

After a CodeReview step completes:

1. Parse the review output for findings by severity
2. Count CRITICAL and HIGH findings
3. **Decision logic**:
   - 0 CRITICAL + 0 HIGH → **PASS** → proceed to next step
   - Any CRITICAL or HIGH → **FAIL** → trigger fix cycle

### Phase 5: Fix Cycle Management

When a review fails:

1. Check the current fix cycle count (max 2 per review)
2. If cycle < 2:
   - Construct fix prompt with: original requirements + review findings
   - Delegate to the appropriate fix agent (`@code-review-fix-impl` or `@code-review-fix-final-impl`)
   - After fix: re-run the review step
3. If cycle ≥ 2:
   - **ESCALATE**: Report to user with summary of unresolved issues
   - Do NOT proceed to the next step

### Phase 6: Completion

When all steps are complete:
1. Summarize the entire workflow execution
2. List all reports generated
3. Report any issues encountered
4. Suggest: "All steps complete. Ready to commit and move files to done/."

## Output Format

After each step, report:

```
=== Step {SNN} — {Agent} ===
Status: PASS | FAIL | ESCALATED
Agent: @{agent-name}
Duration: ~{N} minutes
Report: ai-dev/reports/active/{ID}_{SNN}_{Agent}_report.md
Findings: {N} CRITICAL, {N} HIGH, {N} MEDIUM, {N} LOW
Fix Cycles: {N}/2
Next: {next step description}
```

## Hard Constraints

- NEVER implement code directly — always delegate
- NEVER skip CodeReview steps
- NEVER exceed 2 fix cycles per review
- NEVER proceed past a step with CRITICAL findings
- ALWAYS read the prompt file before delegating
- ALWAYS save the subagent's output as a report file
- If a subagent fails to complete, report the error and stop
```

### 4.2 Permission Architecture

The trust model ensures separation of concerns:

| Agent | Read | Write/Edit | Bash | Task (Delegate) |
|-------|------|------------|------|-----------------|
| orchestrator | Yes | No | Read-only | Yes (all specialists) |
| backend-impl | Yes | Yes | Sandboxed | No |
| frontend-impl | Yes | Yes | Sandboxed | No |
| code-review-impl | Yes | No | Read-only | No |
| quality-validation-impl | Yes | No | Yes (make commands) | No |

This prevents:
- Orchestrator from accidentally modifying code
- Implementers from skipping reviews by delegating to themselves
- Reviewers from "fixing" code they're supposed to review
- Quality validators from modifying code to pass gates

---

## 5) The Entry Command

Create `.opencode/commands/execute.md`:

```markdown
---
description: Execute all pending steps for a work item (F/I/CR number)
agent: orchestrator
---

# Execute Work Item Workflow

Execute the complete development workflow for work item **$1**.

## Work Item Context

Design document:
!`ls ai-dev/design/active/$1_*_Design.md 2>/dev/null || echo "No design document found in active/"`

All prompt files (execution order):
!`ls -1 ai-dev/prompts/active/$1_S*_prompt.md 2>/dev/null | sort || echo "No prompts found"`

Existing reports (completed steps):
!`ls -1 ai-dev/reports/active/$1_S*_report.md 2>/dev/null | sort || echo "No reports yet"`

## Instructions

1. Read the design document for full context
2. Determine which steps are pending (prompts without matching reports)
3. Execute each pending step in order by delegating to the appropriate specialist agent
4. After each implementation step, evaluate the code review
5. Handle fix cycles as needed (max 2 per review)
6. Run quality validation as the final step
7. Report completion status

Start executing now. Do not ask for confirmation — proceed autonomously through all steps.
```

Usage: `/execute F123`

### Alternative: Step-by-Step Command

For more control, execute one step at a time:

```markdown
---
description: Execute a single workflow step
agent: orchestrator
---

Execute step **$2** for work item **$1**.

Prompt file:
!`cat ai-dev/prompts/active/$1_$2_*_prompt.md 2>/dev/null || echo "Step not found"`

Previous reports for context:
!`ls -1 ai-dev/reports/active/$1_S*_report.md 2>/dev/null | sort`
```

Usage: `/step F123 S03`

---

## 6) Specialist Subagent Configuration

Each specialist agent needs proper configuration for autonomous execution. Here are the key patterns:

### 6.1 Implementation Agent Pattern

```markdown
---
description: Implement InnoForge Backend scope from ai-dev prompts using strict TDD
mode: subagent
temperature: 0.1
steps: 35
permission:
  read: allow
  glob: allow
  grep: allow
  edit: allow
  write: allow
  task: deny
  skill: allow
  bash:
    "*": allow
    "git push*": deny
    "git checkout*": deny
    "git reset*": deny
    "rm -rf*": deny
---

# Backend Implementation Agent

You are a backend implementation specialist. When invoked:

1. Read the prompt content provided to you (it contains all requirements)
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
- **Severity Assessment**: Self-assessment of any issues found
```

### 6.2 Code Review Agent Pattern

```markdown
---
description: Review InnoForge code changes against design requirements and coding standards
mode: subagent
temperature: 0.2
steps: 25
tools:
  write: false
  edit: false
  patch: false
permission:
  read: allow
  glob: allow
  grep: allow
  task: deny
  bash:
    "*": deny
    "git diff*": allow
    "git log*": allow
    "git status*": allow
---

# Code Review Agent

You are a code review specialist. When invoked:

1. Read the review prompt provided (contains checklist and files to review)
2. Read the implementation report from the previous step
3. Review each file against the checklist
4. Classify findings by severity: CRITICAL, HIGH, MEDIUM, LOW

## Output Format (CRITICAL — must follow exactly)

Your review MUST end with a structured summary block:

```
## Review Summary

| Severity | Count |
|----------|-------|
| CRITICAL | {N}   |
| HIGH     | {N}   |
| MEDIUM   | {N}   |
| LOW      | {N}   |

**Verdict**: PASS | FAIL

### Findings requiring fix:
1. [CRITICAL] Description...
2. [HIGH] Description...
```

The orchestrator parses this summary to decide whether to proceed or trigger a fix cycle.
```

### 6.3 Quality Validation Agent Pattern

```markdown
---
description: Run InnoForge quality gates (lint, type-check, tests, security, architecture)
mode: subagent
temperature: 0.0
steps: 20
tools:
  edit: false
  write: true
permission:
  read: allow
  glob: allow
  grep: allow
  task: deny
  bash:
    "*": deny
    "make *": allow
    "pytest *": allow
    "ruff *": allow
    "mypy *": allow
    "cd frontend*": allow
    "npx *": allow
---

# Quality Validation Agent

Execute all quality gates and report results:

1. Run each gate from the provided prompt
2. Record pass/fail for each
3. If any gate fails: attempt one auto-fix cycle (ruff format, etc.)
4. Report final results

## Output Format

```
## Quality Validation Results

| Gate | Status | Details |
|------|--------|---------|
| Linting (ruff) | PASS/FAIL | ... |
| Formatting | PASS/FAIL | ... |
| Type checking (mypy) | PASS/FAIL | ... |
| Unit tests | PASS/FAIL | X/Y passed |
| Integration tests | PASS/FAIL | X/Y passed |
| Coverage | PASS/FAIL | XX% (threshold: 80%) |
| Security (semgrep) | PASS/FAIL | ... |
| Architecture | PASS/FAIL | ... |

**Overall**: PASS | FAIL
```
```

---

## 7) State Management Strategies

### 7.1 File-Based State (Recommended)

Use the filesystem as the source of truth. The orchestrator determines state by comparing prompt files to report files:

```
Prompt exists + Report exists → Step COMPLETE
Prompt exists + No report    → Step PENDING
```

This is idempotent — if the orchestrator crashes and restarts, it resumes from the last completed step automatically.

### 7.2 Tracking File State

For more granular tracking, maintain a status file:

```markdown
# F122 Workflow Status

| Step | Agent | Status | Started | Completed | Fix Cycles |
|------|-------|--------|---------|-----------|------------|
| S01 | Backend | COMPLETE | 2026-03-14 09:00 | 2026-03-14 09:15 | 0 |
| S02 | CodeReview_Backend | COMPLETE | 2026-03-14 09:16 | 2026-03-14 09:22 | 0 |
| S03 | Frontend | IN_PROGRESS | 2026-03-14 09:23 | — | 0 |
| S04 | CodeReview_Frontend | PENDING | — | — | 0 |
| S05 | CodeReview_Final | PENDING | — | — | 0 |
| S06 | QualityValidation | PENDING | — | — | 0 |
```

The orchestrator reads and updates this file at each transition.

### 7.3 Session Continuity

For long workflows, use OpenCode's session persistence:

```bash
# Start workflow
opencode run --agent orchestrator --title "F122-workflow" "Execute /execute F122"

# Resume if interrupted
opencode run --continue  # Resumes last session
# OR
opencode run --session <session-id>  # Resume specific session
```

---

## 8) Parallel Execution

When prompt files share the same step number (e.g., `F001_S03_Backend_prompt.md` and `F001_S03_Frontend_prompt.md`), they can run in parallel.

### In-Agent Parallelism

The orchestrator can launch multiple subagents simultaneously via the Task tool. OpenCode's General subagent documentation confirms: "Use this to run multiple units of work in parallel."

The orchestrator should:
1. Identify steps with the same S-number
2. Launch all matching subagents in a single turn
3. Wait for all to complete
4. Evaluate all outputs before proceeding

### External Script Parallelism

```bash
# Find parallel steps (same step number)
S03_PROMPTS=($(ls ai-dev/prompts/active/F122_S03_*_prompt.md))

# Launch in parallel
PIDS=()
for PROMPT in "${S03_PROMPTS[@]}"; do
    AGENT=$(determine_agent "$PROMPT")
    opencode run --agent "$AGENT" --file "$PROMPT" "Execute this prompt" &
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

If a subagent fails to complete:
- The orchestrator receives an error or incomplete response
- Action: Log the error, report to user, and STOP (do not proceed)
- Never retry a failed subagent automatically — the failure may indicate a systemic issue

### 9.2 Review Failure (Fix Cycle)

```
Review finds CRITICAL/HIGH issues
  → Fix cycle 1: delegate to fix agent with findings
  → Re-run review
  → If still failing: Fix cycle 2
  → If still failing after cycle 2: ESCALATE to human
```

Maximum 2 fix cycles prevents infinite loops. The orchestrator must track the cycle count per review step.

### 9.3 Quality Gate Failure

If quality validation fails:
- Auto-fixable issues (formatting): attempt one fix
- Non-auto-fixable issues (type errors, test failures): report to user
- Never modify code to bypass quality gates

### 9.4 Context Window Exhaustion

Long workflows may exhaust the orchestrator's context window. Mitigation strategies:
- Keep orchestrator prompts concise (summaries, not full outputs)
- Use `steps: 100` or higher for complex workflows
- Break very long workflows into phases: `/execute F122 --phase implementation` then `/execute F122 --phase review`

---

## 10) The IW Workflow: Complete Integration Design

This section proposes how to automate the existing Innovation Ways development workflow using the patterns described above.

### 10.1 Current Manual Workflow (As-Is)

```
Human creates design doc + all prompts (via /iw-new-feature skill)
  ↓
Human approves package
  ↓
Human manually launches @backend-impl with S01 prompt
  ↓
Human reads output, manually launches @code-review-impl with S02 prompt
  ↓
Human evaluates review, decides pass/fail
  ↓
If fail: Human launches fix agent, then re-reviews
  ↓
Human launches next implementation agent with S03 prompt
  ↓
... repeat for all steps ...
  ↓
Human launches @quality-validation-impl with final prompt
  ↓
Human commits and moves files to done/
```

### 10.2 Automated Workflow (To-Be)

```
Human creates design doc + all prompts (via /iw-new-feature skill)
  ↓
Human approves package
  ↓
Human types: /execute F122
  ↓
Orchestrator discovers prompts, determines step order
  ↓
For each step:
  ├→ Orchestrator delegates to specialist subagent
  ├→ Subagent implements/reviews and saves report
  ├→ Orchestrator evaluates report
  ├→ If review FAIL: orchestrator triggers fix cycle (max 2)
  └→ Orchestrator proceeds to next step
  ↓
Orchestrator runs quality validation
  ↓
Orchestrator reports: "All steps complete. Ready to commit."
  ↓
Human reviews final state and commits
```

### 10.3 Required Artifacts

| Artifact | Type | File | Purpose |
|----------|------|------|---------|
| Orchestrator agent | Agent | `.opencode/agents/orchestrator.md` | Coordinates workflow |
| Execute command | Command | `.opencode/commands/execute.md` | Entry point (`/execute F122`) |
| Step command | Command | `.opencode/commands/step.md` | Single step (`/step F122 S03`) |
| IW workflow skill | Skill | `.opencode/skills/iw-workflow/SKILL.md` | Workflow rules and conventions |
| Backend impl agent | Agent | `.opencode/agents/backend-impl.md` | Backend implementation |
| Frontend impl agent | Agent | `.opencode/agents/frontend-impl.md` | Frontend implementation |
| Code review agent | Agent | `.opencode/agents/code-review-impl.md` | Code review |
| Code review fix agent | Agent | `.opencode/agents/code-review-fix-impl.md` | Fix review issues |
| Code review final agent | Agent | `.opencode/agents/code-review-final-impl.md` | Global review |
| Quality validation agent | Agent | `.opencode/agents/quality-validation-impl.md` | Quality gates |

### 10.4 Workflow Execution State Machine

```
IDLE → DISCOVERING → EXECUTING_STEP → EVALUATING
                                          ↓
                                    ┌─ PASS → next step or COMPLETE
                                    └─ FAIL → FIX_CYCLE (max 2)
                                                  ↓
                                            RE_EVALUATING
                                                  ↓
                                    ┌─ PASS → next step
                                    └─ FAIL → FIX_CYCLE or ESCALATED
```

### 10.5 Decision Points Requiring Human Input

The orchestrator should pause and ask the human in these cases:

1. **Fix cycle limit exceeded** (2 cycles): "Review still failing after 2 fix cycles. Issues: [list]. Should I continue anyway or do you want to intervene?"
2. **Subagent error**: "Backend agent failed with: [error]. How should I proceed?"
3. **Ambiguous step**: "Multiple possible agents for this step. Which should I use?"
4. **Quality gate failure**: "Quality validation failed: [details]. Should I attempt auto-fix?"
5. **Workflow complete**: "All steps done. Ready to commit?"

---

## 11) Advanced Patterns

### 11.1 Multi-Model Orchestration

Use different models for different roles to get diverse perspectives:

```yaml
# orchestrator.md — needs strong reasoning
model: anthropic/claude-opus-4-6

# backend-impl.md — needs code generation
model: anthropic/claude-sonnet-4-6

# code-review-impl.md — different model = different perspective
model: google/gemini-2.5-pro

# quality-validation-impl.md — just runs commands
model: anthropic/claude-haiku-4-5
```

This follows the pattern from the [ppries/opencode-workflow](https://gist.github.com/ppries/f07fd6316bbd45807dd7a1896555b05b) gist, which uses different models for reviewers vs. implementers to get independent perspectives.

### 11.2 Convergence Detection for Reviews

From the [opencode-orch-mode](https://github.com/agents-to-go/opencode-orch-mode) pattern: if a reviewer returns identical findings on consecutive cycles, stop the loop early rather than wasting cycles.

The orchestrator should compare current review findings with previous cycle findings. If they're substantially the same, escalate to human instead of running another fix cycle.

### 11.3 Fresh Context per Task

From [agent-teams-lite](https://github.com/Gentleman-Programming/agent-teams-lite): each subagent should start with **fresh context** — only the current task spec and relevant code snippets. This prevents context pollution between tasks and avoids the "long conversation" degradation problem.

This is naturally achieved in OpenCode because each subagent invocation creates a new session.

### 11.4 Structured Result Contracts

Subagents should return results in a parseable format so the orchestrator can make automated decisions:

```markdown
## Result Contract

Every subagent MUST end its response with:

---RESULT---
status: ok | warning | failed | blocked
findings_critical: 0
findings_high: 0
findings_medium: 0
findings_low: 0
files_changed: [list]
tests_passed: true | false
next_recommended: [step description]
blockers: [list or "none"]
---END RESULT---
```

The orchestrator can parse this structured block to make routing decisions without relying on natural language interpretation.

### 11.5 Audit Trail

Every orchestrator decision should be logged. Create a workflow log file:

```markdown
# F122 Workflow Execution Log

## 2026-03-14 09:00:00 — STARTED
Work item: F122 — Document Generator
Prompts discovered: S01, S02, S03, S04, S05, S06

## 2026-03-14 09:00:15 — S01 DELEGATED
Agent: @backend-impl
Prompt: F122_S01_Backend_prompt.md

## 2026-03-14 09:15:30 — S01 COMPLETED
Status: ok
Files: 8 changed, 2 created
Tests: 12/12 passed

## 2026-03-14 09:15:45 — S02 DELEGATED
Agent: @code-review-impl
Prompt: F122_S02_CodeReview_Backend_prompt.md

## 2026-03-14 09:22:10 — S02 COMPLETED
Status: PASS (0 CRITICAL, 0 HIGH, 2 MEDIUM, 1 LOW)
Proceeding to S03.
```

---

## 12) Plugin-Driven Orchestration (Advanced)

For fully autonomous workflows that don't require human intervention between steps, OpenCode's plugin system provides event-driven orchestration.

### 12.1 Plugin Architecture

Plugins are TypeScript modules placed in `.opencode/plugins/` or `~/.config/opencode/plugins/`. They intercept the agent lifecycle via events.

**Key events for orchestration**:

| Event | Fires When | Orchestration Use |
|-------|-----------|-------------------|
| `session.idle` | Session finishes with no pending work | Auto-advance to next workflow phase |
| `session.created` | New session spawned | Initialize workflow state |
| `tool.execute.before` | Before any tool call | Block destructive operations, inject context |
| `tool.execute.after` | After any tool call completes | Track file changes, trigger follow-up |
| `command.executed` | Slash command runs | Post-command automation |
| `experimental.session.compacting` | Before context compaction | Inject state that must survive compaction |

**Limitation**: MCP tool calls do NOT trigger `tool.execute.before`/`tool.execute.after` hooks (GitHub issue #2319). Only native OpenCode tools are intercepted.

### 12.2 Plugin Example: Autonomous Workflow Driver

```typescript
// .opencode/plugins/iw-workflow.ts
import type { Plugin } from "@opencode-ai/sdk"
import { readFileSync, existsSync } from "fs"

export const IWWorkflowPlugin: Plugin = async ({ client, project, $ }) => {
  return {
    async event(ev) {
      if (ev.type === "session.idle") {
        // Check if this session is part of a workflow
        const stateFile = "ai-dev/workflow-state.json"
        if (!existsSync(stateFile)) return

        const state = JSON.parse(readFileSync(stateFile, "utf-8"))
        if (state.status !== "running") return

        // Find next pending step
        const nextStep = state.steps.find(s => s.status === "pending")
        if (!nextStep) {
          state.status = "complete"
          // Don't write — let the orchestrator agent do it
          return
        }

        // Spawn next agent
        const session = await client.session.create({
          body: { title: `${state.workItemId} — ${nextStep.agent}` }
        })
        await client.session.prompt({
          path: { id: session.id },
          body: {
            parts: [{
              type: "text",
              text: `Execute: ${nextStep.promptFile}`
            }]
          }
        })
      }
    },

    async "tool.execute.before"(input) {
      // Block destructive git operations in workflow context
      if (input.tool === "bash") {
        const cmd = input.input?.command || ""
        if (cmd.startsWith("git push") || cmd.startsWith("git reset")) {
          throw new Error("Blocked: destructive git operations require manual approval")
        }
      }
    }
  }
}
```

### 12.3 SDK API for Programmatic Control

The TypeScript SDK enables external orchestration scripts:

```typescript
import { createOpencodeClient } from "@opencode-ai/sdk"

const client = createOpencodeClient({ baseUrl: "http://localhost:4096" })

async function runWorkflow(featureId: string) {
  // Phase 1: Implementation
  const implSession = await client.session.create({
    body: { title: `${featureId} — Backend Implementation` }
  })
  await client.session.prompt({
    path: { id: implSession.id },
    body: {
      model: { providerID: "anthropic", modelID: "claude-sonnet-4-6" },
      parts: [{ type: "text", text: `Implement ${featureId} backend...` }]
    }
  })

  // Phase 2: Code Review (fresh session, different model)
  const reviewSession = await client.session.create({
    body: { title: `${featureId} — Code Review` }
  })
  await client.session.prompt({
    path: { id: reviewSession.id },
    body: {
      model: { providerID: "google", modelID: "gemini-2.5-pro" },
      parts: [{ type: "text", text: `Review the implementation...` }]
    }
  })
}
```

Start the server with: `opencode serve --port 4096`

### 12.4 Plugin vs. Agent-Only Decision

| Need | Use Plugin | Use Agent-Only |
|------|-----------|----------------|
| Fully autonomous (no human between steps) | Yes | No |
| Custom event handling (block operations) | Yes | No |
| Simple sequential delegation | No | Yes |
| Team already knows TypeScript | Yes | Depends |
| Quick to set up and maintain | No | Yes |
| Works with `opencode run` CLI | No | Yes |

**Recommendation**: Start with the agent-only orchestrator pattern (Section 4). Add a plugin later only if you need fully autonomous execution without human checkpoints.

### 12.5 Comparison with Claude Code Hooks

| Aspect | OpenCode Plugins | Claude Code Hooks |
|--------|-----------------|-------------------|
| Language | TypeScript (SDK) | Shell commands (JSON stdin/stdout) |
| Interface | Direct API calls | Exit codes + stdout injection |
| Re-injection trigger | `session.promptAsync()` | Exit code 2 on Stop hook |
| MCP interception | Not supported | Not supported |
| Context manipulation | `experimental.chat.system.transform` | `PreCompact` hook |
| Deployment | `.opencode/plugins/*.ts` | `.claude/hooks.json` |

---

## 13) Community References and Inspiration

### Orchestration Frameworks

| Project | Pattern | Key Feature |
|---------|---------|-------------|
| [opencode-workspace](https://github.com/kdcokenny/opencode-workspace) | Hub-and-spoke | 16-component orchestration harness with delegation plugin |
| [OpenAgentsControl](https://github.com/darrenhinde/OpenAgentsControl) | Plan-first with approval gates | ContextScout + TaskManager + 6-stage workflow |
| [agent-teams-lite](https://github.com/Gentleman-Programming/agent-teams-lite) | Spec-driven with 9 sub-agents | Delegate-only orchestrator, dependency graph, multi-model |
| [opencode-orch-mode](https://github.com/agents-to-go/opencode-orch-mode) | Review loop (executor + reviewer) | Compliance scoring (90% threshold), small-model-friendly |
| [ppries/workflow gist](https://gist.github.com/ppries/f07fd6316bbd45807dd7a1896555b05b) | 10-phase autonomous pipeline | Linear→PR, TDD, 5 specialized agents, trust model |
| [opencode-orchestrator](https://github.com/agnusdei1207/opencode-orchestrator) | Plugin-driven autonomous loop | MVCC state, `session.idle` hook, parallel worker pool |

### Official Documentation

| Resource | URL |
|----------|-----|
| Agents docs | [opencode.ai/docs/agents/](https://opencode.ai/docs/agents/) |
| Commands docs | [opencode.ai/docs/commands/](https://opencode.ai/docs/commands/) |
| Skills docs | [opencode.ai/docs/skills/](https://opencode.ai/docs/skills/) |
| CLI docs | [opencode.ai/docs/cli/](https://opencode.ai/docs/cli/) |
| Config docs | [opencode.ai/docs/config/](https://opencode.ai/docs/config/) |
| Plugins docs | [opencode.ai/docs/plugins/](https://opencode.ai/docs/plugins/) |
| SDK docs | [opencode.ai/docs/sdk/](https://opencode.ai/docs/sdk/) |

### Architectural Insights

| Resource | URL | Insight |
|----------|-----|---------|
| OpenCode internals deep dive | [cefboud.com](https://cefboud.com/posts/coding-agents-internals-opencode-deepdive/) | How task tool and sessions work internally |
| Agent teams in OpenCode | [dev.to](https://dev.to/uenyioha/porting-claude-codes-agent-teams-to-opencode-4hol) | JSONL-based messaging, auto-wake pattern |
| Event-driven workflows | [subaud.io](https://www.subaud.io/event-driven-claude-code-and-opencode-workflows-with-hooks/) | Hook implementation patterns, Claude Code comparison |
| OpenCode hooks guide | [dev.to](https://dev.to/einarcesar/does-opencode-support-hooks-a-complete-guide-to-extensibility-k3p) | Plugin extensibility overview |
| Plugin writing reference | [gist](https://gist.github.com/johnlindquist/0adf1032b4e84942f3e1050aba3c5e4a) | Practical plugin implementation |
| Hook system comparison | [gist](https://gist.github.com/zeke/1e0ba44eaddb16afa6edc91fec778935) | OpenCode vs Claude Code hooks |
| A2A protocol integration | [GitHub Issue #3023](https://github.com/sst/opencode/issues/3023) | Future: inter-agent communication protocol |
| DeepWiki: Session Management | [deepwiki.com](https://deepwiki.com/sst/opencode/2.1-session-management) | Session internals and lifecycle |
| DeepWiki: Prompt Orchestration | [deepwiki.com](https://deepwiki.com/sst/opencode/2.3-prompt-orchestration) | Agent loop and task tool internals |

### Best Practices (General Agentic Workflows)

| Resource | URL | Insight |
|----------|-----|---------|
| Agentic Workflows Architectures | [vellum.ai](https://www.vellum.ai/blog/agentic-workflows-emerging-architectures-and-design-patterns) | Design patterns for multi-agent systems |
| Orchestration Patterns That Work | [hatchworks.com](https://hatchworks.com/blog/ai-agents/orchestrating-ai-agents/) | Production orchestration patterns |
| 2026 Agentic Playbook | [promptengineering.org](https://promptengineering.org/agents-at-work-the-2026-playbook-for-building-reliable-agentic-workflows/) | Reliability patterns |

---

## 14) Anti-Patterns to Avoid

| Anti-Pattern | Why It's Bad | Instead |
|--------------|--------------|---------|
| **Orchestrator that writes code** | Loses separation of concerns, can't review its own work | Make orchestrator read-only, delegate ALL work |
| **Infinite fix cycles** | Burns tokens, rarely converges after 2 cycles | Hard cap at 2 cycles, then escalate |
| **Skipping review steps** | Defeats the purpose of the workflow | Orchestrator must enforce review after every implementation |
| **Monolithic orchestrator prompt** | Context pollution, long prompts degrade quality | Use skills for reusable knowledge, keep orchestrator lean |
| **No structured output** | Orchestrator can't parse natural language reliably | Define explicit result contracts for subagents |
| **Auto-committing** | Risky without human review of the final state | Orchestrator reports completion, human decides to commit |
| **Same model for reviewer and implementer** | Similar blind spots | Use different models/providers for independent perspectives |
| **No audit trail** | Can't debug workflow failures | Log every delegation, evaluation, and decision |

---

## 15) Implementation Roadmap

### Phase 1: Foundation (Day 1)
- Create orchestrator agent (`.opencode/agents/orchestrator.md`)
- Create `/execute` command
- Update existing specialist agents with structured output contracts
- Test with a simple 2-step workflow (implement + review)

### Phase 2: Full Workflow (Day 2-3)
- Add fix cycle logic to orchestrator
- Add parallel step detection
- Add quality validation integration
- Test with a complete feature workflow (F122-level complexity)

### Phase 3: Refinement (Day 4-5)
- Add workflow status tracking file
- Add audit trail logging
- Add convergence detection for reviews
- Test with incident and change request workflows
- Fine-tune agent steps limits and temperatures

### Phase 4: Advanced (Optional)
- Multi-model configuration for different perspectives
- External bash script for CI/CD integration
- Session continuity for very long workflows
- Notification system (via OpenCode notify plugin or OS notifications)

---

**Document Version**: 1.0
**Author**: AI Development Team
**Sources**: OpenCode official docs, community frameworks (opencode-workspace, OpenAgentsControl, agent-teams-lite, opencode-orch-mode), workflow gists, DEV community articles
