# F-00070_S02_CodeReview_prompt

**Work Item**: F-00070 -- Pre-commit Hardening
**Step Being Reviewed**: S01
**Review Step**: S02

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

(Standard policies.)

## Input Files

- `uv run iw item-status F-00070 --json`
- `ai-dev/active/F-00070/F-00070_Feature_Design.md`
- `ai-dev/active/F-00070/reports/F-00070_S01_Backend_report.md`
- `.pre-commit-config.yaml` (post-change)
- All files listed in S01's `files_changed`

## Output Files

- `ai-dev/active/F-00070/reports/F-00070_S02_CodeReview_report.md`

## Review Checklist

### 1. Config correctness

- [ ] All 8 new hooks present: `trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-json`, `check-toml`, `check-added-large-files`, `detect-private-key`, `check-merge-conflict`, `check-case-conflict`.
- [ ] `pre-commit-hooks` repo `rev:` is pinned to a specific stable tag (e.g. `v5.0.0`).
- [ ] `--maxkb=1024` set on `check-added-large-files`.
- [ ] `--markdown-linebreak-ext=md` set on `trailing-whitespace` (preserves Markdown two-space line-break convention).
- [ ] If `check-yaml` excludes any files, the exclude is justified (templated YAML, intentionally invalid examples).
- [ ] Existing ruff and mypy hooks unchanged.

### 2. Auto-fix sanity

- [ ] S01 report's `auto_fix_summary` is populated.
- [ ] If counts are unexpectedly large (>50 per hook), review the sample paths to confirm they are routine cleanup not a CRLF/encoding hidden bug.
- [ ] No file in `.env`, `.iw/`, `node_modules/`, `.venv/`, or `tests/output/` was touched by auto-fix.
- [ ] No file under `orch/db/migrations/versions/` had its formatting changed in a way that would affect the migration's `revision` / `down_revision` IDs (touch-only changes like trailing whitespace are fine).

### 3. Idempotency

- [ ] Running `pre-commit run --all-files` a second time exits 0 with no further changes (run it as part of review).

### 4. Gitignore effectiveness

- [ ] `git status` after S01 shows zero entries matching `.env`, `.iw/`, `tests/output/`, or any other gitignored path.

### 5. Conventions

- Read `CLAUDE.md`.
- No new Python runtime deps in pyproject.

## Test Verification

Run as part of review:
- `make lint`
- `make typecheck`
- `make test-unit`
- `uv run pre-commit run --all-files` (must exit 0)

## Severity Levels

| Severity | Meaning |
|---|---|
| CRITICAL | Hook blocks legitimate commits; gitignored path exposed; private key / large file accepted |
| HIGH | Missing required hook; `rev:` not pinned; auto-fix changed unintended files |
| MEDIUM (fixable) | Missing `--maxkb`, missing `--markdown-linebreak-ext`, unjustified exclude |
| MEDIUM (suggestion) | Could reorder hooks for clarity |
| LOW | Comment style, YAML indentation preference |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "F-00070",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
