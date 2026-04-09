# Guide to Creating Effective Claude Code Skills

**Purpose**: Best practices for designing, structuring, and maintaining Claude Code skills and custom commands.
**Audience**: Developers and AI workflow designers using Claude Code.
**Last Updated**: 2026-03-10

---

## What Are Skills?

Skills are modular, markdown-based capability packages that extend Claude Code's functionality. They sit between CLAUDE.md (always loaded) and ad-hoc prompts (one-off), providing **on-demand expertise** that loads only when needed.

Skills can be:
- **User-invoked** via slash commands (e.g., `/iw-new-feature`)
- **Auto-triggered** by Claude when it detects a matching context
- **Both** — invocable by the user AND auto-detected by Claude

### Skills vs. Commands vs. CLAUDE.md

| Mechanism | Loaded When | Token Cost | Best For |
|-----------|-------------|------------|----------|
| **CLAUDE.md** | Always (every conversation) | Permanent | Universal rules, project structure, critical conventions |
| **Skills** (`.claude/skills/`) | On trigger or slash command | On demand | Specialized workflows, multi-step processes, domain expertise |
| **Commands** (`.claude/commands/`) | On slash command only | On demand | Simple user-initiated actions (legacy format, still works) |

**Key difference**: Skills add auto-invocation via descriptions, support reference directories, and can be loaded by Claude proactively. Commands are always user-initiated.

> **Modern recommendation**: Use skills (`.claude/skills/`) for all new work. Existing `.claude/commands/` files continue to work and create the same `/slash-command` interface.

---

## Skill File Structure

### Minimum Viable Skill

```
.claude/skills/
└── my-skill/
    └── SKILL.md          # Required: YAML frontmatter + instructions
```

### Full Skill Structure

```
.claude/skills/
└── my-skill/
    ├── SKILL.md          # Entry point (required)
    ├── references/       # Detailed docs loaded on demand (optional)
    │   ├── patterns.md
    │   └── examples.md
    ├── scripts/          # Executable code (optional)
    │   └── validate.py
    └── assets/           # Templates, images (optional)
        └── template.html
```

### Storage Locations

| Location | Scope | Use For |
|----------|-------|---------|
| `~/.claude/skills/` | Global (all projects) | Personal skills, general-purpose tools |
| `.claude/skills/` | Project-specific | Team workflows, project conventions |
| `iw-development-fw/skills/` | Framework library | Reusable agent skills across projects |

---

## SKILL.md Anatomy

Every skill has two parts: **YAML frontmatter** and a **markdown body**.

### YAML Frontmatter (Required)

```yaml
---
name: my-skill-name
description: What the skill does AND when to use it. Be specific about triggers.
---
```

| Field | Required | Rules |
|-------|----------|-------|
| `name` | Yes | Max 64 chars, lowercase, hyphens allowed, no "anthropic" or "claude" |
| `description` | Yes | Max 1024 chars, non-empty. Include both WHAT and WHEN |

### Optional Frontmatter Fields (for commands-style usage)

When creating skills that serve as slash commands, you can use these additional frontmatter fields inherited from the commands format:

```yaml
---
name: my-command
description: What it does. Use when [triggers].
allowed-tools: Read, Grep, Glob, Edit, Write, Bash(git:*), Bash(make:*)
argument-hint: <feature-name> [brief description]
model: claude-sonnet-4-6
---
```

| Field | Purpose | Example |
|-------|---------|---------|
| `allowed-tools` | Restrict which tools the skill can use | `Read, Grep, Glob, Edit, Write` |
| `argument-hint` | Hint shown in autocomplete for expected arguments | `<issue-number>` |
| `model` | Override the model for this skill | `claude-sonnet-4-6` |
| `disable-model-invocation` | `true` prevents Claude from auto-invoking (user only) | Side-effect skills: deploy, commit |
| `user-invocable` | `false` hides from `/` menu (Claude-only background knowledge) | Legacy system context, reference data |
| `context` | Set to `fork` to run in an isolated subagent context | Research, analysis tasks |
| `agent` | Subagent type when `context: fork` | `Explore`, `Plan`, `general-purpose` |

