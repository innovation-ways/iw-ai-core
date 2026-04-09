# Orchestration Comparison: OpenCode vs Claude Code

**Purpose**: Decision guide for choosing between OpenCode and Claude Code as the workflow orchestrator for InnoForge AI-driven development.
**Audience**: Engineers and team leads deciding which tool to use for a given work item.
**Last Updated**: 2026-03-15

---

## 1) Executive Summary

Both OpenCode and Claude Code can orchestrate the full InnoForge development workflow: design → implement → review → fix → validate → commit. The workflow artifacts (design documents, prompt files, manifest, reports) are **tool-agnostic** — identical files work with either orchestrator.

The choice is not "which is better" but "which fits this specific task better." Each tool has strengths that map to different scenarios.

**Quick decision rule:**
- **Use OpenCode** when you need multi-provider model diversity, have complex bash permission patterns, or prefer the TypeScript plugin ecosystem.
- **Use Claude Code** when you need worktree isolation for parallel work, hook-based automation, headless CLI scripting, or are already using Claude Code for the design phase.

---

## 2) Feature-by-Feature Comparison

### 2.1 Subagent Delegation

| Dimension | OpenCode | Claude Code |
|-----------|----------|-------------|
| **Delegation mechanism** | Task tool (`@agent-name`) | Agent tool (`subagent_type: name`) |
| **Agent definition files** | `.opencode/agents/*.md` | `.claude/agents/*.md` |
| **Frontmatter format** | YAML with `permission:` block | YAML with `tools:`/`disallowedTools:` |
| **Agent nesting** | Orchestrator → specialists (no deeper) | Same — subagents cannot spawn subagents |
| **Parallel delegation** | Multiple task calls in one turn | Multiple Agent calls + `run_in_background` |
| **Result flow** | Subagent output returned to parent | Same — summary returned, full transcript stored |
| **Agent spawning restrictions** | `task: {"*": deny, "name": allow}` | `tools: Agent(name1, name2, ...)` |
| **Default-deny pattern** | Native: `"*": deny` then allow specific | Native: only listed `Agent(...)` types allowed |

**Verdict**: Roughly equivalent. OpenCode's `"*": deny` default is slightly more explicit. Claude Code's `Agent(name)` allowlist achieves the same result with less configuration.

### 2.2 Permission and Security Model

| Dimension | OpenCode | Claude Code |
|-----------|----------|-------------|
| **Bash restrictions** | Per-command YAML patterns: `"cat *": allow` | `tools: Bash(cat *)` or hook-based gating |
| **Write/Edit control** | `write: false` in frontmatter | `disallowedTools: Edit, Write` |
| **Runtime gating** | Limited (plugin hooks) | Full PreToolUse hooks with allow/deny/modify |
| **Permission inheritance** | Subagent gets its own defined permissions | Subagent inherits parent context + own overrides |
| **Settings layers** | Single config | 4-layer: managed > local > project > user |
| **Input modification** | Not supported | PreToolUse hooks can modify tool inputs |

**Verdict**: Claude Code is more flexible. Hooks enable runtime validation that OpenCode can only achieve through plugins. The 4-layer settings model allows organization-wide policy enforcement.

**However**: OpenCode's YAML permission model is more readable and self-contained — everything is in one agent file. Claude Code splits permissions across agent frontmatter, settings.json, and hook scripts, which can be harder to audit.

### 2.3 Bash Command Control (Detailed)

This is a critical difference for orchestrator security.

**OpenCode approach** — declarative YAML in agent frontmatter:
```yaml
permission:
  bash:
    "*": deny
    "cat *": allow
    "ls *": allow
    "grep *": allow
    "git diff*": allow
    "git log*": allow
    "git status*": allow
    "git commit*": deny
    "git push*": deny
```

**Claude Code approach** — three mechanisms that combine:

1. **Agent frontmatter** (static allowlist):
```yaml
tools:
  - Bash(cat *)
  - Bash(ls *)
  - Bash(grep *)
  - Bash(git diff *)
  - Bash(git log *)
  - Bash(git status *)
```

2. **Settings.json** (deny rules):
```json
{
  "permissions": {
    "deny": ["Bash(git commit *)", "Bash(git push *)", "Bash(rm -rf *)"]
  }
}
```

