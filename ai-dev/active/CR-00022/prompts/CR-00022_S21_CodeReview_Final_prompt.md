# CR-00022_S21_CodeReview_Final_prompt

**Work Item**: CR-00022 -- OSS Compliance redesign
**Step**: S21
**Agent**: code-review-final-impl

---

## ⛔ Docker / Migrations off-limits

Standard rules.

## Input Files

- `ai-dev/active/CR-00022/CR-00022_CR_Design.md`
- All step reports S01..S20 in `ai-dev/active/CR-00022/reports/`
- Every file changed across all phases (the union of `files_changed` from each report)

## Output Files

- `ai-dev/active/CR-00022/reports/CR-00022_S21_CodeReview_Final_report.md`

## Context

Global cross-layer review. Verify the implementation as a whole satisfies every AC, that the layers integrate correctly, and that the working-tree-only invariant holds end-to-end.

## Review Checklist

### 1. AC mapping (every AC present in implementation)

Walk every AC1–AC12 from the design. For each:
- Identify the implementation that satisfies it (file:line).
- Identify the test that exercises it.
- Note any gaps.

### 2. Cross-layer integration

- DB column `auto_apply_safe` (S01) → ORM (S01) → persistence (S05/S06) → dashboard route (S09) → template (S11) → modal (S11) — full propagation?
- `compute_finding_hash` agreement: dashboard (`oss_accepted.py`) vs CI script (`honor_accepted.py`) — byte-identical hashes?
- `auto_apply_safe` flag agreement: Finding constructor (S05) vs FixRecipe class (S07) — every check tagged True must have a recipe; every recipe must be tagged True?
- SSE row-update event shape (S09) vs frontend consumer (S11) — fields match?

### 3. Working-tree-only invariant — CRITICAL

Repo-wide grep for any remaining git mutation in OSS code paths:

```bash
grep -rn "git checkout\|git switch\|git branch\b\|git worktree\|git commit\|git reset\|git push" \
  dashboard/ orch/ skills/iw-oss-publish/scripts/ \
  --include="*.py" --include="*.sh"
```

Allowed only: `git status`, `git rev-parse`, `git symbolic-ref` (read-only); CI workflow git operations (separate concern).

Anything else is CRITICAL.

### 4. Brand voice + UX consistency

Spot-check 5 catalog entries: brand voice consistent? "Risk" framed concretely? "How to fix" actionable?
Modal layout matches design sketch?
Filter chip default = failing/human-required?

### 5. No orphan code or dead references

After S19's cleanup, repo-wide grep for `prepare|publish|make_oss|prep-|/tmp/oss` outside `ai-dev/active/CR-00022/`:
- Any remaining hit is a CRITICAL finding.

### 6. Idempotency end-to-end

For at least 3 recipes, manually:
```bash
uv run iw oss fix OSS-CH-01 --project iw-ai-core --apply
uv run iw oss fix OSS-CH-01 --project iw-ai-core --apply
git status --short   # second run should leave file unchanged
```

### 7. CI honor flow

Manually exercise:
```bash
echo "accepted: [{check_id: OSS-CH-99, finding_hash: $(python3 -c 'from dashboard.services.oss_accepted import compute_finding_hash; print(compute_finding_hash("OSS-CH-99","Test",None))'), reason: test, accepted_at: 2026-04-25T00:00:00Z, accepted_by: tester}]" > .iw/oss-accepted.yaml
# Synthetic SARIF + run honor_accepted.py — confirm downgrade
```

### 8. Migration safety

- Migration file is a single-revision file with `down_revision` pointing at the correct head?
- `downgrade()` raises `NotImplementedError`?
- Pre-delete order is correct (rows before enum recreate)?
- Tests cover the migration in a testcontainer?

### 9. QV gates pre-run

Run yourself:
```bash
make lint
make typecheck
make test-unit
```
Quick green verification (full integration runs in S26).

### 10. Documentation

- `docs/IW_AI_Core_OSS_Accepted_Risk.md` exists and is correct?
- `docs/IW_AI_Core_CLI_Spec.md` updated?
- `docs/IW_AI_Core_Database_Schema.md` updated?
- `dashboard/CLAUDE.md` mentions the new endpoints if it lists routes by concern?

## Output Report

Final report contains:
- AC table (AC → impl ref → test ref → status)
- Cross-layer integration findings
- Critical findings (working-tree-only violations, orphan refs, hash mismatches)
- High/Medium/Low findings
- Final verdict (`approve` / `request_changes`)
- If approve: confirm ready for QV gates
- If request_changes: list specific files + what to fix

End with `iw step-done` / `iw step-fail`.