### Invocation Control Matrix

| Setting | User can invoke | Claude can invoke | Use Case |
|---------|-----------------|-------------------|----------|
| (defaults) | Yes | Yes | Most skills |
| `disable-model-invocation: true` | Yes | No | Side-effect skills (deploy, commit, send) |
| `user-invocable: false` | No | Yes | Background knowledge Claude should auto-load |
| Both set | No | No | Temporarily disabled skills |

**CRITICAL**: Always use `disable-model-invocation: true` for skills with side effects (deployment, sending messages, destructive operations). You don't want Claude deciding to deploy because your code "looks ready."

### Arguments and Dynamic Content

Skills receive user arguments via `$ARGUMENTS` (all args) or positional `$1`, `$2`, etc.:

```markdown
Create a design document for: **$ARGUMENTS**
```

Available variables:

| Variable | Description |
|----------|-------------|
| `$ARGUMENTS` | All arguments passed after the skill name |
| `$0`, `$1`, `$2` | Positional arguments (0-indexed) |
| `${CLAUDE_SESSION_ID}` | Current session ID (for logging, session-specific files) |
| `${CLAUDE_SKILL_DIR}` | Absolute path to the skill's directory (for referencing bundled scripts) |

Inline bash execution (when `Bash` is in `allowed-tools`) — preprocessed before Claude sees the content:

```markdown
Current branch: !`git branch --show-current`
```

### Markdown Body (Required)

The instruction body that Claude follows when the skill activates. Guidelines:

- **Keep under 500 lines** — longer skills should use `references/` files
- **Be specific** — Claude is smart, but explicit steps prevent drift
- **Use numbered steps** — sequential workflows are easier to follow
- **Include output format** — define what the skill should produce
- **State constraints** — what NOT to do is as important as what TO do

---

## Writing Effective Descriptions

The description is the **most critical field** — it determines when Claude activates the skill (auto-trigger) and what the user sees in `/help`.

### Good Description Pattern

```
[What it does in one sentence]. Use when [specific triggers, keywords, contexts].
```

### Examples

**Good** (specific triggers, clear scope):
```yaml
description: Creates a new Feature design document with all implementation prompts
  following the IW development workflow. Use when starting a new feature, asked to
  create a feature design, or when user says "new feature", "create feature",
  "design feature", "/iw-new-feature".
```

**Bad** (vague, no triggers):
```yaml
description: Helps with features.
```

### Trigger Word Strategy

Include in your description:
1. The **action verb** (create, review, analyze, generate)
2. The **domain nouns** (feature, incident, migration, deployment)
3. Common **synonyms** users might say ("bug" for incident, "CR" for change request)
4. The **slash command name** for explicit invocation

---

## Progressive Disclosure

Skills use three loading levels to preserve context window:

| Level | When Loaded | Token Cost | Content |
|-------|-------------|------------|---------|
| **1: Metadata** | Always (startup) | ~100 tokens | `name` + `description` only |
| **2: SKILL.md body** | When triggered | < 5k tokens | Full instructions |
| **3: References** | As needed | Unlimited | Scripts, detailed docs, assets |

### Referencing Additional Files

```markdown
## Implementation Details
For template structures, see [references/design-templates.md](references/design-templates.md).
For naming conventions, see [references/naming-guide.md](references/naming-guide.md).
```

Claude reads referenced files only when the task requires them — keeping the initial load small.

### Rule of Thumb

