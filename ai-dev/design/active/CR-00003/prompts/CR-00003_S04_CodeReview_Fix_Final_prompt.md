# CR-00003 S04 — Final Review Fix Implementation

## Input Files

- `ai-dev/work/CR-00003/reports/S03_final_review.md` — findings to address
- `dashboard/static/logo.png` — asset to fix if issues found
- `dashboard/templates/base.html` — template to fix if issues found

## Output Files

- Modified files as needed per S03 findings

## Context

You are implementing fixes identified in the S03 final review for CR-00003. Read `CLAUDE.md` for project conventions.

**Work item**: CR-00003  
**Step**: S04  
**Agent**: code-review-fix-final-impl

## Instructions

1. Read the S03 review report from `ai-dev/work/CR-00003/reports/`
2. Implement fixes for all CRITICAL and HIGH findings
3. For LOW/MEDIUM findings, use your judgment — fix if trivial, note if deferred
4. Re-run any verification commands from S03 to confirm fixes resolve the findings

## Expected Fix Scope

Given the minimal nature of this change (one template line + one PNG file), S03 findings are unlikely to be severe. Common issues to watch for:

- Wrong `alt` text on the `<img>` tag
- Missing or incorrect `w-7 h-7` class
- Static mount path mismatch (`/static/` vs `/static`)
- PNG not generated or corrupted

## Signal completion

```bash
iw step-done CR-00003 S04 --summary "Applied N fixes from final review: <brief description of what was fixed>"
```

If no fixes were needed:
```bash
iw step-done CR-00003 S04 --summary "No fixes required — S03 review found no issues"
```
