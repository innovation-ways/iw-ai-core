# F-00071_S02_CodeReview_prompt

**Work Item**: F-00071 -- Local + CI Security Scanning
**Step Being Reviewed**: S01
**Review Step**: S02

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

(Standard policies.)

## Input Files

- `uv run iw item-status F-00071 --json`
- `ai-dev/active/F-00071/F-00071_Feature_Design.md`
- `ai-dev/active/F-00071/reports/F-00071_S01_Backend_report.md`
- `Makefile`
- `pyproject.toml`
- `.trivyignore`
- `.github/workflows/security-scan.yml`
- `scripts/security_report.py`
- README or tech-stack doc updated

## Output Files

- `ai-dev/active/F-00071/reports/F-00071_S02_CodeReview_report.md`

## Review Checklist

### 1. Makefile

- [ ] Five targets present: `security-deps`, `security-iac`, `security-image-*`, `security-all`, `security-report`.
- [ ] Each target checks `command -v <tool>` before invocation.
- [ ] Install hints reference correct package manager / URL (`uv add --dev pip-audit`, `brew install trivy`, etc.).
- [ ] `.PHONY` updated.
- [ ] No recursive `$(MAKE)` calls except for `security-all` aggregating others (acceptable).
- [ ] Output path is `tests/output/security/` consistently.
- [ ] `security-image-*` clearly handles "image not built" path.

### 2. pyproject.toml

- [ ] `pip-audit>=2.7` and `bandit[toml]>=1.7` in `[dependency-groups] dev`.
- [ ] `[tool.bandit]` block present with `exclude_dirs` covering `tests`, `scripts`, `orch/db/migrations/versions`, `.venv`.
- [ ] Bandit `skips` reasonable (B101 only).
- [ ] No additions to `[project] dependencies`.

### 3. CI workflow

- [ ] File is at `.github/workflows/security-scan.yml`.
- [ ] Triggers: PR + push to main + weekly cron.
- [ ] Permissions limited to `contents: read` + `security-events: write`.
- [ ] Every `uses:` is pinned to a 40-character SHA (regex check).
- [ ] Each SHA has a `# vN.N.N` trailing comment per `compliance-scan.yml` convention.
- [ ] `set -euo pipefail` in run-step shell scripts.
- [ ] SARIF upload uses `if: always()` so failures still publish findings.
- [ ] HIGH/CRITICAL is the failing threshold (verify by reading the `--strict` / `--severity HIGH,CRITICAL` flags).
- [ ] No image-scan job (or, if present, gracefully handles fork PRs without secrets).

### 4. .trivyignore

- [ ] File exists.
- [ ] Documentation comment block at top.
- [ ] No active ignores at this point in time (per design).

### 5. .gitignore

- [ ] `tests/output/security/` is gitignored (directly or via `tests/output/`).

### 6. Documentation

- [ ] README or tech-stack doc has a Security Scanning section (≤120 words).
- [ ] Mentions all three axes and the local Make targets.

### 7. scripts/security_report.py

- [ ] Reads `pip-audit.json`, `bandit.json`, `trivy-iac.json` from `tests/output/security/`.
- [ ] Tolerates missing inputs (skipped — tool unavailable).
- [ ] Writes both `report.json` and `report.md`.
- [ ] No live-DB connections.
- [ ] Type hints, mypy clean.

## Test Verification

- `make lint`, `make typecheck`, `make test-unit`.
- `make security-deps` (if tools installed locally); confirm exit code matches expectations on a clean checkout.
- `make security-iac` if trivy installed.

## Severity Levels

| Severity | Meaning |
|---|---|
| CRITICAL | Action version not pinned; permissions overly broad; HIGH gating bypassed |
| HIGH | Missing required Make target; missing required workflow job; bandit config doesn't exclude tests; install hint missing |
| MEDIUM (fixable) | Inconsistent severity threshold between local and CI; missing `if: always()` on SARIF upload |
| MEDIUM (suggestion) | README phrasing improvements |
| LOW | Comment style |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "F-00071",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
