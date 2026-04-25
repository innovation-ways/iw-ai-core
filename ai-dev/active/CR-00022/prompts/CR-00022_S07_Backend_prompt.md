# CR-00022_S07_Backend_prompt

**Work Item**: CR-00022
**Step**: S07
**Agent**: backend-impl (Phase C — fix CLI + recipe registry)

---

## ⛔ Docker / Migrations off-limits

Standard rules.

## Input Files

- Design + reports from S03, S05
- `orch/cli/oss_commands.py` (post-S03)
- `dashboard/services/oss_service.py` (post-S03 — has `_run_fix` placeholder)
- `skills/iw-oss-publish/templates/*` — template files for community-health renders
- `skills/iw-oss-publish/scripts/checks/*.py` — to know which check IDs need recipes

## Output Files

- New: `orch/oss/fix_recipes/` package
  - `__init__.py` (registry)
  - `base.py` (Protocol + helper utilities)
  - `community.py`, `license_check.py`, `ci_cd.py`, `hygiene.py`, `secrets.py`, `governance.py`, `internal_refs.py`, etc. (one module per domain matching `skills/iw-oss-publish/scripts/checks/`)
- Modified: `orch/cli/oss_commands.py` (add `fix` subcommand)
- Modified: `dashboard/services/oss_service.py` (replace `_run_fix` placeholder with real implementation invoking the CLI subprocess)
- `ai-dev/active/CR-00022/reports/CR-00022_S07_Backend_report.md`

## Context

S05 tagged each check with `auto_apply_safe`. S07 implements the actual fixes for the `auto_apply_safe=True` checks as **idempotent recipes**. The dashboard subprocess-invokes `uv run iw oss fix <CHECK_ID> --apply` to apply one fix; without `--apply` it returns the preview (full content for new files; unified diff for modifications).

## Requirements

### 1. Recipe protocol — `orch/oss/fix_recipes/base.py`

```python
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class FixPreview:
    """Preview of what a recipe would write."""

    target_files: list[Path]
    full_contents: dict[Path, str]   # absolute path → new content (for new files)
    diffs: dict[Path, str]           # absolute path → unified diff (for modifications)
    notes: str | None = None         # operator-facing note shown in modal


class FixRecipe(Protocol):
    """Idempotent fix for one OSS check."""

    check_id: str           # canonical ID, e.g. "OSS-CH-01"
    auto_apply_safe: bool   # MUST match the value on the corresponding Finding(id=…) constructor

    def preview(self, repo_root: Path) -> FixPreview:
        """Compute what would change. MUST NOT write anything."""

    def apply(self, repo_root: Path) -> FixPreview:
        """Apply the fix to the working tree. MUST be idempotent —
        applying twice yields the same on-disk state as once."""


# Module-level registry
_REGISTRY: dict[str, FixRecipe] = {}


def register(recipe: FixRecipe) -> FixRecipe:
    if recipe.check_id in _REGISTRY:
        raise ValueError(f"Duplicate recipe for {recipe.check_id}")
    _REGISTRY[recipe.check_id] = recipe
    return recipe


def get_recipe(check_id: str) -> FixRecipe | None:
    return _REGISTRY.get(check_id)


def list_recipes() -> list[FixRecipe]:
    return list(_REGISTRY.values())
```

### 2. Recipes — one module per domain

