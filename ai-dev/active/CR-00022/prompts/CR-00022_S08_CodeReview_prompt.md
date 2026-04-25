# CR-00022_S08_CodeReview_prompt

**Work Item**: CR-00022
**Step Being Reviewed**: S07 (Phase C — fix CLI + recipes)
**Review Step**: S08
**Agent**: code-review-impl

---

## ⛔ Docker / Migrations off-limits

Standard rules.

## Input Files

- Design + S07 report
- `orch/oss/fix_recipes/**/*.py`
- `orch/cli/oss_commands.py`
- `dashboard/services/oss_service.py` (`_run_fix`, `run_fixes`)

## Output Files

- `ai-dev/active/CR-00022/reports/CR-00022_S08_CodeReview_report.md`

## Review Checklist

### 1. Working-tree-only invariant — CRITICAL

This is the core safety property of CR-00022. Verify in all changed files:
- **No** `git checkout`, `git switch`, `git branch`, `git worktree`, `git commit`, `git reset` calls.
- **No** `subprocess.run(["git", ...])` invocations modifying repo state from recipes (only ALLOWED: `git rev-parse`, `git status` for read-only checks if needed — but recipes shouldn't need these).
- **No** writes outside `repo_root` (e.g., to `/tmp/oss-*`).
- **No** symbolic-link creation that points outside `repo_root`.
- `_run_fix`'s subprocess uses `cwd=project.repo_root` (NOT a worktree path).

Grep:
```bash
grep -rn "git " orch/oss/fix_recipes/ dashboard/services/oss_service.py
grep -rn "worktree\|/tmp/oss\|prep-" orch/oss/fix_recipes/ dashboard/services/oss_service.py
```

Any violation is CRITICAL.

### 2. Idempotency — CRITICAL

For every recipe, mentally trace `apply()` called twice. Confirm:
- Template-render recipes overwrite with deterministic content.
- Patch-style recipes detect existing pattern and skip (no duplicate lines, no growing file).
- No recipe appends timestamps, UUIDs, or otherwise non-deterministic content.
- `preview()` does not invoke `apply()` internally and does not write.

Run yourself:
```bash
for cid in OSS-CH-01 OSS-LIC-01 OSS-CH-02; do
  uv run iw oss fix $cid --project iw-ai-core --apply
  uv run iw oss fix $cid --project iw-ai-core --apply
  git status --short  # should be unchanged after second apply
done
```

### 3. Recipe-vs-flag consistency — HIGH

Every check whose `Finding(...)` declares `auto_apply_safe=True` (per S05) MUST have a registered recipe; every recipe MUST be flagged `auto_apply_safe=True`. Use:

```python
import ast, pathlib
import importlib
import orch.oss.fix_recipes  # triggers registration
from orch.oss.fix_recipes.base import _REGISTRY

# Collect Finding constructors with auto_apply_safe=True
ast_safe = set()
for p in pathlib.Path("skills/iw-oss-publish/scripts/checks").glob("*.py"):
    tree = ast.parse(p.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "Finding":
            kwargs = {kw.arg: kw.value for kw in node.keywords if kw.arg}
            id_v = kwargs.get("id")
            safe_v = kwargs.get("auto_apply_safe")
            if (isinstance(id_v, ast.Constant) and isinstance(safe_v, ast.Constant)
                    and safe_v.value is True):
                ast_safe.add(id_v.value)

print("declared safe:", sorted(ast_safe))
print("registered recipes:", sorted(_REGISTRY))
print("declared but no recipe:", ast_safe - _REGISTRY.keys())
print("recipe but not declared safe:", _REGISTRY.keys() - ast_safe)
```

Both diff sets should be empty.

### 4. CLI shape — MEDIUM

- `iw oss fix <CHECK_ID> --project <id>` runs preview and exits 0?
- `--apply` writes and exits 0?
- `--apply` exits non-zero on recipe error?
- `--json` produces parseable JSON?
- Unknown check_id exits with helpful message?

### 5. Dashboard subprocess — HIGH

- `_run_fix` invocation `cwd=project.repo_root` (NOT `worktree_path`)?
- Subprocess output captured to `stdout_tail` exactly like scan?
- Job status transitions match scan (running → complete | error)?
- No stale references to `WORKTREE_KINDS` or `_run_worktree`?

### 6. Conventions

- Pure Python file I/O (no `os.system`)?
- `pathlib.Path` everywhere, no `os.path.join`?
- Recipes are class-based with the Protocol; no global functions registering on import side-effects beyond `register(...)`?
- Recipe modules import `register` from `.base` and call at module bottom (consistent style)?

## Output Report

Findings list with severity and file:line. End with verdict + `iw step-done` / `iw step-fail`.
