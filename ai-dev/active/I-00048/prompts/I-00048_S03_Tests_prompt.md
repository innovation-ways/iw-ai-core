# I-00048_S03_Tests_prompt

**Work Item**: I-00048 — Prompts and manifest not copied into worktree — agents thrash on orientation every step
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Not applicable for this step.

---

## Input Files

- Design document: `ai-dev/active/I-00048/I-00048_Issue_Design.md`
- Modified file: `executor/worktree_setup.sh`
- S01 report: `ai-dev/active/I-00048/reports/I-00048_S01_Backend_report.md`
- Test conventions: `tests/CLAUDE.md`, `tests/conftest.py`

## Output Files

- `tests/unit/test_worktree_setup_context_copy.py` (new)
- `ai-dev/active/I-00048/reports/I-00048_S03_Tests_report.md`

---

## Context

S01 added a new Step 7 to `executor/worktree_setup.sh` that:
1. Copies `ai-dev/active/<ID>/` (prompts, manifest, design doc) into the worktree so agents can find them via Glob
2. Writes per-worktree git exclude patterns to `$WORKTREE_GITDIR/info/exclude` so the copied files are not committed by `git add -A`

Your job is to write tests that verify this behavior. These tests must be executable with `make test-unit` (no testcontainer required — use subprocess calls against a temporary git repo). Read `tests/CLAUDE.md` before writing tests.

---

## CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert (worktree / "ai-dev").exists()` (shape only — directory exists)
- GOOD: `assert (worktree / "ai-dev/active/I-00048/prompts/my_prompt.md").exists()` (specific file)
- GOOD: `assert "ai-dev/active/I-00048/prompts/" in exclude_content` (specific pattern in exclude)
- GOOD: assert git status output does NOT contain "prompts/" as untracked

---

## Requirements

### 1. Test file: `tests/unit/test_worktree_setup_context_copy.py`

Write tests using `subprocess` and `tmp_path` to create a real (but minimal) git repo and exercise the new Step 7 logic in `worktree_setup.sh`. These tests do NOT need a live DB — they test the bash script behavior in isolation using a temporary git repo. You will need to stub or skip the `iw item-status` call since there is no live DB in unit tests.

**Strategy**: Test the Step 7 logic by replicating it faithfully in a Python helper (`_run_copy_and_exclude`) that calls the real `git` binary via `subprocess`. Do NOT attempt to call `worktree_setup.sh` directly — the script has DB and `uv sync` dependencies that can't be mocked in unit tests. The Python helper must use the same path logic and git invocations as the bash step, and the tests must use real git repos (`git init` + `git worktree add`) — no mocking of git.

The approach that avoids the DB dependency while testing real git behavior:

```python
import subprocess
import os

def _run_copy_and_exclude(worktree_dir: Path, item_id: str, project_repo_root: Path) -> None:
    """Replicate Step 7 logic from worktree_setup.sh for testing."""
    active_src = project_repo_root / "ai-dev" / "active" / item_id
    active_dst = worktree_dir / "ai-dev" / "active" / item_id
    if active_src.exists():
        (worktree_dir / "ai-dev" / "active").mkdir(parents=True, exist_ok=True)
        subprocess.run(["cp", "-r", str(active_src), str(active_dst)], check=True)
        # Resolve worktree gitdir
        result = subprocess.run(
            ["git", "-C", str(worktree_dir), "rev-parse", "--git-dir"],
            capture_output=True, text=True, check=True
        )
        gitdir = result.stdout.strip()
        if not gitdir.startswith("/"):
            gitdir = str(worktree_dir / gitdir)
        os.makedirs(f"{gitdir}/info", exist_ok=True)
        exclude_path = f"{gitdir}/info/exclude"
        with open(exclude_path, "a") as f:
            f.write(f"# iw: read-only context\n")
            f.write(f"ai-dev/active/{item_id}/prompts/\n")
            f.write(f"ai-dev/active/{item_id}/workflow-manifest.json\n")
            f.write(f"ai-dev/active/{item_id}/*.md\n")
```

Then write tests that:
1. Create a minimal git repo in `tmp_path`
2. Create `ai-dev/active/<ID>/` with sample prompt files
3. Call `_run_copy_and_exclude` (or a helper that calls the actual bash script)
4. Assert specific outcomes

### 2. Reproduction test — files are present in worktree after copy

