# Guide to Creating Effective OpenCode Commands

**Purpose**: Practical guidance for designing, structuring, and maintaining OpenCode custom commands.
**Audience**: Engineers and AI workflow designers using OpenCode in project or team settings.
**Last Updated**: 2026-03-14

---

## 1) What an OpenCode Command Is

A command is a **user-triggered prompt shortcut** that sends a predefined prompt to an agent. Commands are the simplest extensibility mechanism — a markdown file whose body becomes the prompt template, optionally targeting a specific agent and model.

Commands are invoked via `/command-name` in the OpenCode TUI.

### Commands vs. Skills vs. Agents

| Mechanism | Triggered By | Receives Args | Has Own Tools | Has Own Permissions | Best For |
|-----------|-------------|---------------|---------------|---------------------|----------|
| **Commands** | User (`/command`) | Yes (`$ARGUMENTS`, `$1`, `$2`) | No (uses agent's) | No | Repetitive prompts, quick actions |
| **Skills** | Agent (auto-load) | No | No (uses agent's) | No | Reusable knowledge, domain expertise |
| **Agents** | User (`@agent`) or system | No (task in message) | Yes (own tools config) | Yes (own permissions) | Specialized AI personas |

**When to use commands**:
- Frequent user-initiated actions ("run tests", "create component")
- Tasks that always need the same prompt structure
- Quick shortcuts that don't need a dedicated agent
- Wrapping complex prompts users shouldn't have to type repeatedly

**When NOT to use commands** (use agents instead):
- Tasks requiring restricted tool access
- Multi-agent orchestration
- Tasks where the AI should auto-detect and invoke

---

## 2) Command File Structure

### File Locations

| Location | Scope | Discovery |
|----------|-------|-----------|
| `~/.config/opencode/commands/` | Global (all projects) | Available everywhere |
| `.opencode/commands/` | Project-specific | Available in this project |

The filename (without `.md`) becomes the command name:
- `test.md` → `/test`
- `create-component.md` → `/create-component`
- `db-migrate.md` → `/db-migrate`

### Basic Structure

```
.opencode/commands/
├── test.md              # /test — run test suite
├── ship.md              # /ship — CI pipeline
├── create-component.md  # /create-component — scaffold React component
└── db-migrate.md        # /db-migrate — create migration
```

---

## 3) Command File Format

Commands use markdown with YAML frontmatter:

```markdown
---
description: Run tests with coverage and suggest fixes for failures
agent: build
model: anthropic/claude-sonnet-4-20250514
---

Run the full test suite with coverage report and show any failures.
Focus on the failing tests and suggest fixes.
```

### YAML Frontmatter Fields

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `description` | string | No | Shown in TUI autocomplete and `/help` |
| `agent` | string | No | Which agent executes the command |
| `subtask` | boolean | No | Force subagent invocation (`true` = runs as subtask) |
| `model` | string | No | Override the default model for this command |

All fields are optional — a command file can be just a markdown body with no frontmatter.

### Agent Selection

- If `agent` is omitted: the currently active primary agent executes the command
- If `agent` names a **subagent**: the command triggers a subagent invocation by default
- If `agent` names a **primary agent**: the command runs in that primary agent's context
- If `subtask: true`: forces subagent execution regardless of agent type

---

## 4) Dynamic Prompt Features

### Arguments

Users pass arguments after the command name. Access them with:

| Variable | Description | Example |
|----------|-------------|---------|
| `$ARGUMENTS` | All arguments as a single string | `/test frontend` → `$ARGUMENTS` = `"frontend"` |
| `$1`, `$2`, `$3` | Positional arguments | `/create Button primary` → `$1` = `"Button"`, `$2` = `"primary"` |

```markdown
---
description: Create a new React component
---

Create a new React component named **$1** with these requirements:
- Use TypeScript strict mode
- Follow the container/presenter pattern
- Add JSDoc documentation
- Include a basic test file

Component variant: $2 (default: "default")
```

Usage: `/create-component Button primary`

### Shell Output Injection

Inject the output of bash commands using `` !`command` `` syntax:

```markdown
---
description: Review recent changes
---

Here are the recent git changes:
!`git diff --stat HEAD~3`

And the current branch status:
!`git status --short`

Based on these changes, review the code for:
1. Potential bugs
2. Missing tests
3. Style violations
```

The shell commands are executed **before** the prompt reaches the agent, and their output is substituted inline.

### File References

Include file contents using `@filename` syntax:

```markdown
---
description: Review a specific file
---

Review the component in @src/components/$1.tsx.
Check for performance issues and suggest improvements.
```

---

## 5) JSON Configuration Alternative

Commands can also be defined in `opencode.json` instead of markdown files:

```json
{
  "command": {
    "test": {
      "template": "Run the full test suite with coverage. Focus on failures and suggest fixes.",
      "description": "Run tests with coverage",
      "agent": "build",
      "model": "anthropic/claude-sonnet-4-20250514"
    },
    "ship": {
      "template": "Run the full CI pipeline: backend tests, quality gates, frontend checks. Fix issues at each stage. Generate a ship report and commit.",
      "description": "Full CI pipeline with auto-fix",
      "agent": "build"
    },
    "review": {
      "template": "Review the code changes in the current branch. Focus on bugs, security, and performance.",
      "description": "Code review current changes",
      "agent": "code-reviewer",
      "subtask": true
    }
  }
}
```

### JSON vs. Markdown

| Aspect | JSON (`opencode.json`) | Markdown (`.opencode/commands/`) |
|--------|------------------------|----------------------------------|
| Multi-line prompts | Awkward (escaped `\n`) | Natural (markdown body) |
| Dynamic content | No shell injection | `` !`command` `` supported |
| File references | No `@file` syntax | `@file` supported |
| Arguments | `$ARGUMENTS` supported | `$ARGUMENTS`, `$1`, `$2` supported |
| Version control | In config file | Individual files |
| Organization | All in one file | One file per command |

**Recommendation**: Use markdown files for commands with complex prompts, shell injection, or file references. Use JSON for simple, short commands.

---

## 6) Built-in Commands

OpenCode includes several built-in commands:

| Command | Purpose |
|---------|---------|
| `/init` | Scan project and generate AGENTS.md |
| `/undo` | Undo the last AI action |
| `/redo` | Redo the last undone action |
| `/share` | Share the current session |
| `/help` | Show available commands |

Custom commands can **override** built-in commands by using the same name. Use this carefully.

---

## 7) Practical Examples

### Example 1: Test Runner

```markdown
---
description: Run backend tests with coverage and fix failures
agent: build
---

Run the full backend test suite:
```bash
make test
```

If any tests fail:
1. Analyze the failure output
2. Identify the root cause
3. Fix the code
4. Re-run tests (max 2 fix cycles)

Report results in this format:
- Tests passed/failed
- Coverage percentage
- Issues found and fixes applied
```

### Example 2: Component Scaffold

```markdown
---
description: Create a new React component with tests
agent: build
---

Create a new React component named **$1** in `frontend/src/components/`:

1. Create `$1.tsx` with:
   - TypeScript strict mode
   - Props interface with JSDoc
   - shadcn/ui components where appropriate
   - Tailwind CSS styling

2. Create `$1.test.tsx` with:
   - Basic render test
   - Props variation tests

3. Export from the parent index if one exists.

Component type: $2 (default: "presenter")
```

### Example 3: Database Migration

```markdown
---
description: Create a new Alembic migration
agent: build
---

Create a new database migration for: **$ARGUMENTS**

1. Analyze what tables/columns need to change
2. Run: `alembic revision --autogenerate -m "$ARGUMENTS"`
3. Review the generated migration file
4. Ensure both `upgrade()` and `downgrade()` are correct
5. Add inline comments explaining non-obvious operations
6. Run: `alembic upgrade head` to test the migration
7. Run: `alembic downgrade -1` to verify rollback works

Constraints:
- BIGSERIAL PKs, BIGINT FKs
- snake_case naming for all tables and columns
- Include `tenant_id` on tenant-scoped tables
- Include audit fields (created_at, created_by, updated_at)
```

### Example 4: Ship Code (equivalent to Claude Code's ship-code skill)

```markdown
---
description: Run full CI pipeline, fix issues, commit, and push
agent: build
---

Run the full CI pipeline sequentially. Fix issues at each stage (max 2 fix cycles per stage).

## Stage 1: Backend Tests
```bash
make test
```

## Stage 2: Backend Quality
```bash
make quality
```
Auto-fix with `make format` first, then address remaining issues.

## Stage 3: Security SAST
```bash
make security-sast
```

## Stage 4: Frontend Checks
Skip if no frontend files changed (`git diff --name-only HEAD | grep -q '^frontend/'`).
```bash
make frontend-check
```

## Stage 5: Generate Report
Write to `ai-dev/reports/code_commits/code-ship-report-YYYY-MM-DD-HHMMSS.md`.

## Stage 6: Commit and Push
Stage all changed files, create a conventional commit, and push.

## Abort Conditions
STOP if a stage still fails after 2 fix cycles. Generate report but do NOT commit.
```

---

## 8) Migrating Commands Between Claude Code and OpenCode

### Claude Code Skills → OpenCode Commands

Claude Code uses skills for both user-invoked slash commands and agent-loaded knowledge. When migrating a user-invoked Claude Code skill to OpenCode, create a **command**:

| Claude Code Skill Field | OpenCode Command Field | Notes |
|-------------------------|------------------------|-------|
| `name` | Filename (e.g., `ship.md` → `/ship`) | Filename becomes command name |
| `description` | `description` | Direct mapping |
| `allowed-tools` | N/A | Commands inherit agent's tools |
| `argument-hint` | N/A | Document in description |
| `model` | `model` | Direct mapping |
| `disable-model-invocation: true` | Default behavior | Commands are always user-only |
| `context: fork` | `subtask: true` | Runs in subagent |
| `agent` | `agent` | Direct mapping |
| SKILL.md body | Markdown body | Direct mapping |
| `$ARGUMENTS`, `$1` | `$ARGUMENTS`, `$1` | Same syntax |
| `` !`command` `` | `` !`command` `` | Same syntax |

### Migration Checklist

- [ ] Create `.opencode/commands/<name>.md` from `.claude/skills/<name>/SKILL.md`
- [ ] Map frontmatter fields (see table above)
- [ ] Remove unsupported fields (`allowed-tools`, `argument-hint`, `user-invocable`)
- [ ] Verify `$ARGUMENTS` and `` !`command` `` syntax still works
- [ ] Test the command in OpenCode TUI
- [ ] If the skill also served as agent-loaded knowledge, create a **separate skill** in `.opencode/skills/`

---

## 9) Anti-Patterns to Avoid

| Anti-Pattern | Why It's Bad | Instead |
|--------------|--------------|---------|
| **No description** | Command invisible in autocomplete | Always add a description |
| **Enormous prompt** | Wastes tokens on every invocation | Break into command + skill reference |
| **Hardcoded paths** | Breaks across projects | Use `$ARGUMENTS` for dynamic paths |
| **Missing agent** | Runs in whatever agent is active | Specify `agent` for predictable behavior |
| **Overriding built-ins** | Confusing for team members | Use unique names unless intentional |
| **Shell injection for side effects** | `` !`rm -rf` `` runs before agent sees prompt | Only use for read-only commands |
| **Trying to restrict tools** | Commands don't control tools | Use an agent if tool restriction is needed |

---

## 10) Quality Checklist

- [ ] Filename uses lowercase with hyphens (kebab-case)
- [ ] Description is concise and explains the command's purpose
- [ ] Agent is specified if the command needs a specific execution context
- [ ] Arguments are documented in the prompt body
- [ ] Shell injections (`` !`command` ``) are read-only and safe
- [ ] Output format is defined if applicable
- [ ] Constraints are stated explicitly
- [ ] Command tested in TUI with and without arguments
- [ ] No overlap with built-in commands (unless intentional override)

---

## 11) When to Use Commands vs. Other Mechanisms

### Decision Flowchart

```
User wants to trigger an action manually?
├── YES → Is the prompt simple and self-contained?
│   ├── YES → Use a COMMAND
│   └── NO → Does it need its own tool/permission profile?
│       ├── YES → Use an AGENT
│       └── NO → Use a COMMAND + reference a SKILL for detailed knowledge
└── NO → Should the agent auto-detect when to use it?
    ├── YES → Use a SKILL
    └── NO → Put it in AGENTS.md or instructions
```

### Quick Reference

| Scenario | Use |
|----------|-----|
| "Run tests and fix failures" | Command |
| "Create a new React component" | Command |
| "Review code for security issues" | Agent (needs restricted tools) |
| "InnoForge coding conventions" | Skill (agent loads when relevant) |
| "Always use TDD" | AGENTS.md (universal rule) |
| "Research a technology" | Agent (needs specific model/tools) |
| "Generate a changelog" | Command targeting a specific agent |

---

## 12) References

### Official OpenCode Documentation
- [Commands](https://opencode.ai/docs/commands/) — canonical commands reference
- [Agent Skills](https://opencode.ai/docs/skills/) — skills reference
- [Agents](https://opencode.ai/docs/agents/) — agent configuration
- [Config](https://opencode.ai/docs/config/) — opencode.json reference
- [Rules](https://opencode.ai/docs/rules/) — AGENTS.md and instructions

### Community Resources
- [Awesome OpenCode](https://github.com/awesome-opencode/awesome-opencode) — curated plugins and resources
- [Superpowers for OpenCode](https://blog.fsck.com/2025/11/24/Superpowers-for-OpenCode/) — practical customization guide

### Innovation Ways
- Agent Guide: `docs/misc/guide_to_create_opencode_agents.md`
- Skill Guide: `docs/misc/guide_to_create_opencode_skills.md`
- Claude Code Skills Guide: `docs/misc/guide_to_create_claude_skills.md`
- CLAUDE.md Guide: `docs/misc/guide_to_create_claude_file.md`

---

**Document Version**: 1.0
**Author**: AI Development Team
