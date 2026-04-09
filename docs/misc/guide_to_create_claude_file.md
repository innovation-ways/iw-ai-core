# Guide to Creating Effective CLAUDE.md Files

**Purpose**: Best practices for writing and maintaining CLAUDE.md files for Claude Code.

**Last Updated**: 2026-01-10

---

## What is CLAUDE.md?

CLAUDE.md is a special file that Claude Code automatically loads into context at the start of every conversation. It serves as persistent memory, teaching Claude essential information about your project without requiring repeated explanations.

**Key Insight**: This is the ONLY file that enters every conversation by default. Make every line count.

---

## File Locations & Hierarchy

Claude uses a hierarchical memory system, loading files from multiple locations:

| Location | Scope | Use Case |
|----------|-------|----------|
| `~/.claude/CLAUDE.md` | All projects | Personal preferences, global settings |
| `./CLAUDE.md` | Project root | Main project documentation (most common) |
| `./backend/CLAUDE.md` | Subdirectory | Subsystem-specific context (monorepos) |
| `./CLAUDE.local.md` | Local only | Personal overrides (gitignored) |

**Best Practice**: Check main CLAUDE.md into git for team sharing. Use CLAUDE.local.md for personal preferences.

---

## The Golden Rules

### 1. Keep It SHORT

**Target Lengths**:
- Ideal: **< 60 lines**
- Acceptable: **< 150 lines**
- Maximum: **< 300 lines**

**Why**: LLMs reliably follow ~150-200 instructions. Claude Code's system prompt already contains ~50 instructions. More content = lower instruction-following quality.

### 2. Universal Content Only

Since CLAUDE.md enters EVERY conversation, include only universally applicable information.

**Include**:
- Project structure and navigation
- Critical rules that always apply
- Essential commands used daily
- Non-obvious gotchas

**Exclude**:
- Task-specific instructions (use separate docs)
- Rarely-needed information
- Content that only applies to certain features

### 3. Pointers, Not Copies

**Never include code snippets** - they become outdated quickly.

```markdown
# ❌ BAD - Code that will become outdated
```python
async def get_episode(db: AsyncSession, episode_id: int):
    result = await db.execute(select(Episode).where(...))
    return result.scalar_one_or_none()
```

# ✅ GOOD - Reference to actual code
- **Async DB pattern**: See `app/services/episode_service.py:45`
```

### 4. Let Linters Handle Style

**Never include code style guidelines**. LLMs are expensive and slow compared to linters.

```markdown
# ❌ BAD
- Use snake_case for Python functions
- Use 4 spaces for indentation
- Maximum line length: 88 characters

# ✅ GOOD
- **Linting**: Run `ruff check` before commits (config in `pyproject.toml`)
```

### 5. Avoid Statistics That Change

Remove counts, percentages, and metrics that become stale.

```markdown
# ❌ BAD - Will become outdated
├── services/            # Business logic (79 services)
├── models/              # SQLAlchemy ORM (34 models)

# ✅ GOOD - Stable description
├── services/            # Business logic layer
├── models/              # SQLAlchemy ORM models
```

### 6. Use Emphasis for Critical Rules

Add "MUST", "NEVER", "CRITICAL" for rules that require strict adherence.

```markdown
## Critical Rules
- **MUST** use async/await for all database operations
- **NEVER** hardcode LLM prompts (use `prompt_templates` table)
- **CRITICAL**: Update `docs/db_datamodel.md` with every migration
```

---

## The WHAT-WHY-HOW Framework

Structure content around three dimensions:

### WHAT - The Map
Tell Claude about your tech stack and project structure.

```markdown
## Project Structure
- Backend: FastAPI + SQLAlchemy (async)
- Frontend: Next.js 16 + React 19
- Database: PostgreSQL 16+
```

### WHY - The Purpose
Explain what components do and why they exist.

```markdown
## Architecture
- Services layer handles all business logic
- Routes are thin - validation and delegation only
- TTS runs on separate GPU server (cost optimization)
```

### HOW - The Execution
Provide practical commands and workflows.

```markdown
## Commands
docker compose up backend    # Run backend
alembic upgrade head         # Apply migrations
pytest tests/unit/ -v        # Run tests
```

---

## Recommended Structure

### Minimal Template (~60 lines)

```markdown
# [Project] CLAUDE.md

[One-line project description]

## Quick Navigation
| Task | Location |
|------|----------|
| [Common task 1] | `path/to/location` |
| [Common task 2] | `path/to/location` |

## Critical Rules
- **MUST**: [Essential rule 1]
- **MUST**: [Essential rule 2]
- **NEVER**: [Anti-pattern to avoid]

## Commands
```bash
[command 1]    # Description
[command 2]    # Description
```

## Key Files
| File | Purpose |
|------|---------|
| `path/file.py` | [What it does] |

## Gotchas
- [Non-obvious issue 1]
- [Non-obvious issue 2]

## More Info
- **[Topic]**: `docs/relevant-doc.md`
```

