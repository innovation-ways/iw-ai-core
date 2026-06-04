# Guide to Creating Effective OpenCode Agents

**Purpose**: Practical, detailed guidance for designing safe, focused, high-performing OpenCode agents.
**Audience**: Engineers and AI workflow designers using OpenCode in project or team settings.
**Last Updated**: 2026-03-14

---

## 1) What an OpenCode Agent Is

An OpenCode agent is a configurable AI assistant with:

- a dedicated role (`description`)
- optional execution mode (`primary`, `subagent`, or `all`)
- optional model/runtime settings
- optional prompt specialization
- optional tool and permission restrictions

### Agents vs. Skills vs. Commands

| Mechanism | Triggered By | Has Own Tools | Has Own Permissions | Best For |
|-----------|-------------|---------------|---------------------|----------|
| **Agents** | User (`@agent`) or system (Task tool) | Yes | Yes | Specialized AI personas with distinct capabilities |
| **Skills** | Agent (auto-load via `skill` tool) | No (inherits agent's) | No | Reusable knowledge, domain expertise |
| **Commands** | User (`/command`) | No (inherits agent's) | No | User-triggered prompt shortcuts |

Use agents when you need **execution identity** — your own tools, permissions, and model settings. Use skills for reusable knowledge agents can load. Use commands for user-triggered prompt shortcuts.

See also: `docs/misc/guide_to_create_opencode_skills.md` and `docs/misc/guide_to_create_opencode_commands.md`.

### Configuration Locations

Agents can be defined in:

- Project scope: `.opencode/agents/*.md`
- Global scope: `~/.config/opencode/agents/*.md`
- JSON config: `opencode.json` under `agent`

For Markdown-defined agents, **the file name becomes the agent name**.
Example: `.opencode/agents/database-impl.md` => `@database-impl`.

### Built-in Agents

OpenCode ships with these built-in agents:

| Agent | Mode | Purpose |
|-------|------|---------|
| **Build** | Primary | Default agent with comprehensive tool access for development |
| **Plan** | Primary | Restricted mode for analysis without modifications (edit/bash = ask) |
| **General** | Subagent | Full tool access for complex multi-step tasks |
| **Explore** | Subagent | Fast, read-only codebase analysis |
| **Compaction** | Hidden | Automatic context compaction |
| **Title** | Hidden | Session title generation |
| **Summary** | Hidden | Session summary generation |

You can customize built-in agents via `opencode.json` or override them with markdown files.

---

## 2) Primary vs Subagent Strategy

Use the right mode:

- `primary`: interactive lead assistant you switch to directly (Tab / keybind)
- `subagent`: specialist helper invoked manually (`@agent-name`) or via task delegation
- `all`: can be used both ways (default if omitted)

### Recommended default

For specialist roles (security reviewer, docs writer, database implementer), use `mode: subagent`.

---

## 3) Agent File Structure (Markdown)

A robust agent file has two parts:

1. YAML frontmatter (configuration)
2. Instruction body (system prompt behavior)

### Minimal template

```markdown
---
description: Implements database requirements for feature prompts with strict scope and TDD
mode: subagent
model: opencode/gpt-5.1-codex
temperature: 0.1
steps: 20
permission:
  edit: ask
  bash:
    "*": ask
    "git status*": allow
    "git diff*": allow
    "pytest *": allow
---

You are a database implementation specialist...
```

---

## 4) Frontmatter Fields Reference

### Required

- `description`: what the agent does + when to use it

### High-impact optional fields

| Field | Type | Purpose | Example |
|-------|------|---------|---------|
| `mode` | string | `primary`, `subagent`, or `all` | `subagent` |
| `model` | string | Override default model | `anthropic/claude-sonnet-4-20250514` |
| `prompt` | string | External prompt file reference | `{file:./prompts/build.txt}` |
| `temperature` | float | Determinism (0.0) vs creativity (1.0) | `0.1` |
| `top_p` | float | Sampling diversity alternative | `0.9` |
| `steps` | int | Max agentic iterations | `30` |
| `disable` | bool | Disable agent entirely | `true` |
| `hidden` | bool | Hide from `@` autocomplete | `true` |
| `color` | string | UI color for agent | `"#FF5733"` or `"accent"` |
| `permission` | object | allow/ask/deny at tool and pattern granularity | See section 5 |
| `tools` | object | Enable/disable specific tools (boolean per tool) | `{"write": false}` |

### Temperature Guidance

| Range | Use Case | Example |
|-------|----------|---------|
| 0.0–0.2 | Deterministic, code analysis, implementation | Implementer agents |
| 0.3–0.5 | Balanced, standard development | General-purpose agents |
| 0.6–1.0 | High creativity, brainstorming | Research, documentation |

### JSON Agent Configuration

Agents defined in `opencode.json` support the same fields plus `prompt` as inline string or file reference:

```json
{
  "agent": {
    "code-reviewer": {
      "description": "Reviews code for best practices",
      "mode": "subagent",
      "model": "anthropic/claude-sonnet-4-20250514",
      "prompt": "You are a code reviewer...",
      "tools": {
        "write": false,
        "edit": false
      }
    }
  }
}
```

### Interactive Agent Creation

OpenCode provides a built-in wizard:

```bash
opencode agent create
```

This prompts for storage location, description, system prompt, tool selection, and generates the agent file.

### Important compatibility notes

- `maxSteps` is deprecated; use `steps`.
- Both `permission` (granular) and `tools` (boolean) are supported. Use `permission` for fine-grained control, `tools` for simple enable/disable.

---

## 5) Permissions Design (Most Important Best Practice)

Use **least privilege first**. Start restrictive, then open only what is needed.

### Safe baseline pattern

```yaml
permission:
  "*": ask
  edit: ask
  bash:
    "*": ask
    "git status*": allow
    "git diff*": allow
```

### All permission targets

| Target | Controls | Supports Globs |
|--------|----------|----------------|
| `edit` | File editing | No |
| `bash` | Shell commands | Yes (glob patterns on command) |
| `webfetch` | Web content fetching | No |
| `websearch` | Web searching | No |
| `skill` | Skill loading | Yes (glob on skill names) |
| `task` | Subagent invocation | Yes (glob on agent names) |
| `"*"` | Default for all targets | N/A |

### Permission values

| Value | Behavior |
|-------|----------|
| `allow` | Execute immediately, no user prompt |
| `ask` | Prompt user for approval each time |
| `deny` | Reject silently, never execute |

### Why this matters

- Limits accidental destructive actions
- Gives auditable, predictable behavior
- Improves trust in autonomous execution

### Pattern rule behavior

For object syntax (`bash`, `task`, `skill`), **last matching rule wins**.
Put broad rule first (`"*": ...`), then specific overrides after.

### Controlling subagent delegation

Use `permission.task` to control which subagents an agent can invoke:

```yaml
permission:
  task:
    "*": deny
    "code-reviewer": allow
    "explore": allow
```

---

## 6) Writing High-Performance Agent Prompts

A strong agent prompt should include:

1. **Role clarity**: single responsibility
2. **Execution sequence**: step-by-step process
3. **Input contract**: what user must provide
4. **Output contract**: format and expected artifacts
5. **Constraints**: explicit non-goals and guardrails
6. **Validation loop**: how to verify work
7. **Failure behavior**: what to do when blocked

### Good prompt pattern

- "When invoked, first read X, then Y, then generate plan."
- "Only modify files explicitly in scope."
- "Run these checks before returning."
- "Return: changed files, test results, unresolved blockers."

---

## 7) Tooling Best Practices

Map tools to mission; do not over-enable.

### Available tools

| Tool | Purpose |
|------|---------|
| `bash` | Execute shell commands |
| `edit` | Modify existing files (string replacement) |
| `write` | Create new files or overwrite |
| `read` | Read file contents |
| `grep` | Search file contents (regex) |
| `glob` | Find files by pattern |
| `list` | List directory contents |
| `patch` | Apply patches to files |
| `skill` | Load agent skills |
| `todowrite` | Manage todo lists |
| `todoread` | Read todo lists |
| `webfetch` | Fetch web content |
| `websearch` | Web search (requires `OPENCODE_ENABLE_EXA=1`) |
| `question` | Ask user questions |
| `lsp` | LSP code intelligence (experimental) |

### Typical profiles

- **Read-only reviewer**: `read`, `glob`, `grep`, `list`; disable `write`, `edit`, `bash`
- **Implementer**: add `edit`, `write` + controlled `bash`
- **Researcher**: add `webfetch` (and `websearch` if Exa enabled)
- **Orchestrator**: add `task` (subagent delegation) + `skill`

### Disabling tools

Use `tools` in frontmatter for simple boolean gating:

```yaml
tools:
  write: false
  edit: false
  bash: false
  mymcp_*: false
```

Wildcard patterns (e.g., `mymcp_*`) enable bulk control over MCP server tool families.

### Notes

- `websearch` requires `OPENCODE_ENABLE_EXA=1` environment variable.
- Subagents generally should not have `todowrite`/`todoread` unless explicitly needed.
- MCP server tools can be disabled with glob patterns in the `tools` config.

---

## 8) Integrating Project Context Correctly

Agent quality depends on context quality.

Use:

- `AGENTS.md` for durable project rules
- `opencode.json` `instructions` for reusable guidance docs
- `skills` for reusable domain instruction packs

### Recommended hierarchy

1. `AGENTS.md` for universal project rules
2. Agent-specific prompt for specialist behavior
3. Optional skill loading for deeper reusable workflows

---

## 9) Testing an Agent Before Team Use

Use a repeatable validation checklist:

1. **Invocation check**: appears as `@agent-name`
2. **Scope check**: does not edit outside target paths
3. **Permission check**: blocked/asked where expected
4. **Output check**: follows required format consistently
5. **Cost/loop check**: respects `steps` and exits cleanly
6. **Safety check**: does not execute risky bash unexpectedly

### Practical test matrix

- Happy path prompt
- Ambiguous prompt
- Out-of-scope prompt
- Destructive command attempt
- Missing input prompt

---

## 10) Common Anti-Patterns to Avoid

- Vague description ("helps with coding")
- Broad tool access "just in case"
- No permission guardrails on bash/edit
- Multi-role "do everything" prompts
- Missing output schema
- Missing stop criteria (`steps`)
- Relying on deprecated fields only

---

## 11) Example: `database-impl` Agent for InnoForge

Create `.opencode/agents/database-impl.md`:

```markdown
---
description: Implements InnoForge database requirements from ai-dev prompt files using strict TDD and architecture constraints. Use for SQLAlchemy model, migration, and DB-focused test implementation tasks.
mode: subagent
model: opencode/gpt-5.1-codex
temperature: 0.1
steps: 30
permission:
  "*": ask
  read: allow
  glob: allow
  grep: allow
  edit: ask
  bash:
    "*": ask
    "git status*": allow
    "git diff*": allow
    "pytest *": allow
    "make test-*": allow
    "make lint*": allow
    "make type-check*": allow
---

You are Database-impl, a specialist for InnoForge database implementation.

Execution protocol:
1) Read the target implementation prompt in ai-dev/prompts/active/.
2) Read referenced architecture/design docs before coding.
3) Follow TDD strictly: RED -> GREEN -> REFACTOR.
4) Implement only in-scope database/model/test requirements.
5) Respect InnoForge rules:
   - BIGSERIAL PKs, BIGINT FKs
   - snake_case naming
   - tenant_id on tenant-scoped tables
   - audit fields conventions
   - SQLAlchemy 2.0 style (Mapped[], mapped_column)
6) Run required quality/test commands for touched scope.
7) Return:
   - files changed
   - test results
   - coverage for new code (if available)
   - key decisions
   - blockers/risks

Hard constraints:
- Do not implement out-of-scope layers (API/services/repositories) unless explicitly required.
- Do not introduce forbidden dependencies.
- Do not create destructive git operations.
```

Usage examples:

- `@database-impl implement ai-dev/prompts/active/F001_S01_Database_prompt.md`
- `@database-impl review this DB prompt and produce execution plan first`

---

## 12) Operational Rollout Recommendations

- Start with one high-value specialist (`database-impl`)
- Validate with 3-5 real prompts
- Tighten permissions based on observed behavior
- Add companion reviewer agent later (read-only)
- Version agent files in git and review changes like code

---

## 13) Troubleshooting

### Agent not showing in `@` menu

- Confirm file is under `.opencode/agents/`
- Confirm valid frontmatter and required `description`
- Confirm agent not `disable: true`
- If `hidden: true`, it won’t appear in autocomplete

### Agent behaves too broadly

- Narrow `description`
- Add explicit "in scope/out of scope" section in body
- Reduce tools and tighten permissions

### Agent loops too long

- Set lower `steps`
- Add explicit completion criteria in prompt

---

## 14) Migrating Agents Between Claude Code and OpenCode

### Claude Code Subagents → OpenCode Agents

Claude Code uses the Agent tool to launch subagents with a `subagent_type` parameter. OpenCode agents are defined as markdown files with their own tool/permission configuration.

| Claude Code Concept | OpenCode Equivalent |
|---------------------|---------------------|
| Agent tool with `subagent_type` | `.opencode/agents/<name>.md` with `mode: subagent` |
| Agent `prompt` parameter | Markdown body of agent file |
| Agent `model` parameter | `model` frontmatter field |
| Subagent tool restrictions | `tools` and `permission` frontmatter fields |
| Agent `isolation: worktree` | N/A (use git worktree plugin if needed) |

### Key Differences

- **Invocation**: Claude Code launches agents programmatically via the Agent tool. OpenCode agents are invoked via `@agent-name` mention or Tab switch.
- **Tool control**: Claude Code agents inherit parent context tools. OpenCode agents have independent `tools` and `permission` config.
- **Session model**: Claude Code agents run in forked subprocesses. OpenCode agents run as child sessions navigable via keybinds (Up/Down/Left/Right).
- **Persistence**: Claude Code agents are ephemeral. OpenCode agent sessions persist and can be revisited.

### Migration Checklist

- [ ] Create `.opencode/agents/<name>.md` for each specialized Claude Code subagent
- [ ] Map `subagent_type` description to `description` frontmatter
- [ ] Map tool restrictions to `tools` and `permission` frontmatter
- [ ] Convert inline prompts to markdown body
- [ ] Test invocation via `@agent-name`

---

## 15) References

### Official OpenCode Documentation
- [Agents](https://opencode.ai/docs/agents/) — canonical agents reference
- [Config](https://opencode.ai/docs/config/) — opencode.json reference
- [Tools](https://opencode.ai/docs/tools/) — available tools
- [Rules](https://opencode.ai/docs/rules/) — AGENTS.md and instructions
- [Skills](https://opencode.ai/docs/skills/) — agent skills
- [Commands](https://opencode.ai/docs/commands/) — custom commands

### Community Resources
- [Awesome OpenCode](https://github.com/awesome-opencode/awesome-opencode) — curated plugins, themes, agents
- [Superpowers for OpenCode](https://blog.fsck.com/2025/11/24/Superpowers-for-OpenCode/) — practical customization guide
- [OpenAgentsControl](https://github.com/darrenhinde/OpenAgentsControl) — plan-first agent framework
- [agents.md](https://agents.md/) — cross-tool agent specification

### Innovation Ways
- Skill Guide: `docs/misc/guide_to_create_opencode_skills.md`
- Command Guide: `docs/misc/guide_to_create_opencode_commands.md`
- Claude Code Skills Guide: `docs/misc/guide_to_create_claude_skills.md`
- CLAUDE.md Guide: `docs/misc/guide_to_create_claude_file.md`

---

**Document Version**: 1.1
**Author**: AI Development Team