Implement recipes for every check ID where `auto_apply_safe=True` (per S05's audit). Examples:

**`orch/oss/fix_recipes/community.py`**:
```python
from pathlib import Path
from .base import FixPreview, FixRecipe, register

README_TEMPLATE = """# {project_name}

{project_description}

## Install

…
"""


class ReadmeRecipe:
    check_id = "OSS-CH-01"
    auto_apply_safe = True

    def preview(self, repo_root: Path) -> FixPreview:
        target = repo_root / "README.md"
        content = README_TEMPLATE.format(
            project_name=repo_root.name,
            project_description="(replace this paragraph)",
        )
        return FixPreview(
            target_files=[target],
            full_contents={target: content},
            diffs={},
            notes="Generated from iw-oss-publish README template; replace placeholders.",
        )

    def apply(self, repo_root: Path) -> FixPreview:
        preview = self.preview(repo_root)
        for path, content in preview.full_contents.items():
            # Idempotent: if file already has matching content, this is a no-op write.
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        return preview


register(ReadmeRecipe())
```

For patch-style recipes (e.g., `.gitignore` line additions), check existing content for the pattern and skip if present:

```python
class GitignoreSecretsRecipe:
    check_id = "OSS-HY-04"
    auto_apply_safe = True

    REQUIRED_PATTERNS = [".env", ".env.local", "*.pem", "id_rsa*"]

    def preview(self, repo_root: Path) -> FixPreview:
        gi = repo_root / ".gitignore"
        existing = gi.read_text() if gi.exists() else ""
        existing_lines = set(existing.splitlines())
        missing = [p for p in self.REQUIRED_PATTERNS if p not in existing_lines]
        if not missing:
            return FixPreview(target_files=[], full_contents={}, diffs={}, notes="No changes needed.")
        new_content = existing.rstrip() + "\n\n# IW OSS — secrets patterns\n" + "\n".join(missing) + "\n"
        diff = unified_diff(existing, new_content, gi)
        return FixPreview(
            target_files=[gi],
            full_contents={},
            diffs={gi: diff},
            notes=f"Adding {len(missing)} pattern(s) to .gitignore.",
        )

    def apply(self, repo_root: Path) -> FixPreview:
        preview = self.preview(repo_root)
        if not preview.target_files:
            return preview
        gi = preview.target_files[0]
        # Re-read so concurrent edits between preview and apply don't clobber.
        existing = gi.read_text() if gi.exists() else ""
        existing_lines = set(existing.splitlines())
        missing = [p for p in self.REQUIRED_PATTERNS if p not in existing_lines]
        if not missing:
            return preview
        gi.write_text(existing.rstrip() + "\n\n# IW OSS — secrets patterns\n" + "\n".join(missing) + "\n")
        return preview


register(GitignoreSecretsRecipe())
```

**Idempotency contract** (every recipe MUST honor):
- `apply` called twice yields the same on-disk state as called once.
- `preview` does not write to disk.
- Patch-style recipes detect their own pattern and no-op if already present.
- Template-render recipes overwrite the target file (idempotent by construction).

### 3. Templates

Reuse Jinja2 templates from `skills/iw-oss-publish/templates/` where applicable (`LICENSE-Apache-2.0`, `SECURITY.md.j2`, `CONTRIBUTING.md.j2`, etc.). Read template variables from `.iw/oss-publish.toml` if present (project_name, license, contact_email…), else fall back to the IW defaults documented in the skill.

### 4. CLI subcommand — `orch/cli/oss_commands.py`

Add:

```python
@oss.command("fix")
@click.argument("check_id")
@click.option("--project", "project_id", required=True, help="Project ID")
@click.option("--apply", is_flag=True, help="Apply the fix (default: preview only)")
@click.option("--json", "json_output", is_flag=True, help="Machine-readable JSON output")
@click.pass_context
def fix(ctx: click.Context, check_id: str, project_id: str, apply: bool, json_output: bool) -> None:
    """Preview or apply the auto-fix for a single OSS check."""
    from orch.oss.fix_recipes import get_recipe
    from pathlib import Path
    # Resolve project repo_root from DB.
    get_session = ctx.obj["get_session"]
    with get_session() as session:
        from orch.db.models import Project
        project = session.get(Project, project_id)
        if project is None:
            click.echo(f"Project {project_id} not found", err=True)
            sys.exit(2)
    recipe = get_recipe(check_id)
    if recipe is None:
        click.echo(f"No auto-fix recipe registered for {check_id}", err=True)
        sys.exit(2)
    repo_root = Path(project.repo_root)
    if apply:
        preview = recipe.apply(repo_root)
        action = "apply"
    else:
        preview = recipe.preview(repo_root)
        action = "preview"
    if json_output:
        click.echo(json.dumps({
            "action": action,
            "check_id": check_id,
            "target_files": [str(p) for p in preview.target_files],
            "full_contents": {str(p): c for p, c in preview.full_contents.items()},
            "diffs": {str(p): d for p, d in preview.diffs.items()},
            "notes": preview.notes,
        }))
    else:
        click.echo(f"{action}: {check_id} — {len(preview.target_files)} file(s)")
        if preview.notes:
            click.echo(f"  notes: {preview.notes}")
        for p in preview.target_files:
            click.echo(f"  - {p}")
    sys.exit(0)
```

### 5. Dashboard `_run_fix` implementation

In `dashboard/services/oss_service.py`, replace the S03 placeholder with:

```python
async def _run_fix(
    project: Project,
    job_id: int,
    session_factory: Callable[[], Session],
    check_id: str,
    apply: bool,
) -> None:
    cmd = ["uv", "run", "iw", "oss", "fix", check_id, "--project", project.id]
    if apply:
        cmd.append("--apply")
    cmd.append("--json")
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=project.repo_root,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    if proc.stdout is None:
        raise RuntimeError("No stdout pipe from subprocess")
    full_output = await _stream_to_tail(proc.stdout, job_id, session_factory)
    exit_code = await proc.wait()
    sess = session_factory()
    try:
        sess.query(ProjectOssJob).filter(ProjectOssJob.id == job_id).update(
            {
                "exit_code": exit_code,
                "stdout_tail": _truncate_tail(full_output),
                "completed_at": _utcnow(),
                "status": ProjectOssJobStatus.complete if exit_code == 0
                          else ProjectOssJobStatus.error,
            },
            synchronize_session=False,
        )
        sess.commit()
    finally:
        sess.close()
```

Note: `_run_fix` runs the CLI in `cwd=project.repo_root` directly — **no worktree**. The fix recipe writes to the user's working tree.

### 6. Apply-all-safe orchestration

Add a helper function (used by S09's `/oss/apply-all-safe` endpoint):

```python
async def run_fixes(
    project: Project,
    job_id: int,
    session_factory: Callable[[], Session],
    check_ids: list[str],
    apply: bool,
) -> None:
    """Run multiple fix recipes sequentially against the same working tree."""
    # Iterate through check_ids, run each via _run_fix-like logic, accumulate output.
    # All writes go to project.repo_root directly. No worktree.
```

### 7. Verification

```bash
uv run iw oss fix OSS-CH-01 --project iw-ai-core             # preview
uv run iw oss fix OSS-CH-01 --project iw-ai-core --apply     # apply
git status   # README.md should be modified or untracked, no branch change
git rev-parse HEAD  # unchanged
uv run iw oss fix OSS-CH-01 --project iw-ai-core --apply     # second apply — file unchanged
git diff      # empty diff (idempotent)
```

Run for at least 3 different recipes to confirm the pattern.

## Project Conventions

- `orch/CLAUDE.md` for CLI patterns (Click groups, sync session via `ctx.obj["get_session"]`).
- No subprocess calls inside recipes themselves — recipes are pure Python file I/O.
- No `os.system()` — use `pathlib.Path.write_text()` / `read_text()` exclusively.
- Path operations use `pathlib.Path`, never `os.path.join`.
- No global mutable state outside the registry (which is module-level by design).

## TDD Requirement

Idempotency tests live in `tests/unit/test_oss_fix_recipes_idempotent.py` (S17). For S07 itself, write a smoke run for at least 3 recipes and include the output in the report.

## Output / Report

Report contains:
- Recipe modules created with check_id list per module
- Total `auto_apply_safe=True` checks vs total recipes registered (these MUST match)
- Manual verification: preview + apply + apply (idempotency) for 3 recipes with `git status` output
- Any check IDs marked `auto_apply_safe=True` in S05 but lacking a recipe — flag for revisit
- Any unexpected interactions between recipes (e.g., recipe A writes a file recipe B then patches)

End with `iw step-done` / `iw step-fail`.
