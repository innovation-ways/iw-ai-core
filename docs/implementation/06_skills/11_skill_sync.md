# Step 11: Skill Sync & Project Initialization

## Context

Implement the skill distribution engine and the project onboarding command.

Read these documents:
- `IW_AI_Core_Architecture.md` — section 5 (Skills Distribution Model)
- `IW_AI_Core_CLI_Spec.md` — section 3.6 (sync-skills, init-project)

## Task

### 1. Skill Sync Engine (`orch/skills/sync.py`)

#### `sync_skills(project_path, skills_dir, check_only=False, force_skill=None)`

1. Read `.iw-skills-lock.json` from the project (create if missing)
2. Scan `skills_dir` (iw-ai-core/skills/) for all master skills
3. For each master skill:
   - Read version from `SKILL.md` frontmatter (YAML `version:` line)
   - Check if project has an override (same skill name in project's `.claude/skills/`)
   - If override exists and not force → skip, mark as overridden in lock
   - If no override and version outdated → copy from master to project
   - If `check_only`: report what would change, don't modify files
   - If `force_skill`: overwrite that specific skill even if project has override
4. Update `.iw-skills-lock.json` with current state

#### Lock file format (`.iw-skills-lock.json`):
```json
{
  "synced_at": "2026-04-07T10:30:00Z",
  "platform_version": "1.0.0",
  "skills": {
    "iw-new-incident": {"version": "2.1.0", "source": "platform", "overridden": false},
    "innoforge-testing": {"version": "1.0.0", "source": "project", "overridden": true}
  }
}
```

### 2. Project Initialization (`orch/skills/init_project.py`)

#### `init_project(project_id, repo_path, display_name, db)`

1. Create `.iw-orch.json` in the repo root with default config
2. Add entry to `projects.toml` in iw-ai-core (append, don't overwrite)
3. Register project in DB: INSERT into `projects`
4. Create ID sequences: INSERT F, I, CR, BATCH starting at 1
5. Create migration lock row (unlocked)
6. Create `ai-dev/design/active/` directory
7. Create `ai-dev/workflow.md` from default template (copy from `iw-ai-core/templates/default_workflow.md`)
8. Sync base skills to `.claude/skills/`
9. Return summary of what was created

### 3. Default Workflow Template

Create `templates/default_workflow.md` — a generic workflow definition that new projects start with:
```markdown
# Workflow Definition

## Steps
1. Implementation (agent: per step_type)
2. Code Review (agent: code-review-impl)
3. Code Review Fix (agent: code-review-fix-impl, conditional: review finds issues)
4. Code Review Final (agent: code-review-final-impl)
5. Code Review Fix Final (agent: code-review-fix-final-impl, conditional)
6. Quality Validation: lint (script)
7. Quality Validation: format (script)
8. Quality Validation: typecheck (script)
9. Quality Validation: tests (script)
10. Browser Verification (agent: quality-validation-impl, conditional: browser_verification=true)

## Timeouts
(use platform defaults)

## Fix Cycles
max_fix_cycles: 5
```

### 4. Wire Into CLI

Ensure `iw sync-skills` and `iw init-project` call the implementations above.

### 5. Tests (TDD)

**Unit tests** (`tests/unit/test_skill_sync.py`):
- Test: new skill not in project → copied
- Test: outdated skill → updated
- Test: up-to-date skill → skipped
- Test: project override → skipped (not overwritten)
- Test: force flag on override → overwritten
- Test: check_only mode → no files modified, report generated
- Test: lock file created on first sync
- Test: lock file updated on subsequent sync
- Test: version parsing from SKILL.md frontmatter

**Unit tests** (`tests/unit/test_init_project.py`):
- Test: creates .iw-orch.json with correct structure
- Test: creates ai-dev directories
- Test: creates workflow.md from template

**Integration tests** (`tests/integration/test_init_project.py`):
- Test: full init creates DB records (project, id_sequences, migration_lock)
- Test: `iw projects list` shows newly initialized project
- Test: `iw next-id` works for the new project (starts at 1)

## Acceptance Criteria

- [ ] `iw init-project --id test-proj --path /tmp/test --name "Test"` creates everything
- [ ] `iw sync-skills --project test-proj` copies skills, creates lock file
- [ ] `iw sync-skills --check` reports without modifying
- [ ] Project overrides are not overwritten
- [ ] `make test` passes, `make quality` passes