- **SKILL.md body**: Decision logic, step sequence, output format, constraints
- **references/**: Detailed templates, examples, lookup tables, patterns
- **scripts/**: Deterministic operations Claude should execute, not load into context
- **assets/**: Output templates, images, boilerplate files

---

## Degrees of Freedom

Match instruction specificity to how fragile the task is:

### High Freedom (Multiple valid approaches)

```markdown
## Analyze the Codebase
1. Identify relevant files and patterns
2. Assess impact and dependencies
3. Summarize findings
```

Use for: research, analysis, exploration tasks.

### Medium Freedom (Preferred pattern with flexibility)

```markdown
## Generate Report
Use this structure, customize sections as needed:
- Executive summary (2-3 sentences)
- Findings with severity ratings
- Recommended actions
```

Use for: documentation, reviews, reports.

### Low Freedom (Critical, fragile operations)

```markdown
## Create Migration
Run EXACTLY this command:
```bash
alembic revision --autogenerate -m "$ARGUMENTS"
```
Do NOT modify flags. Do NOT skip the downgrade function.
```

Use for: database operations, deployments, ID generation, file naming.

---

## Skill Design Patterns

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
Based on $ARGUMENTS, determine what information is missing.

## Step 2: Ask Clarifying Questions
Present a numbered list of questions. Wait for answers.

## Step 3: Generate Based on Answers
Use the gathered context to produce the output.
```

---

## Subagent Execution

Skills can run in an isolated subagent context using `context: fork`. The skill content becomes the prompt for the subagent, which has no access to your conversation history.

```yaml
---
name: research-topic
description: Research a topic thoroughly across the codebase
context: fork
agent: Explore
---

Research $ARGUMENTS thoroughly:
1. Use Grep/Glob to find all relevant files
2. Read and analyze the code
3. Return a structured summary with file references
```

Built-in agent types: `Explore` (read-only codebase search), `Plan` (planning-focused), `general-purpose` (default).

**Warning**: `context: fork` only works for skills with concrete task instructions. A skill containing only guidelines (no actionable prompt) will return without meaningful output from the subagent.

---

## Context Budget and Limits

- Skill `name`: max 64 characters
- Skill `description`: max 1024 characters
- SKILL.md body: keep under 500 lines for optimal performance
- Total skills metadata budget: ~2% of context window (~16,000 chars fallback)
- If many skills are installed, descriptions may exceed the budget — check with `/context` for warnings
- Override limit with `SLASH_COMMAND_TOOL_CHAR_BUDGET` environment variable

---

## Anti-Patterns to Avoid

| Anti-Pattern | Why It's Bad | Instead |
|--------------|--------------|---------|
| **Vague description** | Claude can't decide when to trigger (~20% activation) | Specific triggers with "Use when" language (~72%+ activation) |
| **Monster SKILL.md** (500+ lines) | Wastes tokens, dilutes instructions | Use references/ for detailed content |
| **Embedding code snippets** | Becomes outdated, wastes context | Reference actual files via paths |
| **No output format** | Inconsistent, unpredictable results | Define exact output structure |
| **No constraints** | Scope creep, unintended changes | State what NOT to do explicitly |
| **Deeply nested references** | Claude may `head -100` instead of full read | Keep one level deep from SKILL.md |
| **Time-sensitive info** | Becomes outdated quickly | Use dynamic lookups (read files, run commands) |
| **Multiple options without default** | Decision paralysis | Provide recommended default |
| **Duplicating CLAUDE.md rules** | Token waste, risk of contradiction | Reference CLAUDE.md, don't copy |
| **Side-effect skills without gating** | Claude may auto-invoke deploy/commit | Use `disable-model-invocation: true` |
| **First/second person descriptions** | POV mismatch in system prompt | Write in third person: "Processes X" |
| **`context: fork` on guideline-only skills** | Subagent gets guidelines but no task | Only fork skills with concrete tasks |

---

## Quality Checklist

### Before Release

- [ ] Description includes WHAT and WHEN triggers
- [ ] SKILL.md body under 500 lines
- [ ] References are one level deep only
- [ ] Consistent terminology throughout
- [ ] No time-sensitive information (dates, counts, versions)
- [ ] Output format clearly defined
- [ ] Constraints explicitly stated
- [ ] Forward slashes in all paths (`/` not `\`)
- [ ] All referenced files exist

### Testing

- [ ] Invoke via slash command — verify it triggers
- [ ] Test with typical arguments
- [ ] Test with no arguments (graceful handling)
- [ ] Test with edge-case arguments
- [ ] Verify progressive disclosure works (references load when needed)
- [ ] Confirm output matches expected format

---

## Skill Creation Process

### Step 1: Identify the Need

What does Claude struggle with or need repeated guidance for?
- Recurring multi-step workflows
- Tasks requiring specific file naming or structure
- Processes with mandatory steps that shouldn't be skipped
- Domain-specific knowledge not in CLAUDE.md

### Step 2: Define Scope and Triggers

- What exactly should this skill do?
- What should it NOT do?
- What keywords or contexts should trigger it?
- Should it be user-invoked, auto-triggered, or both?

### Step 3: Write Minimal SKILL.md

Start with:
1. Frontmatter with name and description
2. High-level step sequence
3. Output format
4. Key constraints

### Step 4: Test with Real Tasks

Run the skill on actual work items. Observe:
- Does it follow the steps correctly?
- Is the output format consistent?
- Does it stay in scope?
- Are there missing steps or ambiguities?

### Step 5: Add References (if needed)

Only add references/ when SKILL.md alone isn't sufficient:
- Templates too large for SKILL.md body
- Lookup tables or detailed patterns
- Examples that would bloat the main instructions

### Step 6: Iterate and Refine

Based on real usage:
- Tighten vague instructions
- Add constraints for observed scope creep
- Simplify over-specified steps
- Update description triggers based on how users actually invoke it

---

## Example: Complete Workflow Skill

```
.claude/skills/
└── iw-new-feature/
    ├── SKILL.md              # Main instructions
    └── references/
        └── workflow-steps.md  # Detailed prompt generation rules
```

**SKILL.md**:
```yaml
---
name: iw-new-feature
description: Creates a new Feature design document with all implementation prompts
  following the IW development workflow. Use when starting a new feature, creating
  feature designs, or user says "new feature".
allowed-tools: Read, Grep, Glob, Edit, Write
argument-hint: <brief feature description>
---

# New Feature Creator

Create a complete feature design package for: **$ARGUMENTS**

## Step 1: Reserve Feature ID
Read `ai-dev/design/Features_tracking.md` to find the next available F-number.

## Step 2: Gather Requirements
[Ask clarifying questions if $ARGUMENTS is insufficient]

## Step 3: Create Design Document
Create `ai-dev/design/active/F{NNN}_Feature_Design.md` using the template.

## Step 4: Generate All Prompts
Create implementation, code review, final review, and quality validation prompts.

## Step 5: Register ID
Append the new ID + summary to the tracking file.

## Step 6: Present Package
List all created files for human review and approval.
```

---

## References

### Official Anthropic Documentation
- [Claude Code Slash Commands](https://code.claude.com/docs/en/slash-commands) — canonical merged reference
- [Agent Skills Overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview) — architecture, three-level loading
- [Agent Skills Best Practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) — authoring guidance
- [Official Skills Repository](https://github.com/anthropics/skills) — reference implementations (pdf, pptx, docx, skill-creator)
- [Claude Code Best Practices](https://www.anthropic.com/engineering/claude-code-best-practices)

### Community Resources
- [Claude Code Customization Guide](https://alexop.dev/posts/claude-code-customization-guide-claudemd-skills-subagents/) — skills, subagents, CLAUDE.md comparison
- [Inside Claude Code Skills](https://mikhail.io/2025/10/claude-code-skills/) — internal mechanics deep dive
- [Claude Agent Skills: A First Principles Deep Dive](https://leehanchung.github.io/blogs/2025/10/26/claude-skills-deep-dive/) — activation rate analysis
- [Awesome Claude Code](https://github.com/hesreallyhim/awesome-claude-code) — curated skills, hooks, and commands
- [Production-Ready Slash Commands](https://github.com/wshobson/commands) — community command collection
- [Claude Code CLI Cheatsheet](https://shipyard.build/blog/claude-code-cheat-sheet/)

### Innovation Ways
- Skill Guide (framework): `iw-development-fw/skills/40-GUIDE_TO_CREATE_CLAUDE_SKILLS.md`
- Agent Catalog: `iw-development-fw/ai-development/21-AGENT_CATALOG.md`
- Prompt Templates: `iw-development-fw/ai-development/23-AGENT_PROMPT_TEMPLATES.md`
- CLAUDE.md Guide: `docs/misc/guide_to_create_claude_file.md`

---

**Document Version**: 1.0
**Author**: AI Development Team
