# F-00070: Pre-commit Hardening

**Type**: Feature
**Priority**: Medium
**Created**: 2026-04-29
**Status**: Draft

---

## ⛔ Docker is off-limits

(Standard policy — see `docs/IW_AI_Core_Agent_Constraints.md`. This feature does not need Docker.)

## ⛔ Migrations: agents generate, daemon applies

This feature does NOT modify migrations. No alembic invocations.

## Description

Expand `.pre-commit-config.yaml` from the current 2 hooks (ruff + mypy) to a richer set that catches common mistakes locally before they reach CI: trailing whitespace, missing-newline-at-EOF, malformed YAML/JSON, accidentally committed large binaries, accidentally committed private keys, and unresolved merge-conflict markers. This reduces CI churn and prevents an entire class of trivially-fixable failures.

## Project Context

Read the project's `CLAUDE.md`. The relevant rules:

- `.env` and `.iw/` MUST be gitignored — the daemon refuses to launch worktrees otherwise. Hooks must not accidentally commit those.
- Many YAML files in this repo are critical (workflow manifests, docker-compose, GitHub workflows). Schema-broken YAML must be caught locally.

## Scope

### In Scope

1. **Update `.pre-commit-config.yaml`** to add the following hooks (in addition to the existing ruff + mypy):

   From `pre-commit/pre-commit-hooks` (latest stable rev — pin to a specific tag):
   - `trailing-whitespace`
   - `end-of-file-fixer`
   - `check-yaml` — exclude `mkdocs.yml` if it has custom tags; exclude any templated YAML files that intentionally contain Jinja
   - `check-json`
   - `check-added-large-files` with `--maxkb=1024`
   - `detect-private-key`
   - `check-merge-conflict`
   - `check-toml`
   - `check-case-conflict` — catches files that differ only in case (Windows-incompatible)

