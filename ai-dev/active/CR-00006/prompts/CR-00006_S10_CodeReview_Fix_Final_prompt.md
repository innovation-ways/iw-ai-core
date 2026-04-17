# CR-00006 S10 — Fix Findings From Final Review

## Input Files

- `ai-dev/work/CR-00006/reports/S09_code_review_final.md` — the final review report (source of work for this step)
- `ai-dev/active/CR-00006/CR-00006_CR_Design.md` — design doc (do not diverge from)
- Any source file referenced by CRITICAL or HIGH findings

## Output Files

- Any source files that need edits to resolve findings
- `ai-dev/work/CR-00006/reports/S10_fix_log.md` — short log of what was changed per finding

## Context

**Work item**: CR-00006
**Step**: S10
**Agent**: code-review-fix-final-impl

Apply fixes for all CRITICAL and HIGH findings from S09. MEDIUM/LOW findings may be fixed if cheap; otherwise document them for follow-up.

## Process

1. Read `ai-dev/work/CR-00006/reports/S09_code_review_final.md`.
2. For each finding at severity CRITICAL or HIGH:
   - Locate the file:line reference.
   - Apply the suggested fix (or a better one if you can justify it in the fix log).
   - Re-run the specific test(s) that cover that area.
3. For MEDIUM/LOW: fix if trivial; otherwise list them at the bottom of `S10_fix_log.md` under "Deferred".
4. Run the full quality + test gates once all fixes are in:

   ```bash
   uv run ruff check .
   uv run ruff format .
   uv run mypy orch/ dashboard/
   make test-unit
   make test-integration
   ```

5. If any test regresses, root-cause and fix. Do NOT disable tests or weaken assertions.

## Constraints

- Do NOT introduce new features, refactors, or reorganizations beyond what the findings require.
- Do NOT modify the design doc — it is the source of truth; if a finding requires a design change, escalate via `iw step-fail`.
- Do NOT change the wire format of `/api/projects/{id}/code/qa`.
- Do NOT change the database schema.
- Do NOT bypass CLAUDE.md hard rules to make a test pass (e.g., don't switch integration tests to live DB).

## Signal completion

If all CRITICAL/HIGH findings are resolved and all tests pass:

```bash
iw step-done CR-00006 S10 --summary "Resolved N CRITICAL + M HIGH findings from S09. Deferred K LOW/MEDIUM to backlog. All tests pass, ruff/mypy clean."
```

If resolution requires a design change or cannot be completed:

```bash
iw step-fail CR-00006 S10 --reason "<specific finding that cannot be fixed without design change — e.g., 'Finding #3 requires new schema column; design must be revised'>"
```
