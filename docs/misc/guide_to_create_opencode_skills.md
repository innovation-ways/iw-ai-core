# Guide to Creating Effective OpenCode Skills

**Purpose**: Practical guidance for designing, structuring, and maintaining OpenCode skills.
**Audience**: Engineers and AI workflow designers using OpenCode in project or team settings.
**Last Updated**: 2026-03-14

---

## 1) What an OpenCode Skill Is

A skill is a **reusable instruction package** that agents can discover and load on demand. Skills are not active by default — an agent sees the list of available skills (name + description only) and pulls in the full `SKILL.md` body when the task requires it. This lazy-loading approach preserves context window budget.

OpenCode skills implement the open **[Agent Skills specification](https://agentskills.io/specification)**, making them cross-compatible with other tools that support the same standard (including Claude Code).

### Skills vs. Commands vs. Agents vs. AGENTS.md

| Mechanism | Loaded When | Token Cost | Invoked By | Best For |
|-----------|-------------|------------|------------|----------|
| **AGENTS.md** | Always (every conversation) | Permanent | System | Universal rules, project structure, critical conventions |
| **Skills** (`.opencode/skills/`) | On demand via `skill` tool | Pay-per-use | Agent (auto) or user | Reusable workflows, domain expertise, multi-step processes |
| **Commands** (`.opencode/commands/`) | On `/command` invocation | On demand | User only | User-triggered prompt shortcuts, repetitive tasks |
| **Agents** (`.opencode/agents/`) | On `@agent` mention or Tab switch | On demand | User or system | Specialized AI personas with distinct tools and permissions |

**Key distinction**: Skills are **agent-loadable knowledge**. Commands are **user-triggered prompts**. Agents are **execution personas** with their own tool access and permissions.

> **When to choose skills**: Use skills for instructions that (a) are reusable across tasks, (b) don't need their own tool/permission profile, and (c) should load only when relevant. If the instructions need their own tool restrictions or execution identity, use an agent instead.

---

## 2) Skill File Structure

### Minimum Viable Skill

```
.opencode/skills/
└── my-skill/
    └── SKILL.md          # Required: YAML frontmatter + instructions
```

### Full Skill Structure

```
.opencode/skills/
└── my-skill/
    ├── SKILL.md          # Entry point (required)
    └── references/       # Detailed docs loaded on demand (optional)
        ├── patterns.md
        └── examples.md
```

### Storage Locations

OpenCode discovers skills from multiple standard locations:

**Project-level (highest priority):**

| Path | Scope |
|------|-------|
| `.opencode/skills/<name>/SKILL.md` | Project-local (OpenCode native) |
| `.claude/skills/<name>/SKILL.md` | Project-local (Claude Code compatible) |
| `.agents/skills/<name>/SKILL.md` | Project-local (Agents.md compatible) |

**Global (supplements project-local):**

| Path | Scope |
|------|-------|
| `~/.config/opencode/skills/<name>/SKILL.md` | Global (OpenCode native) |
| `~/.claude/skills/<name>/SKILL.md` | Global (Claude Code compatible) |
| `~/.agents/skills/<name>/SKILL.md` | Global (Agents.md compatible) |

OpenCode traverses upward from the current working directory until reaching the git worktree root, loading all matching skill definitions along the way. Global definitions supplement project-local ones automatically.

> **Cross-tool compatibility**: Because OpenCode reads `.claude/skills/` paths, skills written for Claude Code work in OpenCode without modification. If you maintain both tools, keep skills in `.claude/skills/` for maximum portability, or symlink between locations.

---

## 3) SKILL.md Anatomy

Every skill has two parts: **YAML frontmatter** and a **markdown body**.

### YAML Frontmatter

```yaml
---
name: git-release
description: Create consistent releases and changelogs from merged PRs.
  Use when preparing a release, generating changelogs, or bumping versions.
license: MIT
compatibility: opencode
metadata:
  audience: maintainers
  workflow: github
---
```

| Field | Required | Rules |
|-------|----------|-------|
| `name` | Yes | 1–64 chars, lowercase alphanumeric with single hyphens, must match directory name |
| `description` | Yes | 1–1024 chars, must describe WHAT and WHEN |
| `license` | No | License identifier (MIT, BSD, Apache-2.0) |
| `compatibility` | No | Target tool (opencode, claude-code) |
| `metadata` | No | Arbitrary key-value pairs for filtering/discovery |

### Name Validation Rules

Skill names must:
- Contain 1–64 characters
- Use lowercase alphanumeric characters with single hyphen separators
- Not start, end, or contain consecutive hyphens
- Match the containing directory name exactly

**Regex**: `^[a-z0-9]+(-[a-z0-9]+)*$`

Valid: `git-release`, `db-migrate`, `iw-new-feature`
Invalid: `Git-Release`, `--release`, `release-`, `my--skill`

### Markdown Body

The instruction body that agents load when the skill is activated. Guidelines:

- **Keep under 500 lines** — use `references/` for detailed content
- **Be specific** — explicit steps prevent drift
- **Use numbered steps** for sequential workflows
- **Include output format** — define what the skill should produce
- **State constraints** — what NOT to do is as important as what TO do

---

## 4) Writing Effective Descriptions

The description is the **single most important field** — it determines whether an agent selects the skill for a given task. Agents only see the name and description until they explicitly load the skill.

### Good Description Pattern

```
[What it does in one sentence]. Use when [specific triggers, keywords, contexts].
```

### Examples

**Good** (specific triggers, clear scope):
```yaml
description: Create consistent releases and changelogs from merged PRs.
  Use when preparing a release, generating changelogs, bumping versions,
  or user says "release", "changelog", "version bump".
```

**Bad** (vague, no triggers):
```yaml
description: Helps with releases.
```

### Trigger Word Strategy

Include in your description:
1. The **action verb** (create, review, analyze, generate)
2. The **domain nouns** (release, migration, deployment)
3. Common **synonyms** users might say
4. The **skill name** for explicit reference

---

## 5) How Skills Are Loaded (The `skill` Tool)

Agents interact with skills through the built-in `skill` tool:

1. **Discovery**: At startup, OpenCode scans all skill directories and builds an index of `name` + `description` pairs
2. **Selection**: When an agent decides it needs a skill, it calls `skill({ name: "git-release" })`
3. **Loading**: The full `SKILL.md` body is loaded into the agent's context
4. **Execution**: The agent follows the skill's instructions within its own tool/permission context

This means:
- Skills do NOT have their own tool access — they inherit the calling agent's tools and permissions
- Skills do NOT run in isolation — they execute within the agent's conversation context
- Multiple skills can be loaded in a single session

---

## 6) Permission Configuration

Control which skills agents can load via `opencode.json`:

### Global Skill Permissions

```json
{
  "permission": {
    "skill": {
      "*": "allow",
      "pr-review": "allow",
      "internal-*": "deny",
      "experimental-*": "ask"
    }
  }
}
```

| Permission | Behavior |
|------------|----------|
| `allow` | Immediate loading, no user prompt |
| `deny` | Skill hidden and rejected if requested |
| `ask` | User must approve before loading |

### Per-Agent Skill Permissions

**Custom agents** (in agent markdown frontmatter):
```yaml
---
permission:
  skill:
    "documents-*": "allow"
    "deploy-*": "deny"
---
```

**Built-in agents** (in `opencode.json`):
```json
{
  "agent": {
    "plan": {
      "permission": {
        "skill": {
          "internal-*": "allow"
        }
      }
    }
  }
}
```

### Disabling Skills Entirely

For agents that should never use skills:

```yaml
---
tools:
  skill: false
---
```

Or in `opencode.json`:
```json
{
  "agent": {
    "plan": {
      "tools": {
        "skill": false
      }
    }
  }
}
```

---

## 7) Skill Design Patterns

### Pattern 1: Multi-Step Workflow

Best for: complex processes with multiple phases (feature creation, deployment).

```markdown
## Step 1: Gather Context
Read existing state, validate preconditions.

## Step 2: Generate Artifacts
Create files following templates.

## Step 3: Validate
Run checks, verify output.

## Step 4: Report
Summarize what was done, suggest next steps.
```

### Pattern 2: Analysis → Decision → Action

Best for: code review, migration planning, incident triage.

```markdown
## Phase 1: Analyze
[Read and understand the current state]

## Phase 2: Decide
[Based on analysis, determine the approach]

## Phase 3: Execute
[Carry out the decided action]

## Phase 4: Verify
[Confirm the action succeeded]
```

### Pattern 3: Template-Driven Generation

Best for: creating standardized artifacts (design docs, prompts, reports).

```markdown
## Step 1: Determine Parameters
Read tracking file, get next ID, gather user input.

## Step 2: Fill Template
Use the template from references/, substituting parameters.

## Step 3: Write Files
Create all required files in the correct locations.

## Step 4: Register
Update tracking/registry files.
```

### Pattern 4: Interactive Q&A

Best for: requirements gathering, when user input shapes the output.

```markdown
## Step 1: Initial Assessment
Based on the user's request, determine what information is missing.

## Step 2: Ask Clarifying Questions
Present a numbered list of questions. Wait for answers.

## Step 3: Generate Based on Answers
Use the gathered context to produce the output.
```

---

## 8) Progressive Disclosure with References

Skills use a two-level loading model to preserve context window:

| Level | When Loaded | Token Cost | Content |
|-------|-------------|------------|---------|
| **1: Metadata** | At startup | ~50 tokens | `name` + `description` only |
| **2: SKILL.md body** | When `skill` tool invoked | Variable | Full instructions + referenced files |

### Referencing Additional Files

```markdown
## Implementation Details
For template structures, see [references/design-templates.md](references/design-templates.md).
For naming conventions, see [references/naming-guide.md](references/naming-guide.md).
```

### Rule of Thumb

- **SKILL.md body**: Decision logic, step sequence, output format, constraints
- **references/**: Detailed templates, examples, lookup tables, patterns

---

## 9) Migrating Skills Between Claude Code and OpenCode

Because OpenCode discovers `.claude/skills/` paths, many Claude Code skills work without changes. Key differences to account for:

### Frontmatter Compatibility

| Claude Code Field | OpenCode Equivalent | Notes |
|-------------------|---------------------|-------|
| `name` | `name` | Same (1–64 chars, lowercase) |
| `description` | `description` | Same (1–1024 chars) |
| `allowed-tools` | N/A | Skills don't control tools in OpenCode — the calling agent does |
| `argument-hint` | N/A | Not supported; document args in the body |
| `model` | N/A | Skills don't override model — the calling agent's model is used |
| `disable-model-invocation` | Use `permission.skill` config | Control via permission globs |
| `user-invocable` | N/A | Skills are always agent-invocable; use commands for user-only triggers |
| `context: fork` | N/A | Use a subagent instead if isolation is needed |
| `agent` | N/A | Skills don't specify execution agent |

### Migration Checklist

- [ ] Verify `name` matches directory name and follows OpenCode naming regex
- [ ] Remove Claude Code-only frontmatter fields (`allowed-tools`, `model`, `context`, `agent`)
- [ ] If skill used `context: fork`, consider creating an agent instead
- [ ] If skill used `disable-model-invocation: true`, add `permission.skill` deny rule
- [ ] Replace `$ARGUMENTS` references — OpenCode skills don't receive arguments directly (use commands for that)
- [ ] Replace `!`backtick`` shell execution — OpenCode skills don't support inline bash preprocessing
- [ ] Test that the calling agent has the necessary tool access for the skill's instructions

### Key Conceptual Difference

In Claude Code, a skill can be both a user-invoked slash command AND an agent-loaded knowledge pack. In OpenCode, these are **separate mechanisms**:
- **User-triggered prompt** → Use a **command** (`.opencode/commands/`)
- **Agent-loadable knowledge** → Use a **skill** (`.opencode/skills/`)

If you need both, create both: a command that triggers the workflow and a skill with the reusable knowledge.

---

## 10) Anti-Patterns to Avoid

| Anti-Pattern | Why It's Bad | Instead |
|--------------|--------------|---------|
| **Vague description** | Agent can't decide when to load | Specific triggers with "Use when" language |
| **Monster SKILL.md** (500+ lines) | Wastes tokens, dilutes instructions | Use references/ for detailed content |
| **Embedding code snippets** | Becomes outdated, wastes context | Reference actual files via paths |
| **No output format** | Inconsistent, unpredictable results | Define exact output structure |
| **No constraints** | Scope creep, unintended changes | State what NOT to do explicitly |
| **Time-sensitive info** | Becomes outdated quickly | Use dynamic lookups (read files) |
| **Duplicating AGENTS.md rules** | Token waste, risk of contradiction | Reference AGENTS.md, don't copy |
| **Trying to control tools** | Skills don't own tools | Use agent-level tool config instead |
| **Using skill for user prompts** | Skills are agent-facing | Use commands for user-triggered prompts |

---

## 11) Quality Checklist

### Before Release

- [ ] `name` matches directory name and follows naming regex
- [ ] `description` includes WHAT and WHEN triggers (1–1024 chars)
- [ ] `SKILL.md` body under 500 lines
- [ ] References are one level deep only
- [ ] Consistent terminology throughout
- [ ] No time-sensitive information
- [ ] Output format clearly defined
- [ ] Constraints explicitly stated
- [ ] All referenced files exist

### Testing

- [ ] Verify skill appears in agent's skill listing
- [ ] Test that agent loads skill for matching task descriptions
- [ ] Verify skill instructions execute correctly within agent context
- [ ] Confirm output matches expected format
- [ ] Test with edge-case inputs

---

## 12) Example: `iw-new-feature` Skill for InnoForge

```
.opencode/skills/
└── iw-new-feature/
    └── SKILL.md
```

**SKILL.md**:
```yaml
---
name: iw-new-feature
description: Creates a new Feature design document with all implementation prompts
  following the IW development workflow. Use when starting a new feature, creating
  feature designs, or planning feature implementation.
license: MIT
compatibility: opencode
metadata:
  audience: developers
  workflow: iw-development
---

# New Feature Creator

Create a complete feature design package for the InnoForge Document Platform.

## Step 1: Reserve Feature ID
Read `ai-dev/design/Features_tracking.md` to find the next available F-number.

## Step 2: Gather Requirements
Ask the user to confirm or correct:
1. What does this feature do?
2. Which layers are involved?
3. Priority and phase
4. Key acceptance criteria

## Step 3: Create Design Document
Create `ai-dev/design/active/F{NNN}_Feature_Design.md` using the template.

## Step 4: Generate All Prompts
Create implementation, code review, final review, and quality validation prompts.

## Step 5: Register ID
Append the new ID + summary to the tracking file.

## Constraints
- NEVER implement code — this skill ONLY creates documentation
- MUST read the tracking file before creating any files
- MUST create ALL files in a single session
```

---

## 13) Troubleshooting

### Skill not discovered by agents

- Confirm file is `SKILL.md` (all caps)
- Confirm valid YAML frontmatter with both `name` and `description`
- Confirm `name` matches directory name exactly
- Check for duplicate skill names across locations
- Verify permission settings don't `deny` the skill

### Skill loads but agent ignores instructions

- Make description more specific with trigger keywords
- Ensure the calling agent has the necessary tool permissions
- Check that instructions are concrete, not just guidelines

### Skill conflicts between Claude Code and OpenCode

- Remove Claude Code-only fields from frontmatter
- Keep only `name`, `description`, and optional metadata
- Test loading in both tools if dual support is needed

---

## 14) References

### Official OpenCode Documentation
- [Agent Skills](https://opencode.ai/docs/skills/) — canonical skills reference
- [Agents](https://opencode.ai/docs/agents/) — agent configuration
- [Commands](https://opencode.ai/docs/commands/) — custom commands
- [Config](https://opencode.ai/docs/config/) — opencode.json reference
- [Rules](https://opencode.ai/docs/rules/) — AGENTS.md and instructions
- [Tools](https://opencode.ai/docs/tools/) — available tools

### Community Resources
- [Superpowers for OpenCode](https://blog.fsck.com/2025/11/24/Superpowers-for-OpenCode/) — practical skills and customization
- [Awesome OpenCode](https://github.com/awesome-opencode/awesome-opencode) — curated plugins, themes, agents
- [OpenCode Agent Skills Plugin](https://github.com/joshuadavidthomas/opencode-agent-skills) — dynamic skill discovery
- [AI Skills Collection](https://github.com/ssdeanx/AI-Skills) — cross-platform skill library

### Innovation Ways
- Agent Guide: `docs/misc/guide_to_create_opencode_agents.md`
- Command Guide: `docs/misc/guide_to_create_opencode_commands.md`
- CLAUDE.md Guide: `docs/misc/guide_to_create_claude_file.md`
- Claude Code Skills Guide: `docs/misc/guide_to_create_claude_skills.md`

---

**Document Version**: 1.0
**Author**: AI Development Team
