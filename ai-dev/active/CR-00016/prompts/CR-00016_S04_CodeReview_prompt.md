# CR-00016_S04_CodeReview_prompt

**Work Item**: CR-00016 — Agent prompt hardening
**Step Being Reviewed**: S03 (template-impl)
**Review Step**: S04

---

## Input Files

- `ai-dev/active/CR-00016/CR-00016_CR_Design.md`
- `ai-dev/active/CR-00016/reports/CR-00016_S03_Template_report.md`
- All files in S03's `files_changed`

## Output Files

- `ai-dev/active/CR-00016/reports/CR-00016_S04_CodeReview_report.md`

## Review Checklist

### 1. All 5 CLAUDE.md files have the rule

For each of `CLAUDE.md`, `orch/CLAUDE.md`, `dashboard/CLAUDE.md`, `executor/CLAUDE.md`, `tests/CLAUDE.md`:

- A new bullet references both "docker" (in the command list) AND `docs/IW_AI_Core_Agent_Constraints.md` (the link).
- The bullet matches the style of existing rules in that specific file (the root `CLAUDE.md` uses terse `- **NEVER** …` bullets; `tests/CLAUDE.md` may use slightly different phrasing — reviewer judges).
- The link to the policy doc uses a relative path that resolves.

### 2. Tests CLAUDE.md calls out the testcontainer exception explicitly

The tests layer is special — it does legitimately use docker via testcontainers. Confirm the bullet in `tests/CLAUDE.md` mentions this exception explicitly so test authors aren't confused.

### 3. Bullet style discipline

- No reformatting of unrelated existing bullets.
- Bullet position in the Critical Rules list is sensible (top, or grouped near related rules).
- Font emphasis style matches existing (if the file uses `**NEVER**`, the new bullet does too; same for `**MUST**`).

### 4. `docs/IW_AI_Core_DB_Setup.md` cross-reference

- A "Related policy" (or equivalent) section exists at the end or in a linked-topics area.
- Links to `IW_AI_Core_Agent_Constraints.md` with a descriptive label.

### 5. No contradictions

Search every updated CLAUDE.md for any old text that contradicts the new rule. Specifically grep for `docker compose up` / `docker kill` / `docker rm` outside the new bullet:

```bash
for f in CLAUDE.md orch/CLAUDE.md dashboard/CLAUDE.md executor/CLAUDE.md tests/CLAUDE.md; do
  grep -n "docker " "$f" | grep -v "docker ps\|docker inspect\|docker logs\|IW_AI_Core_Agent_Constraints"
done
```

Any suspicious hit → flag MEDIUM or higher.

### 6. Scope discipline

- No prompt template touched in S03 (S01 did that).
- No new files created (the policy doc is from S01).
- No changes to `ai-core.sh`, Makefile, code files.

### 7. Readability

- Each CLAUDE.md still reads coherently with the new bullet inserted.
- No duplicate bullets (if a pre-CR bullet already said "never touch docker" loosely, either consolidate or explicitly keep both with a note explaining).

## Severity Grading

Standard. Fix in place.

## Subagent Result Contract

Same pattern as prior S02/S04 reviews.

## Lifecycle commands

```bash
uv run iw step-start CR-00016 --step S04
uv run iw step-done CR-00016 --step S04 --report ai-dev/active/CR-00016/reports/CR-00016_S04_CodeReview_report.md
```
