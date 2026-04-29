# F-00070_S01_Backend_prompt

**Work Item**: F-00070 -- Pre-commit Hardening
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

(Standard policies. Neither Docker nor migrations are touched.)

## Input Files

- `uv run iw item-status F-00070 --json`
- `ai-dev/active/F-00070/F-00070_Feature_Design.md`
- `.pre-commit-config.yaml` — current config (2 hooks)
- `pyproject.toml` — dep groups
- `CLAUDE.md`, `tests/CLAUDE.md`

## Output Files

- Modified: `.pre-commit-config.yaml`
- Possibly modified: many files repo-wide (auto-fix output)
- `ai-dev/active/F-00070/reports/F-00070_S01_Backend_report.md`

## Context

Add 8 hooks to `.pre-commit-config.yaml` and run them across the repo, fixing whatever the auto-fixers touch.

## Requirements

### 1. Update `.pre-commit-config.yaml`

Append a new repo block to the existing config, BEFORE the ruff repo block (since `pre-commit-hooks` is the canonical "always first" repo):

```yaml
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0   # pin to a specific stable tag — verify latest at runtime
    hooks:
      - id: trailing-whitespace
        args: [--markdown-linebreak-ext=md]
      - id: end-of-file-fixer
      - id: check-yaml
        # Exclude templated YAML if any exists. Inspect the repo for
        # workflow-manifest.json (JSON, fine) and any *.j2.yaml or
        # similar before adding excludes.
      - id: check-json
      - id: check-toml
      - id: check-added-large-files
        args: ['--maxkb=1024']
      - id: detect-private-key
      - id: check-merge-conflict
      - id: check-case-conflict
```

Verify the latest stable `rev` from https://github.com/pre-commit/pre-commit-hooks/tags before pinning. As of 2026-04, `v5.0.0` is the current major.

### 2. Install and run

```bash
uv run pre-commit install            # install git hook
uv run pre-commit run --all-files    # run all hooks against the entire repo
```

The run will likely:
- Auto-fix trailing whitespace in many files
- Add missing newlines at EOF
- Possibly succeed cleanly if the repo is already hygienic

If a hook BLOCKS (large file, private key, merge conflict marker, malformed YAML/JSON/TOML, case conflict): STOP and raise a blocker. Do NOT auto-bypass with `--no-verify`. Investigate and either fix at the root or call `iw step-fail` with a clear reason.

### 3. Inspect and document the auto-fix diff

After auto-fixers run:

```bash
git status -s
git diff --stat
```

Group the changes by hook:
- Files modified by `trailing-whitespace` (count + sample paths)
- Files modified by `end-of-file-fixer` (count + sample paths)

If the count is unexpectedly high (>50 files), pause and consider whether there's a CRLF/LF or editor-config issue at the root. If yes, fix `.editorconfig` or `.gitattributes` first; if no, document the count and proceed.

Re-stage all changes:

```bash
git add -u
```

(Use `-u` to stage modifications only — do NOT add untracked files in this step.)

### 4. Re-run to confirm clean

```bash
uv run pre-commit run --all-files
```

Should now exit 0 with all hooks passing.

### 5. Verify .gitignore is still effective

After auto-fixes, run:

```bash
git status -s | grep -E '^[?M].*(\.env|\.iw/)' || echo "ok — .env / .iw not exposed"
```

If anything in `.env` or `.iw/` was modified or appears in the status, the gitignore is broken — STOP and raise a blocker. The daemon refuses to launch worktrees in that state.

### 6. Report

In `F-00070_S01_Backend_report.md`, include:
- The exact `rev:` you pinned for `pre-commit-hooks`.
- Auto-fix file counts by hook.
- A brief sample of paths fixed (5–10 max — don't paste 200 lines).
- Any blockers encountered and how they were resolved.
- Confirmation that `pre-commit run --all-files` exits 0 after the run.

## Project Conventions

- Read `CLAUDE.md` for the full set of project rules.
- Pin all external versions — no `HEAD`, no `latest`, no branch refs.
- Do NOT modify any file outside the auto-fix scope and the config itself.
- Do NOT add new Python runtime dependencies — `pre-commit-hooks` is a separate set of executables fetched by pre-commit, not pip.

## TDD Requirement

Tests are owned by S03. For S01, the verification is operational: hooks run, exit 0, no genuine issues hidden.

## Pre-flight Quality Gates

1. `make format` — auto-fix
2. `make typecheck` — zero new errors on touched files
3. `make lint` — zero errors
4. `make test-unit` — passes (no test changes in this step, just regression check)

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "F-00070",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    ".pre-commit-config.yaml"
  ],
  "auto_fix_summary": {
    "trailing-whitespace": {"count": 0, "sample_paths": []},
    "end-of-file-fixer": {"count": 0, "sample_paths": []}
  },
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "precommit_run_clean": true,
  "blockers": [],
  "notes": ""
}
```