```python
def test_context_files_exist_in_worktree_after_copy(tmp_path):
    """FAILS before S01 fix; PASSES after. Verifies the specific prompt file exists."""
    # Arrange: main repo with ai-dev/active/I-00048/ containing a prompt file
    repo = tmp_path / "repo"
    # ... set up git repo ...
    prompt_content = "# S01 prompt content"
    prompt_file = repo / "ai-dev" / "active" / "I-00048" / "prompts" / "I-00048_S01_Backend_prompt.md"
    prompt_file.parent.mkdir(parents=True)
    prompt_file.write_text(prompt_content)
    manifest = repo / "ai-dev" / "active" / "I-00048" / "workflow-manifest.json"
    manifest.write_text('{"id": "I-00048"}')
    design = repo / "ai-dev" / "active" / "I-00048" / "I-00048_Issue_Design.md"
    design.write_text("# design")

    worktree = tmp_path / "worktree"
    worktree.mkdir()
    # ... set up as git worktree ...

    # Act: run copy+exclude logic
    _run_copy_and_exclude(worktree, "I-00048", repo)

    # Assert specific files — not just directory existence
    assert (worktree / "ai-dev/active/I-00048/prompts/I-00048_S01_Backend_prompt.md").exists()
    assert (worktree / "ai-dev/active/I-00048/workflow-manifest.json").exists()
    assert (worktree / "ai-dev/active/I-00048/I-00048_Issue_Design.md").exists()
    # Verify content — not just existence
    assert (worktree / "ai-dev/active/I-00048/prompts/I-00048_S01_Backend_prompt.md").read_text() == prompt_content
```

### 3. Test — copied files are NOT staged by `git add -A`

This is the merge-safety test. After copying and writing the exclude file, `git add -A` in the worktree must NOT stage the prompt files.

```python
def test_copied_context_files_are_not_staged_by_git_add(tmp_path):
    """Verifies that git add -A does not commit the copied context files.
    If this test fails, worktree_commit.sh would create .iw-collision artifacts at merge.
    """
    # ... set up as above ...
    _run_copy_and_exclude(worktree, "I-00048", repo)

    # Run git add -A inside the worktree
    subprocess.run(["git", "-C", str(worktree), "add", "-A"], check=True)

    # Check what is staged
    result = subprocess.run(
        ["git", "-C", str(worktree), "status", "--porcelain"],
        capture_output=True, text=True, check=True
    )
    staged = result.stdout

    # The prompt file must NOT be staged
    assert "I-00048_S01_Backend_prompt.md" not in staged
    assert "workflow-manifest.json" not in staged
    assert "I-00048_Issue_Design.md" not in staged
```

### 4. Test — exclude file contains the specific expected patterns

```python
def test_worktree_exclude_file_contains_correct_patterns(tmp_path):
    """Verifies the info/exclude file has the right patterns — not just that it exists."""
    # ... set up as above ...
    _run_copy_and_exclude(worktree, "I-00048", repo)

    gitdir = subprocess.run(
        ["git", "-C", str(worktree), "rev-parse", "--git-dir"],
        capture_output=True, text=True, check=True
    ).stdout.strip()
    if not gitdir.startswith("/"):
        gitdir = str(worktree / gitdir)

    exclude_path = Path(gitdir) / "info" / "exclude"
    assert exclude_path.exists()
    content = exclude_path.read_text()

    # Verify specific patterns — not just non-empty
    assert "ai-dev/active/I-00048/prompts/" in content
    assert "ai-dev/active/I-00048/workflow-manifest.json" in content
    assert "ai-dev/active/I-00048/*.md" in content
    # Reports must NOT be excluded — they need to be committed
    assert "ai-dev/active/I-00048/reports/" not in content
```

### 5. Test — no-op when `ai-dev/active/<ID>/` does not exist

```python
def test_copy_step_is_silent_when_active_dir_missing(tmp_path):
    """If ai-dev/active/<ID>/ doesn't exist, the step must skip without error."""
    # ... set up worktree but do NOT create ai-dev/active/I-00099/ ...
    # Act — should not raise
    _run_copy_and_exclude(worktree, "I-00099", repo)  # ID that has no active dir
    # Worktree should have no ai-dev/active/I-00099/
    assert not (worktree / "ai-dev" / "active" / "I-00099").exists()
```

### 6. Set up real git repos for test fixtures

Use `subprocess` to initialize real git repos — do NOT mock git. The worktree must be a valid git worktree (created via `git worktree add`) for `git rev-parse --git-dir` to return the correct worktree-specific path.

Example minimal setup:
```python
def _make_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-b", "main", str(path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@test.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Test"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "commit", "--allow-empty", "-m", "init"], check=True, capture_output=True)

def _make_worktree(repo: Path, branch: str, worktree_path: Path) -> None:
    subprocess.run(["git", "-C", str(repo), "worktree", "add", "-b", branch, str(worktree_path), "HEAD"], check=True, capture_output=True)
```

---

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`:

1. `make format` — auto-fixes formatting drift
2. `make typecheck` — zero errors on files you touched
3. `make lint` — zero errors (project-wide)

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
```

All tests must pass. Do NOT report `tests_passed: true` unless all unit tests pass.

---

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00048",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/test_worktree_setup_context_copy.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