3. **PreToolUse hook** (runtime validation with custom logic):
```bash
#!/bin/bash
# .claude/scripts/bash-guard.sh
INPUT=$(cat)
CMD=$(echo "$INPUT" | jq -r '.tool_input.command // ""')
if echo "$CMD" | grep -qE '^git (push|commit|reset)'; then
    echo '{"hookSpecificOutput":{"permissionDecision":"deny","permissionDecisionReason":"Blocked by policy"}}'
fi
exit 0
```

| Aspect | OpenCode | Claude Code |
|--------|----------|-------------|
| **Readability** | All in one file, clear pattern | Split across 3 locations |
| **Power** | Pattern matching only | Pattern matching + arbitrary logic |
| **Regex support** | Glob patterns (`*`) | Prefix patterns + regex in hooks |
| **Dynamic decisions** | No | Yes (hooks can inspect command context) |
| **Maintenance** | Easy — edit one YAML block | Requires coordinating multiple files |

**Verdict**: OpenCode is simpler for standard patterns. Claude Code is more powerful for complex policies (e.g., "allow `git commit` only if tests pass" — achievable via hooks but not via static patterns).

### 2.4 Multi-Model Support

| Dimension | OpenCode | Claude Code |
|-----------|----------|-------------|
| **Provider diversity** | Any provider (Anthropic, Google, OpenAI, local) | Anthropic only |
| **Per-agent model** | `model: google/gemini-2.5-pro` | `model: sonnet \| opus \| haiku` |
| **Reviewer vs Implementer diversity** | Different providers = different blind spots | Same provider, different model sizes |
| **Cost optimization** | Mix cheap/expensive models freely | Limited to Anthropic tiers |
| **Temperature control** | `temperature: 0.1` per agent | No per-agent temperature control |

**Verdict**: OpenCode wins decisively. Multi-provider support means you can use Gemini for code review (different perspective) and Claude for implementation. Claude Code is locked to Anthropic models.

**Impact on InnoForge**: The guide_to_opencode_orchestration.md specifically recommends different providers for reviewers vs implementers to get independent perspectives. Claude Code cannot replicate this.

### 2.5 Context Management

| Dimension | OpenCode | Claude Code |
|-----------|----------|-------------|
| **Fresh context per subagent** | Yes | Yes |
| **Context compaction** | Available | Available with PreCompact/PostCompact hooks |
| **Session resume** | `opencode run --session <id>` | `claude -p --resume <id>` or `--continue` |
| **Cross-session memory** | Context window only | Auto-memory at `~/.claude/projects/.../memory/` |
| **CLAUDE.md/instructions** | `OPENCODE.md` equivalent | CLAUDE.md + `.claude/rules/` with path scoping |
| **Skill preloading** | Via skills system | `skills:` field in agent frontmatter |
| **Context pollution prevention** | Fresh session per subagent | Same + worktree isolation |

**Verdict**: Claude Code has an edge. Auto-memory provides cross-session learning. Path-scoped rules in `.claude/rules/` reduce context bloat by loading only relevant rules. The `skills:` preloading in agent frontmatter is more explicit than OpenCode's skill system.

### 2.6 Headless/CLI Automation

| Dimension | OpenCode | Claude Code |
|-----------|----------|-------------|
| **Headless command** | `opencode run --agent X` | `claude -p --agent X` |
| **File attachment** | `--file <path>` | Pipe via stdin or `--append-system-prompt-file` |
| **Output format** | `--format json` | `--output-format json \| stream-json \| text` |
| **Structured output** | Not native | `--json-schema` for validated JSON |
| **Tool restrictions** | Via agent permissions | `--allowedTools` / `--disallowedTools` flags |
| **Budget control** | Not native | `--max-budget-usd N.NN` |
| **Turn limit** | Via agent `steps:` | `--max-turns N` |
| **Session naming** | `--title "name"` | `--name "name"` or `-n` |
| **Session continuation** | `--continue` / `--session <id>` | `--continue` / `--resume <id>` |
| **Worktree mode** | Not native | `--worktree` / `-w` |
| **Inline agent definition** | Not supported | `--agents '{"name": {...}}'` |

