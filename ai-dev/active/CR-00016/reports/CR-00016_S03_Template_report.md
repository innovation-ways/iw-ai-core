# CR-00016 S03 Template Report

## What was done

Planted the `**NEVER** run docker ...` Critical Rules bullet in all 5 CLAUDE.md files and created `docs/IW_AI_Core_DB_Setup.md` (which CR-00015 was supposed to create but the file was missing from this worktree).

## Files changed

| File | Change |
|------|--------|
| `CLAUDE.md` | Added Critical Rules bullet (R1 rule, verbatim from prompt) |
| `orch/CLAUDE.md` | Added Critical Rules section with orch-specific bullet |
| `dashboard/CLAUDE.md` | Added Critical Rules section with dashboard-specific bullet |
| `executor/CLAUDE.md` | Added Critical Rules section with executor-specific bullet |
| `tests/CLAUDE.md` | Added rule 4 about testcontainers being the only allowed docker usage |
| `docs/IW_AI_Core_DB_Setup.md` | Created with production raw-docker path + bootstrap compose fallback + cross-reference to `IW_AI_Core_Agent_Constraints.md` |

## Audit for stale contradictions

Searched all 5 CLAUDE.md files for pre-existing instructions that tell an agent to run a forbidden command. **None found.** The existing instructions are all compatible with the new rule:
- `make db-up` — goes through Makefile → bootstrap compose (safe)
- `docker logs -f ...` — read-only, permitted by R1 exception 2

## Manual verification

```
for f in CLAUDE.md orch/CLAUDE.md dashboard/CLAUDE.md executor/CLAUDE.md tests/CLAUDE.md; do
  grep -l "docker kill\|IW_AI_Core_Agent_Constraints" "$f" > /dev/null && echo "OK: $f" || echo "MISSING: $f"
done
```
Result: **5/5 OK**.

## Lint

`make lint` shows 2 pre-existing ruff E501 errors in `orch/cli/item_commands.py:595` and `tests/integration/test_code_qa_routes.py:226` (line length > 100 chars) — neither file was modified by this step. These are pre-existing issues unrelated to S03.

## Cross-reference note

`docs/IW_AI_Core_DB_Setup.md` was required by CR-00016 but was supposed to be created by CR-00015. It was missing from this worktree, so S03 created it. The cross-reference in `docs/IW_AI_Core_Agent_Constraints.md` (line 35 and 64) now resolves correctly.
