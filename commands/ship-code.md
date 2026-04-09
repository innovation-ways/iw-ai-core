---
description: Run the full quality pipeline (tests, lint, format, typecheck), fix any issues, and commit code changes.
---

# Ship Code

Run the full quality pipeline, fix issues, and commit.

## Workflow

1. **Read CLAUDE.md** to understand the project's quality tools and commands.

2. **Read the Makefile** to identify quality targets.

3. **Run formatting**:
   - Run the formatter (e.g., `make format` or equivalent)
   - Fix any formatting issues automatically

4. **Run linting**:
   - Run the linter (e.g., `make lint` or equivalent)
   - Fix any lint issues that can be auto-fixed
   - For issues requiring manual fixes, fix them following project conventions

5. **Run type checking**:
   - Run the type checker (e.g., `make typecheck` or equivalent)
   - Fix any type errors

6. **Run tests**:
   - Run unit tests (e.g., `make test-unit`)
   - Run integration tests if available (e.g., `make test-integration`)
   - Fix any test failures

7. **Iterate** until all checks pass with zero errors.

8. **Stage and commit**:
   ```bash
   git add -A
   git status
   git commit -m "descriptive commit message"
   ```

9. **Report** to the user:
   - All quality check results
   - Files changed
   - Commit hash

## Safety

- Do NOT push to remote — only commit locally
- Do NOT skip any quality checks
- Fix all issues before committing — never commit code with known failures
