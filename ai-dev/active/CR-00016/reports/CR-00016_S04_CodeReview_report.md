# CR-00016 S04 Code Review Report

## Step reviewed: S03 (template-impl)

## What was done (S03)

Added Critical Rules bullets about Docker to all 5 CLAUDE.md files and created `docs/IW_AI_Core_DB_Setup.md` with a cross-reference to `IW_AI_Core_Agent_Constraints.md`.

## Files changed

| File | Change |
|------|--------|
| `CLAUDE.md` | Added docker bullet at end of Critical Rules (line 33) |
| `orch/CLAUDE.md` | Added new `## Critical Rules` section with docker bullet |
| `dashboard/CLAUDE.md` | Added new `## Critical Rules` section with docker bullet |
| `executor/CLAUDE.md` | Added new `## Critical Rules` section with docker bullet |
| `tests/CLAUDE.md` | Renumbered rules, added rule 4 with explicit testcontainers exception |
| `docs/IW_AI_Core_DB_Setup.md` | Created with cross-reference to policy doc |

## Checklist verification

### 1. All 5 CLAUDE.md files have the rule

- `CLAUDE.md` (root): Line 33 — bullet contains `docker kill`, `docker stop`, `docker rm`, `docker compose`, `docker-compose`, `docker volume`, `docker system` and links to `docs/IW_AI_Core_Agent_Constraints.md` with exceptions listed inline.
- `orch/CLAUDE.md`: Line 7 — bullet references docker commands and links to policy doc.
- `dashboard/CLAUDE.md`: Line 7 — bullet references docker commands and links to policy doc.
- `executor/CLAUDE.md`: Line 7 — bullet references docker commands and links to policy doc.
- `tests/CLAUDE.md`: Line 19 (rule 4) — bullet explicitly mentions `testcontainers` as the only allowed docker usage and links to policy doc.
- Result: **5/5 PASS**

### 2. tests/CLAUDE.md calls out the testcontainer exception explicitly

Rule 4 in `tests/CLAUDE.md` reads:
> **NEVER** run raw `docker` / `docker compose` / `docker-compose` from test code. The ONLY allowed docker usage in tests is via `testcontainers` fixtures (which self-label under Ryuk and self-destruct). Never stop/remove containers from test teardown — let the fixture lifecycle handle it. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

The testcontainer exception is explicit. **PASS**

### 3. Bullet style discipline

- Root `CLAUDE.md` uses `**NEVER**` format — new bullet follows this exactly.
- `orch/`, `dashboard/`, `executor/` CLAUDE.md files all introduced a new `## Critical Rules` section in the same style, using `**NEVER**` phrasing consistent with the root file.
- `tests/CLAUDE.md` uses numbered rule format `1. **NEVER** ...` — new rule 4 follows the same pattern.
- Bullet positions are logical (end of Critical Rules list in root; new sections at top of subdirectory CLAUDE.md files).
- No existing bullets were reformatted.
- **PASS**

### 4. `docs/IW_AI_Core_DB_Setup.md` cross-reference

The file has a "Related policy" section (lines 32-35) that links to `IW_AI_Core_Agent_Constraints.md` with a descriptive label. **PASS**

### 5. No contradictions

```bash
for f in CLAUDE.md orch/CLAUDE.md dashboard/CLAUDE.md executor/CLAUDE.md tests/CLAUDE.md; do
  grep -n "docker " "$f" | grep -v "docker ps\|docker inspect\|docker logs\|IW_AI_Core_Agent_Constraints"
done
```
Result: **no output** — no suspicious hits found. **PASS**

### 6. Scope discipline

S03 did not touch any prompt templates (S01 did that), did not create new code files, and did not modify `ai-core.sh` or `Makefile`. **PASS**

### 7. Readability

Each CLAUDE.md reads coherently after the bullet insertion. No duplicate bullets. **PASS**

## Issues found

None. **APPROVED**

## Note

The `ai-dev/templates/*.md` files (11 files) were modified in this worktree but are S01's scope — they carry the `⛔ Docker is off-limits` marker from S01. The S03 scope (CLAUDE.md files + cross-reference doc) is clean.