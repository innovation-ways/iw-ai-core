# CR-00062_S09_CodeReviewFix_Final_prompt

**Work Item**: CR-00062 — Add Pi (pi.dev) as a third agent runtime
**Step**: S09
**Agent**: code-review-fix-final-impl

---

## ⛔ Docker is off-limits

Testcontainers exempt. No state-changing docker commands. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

If S08 flagged a migration issue, write a new revision file rather than editing S01's. Do NOT run alembic against the live orch DB.

## Input Files

- S08 report: `ai-dev/active/CR-00062/reports/CR-00062_S08_CodeReview_Final_report.md`
- All prior step reports
- Design doc

## Output Files

- Edits to files identified by S08
- `ai-dev/active/CR-00062/reports/CR-00062_S09_CodeReviewFix_Final_report.md`

## Context

Apply CRITICAL and HIGH cross-cutting findings from S08. After S09, the only remaining steps are QV gates (S10..S13) and SelfAssess (S14). If S09 finds it cannot resolve a finding within scope (e.g., it requires a database schema change beyond S01's seed migration, or it spans more files than the current scope.allowed_paths permits), document the gap and either expand the scope through the operator (file a scope-amendment note in S09's report) or defer the finding to a follow-up.

## Requirements

### 1. Apply each CRITICAL and HIGH finding from S08

For each cross-cutting finding, edit the affected file(s). Do NOT introduce out-of-scope changes; if you discover a related issue while fixing, file it as `<!-- TODO(CR-00062-followup): -->` rather than fixing it.

### 2. Targeted re-verification

For each file you edit, run the affected targeted test:

```bash
uv run pytest tests/unit/<affected_test_file>.py tests/integration/test_pi_dispatch_end_to_end.py -v
```

### 3. Re-run preflight gates

1. `make format`
2. `make typecheck`
3. `make lint`

### 4. Migration-check re-run if S09 touched the migration or models

```bash
make migration-check
```

Must report green. If it fails, fix and re-run until green.

### 5. AC coverage re-tick

Update the `ac_coverage` table from S08's report — flip any "gap:..." entries to "satisfied" where your fixes resolved them. If any AC still has a gap, document the remaining gap and whether it blocks merge.

## Subagent Result Contract

```json
{
  "step": "S09",
  "agent": "code-review-fix-final-impl",
  "work_item": "CR-00062",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "<path>"
  ],
  "preflight": {
    "format": "ok|fixed",
    "typecheck": "ok",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "X passed",
  "tdd_red_evidence": "<test id list> or n/a — non-behavioural fixes",
  "findings_addressed": [
    {"id": "FF1", "severity": "CRITICAL|HIGH", "status": "fixed|deferred", "notes": ""}
  ],
  "ac_coverage": {
    "AC1": "satisfied",
    "AC2": "satisfied",
    "AC3": "satisfied",
    "AC4": "satisfied",
    "AC5": "satisfied",
    "AC6": "satisfied"
  },
  "blockers": [],
  "notes": ""
}
```
