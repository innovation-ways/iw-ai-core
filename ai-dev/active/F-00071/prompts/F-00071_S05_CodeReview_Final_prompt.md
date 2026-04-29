# F-00071_S05_CodeReview_Final_prompt

**Work Item**: F-00071 -- Local + CI Security Scanning
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S03

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

(Standard policies.)

## Input Files

- `ai-dev/active/F-00071/F-00071_Feature_Design.md`
- All step reports under `ai-dev/active/F-00071/reports/`
- All files modified by S01: `Makefile`, `pyproject.toml`, `.gitignore`, `.trivyignore`, `.github/workflows/security-scan.yml`, `scripts/security_report.py`, README/docs
- `tests/unit/test_security_targets.py`

## Output Files

- `ai-dev/active/F-00071/reports/F-00071_S05_CodeReview_Final_report.md`

## Review Checklist

### 1. Completeness vs Design

- [ ] All 6 ACs (AC1–AC6) implemented.
- [ ] All 7 invariants verifiable from the code.
- [ ] No "Out of Scope" items accidentally added (gitleaks local target, license scan, mutation testing, image-scan job).

### 2. Cross-step consistency

- [ ] Make target names in `Makefile` exactly match the strings asserted by `tests/unit/test_security_targets.py`.
- [ ] Workflow `jobs:` names asserted by tests match the actual workflow.
- [ ] Severity threshold (HIGH/CRITICAL gating) consistent in Makefile, workflow, and design.

### 3. Integration

- [ ] `make security-all` actually invokes `security-deps` and `security-iac` (verify by `make -n security-all`).
- [ ] CI workflow YAML parses cleanly (verify with `python -c "import yaml; yaml.safe_load(open('.github/workflows/security-scan.yml'))"`).
- [ ] `scripts/security_report.py` runs without error when no scan outputs exist (graceful skip case).

### 4. Cross-cutting security

- [ ] All action `uses:` are pinned to 40-char SHAs.
- [ ] Workflow permissions are minimal (`contents: read`, `security-events: write` only).
- [ ] No secrets / tokens hardcoded anywhere.
- [ ] Bandit config doesn't accidentally skip critical paths (orch, dashboard, executor are still scanned).
- [ ] `.trivyignore` has no active ignores at this point.

### 5. Architecture

- [ ] No new top-level Python deps in `[project] dependencies`.
- [ ] `compliance-scan.yml` and `codeql.yml` still work (no shared file conflicts).
- [ ] `tests/output/security/` is gitignored.

### 6. Holistic test pass

1. `make lint`
2. `make format-check`
3. `make typecheck`
4. `make test-unit`
5. `make test-integration`
6. `uv run pytest tests/unit/test_security_targets.py -v`
7. If tools installed: `make security-deps && make security-iac`

## Severity Levels

| Severity | Meaning |
|---|---|
| CRITICAL | Workflow action pin to non-SHA; permissions overly broad; gating threshold bypassed or inconsistent |
| HIGH | Missing required file; missing required Makefile target; test doesn't fail when guard is removed |
| MEDIUM | Inconsistency between local Make and CI behavior; SARIF upload not guarded with `if: always()` |
| LOW | Comment style, doc phrasing, naming inconsistencies |

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "code-review-final-impl",
  "work_item": "F-00071",
  "steps_reviewed": ["S01", "S02", "S03", "S04"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```
