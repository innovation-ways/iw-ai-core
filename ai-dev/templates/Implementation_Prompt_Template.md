# {TYPE}{NNN}_S{NN}_{Agent}_prompt

**Work Item**: {ID} -- {Title}
**Step**: S{NN}
**Agent**: {Agent}

---

## Input Files

- `ai-dev/work/{ID}/{ID}_{Type}_Design.md` -- Design document
- Previous step reports (if applicable): `ai-dev/work/{ID}/reports/{ID}_S{prev}_*_report.md`

## Output Files

- `ai-dev/work/{ID}/reports/{ID}_S{NN}_{Agent}_report.md` -- Step report

## Context

You are implementing part of **{Work Item Title}**.

Read the design document first to understand the full scope and your step's deliverables. Then read `CLAUDE.md` for project-specific patterns and conventions.

## Requirements

### 1. {First deliverable}

{Detailed description of what to build, referencing design document sections.}

### 2. {Second deliverable}

{Detailed description of what to build, referencing design document sections.}

{Add more numbered deliverables as needed.}

## Project Conventions

Read the project's `CLAUDE.md` for:

- Architecture patterns and layer boundaries
- Coding conventions and naming rules
- Framework-specific patterns (ORM style, API patterns, etc.)
- Test organization and fixtures
- Build and run commands

Follow all rules defined there exactly. When in doubt, match existing code in the repository.

## TDD Requirement

Follow TDD (Red-Green-Refactor):

1. **RED**: Write failing tests first that define the expected behavior
2. **GREEN**: Write the minimal implementation to make tests pass
3. **REFACTOR**: Improve code structure while keeping all tests green

Do not skip the RED phase. Tests must exist before implementation code.

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. Run the project's unit test command (check Makefile or `CLAUDE.md` for the exact command)
2. Run lint and type checking (check Makefile or `CLAUDE.md` for the exact command)
3. Do **NOT** report `tests_passed: true` unless ALL unit tests pass with zero failures
4. If tests fail, fix them before reporting completion

## Subagent Result Contract

When your work is complete, report results in this JSON structure:

```json
{
  "step": "S{NN}",
  "agent": "{Agent}",
  "work_item": "{ID}",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "path/to/file1.py",
    "path/to/file2.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```

- `completion_status`: Use `complete` when all deliverables are done and tests pass. Use `partial` if some deliverables are done but others remain. Use `blocked` if external dependencies prevent progress.
- `blockers`: List any issues that prevented full completion. Include enough detail for the orchestrator to decide next steps.
- `notes`: Any context the next step or reviewer should know.