### Standard Template (~100-150 lines)

```markdown
# [Project] CLAUDE.md

[One-line project description]

## Quick Navigation
| Task | Location |
|------|----------|
[8-10 common tasks]

## Directory Structure
```
project/
├── src/           # Source code
├── tests/         # Test suite
└── docs/          # Documentation
```

## Critical Rules
- **MUST**: [Rule with emphasis]
- **NEVER**: [Anti-pattern]

## Commands
```bash
[8-10 essential commands]
```

## Key Files
| File | Purpose |
|------|---------|
[5-8 critical files]

## Patterns
- **[Pattern name]**: See `file:line`
- **[Pattern name]**: See `file:line`

## Gotchas
- [3-5 non-obvious issues]

## Documentation
| Topic | Location |
|-------|----------|
| Architecture | `docs/architecture.md` |
| API Design | `docs/api-design.md` |
```

---

## Progressive Disclosure

For complex projects, use progressive disclosure instead of cramming everything into CLAUDE.md.

### Strategy

1. **Root CLAUDE.md**: Universal navigation and critical rules only
2. **Subdirectory CLAUDE.md**: Subsystem-specific context
3. **Separate markdown files**: Task-specific instructions

### Example Structure

```
project/
├── CLAUDE.md                 # Project overview, navigation, critical rules
├── backend/
│   └── CLAUDE.md             # Backend-specific patterns and commands
├── frontend/
│   └── CLAUDE.md             # Frontend-specific patterns and commands
└── docs/
    ├── adding-api-endpoint.md    # Detailed guide
    ├── database-migrations.md    # Detailed guide
    └── testing-strategy.md       # Detailed guide
```

### Reference in CLAUDE.md

```markdown
## Detailed Guides
- **New API endpoint**: See `docs/adding-api-endpoint.md`
- **Database changes**: See `docs/database-migrations.md`
- **Testing**: See `docs/testing-strategy.md`
```

---

## Anti-Patterns to Avoid

### 1. Kitchen Sink Approach
❌ Including every possible command, pattern, and guideline
✅ Include only universally applicable, frequently needed content

### 2. Outdated Code Snippets
❌ Embedding code examples that drift from actual implementation
✅ Use file:line references to authoritative source

### 3. Duplicate Information
❌ Repeating what's in README, docs, or config files
✅ Point to existing documentation

### 4. Feature Lists
❌ Listing implemented features (F001, F002, etc.)
✅ Keep feature tracking in project management tools

### 5. Verbose Explanations
❌ Paragraph-style explanations of each component
✅ Terse bullet points with references

### 6. Unstable Metrics
❌ "213 components", "79 services", "85% complete"
✅ Descriptions that remain true as project evolves

---

## Maintenance Best Practices

### 1. Treat as Living Document
Review and update CLAUDE.md when:
- Major architectural changes occur
- New critical patterns are established
- Team discovers new gotchas
- Instructions aren't being followed

### 2. Use # Key During Sessions
Press `#` during Claude Code sessions to add new instructions. Claude will incorporate them into the relevant CLAUDE.md file.

### 3. Test Instruction Adherence
If Claude isn't following a rule:
1. Add emphasis ("MUST", "NEVER", "CRITICAL")
2. Move rule higher in the file (LLMs bias toward peripheries)
3. Simplify the instruction
4. Remove conflicting or redundant instructions

### 4. Version Control
- Commit CLAUDE.md changes with descriptive messages
- Review CLAUDE.md changes in PRs
- Document rationale for rule changes

### 5. Team Alignment
- Discuss CLAUDE.md changes in team meetings
- Ensure all team members understand critical rules
- Collect feedback on instruction effectiveness

---

## Checklist for New CLAUDE.md

- [ ] Under 150 lines (ideally under 60)
- [ ] No code snippets (use file:line references)
- [ ] No statistics that will change
- [ ] No code style rules (use linters)
- [ ] Critical rules have emphasis (MUST/NEVER)
- [ ] Quick navigation table included
- [ ] Essential commands documented
- [ ] Key files identified
- [ ] Gotchas listed
- [ ] References to detailed docs

---

## Checklist for CLAUDE.md Review

- [ ] Is every line universally applicable?
- [ ] Can any sections be moved to separate docs?
- [ ] Are code snippets replaced with references?
- [ ] Are statistics current? (If not, remove them)
- [ ] Are critical rules being followed? (If not, add emphasis)
- [ ] Is the file under 150 lines?

---

## Resources

- [Claude Code: Best practices for agentic coding](https://www.anthropic.com/engineering/claude-code-best-practices) - Anthropic official
- [Writing a good CLAUDE.md](https://www.humanlayer.dev/blog/writing-a-good-claude-md) - HumanLayer
- [5 Best Practices for CLAUDE.md](https://apidog.com/blog/claude-md/) - Apidog
- [Using CLAUDE.MD files](https://claude.com/blog/using-claude-md-files) - Claude blog

---

**Document Version**: 1.0
**Author**: AI Development Team
