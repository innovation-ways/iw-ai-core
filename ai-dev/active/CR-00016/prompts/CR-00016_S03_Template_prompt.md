# CR-00016_S03_Template_prompt

**Work Item**: CR-00016 — Agent prompt hardening
**Step**: S03
**Agent**: template-impl

---

## Input Files

- `ai-dev/active/CR-00016/CR-00016_CR_Design.md` — Design (AC3)
- `ai-dev/active/CR-00016/reports/CR-00016_S01_Template_report.md` — policy doc is in place
- `CLAUDE.md` (project root)
- `orch/CLAUDE.md`
- `dashboard/CLAUDE.md`
- `executor/CLAUDE.md`
- `tests/CLAUDE.md`
- `docs/IW_AI_Core_DB_Setup.md` (from CR-00015) — add cross-reference
- `docs/IW_AI_Core_Agent_Constraints.md` (from S01) — the link target

## Output Files

- `ai-dev/active/CR-00016/reports/CR-00016_S03_Template_report.md`
- Updated: `CLAUDE.md`, `orch/CLAUDE.md`, `dashboard/CLAUDE.md`, `executor/CLAUDE.md`, `tests/CLAUDE.md`
- Updated: `docs/IW_AI_Core_DB_Setup.md` (cross-reference to the new policy doc)

## Context

S01 created the policy doc and embedded the rule in prompt templates + iw-workflow. Your job is to plant the rule in every CLAUDE.md so it's also visible to anyone (human or AI) reading the project conventions from a layer-specific vantage point.

Read the design doc's AC3 and the existing Critical Rules style in `CLAUDE.md` (root) so your new bullet matches that style exactly.

## Requirements

### 1. Root `CLAUDE.md` — Critical Rules bullet

Find the **Critical Rules** section (exists near the top of the file, bulleted list with bold **NEVER** / **MUST** formatting). Add a new bullet at the top of the list OR the bottom (preserve existing order — the new rule is equally critical; put it where it reads best):

```markdown
- **NEVER** run `docker kill`, `docker stop`, `docker rm`, `docker restart`, `docker compose up|down|restart`, `docker-compose up|down|restart`, `docker volume rm|prune`, or `docker system|container|image prune` — these can clobber shared infrastructure (see 2026-04-22 incident). Full policy: `docs/IW_AI_Core_Agent_Constraints.md`. Exceptions: read-only `docker ps|inspect|logs`, testcontainers via pytest, and `./ai-core.sh` / `make` targets.
```

Preserve every existing Critical Rule. Do NOT reformat or reorder unrelated bullets.

### 2. `orch/CLAUDE.md`

Add a bullet to its rules section (style matches existing bullets in that file):

```markdown
- **NEVER** execute docker container/volume/network management commands from orch code or scripts. Any shared-DB container management goes through `./ai-core.sh` or the operator. See `docs/IW_AI_Core_Agent_Constraints.md`.
```

### 3. `dashboard/CLAUDE.md`

Same pattern; add to its rules section:

```markdown
- **NEVER** invoke docker commands from dashboard code, fixtures, or dev scripts. See `docs/IW_AI_Core_Agent_Constraints.md`. Dashboard tests use TestClient — they never need to touch docker directly.
```

### 4. `executor/CLAUDE.md`

```markdown
- **NEVER** run `docker`, `docker compose`, or `docker-compose` from executor bash scripts. Executor scripts run as part of agent workflows and inherit the R1 rule from `docs/IW_AI_Core_Agent_Constraints.md`.
```

### 5. `tests/CLAUDE.md`

Special case — tests DO use docker via testcontainers. Make the rule + exception crystal clear:

```markdown
- **NEVER** run raw `docker` / `docker compose` / `docker-compose` from test code. The ONLY allowed docker usage in tests is via `testcontainers` fixtures (which self-label under Ryuk and self-destruct). Never stop/remove containers from test teardown — let the fixture lifecycle handle it. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.
```

### 6. `docs/IW_AI_Core_DB_Setup.md` cross-reference

At the bottom of the doc (or in a "Related" / "See also" section if one exists), add:

```markdown
## Related policy

- [`docs/IW_AI_Core_Agent_Constraints.md`](IW_AI_Core_Agent_Constraints.md) — the
  Docker-is-off-limits rule that restricts agent behavior around this DB.
```

### 7. Audit for stale contradictions

After all edits, search for any pre-existing instruction in the 5 CLAUDE.md files that explicitly tells an agent to run a forbidden command. Examples to watch for:

- "run `make db-up`" — OK (goes through Makefile which uses the bootstrap file post-CR-00015).
- "run `docker compose up -d db`" — NOT OK if it still exists; should have been caught by CR-00015 S03, but verify.
- "run `docker logs -f ...`" — OK (read-only introspection).

Flag any remaining contradictions in your report.

### 8. Preserve order

Do NOT reorder Critical Rules lists unless the new bullet clearly reads better in a different position. If in doubt, append.

## Project Conventions

- Match the bullet style of each CLAUDE.md file (bold `NEVER`/`MUST`, backtick code, trailing period).
- Relative links.
- No emoji in the bullets themselves (emoji is reserved for the rule section in `docs/IW_AI_Core_Agent_Constraints.md` and the prompt templates — it's the visual marker for the grep test).

## TDD Requirement

No automated test — S05 creates the coverage test. Manual verification:

```bash
for f in CLAUDE.md orch/CLAUDE.md dashboard/CLAUDE.md executor/CLAUDE.md tests/CLAUDE.md; do
  grep -l "docker kill\|IW_AI_Core_Agent_Constraints" "$f" > /dev/null && echo "OK: $f" || echo "MISSING: $f"
done
```

## Test Verification (NON-NEGOTIABLE)

1. `make lint` — pass.
2. Manual grep check above returns OK for all 5 files.
3. `docs/IW_AI_Core_DB_Setup.md` has the cross-reference and the link resolves.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "template-impl",
  "work_item": "CR-00016",
  "completion_status": "complete",
  "files_changed": [
    "CLAUDE.md",
    "orch/CLAUDE.md",
    "dashboard/CLAUDE.md",
    "executor/CLAUDE.md",
    "tests/CLAUDE.md",
    "docs/IW_AI_Core_DB_Setup.md"
  ],
  "tests_passed": true,
  "test_summary": "lint green; 5/5 CLAUDE.md files contain the rule + link",
  "blockers": [],
  "notes": ""
}
```

## Lifecycle commands

```bash
uv run iw step-start CR-00016 --step S03
# edit ...
uv run iw step-done CR-00016 --step S03 --report ai-dev/active/CR-00016/reports/CR-00016_S03_Template_report.md
```
