# CR-00017_S10_CodeReview_prompt

**Work Item**: CR-00017 — Daemon-only migration application
**Step Being Reviewed**: S09 (template-impl)
**Review Step**: S10

---

## Input Files

- `ai-dev/active/CR-00017/CR-00017_CR_Design.md`
- `ai-dev/active/CR-00017/reports/CR-00017_S09_Template_report.md`
- All files in S09's `files_changed`

## Output Files

- `ai-dev/active/CR-00017/reports/CR-00017_S10_CodeReview_report.md`

## Review Checklist

### 1. R2 in policy doc
- `docs/IW_AI_Core_Agent_Constraints.md` has R2 directly after R1.
- Marker phrase `⛔ Migrations: agents generate, daemon applies` appears verbatim.
- Allowed / forbidden lists are accurate (agents can run `revision --autogenerate`; operators can run `iw migrations apply`).

### 2. All 11 prompt templates carry BOTH markers
```bash
for f in ai-dev/templates/*.md; do
  grep -q "⛔ Docker is off-limits" "$f" && \
  grep -q "⛔ Migrations: agents generate, daemon applies" "$f" || echo "MISSING: $f"
done
```
No MISSING lines allowed.

### 3. All 5 CLAUDE.md files have BOTH bullets
- CR-00016 bullet (Docker) preserved.
- New CR-00017 bullet (migrations) added.
- Both reference `docs/IW_AI_Core_Agent_Constraints.md`.

### 4. Migration Checklist rewritten cleanly
- Old "run alembic upgrade head" step removed.
- New 3-phase description present.
- Operator CLI section at the bottom.

### 5. Tech stack doc updated
- Old "agents apply migrations" prose replaced with new model.
- Includes the ASCII pipeline diagram (or equivalent clear explanation).

### 6. merge_fix_automation.md updated
- Old `alembic upgrade head` verification step replaced with "daemon auto-verifies".

### 7. Grep audit clean
Run from project root:
```bash
grep -rn "alembic upgrade head" . \
  --include="*.md" \
  --exclude-dir=.git --exclude-dir=.worktrees --exclude-dir=.venv \
  --exclude-dir=ai-dev/active
```
Remaining hits must be in operator-facing contexts only — `ai-core.sh` (but it's not .md), Makefile help output (likewise), or `docs/IW_AI_Core_DB_Setup.md` (operator setup doc, OK to still mention in operator sections).

### 8. Not touched
- `ai-core.sh` — untouched in S09.
- `Makefile` — untouched.
- `scripts/e2e_dashboard_entrypoint.sh` — untouched.
- Coverage test (`test_agent_constraints_coverage.py`) — untouched.
- No code files — untouched.

### 9. Link integrity
- All relative links resolve.
- No broken cross-references.

## Severity Grading

CRITICAL / HIGH / MEDIUM / LOW. Fix in place.

## Subagent Result Contract

Standard code-review JSON.

## Lifecycle commands

```bash
uv run iw step-start CR-00017 --step S10
uv run iw step-done CR-00017 --step S10 --report ai-dev/active/CR-00017/reports/CR-00017_S10_CodeReview_report.md
```