**Verdict**: Claude Code has significantly more CLI automation features. Budget caps, structured output with JSON schema validation, inline agent definitions, and worktree mode provide capabilities that OpenCode lacks for scripted workflows.

### 2.7 Parallel Execution

| Dimension | OpenCode | Claude Code |
|-----------|----------|-------------|
| **In-agent parallelism** | Multiple task calls in one turn | Multiple Agent calls with `run_in_background` |
| **File isolation** | Not native (risk of conflicts) | `isolation: worktree` per subagent |
| **Bash script parallelism** | Background processes with `&` | Same + `--worktree` flag for isolation |
| **Built-in batch mode** | Not available | `/batch` skill (5-30 parallel worktree agents) |
| **Conflict resolution** | Manual | Worktree branches merged by user |

**Verdict**: Claude Code wins. Native worktree isolation solves the core problem of parallel agents modifying the same files. The `/batch` skill automates the entire pattern. OpenCode requires manual workaround for file conflicts.

### 2.8 Hooks and Event-Driven Automation

| Dimension | OpenCode | Claude Code |
|-----------|----------|-------------|
| **Hook system** | TypeScript plugins (`session.idle`, `tool.execute.*`) | Shell-based hooks (20+ events) |
| **Hook language** | TypeScript | Any language (shell, Python, etc.) |
| **Event coverage** | ~6 events | 20+ events including SubagentStart/Stop |
| **Tool call interception** | `tool.execute.before/after` | PreToolUse / PostToolUse |
| **Input modification** | Not supported | `updatedInput` in PreToolUse response |
| **Subagent lifecycle hooks** | Not available | SubagentStart, SubagentStop |
| **Team coordination hooks** | Not available | TeammateIdle, TaskCompleted |
| **Context compaction hooks** | `experimental.session.compacting` | PreCompact, PostCompact |
| **MCP tool interception** | Not supported (GitHub #2319) | Not supported |
| **Scoped hooks** | Not available | Per-agent and per-skill hooks |

**Verdict**: Claude Code wins. More events, more control, and per-agent hook scoping. The SubagentStop hook is particularly valuable for orchestration — it fires when a specialist agent completes, allowing the orchestrator to validate output automatically.

**However**: OpenCode plugins are full TypeScript with SDK access, enabling complex logic. Claude Code hooks are shell commands, which are simpler but less powerful for complex state management.

### 2.9 Error Handling and Recovery

| Dimension | OpenCode | Claude Code |
|-----------|----------|-------------|
| **Subagent failure** | Error returned to orchestrator | Same |
| **Session resume** | `--session <id>` or `--continue` | `--resume <id>` or `--continue` |
| **Fix cycle tracking** | Manifest-based (tool-agnostic) | Same manifest works |
| **Budget enforcement** | Not native | `--max-budget-usd` prevents runaway costs |
| **Turn limits** | `steps: N` in agent definition | `maxTurns: N` in agent definition |
| **Context exhaustion** | Subagent retries (up to 3) | Auto-compaction + manifest-based resume |
| **Crash recovery** | Manifest tracks state; `/execute` resumes | Same manifest; `/execute` resumes |

**Verdict**: Roughly equivalent for workflow-level recovery. Claude Code's budget caps add a cost safety net that OpenCode lacks. Both use the same manifest for state, making crash recovery identical.

### 2.10 State Management

| Dimension | OpenCode | Claude Code |
|-----------|----------|-------------|
| **State file** | `workflow-manifest.json` | Same file (tool-agnostic) |
| **State updates** | Orchestrator reads/writes manifest | Same |
| **Resume mechanism** | Compare prompts to reports | Same + manifest step status |
| **Audit trail** | Manifest `runs[]` and `fix_cycles[]` | Same |
| **Cross-tool compatibility** | — | Same manifest works with both tools |

**Verdict**: Equal. The manifest is tool-agnostic by design. Both orchestrators read and update the same file using the same schema.

### 2.11 Ecosystem and Community

| Dimension | OpenCode | Claude Code |
|-----------|----------|-------------|
| **Community size** | Growing, smaller | Larger, more active |
| **Orchestration examples** | Several GitHub projects and gists | Many projects, blog posts, official examples |
| **Plugin/skill marketplace** | Community GitHub repos | 340+ plugins, growing marketplace |
| **Documentation quality** | Good (official docs) | Extensive (official docs + community) |
| **Official support** | Community-driven | Anthropic-backed |
| **Update frequency** | Regular | Frequent (multiple releases per week) |

**Verdict**: Claude Code has a larger ecosystem and more community resources for orchestration patterns. Anthropic's backing ensures continued development.

### 2.12 Cost Considerations

| Dimension | OpenCode | Claude Code |
|-----------|----------|-------------|
| **Model cost optimization** | Use cheaper models for simple tasks (Haiku for QV, Gemini Flash for reviews) | Limited to Anthropic tiers (Haiku < Sonnet < Opus) |
| **Budget caps** | Not native | `--max-budget-usd` per invocation |
| **Token efficiency** | Depends on model selection | Context management via auto-compaction |
| **Orchestrator overhead** | Orchestrator model cost + all subagent costs | Same structure |
| **Provider pricing flexibility** | Shop for cheapest provider per role | Anthropic pricing only |

**Verdict**: OpenCode has more flexibility for cost optimization through multi-provider support. Claude Code has better cost control mechanisms (budget caps) but less pricing flexibility.

---

## 3) Strengths Summary

### OpenCode Strengths

1. **Multi-provider model diversity** — Use different AI providers for different roles (Gemini for review, Claude for implementation, GPT-4 for architecture). This provides genuinely independent perspectives.

2. **Declarative permission model** — All permissions in one YAML block per agent. Easy to read, easy to audit, easy to copy between agents.

3. **Temperature control** — Per-agent temperature settings for deterministic vs creative behavior.

4. **TypeScript plugin power** — Full SDK access for complex event-driven logic. Plugins can maintain state, make API calls, and coordinate complex workflows.

5. **Cost optimization** — Mix expensive models for critical tasks and cheap models for routine work across any provider.

### Claude Code Strengths

1. **Worktree isolation** — Native `isolation: worktree` for parallel subagents working on the same codebase without file conflicts. This is a game-changer for parallel step execution.

2. **Rich hook system** — 20+ lifecycle events with per-agent scoping. SubagentStop hooks enable automatic validation when specialist agents complete.

3. **Headless CLI automation** — More CLI flags, structured JSON output, budget caps, inline agent definitions. Superior for bash-scripted workflows and CI/CD integration.

4. **Unified design + execution** — The design phase (skills for `/iw-new-feature`, `/iw-review-design`) already runs in Claude Code. Using Claude Code for execution eliminates the need to switch tools.

5. **Cross-session memory** — Auto-memory persists learnings between conversations. Agents can build up project-specific knowledge over time.

6. **`/batch` for codebase-wide changes** — Built-in skill for decomposing large changes into parallel worktree agents with automatic PR creation.

7. **Built-in budget control** — `--max-budget-usd` prevents cost surprises on long-running workflows.

8. **Agent teams** (experimental) — Peer-to-peer agent coordination for complex work requiring discussion or competing hypotheses.

---

## 4) Weaknesses Summary

### OpenCode Weaknesses

1. **No native worktree isolation** — Parallel agents risk file conflicts. Requires manual workaround or sequential execution.

2. **Limited hook events** — Fewer lifecycle hooks than Claude Code. No SubagentStart/Stop events for automatic validation.

3. **No budget control** — No built-in mechanism to cap spend per agent or workflow. Runaway costs possible.

4. **Requires tool-switching** — Design phase in Claude Code → execution in OpenCode. Context switch between terminals.

5. **No cross-session memory** — Each session starts fresh. No persistent learning between conversations.

6. **No structured output validation** — No `--json-schema` equivalent for forcing subagent output format.

### Claude Code Weaknesses

1. **Anthropic models only** — Cannot use Gemini, GPT-4, or local models. Limits perspective diversity for reviewers.

2. **Split permission configuration** — Permissions spread across agent frontmatter, settings.json, and hook scripts. Harder to audit than OpenCode's single YAML block.

3. **No temperature control** — Cannot set per-agent temperature for deterministic behavior.

4. **Agent teams experimental** — The teams feature is unstable and may change. Session resume doesn't work with teammates.

5. **Hook complexity** — Shell-based hooks are simpler than TypeScript plugins but less powerful for complex state management.

6. **No native multi-provider subagents** — All subagents use Anthropic models. A reviewer and implementer on the same provider may share blind spots.

---

## 5) Decision Matrix: When to Use Which

### Use OpenCode When:

| Scenario | Why OpenCode |
|----------|-------------|
| **You want reviewer/implementer model diversity** | Different providers give genuinely independent perspectives on the same code |
| **You need tight bash permission control** | OpenCode's YAML pattern matching is more readable and self-contained |
| **You want TypeScript plugin extensibility** | Full SDK access for complex event-driven logic |
| **Cost optimization is critical** | Mix cheap models (Gemini Flash, Haiku) with expensive ones (Opus) across providers |
| **You're already using OpenCode** | No tool switch needed |
| **Temperature control matters** | Deterministic agents for implementation, creative for design |

### Use Claude Code When:

| Scenario | Why Claude Code |
|----------|----------------|
| **Parallel steps need file isolation** | Native worktree isolation prevents conflicts |
| **You want unified design + execution** | No tool switch — design and execute in the same terminal |
| **You need headless/CI automation** | More CLI flags, budget caps, structured output |
| **You want hook-based automation** | SubagentStop hooks for automatic result validation |
| **Cross-session learning matters** | Auto-memory persists knowledge between conversations |
| **You're doing a large codebase change** | `/batch` skill automates parallel worktree + PR workflow |
| **Budget control is important** | `--max-budget-usd` prevents cost surprises |
| **You want to script the workflow externally** | Better CLI automation with `--json-schema`, `--agents`, etc. |

### Task-Specific Recommendations

| Task Type | Recommended Tool | Rationale |
|-----------|-----------------|-----------|
| **Simple incident (1-2 steps)** | Claude Code | No tool switch, fast execution, minimal overhead |
| **Standard feature (3-6 steps)** | Either | Both work well; choose based on personal preference |
| **Complex feature (7+ steps)** | OpenCode | Multi-provider diversity helps catch more review issues |
| **Parallel implementation steps** | Claude Code | Worktree isolation prevents file conflicts |
| **Security-sensitive changes** | OpenCode | Use a different provider for security review (different blind spots) |
| **Quick bug fix with known solution** | Claude Code | Unified flow, no tool switch needed |
| **CI/CD automated workflow** | Claude Code | Better CLI automation, budget caps, structured output |
| **Codebase-wide refactoring** | Claude Code | `/batch` skill handles decomposition and parallelism |
| **Performance-critical changes** | OpenCode | Temperature control for deterministic implementation |
| **First time running a workflow type** | Claude Code | Cross-session memory learns from experience |

---

## 6) Hybrid Approach: Best of Both Worlds

The tools are not mutually exclusive. The InnoForge manifest is tool-agnostic, so you can mix orchestrators:

### Pattern: Design in Claude Code, Choose Orchestrator Per Task

```
1. Claude Code: /iw-new-feature (always)
2. Claude Code: /iw-review-design (always)
3. Human: Approve manifest
4. Decision point:
   ├── Simple/parallel task → Claude Code: /execute {ID}
   └── Complex/security task → OpenCode: /execute {ID}
5. Human: Review, commit, move to done/
```

### Pattern: Claude Code for Implementation, OpenCode for Review

```
1. Claude Code orchestrator delegates implementation steps
2. For code review steps, switch to OpenCode with a different-provider reviewer
3. Resume in Claude Code for quality validation
```

This requires manual step management but maximizes the strengths of each tool.

### Pattern: Claude Code Headless in CI, OpenCode Interactive

```
# CI/CD pipeline (automated, budget-capped)
claude -p --agent orchestrator --max-budget-usd 15.00 \
    "Execute workflow for F122"

# Interactive development (when human wants to observe)
opencode → /execute F122
```

---

## 7) Known Gotchas and Real-World Limitations

### 7.1 OpenCode Gotchas

| Issue | Impact | Workaround |
|-------|--------|------------|
| **Headless compaction exit bug** (GitHub #13946) | `opencode run` exits silently after auto-compaction if the compaction model's response exceeds the overflow threshold. Critical for 10+ step workflows in CI/CD. | Use `opencode serve` + API calls, or break into shorter headless runs with session resume. Monitor for patch. |
| **Direct @mention bypasses task permissions** | A user typing `@backend-impl` in the orchestrator session can invoke any agent regardless of the `task:` permission rules. Rules only apply to programmatic delegation. | Document as team convention; rely on review process. |
| **`steps` cap is soft** | When step limit is reached, the agent summarizes and recommends remaining tasks rather than hard-stopping. Orchestrator must parse this. | Check result contract for `completion_status: "partial"` and handle explicitly. |
| **No delivery receipt for inter-agent messages** | Crashed agents do not auto-restart; human re-engagement required. | Manifest-based state recovery handles this at the workflow level. |
| **MCP tool granularity** | Cannot disable individual commands within an MCP server — only all-or-nothing per server. | Avoid MCP for security-sensitive operations; use native tools. |

### 7.2 Claude Code Gotchas

| Issue | Impact | Workaround |
|-------|--------|------------|
| **Subagents cannot spawn subagents** (hard constraint) | The orchestrator must run as the main session (`--agent orchestrator`), not as a subagent of something else. This is not configurable. | Design the workflow with the orchestrator as the entry point, not a delegated worker. |
| **Task name uniqueness bug** (GitHub #11028) | Spawning multiple subagents of the same type in a single turn can fail with "Tool names must be unique". | Spawn them sequentially or use different agent names per step. |
| **Custom agents cannot spawn into teams** (GitHub #23506) | If you launch a coordinator with `claude --agent coordinator`, it cannot spawn agent team members. | Use agent teams only from the default main session. |
| **PreToolUse hook API change** (GitHub #4362) | `approve: false` at the top level is silently ignored. Must use `hookSpecificOutput.permissionDecision: "deny"`. | Use the correct structured JSON response format. |
| **Teammates have fewer tools than subagents** (GitHub #32731) | Teammate tool access is more restricted than plain subagent tool access. | Verify tool availability in agent teams before relying on them. |
| **Cost explosion with parallel subagents** | 49 parallel agents generated 887K tokens/minute in a documented incident. No built-in token cap. | Use hierarchical structure (1 orchestrator → 3-5 specialists), not flat parallel pools. |
| **Agent teams: no session resume** | Restarting a session with agent teams loses all teammates. | Agent teams not suitable for long-running interruptible workflows yet. |

### 7.3 Shared Limitations

Both tools:
- Cannot control individual commands within an MCP server
- Require user-implemented fix cycle logic in the orchestrator
- Have no guaranteed exactly-once execution semantics for subagent outputs
- Produce cumulative quality degradation with multiple sequential context compactions
- Cannot nest subagent delegation beyond one level (orchestrator → specialist)

---

## 8) Weighted Scoring Matrix

Criteria weighted for the InnoForge orchestrator-to-specialist-agent workflow pattern:

| Criterion | Weight | OpenCode | Claude Code | Notes |
|-----------|--------|----------|-------------|-------|
| Delegation model fit | 20% | 9/10 | 7/10 | OpenCode's hub-and-spoke YAML model matches exactly; CC has hard nesting limit |
| Permission granularity | 15% | 8/10 | 8/10 | OC: declarative glob; CC: static + dynamic hooks |
| Multi-model support | 15% | 10/10 | 4/10 | OC: 75+ providers; CC: Anthropic only |
| Headless/CI reliability | 15% | 6/10 | 9/10 | OC: compaction exit bug; CC: stable + official CI docs |
| Context management | 10% | 7/10 | 8/10 | CC: per-agent memory, worktree isolation |
| Parallel execution | 10% | 6/10 | 8/10 | CC: worktree isolation; OC: no file conflict prevention |
| Error handling/recovery | 10% | 8/10 | 7/10 | OC: manifest state is more auditable |
| Cost control | 5% | 9/10 | 6/10 | OC: cross-provider pricing flexibility |
| **Weighted Total** | **100%** | **8.0** | **7.1** | |

**Interpretation**: OpenCode scores higher overall due to multi-model diversity and delegation model fit. Claude Code scores higher on headless/CI reliability and parallel execution. The difference is small enough that scenario-specific factors (from the decision matrix in Section 5) should drive the choice per task.

---

## 9) Migration Path

If you're currently using OpenCode and want to add Claude Code as an option:

### Phase 1: Dual Setup (Recommended Starting Point)

Keep both orchestrator configurations:
- `.opencode/agents/orchestrator.md` — existing, unchanged
- `.claude/agents/orchestrator.md` — new, ported from OpenCode version
- `.claude/skills/execute/SKILL.md` — new, entry point for Claude Code

The manifest and all workflow artifacts remain shared. Choose which orchestrator to invoke per task.

### Phase 2: Evaluate and Specialize

After running several work items through each orchestrator:
1. Identify which scenarios each tool handles better
2. Document team preferences and lessons learned
3. Update the decision matrix with real-world experience

### Phase 3: Optimize

- Add hooks for automatic validation (SubagentStop)
- Add worktree isolation for parallel steps
- Configure budget caps for CI/CD integration
- Consider the hybrid patterns above

---

## 10) Summary Table

| Dimension | OpenCode | Claude Code | Winner |
|-----------|----------|-------------|--------|
| Subagent delegation | Task tool | Agent tool | Tie |
| Permission model (readability) | YAML in agent file | Split across files | OpenCode |
| Permission model (power) | Static patterns | Patterns + runtime hooks | Claude Code |
| Multi-provider models | Any provider | Anthropic only | OpenCode |
| Parallel execution | No isolation | Worktree isolation | Claude Code |
| Hook/event system | TypeScript plugins (~6 events) | Shell hooks (20+ events) | Claude Code |
| Headless CLI | Basic | Rich (budget, schema, inline agents) | Claude Code |
| Cost optimization | Multi-provider flexibility | Budget caps per invocation | Tie (different strengths) |
| Cross-session memory | None | Auto-memory | Claude Code |
| Community/ecosystem | Growing | Larger, Anthropic-backed | Claude Code |
| State management | Manifest-based | Same manifest | Tie |
| Error recovery | Manifest resume | Same + budget caps | Claude Code |
| Temperature control | Per-agent | Not available | OpenCode |
| Unified workflow | Requires tool switch | Design + execute in one tool | Claude Code |
| Security review diversity | Different AI providers | Same provider only | OpenCode |

**Overall**: Claude Code has more features and a larger ecosystem. OpenCode's key advantage is multi-provider model diversity, which matters most for code review independence. For most InnoForge workflow scenarios, Claude Code is the more capable choice — but OpenCode remains the better option when review quality from diverse perspectives is the priority.

---

## 11) Immediate Action Items

Based on this analysis, the recommended next steps are:

### Regardless of Tool Choice

1. **Enable multi-model code review in OpenCode** — Set `model: google/gemini-2.5-pro` in `code-review-impl.md` and `code-review-final-impl.md`. This is the single highest-value change: different provider = different training data = genuinely independent code review perspective.

2. **Add convergence detection** — Update the orchestrator to compare review findings across fix cycles. If consecutive cycles produce identical findings, escalate immediately instead of burning all 5 cycles.

### To Enable Claude Code Orchestration

3. **Port the orchestrator agent** — Create `.claude/agents/orchestrator.md` translating the OpenCode permission model to Claude Code's `tools`/`disallowedTools` + hooks.

4. **Create the `/execute` skill** — Create `.claude/skills/execute/SKILL.md` with `context: fork` and `agent: orchestrator`.

5. **Create bash guard scripts** — `.claude/scripts/orchestrator-bash-guard.sh` for enforcing read-only bash on the orchestrator.

6. **Port specialist agents** — Create `.claude/agents/*.md` for all implementation, review, fix, and QV agents.

7. **Test with a simple incident** — Run a 2-step workflow (implement + review) through Claude Code's orchestrator before attempting a full feature.

---

**Document Version**: 1.1
**Author**: AI Development Team
**Sources**: Claude Code official docs, OpenCode official docs, community patterns, IW workflow implementation experience, GitHub issue reports

---

**Document Version**: 1.0
**Author**: AI Development Team
**Sources**: Claude Code official docs, OpenCode official docs, community patterns, IW workflow implementation experience
