---
description: Commit documentation changes (design docs, reports, notes) without running the full code quality pipeline.
---

# Ship Docs

Commit documentation changes without running the full code quality pipeline.

## Workflow

1. **Check git status** to see what documentation files have changed:
   ```bash
   git status
   ```

2. **Review changes** — read the changed files to ensure they are documentation only (no code changes mixed in).

3. **Stage documentation files**:
   ```bash
   git add ai-dev/ docs/ *.md
   ```
   Only stage documentation files. If code files are also changed, warn the user and suggest using `/ship-code` instead.

4. **Commit**:
   ```bash
   git commit -m "docs: descriptive message about what documentation changed"
   ```

5. **Report** to the user:
   - Files committed
   - Commit hash

## Safety

- Do NOT push to remote — only commit locally
- Do NOT stage code files — only documentation
- Warn the user if code files are mixed in with documentation changes