2. **Run `pre-commit run --all-files`** during S01 implementation. This will likely auto-fix trailing whitespace and missing EOF newlines across the repo. The agent must:
   - Run the hooks
   - Inspect every change made by the auto-fixers
   - Re-stage the changes
   - Commit message convention: keep the commit hygienic (this isn't user-facing — but the resulting diff IS visible to reviewers)
   - Document in the S01 report which files were touched by auto-fix and why
   - If any hook flags a real issue (large file, private key, merge conflict marker), STOP and raise a blocker — do not auto-bypass

3. **Update `pyproject.toml`** dev dependencies if any pre-commit hook needs a Python tool that isn't already present. (None expected; the hooks listed are all from `pre-commit-hooks`.)

4. **Smoke test** (`tests/unit/test_precommit_config.py`) that parses `.pre-commit-config.yaml` and asserts the expected hook IDs are all present. This is a regression guard against accidental future deletions.

### Out of Scope

- ERD auto-regen pre-commit hook (explicitly skipped per user decision 2026-04-29).
- Black, isort — already covered by ruff format + ruff isort.
- Schema-doc auto-gen hook — out of scope; could be a future feature.
- gitleaks pre-commit hook — gitleaks runs in CI via `compliance-scan.yml`; adding a local hook is in scope of F-D (security scanning), not F-00070.
- Any change to GitHub Actions workflows.
- Any change to CI/CD configuration.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Update `.pre-commit-config.yaml`, run `pre-commit run --all-files`, fix any auto-fixed files, document touched files | — |
| S02 | code-review-impl | Review S01 (config + auto-fix diff) | — |
| S03 | tests-impl | Smoke test asserting hook IDs are present in the config | — |
| S04 | code-review-impl | Review S03 | — |
| S05 | code-review-final-impl | Cross-layer global review | — |
| S06 | qv-gate | `make lint` | — |
| S07 | qv-gate | `make format` | — |
| S08 | qv-gate | `make typecheck` | — |
| S09 | qv-gate | `make test-unit` | — |

No frontend step (no UI). No browser verification (no UI). No integration test step (no DB or API behavior changed).

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None

### API Changes

- **New endpoints**: None
- **Modified endpoints**: None

### Frontend Changes

- **New components**: None
- **Modified components**: None

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `ai-dev/active/F-00070/F-00070_Feature_Design.md` | Design | This document |
| `ai-dev/active/F-00070/workflow-manifest.json` | Manifest | Step definitions |
| `ai-dev/active/F-00070/prompts/F-00070_S01_Backend_prompt.md` | Prompt | S01 implementation |
| `ai-dev/active/F-00070/prompts/F-00070_S02_CodeReview_prompt.md` | Prompt | Review of S01 |
| `ai-dev/active/F-00070/prompts/F-00070_S03_Tests_prompt.md` | Prompt | Test step |
| `ai-dev/active/F-00070/prompts/F-00070_S04_CodeReview_Tests_prompt.md` | Prompt | Review of S03 |
| `ai-dev/active/F-00070/prompts/F-00070_S05_CodeReview_Final_prompt.md` | Prompt | Final review |
| `.pre-commit-config.yaml` | Modified | Add 8 new hooks |
| `tests/unit/test_precommit_config.py` | New | Smoke test for hook IDs |
| (Various files repo-wide) | Modified | Auto-fixed trailing whitespace / EOF newlines (S01 will inventory) |

## Acceptance Criteria

### AC1: Hooks present in config

```
Given a fresh checkout of the repo after this feature merges
When the developer runs `pre-commit run --all-files`
Then ruff, ruff-format, mypy, trailing-whitespace, end-of-file-fixer, check-yaml, check-json, check-added-large-files, detect-private-key, check-merge-conflict, check-toml, and check-case-conflict are all executed
And every hook reports zero failures (the auto-fixers having already been run during S01)
```

### AC2: Smoke test catches deletions

```
Given a developer accidentally removes one of the new hooks from .pre-commit-config.yaml
When the developer runs `make test-unit`
Then tests/unit/test_precommit_config.py fails with a clear message identifying the missing hook ID
```

### AC3: Pre-existing files are now hygienic

```
Given the auto-fixers ran during S01 implementation
When the developer runs `pre-commit run --all-files` on the merged main branch
Then trailing-whitespace and end-of-file-fixer report zero changes
And no YAML/JSON/TOML files are flagged as malformed
And no large files are flagged
```

### AC4: Existing test suite unchanged

```
Given F-00070 is merged
When the developer runs `make test`
Then all pre-existing tests pass with no new failures or flakes
And the new smoke test passes
```

## Boundary Behavior

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| Whitespace at EOL of a Python file | Contains trailing space | `trailing-whitespace` auto-fixes; commit succeeds on retry |
| File missing newline at EOF | No `\n` at end | `end-of-file-fixer` auto-fixes |
| Malformed YAML in `.github/workflows/*` | Bad indentation | `check-yaml` blocks commit |
| Templated YAML with Jinja | e.g. workflow manifest with `{{ }}` | Either excluded via `exclude:` or skipped — must not block commits |
| File > 1MB committed | e.g. accidental binary | `check-added-large-files` blocks commit; agent raises blocker, does not bypass |
| Private key accidentally committed | `-----BEGIN PRIVATE KEY-----` content | `detect-private-key` blocks commit; agent raises blocker |
| Merge conflict markers in file | `<<<<<<<`, `=======`, `>>>>>>>` | `check-merge-conflict` blocks commit |
| Filename collision on case | `Foo.py` and `foo.py` | `check-case-conflict` blocks commit |
| Hooks run on a worktree with no changes | Idempotent | `pre-commit run --all-files` exits 0 |

## Invariants

1. The hook config MUST pin every external repo to a specific `rev:` tag (no `HEAD`, no `latest`, no branch refs) — reproducible local runs.
2. `pre-commit run --all-files` exits 0 on a clean checkout after F-00070 merges.
3. The smoke test MUST assert each new hook ID by exact string match — typo-resistance.
4. No new Python runtime dependencies introduced by this feature.
5. `.env`, `.iw/`, and any other gitignored path are not accidentally exposed by hook auto-fixes (verify by `git status` after running hooks — only tracked files should be modified).
6. The mypy hook config MUST remain compatible with the existing `tool.mypy` block in pyproject (the hook uses `--ignore-missing-imports`; preserve).

## Dependencies

- **Depends on**: None
- **Blocks**: None

## TDD Approach

- **Unit tests**: `tests/unit/test_precommit_config.py` parses `.pre-commit-config.yaml` (use `pyyaml`) and asserts each expected hook ID is present in some repo's hooks list. Single test file with parameterised assertions or a list of expected IDs.
- **Integration tests**: None.
- **Edge cases**: Test that the smoke test fails when an ID is removed (write a parameterised case using `tmp_path` + a stripped-down config).

## Notes

- S01 will likely modify many files via auto-fix (trailing whitespace cleanup is common across older codebases). The S01 report MUST include a summary of how many files were touched and group them by reason (trailing-whitespace vs EOF-fixer). This helps reviewers focus on the config diff, not the noise.
- If any single auto-fix run modifies more than ~50 files, that is a signal of either:
  - (a) a genuine cleanup the team has been deferring — fine, document and proceed
  - (b) an editor mismatch (CRLF vs LF) — investigate and fix root cause before bulk-applying
- The hooks operate at the file level. They do NOT check semantic correctness (Python syntax, docker-compose schema, etc.) — that's still ruff/mypy's job.
