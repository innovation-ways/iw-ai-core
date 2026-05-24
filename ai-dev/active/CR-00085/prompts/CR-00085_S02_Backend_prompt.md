# CR-00085_S02_Backend_prompt

**Work Item**: CR-00085 -- DB-column documentation gate
**Step**: S02
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope.

Allowed exceptions: testcontainers spun up by pytest fixtures; read-only
`docker ps`/`inspect`/`logs`; `./ai-core.sh` and `make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This step adds NO Alembic migration.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status CR-00085 --json`.
- `ai-dev/work/CR-00085/CR-00085_CR_Design.md` — Design document (read FIRST).
- `ai-dev/work/CR-00085/reports/CR-00085_S01_Backend_report.md` — S01's report (gives you the baseline entry count to cite in tracker/docs).
- `scripts/check_db_column_docs.py`, `orch/db/column_docs_baseline.txt`, `tests/orch/db/test_column_docs.py` — S01's outputs.
- `Makefile` — existing `quality` chain to extend.
- `.github/workflows/test-quality.yml` — existing `lint-typecheck` job to extend.
- `docs/IW_AI_Core_Testing_Strategy.md` — §5 quality-gates table and §9 known-gaps table.
- `skills/iw-ai-core-testing/SKILL.md` and `.claude/skills/iw-ai-core-testing/SKILL.md` — master + sync copy.
- `ai-dev/work/TESTS_ENHANCEMENT.md` — §8 Phase 4 table (row 4.5) and §11 changelog.

## Output Files

- `Makefile` — modified to add `check-column-docs` target and fold into `quality` (warn-first).
- `.github/workflows/test-quality.yml` — modified to add one warn-first step in `lint-typecheck`.
- `docs/IW_AI_Core_Testing_Strategy.md` — §5 + §9 + ChangeLog updated.
- `skills/iw-ai-core-testing/SKILL.md` — new section on the column-doc gate.
- `.claude/skills/iw-ai-core-testing/SKILL.md` — synced copy of the above.
- `ai-dev/work/TESTS_ENHANCEMENT.md` — §8 row 4.5 marked ✅ + new follow-up tracker row + §11 changelog entry.
- `ai-dev/work/CR-00085/reports/CR-00085_S02_Backend_report.md` — step report.

## Context

You are implementing the **integration** piece of CR-00085: wiring the scanner from S01 into the Makefile, the CI workflow, the strategy doc, the testing skill, and the tracker. No new Python code in this step — only orchestration / documentation surfaces.

Read the design document first, then `CLAUDE.md`.

## Requirements

### 1. `Makefile` — add `check-column-docs` target and fold into `quality`

Add `check-column-docs` to the `.PHONY` line.

Add the target (place near `test-assertions` — they are conceptually paired baseline-scanner gates):

```makefile
# DB-column doc scanner gate (CR-00085, Phase-4 4.5) — flag SQLAlchemy
# Column declarations missing a `doc=` description. See
# scripts/check_db_column_docs.py and orch/db/column_docs_baseline.txt.
# Warn-first during burn-in; a follow-up CR flips it blocking once the
# baseline is small enough.
check-column-docs:
	uv run python scripts/check_db_column_docs.py --baseline orch/db/column_docs_baseline.txt
```

Update the `quality` target to include it WARN-FIRST (`|| true`):

```makefile
quality: lint format typecheck test-assertions dead-code dep-check
	@$(MAKE) check-column-docs || true
```

The `|| true` is **mandatory** for this burn-in CR — flipping to blocking is the explicit job of the follow-up CR (`CR-00085-followup-column-docs-gate-blocking`). Do NOT make it blocking here.

### 2. `.github/workflows/test-quality.yml` — add warn-first step

In the `lint-typecheck` job, add one new step **after** `make dep-check`:

```yaml
      # DB-column doc gate (CR-00085, Phase-4 4.5) — warn-only during burn-in.
      # Flipping to blocking is a follow-up after the baseline shrinks.
      - run: make check-column-docs || true
```

Keep the placement consistent with `make dead-code || true` and `make dep-check || true` — these are the existing warn-first informational steps. Do NOT make it blocking. Do NOT add it to other jobs (`unit`, `integration`, `smoke`).

### 3. `docs/IW_AI_Core_Testing_Strategy.md` — strategy-doc updates

**§5 (Quality gates table)** — add ONE new row, alongside the other gates. Pick a placement near "Architecture" / "Dead-code detection" since this is an informational/burn-in-warn-first gate:

```markdown
| DB-column doc gate (CR-00085, P4-4.5) | `scripts/check_db_column_docs.py` against `orch/db/column_docs_baseline.txt` | warnings during burn-in (warn-first); flips to blocking in `CR-00085-followup-column-docs-gate-blocking` | `make check-column-docs` (informational in `make quality`; `lint-typecheck` GH job runs it with `|| true`) |
```

**§9 (Known gaps & roadmap table)** — flip the relevant row. There is no existing row for this in §9 today (it's only in `ai-dev/work/TESTS_ENHANCEMENT.md` §8); add a new row to the §9 table:

```markdown
| DB-column doc gate (4.5) | ✅ (CR-00085, 2026-05-24) — `make check-column-docs` + baseline `orch/db/column_docs_baseline.txt`; warn-first during burn-in; follow-up CR-00085-followup-column-docs-gate-blocking will flip to blocking |
```

If §9 has no Phase-4 row template, place this consistently with the other ✅/❌ rows in the same table.

**Add a Changelog/version entry** if the doc has a version-history footer; if not, leave it.

### 4. `skills/iw-ai-core-testing/SKILL.md` — testing-skill section

Add a new section (placement: right after the assertion-scanner section, since the patterns rhyme):

```markdown
## DB-column documentation gate (CR-00085, P4-4.5)

`scripts/check_db_column_docs.py` is a static SQLAlchemy-mapper-walking
scanner that flags every Column declaration missing a `doc=` description.
It runs as `make check-column-docs`, folded into `make quality` warn-first
during the burn-in period, and as a step in `.github/workflows/test-quality.yml`'s
`lint-typecheck` job (also warn-first).

**The rule when you add a new column.** Every new `Column(...)` declaration
on a SQLAlchemy model under `orch/db/` MUST carry a `doc="<one-line description>"`
argument. Example:

```python
class WorkItem(Base):
    foo = Column(Integer, nullable=False, doc="What this column means in one line.")
```

**The committed baseline at `orch/db/column_docs_baseline.txt`** lists today's
undocumented columns so the gate fires only on **NEW** violations. Regenerate
with:

```bash
uv run python scripts/check_db_column_docs.py \
    --write-baseline orch/db/column_docs_baseline.txt
```

**The right way to silence the gate is to write a `doc=` on the column, not
to add the FQN to the baseline.** The baseline is a cleanup backlog, not an
accept-list — reviewers should push back on baseline growth.

**Reserved-name trap.** Because SQLAlchemy reserves `metadata` on the
declarative base, the `DaemonEvent` table's `metadata` column is bound to
the python attribute `event_metadata`. The scanner walks the SQL columns
via `Base.registry.mappers` → `mapper.local_table.columns`, so it reports
the SQL column name (`metadata`), not the python attribute name. If you
encounter a similar SQLAlchemy-reserved-name collision, follow the same
pattern.
```

(Use a fenced code block for the example; the testing skill already has many code fences — this is fine; the no-fences rule applies to the **functional design doc**, not skills.)

### 5. `.claude/skills/iw-ai-core-testing/SKILL.md` — sync the master copy

Copy your changes verbatim from `skills/iw-ai-core-testing/SKILL.md` to `.claude/skills/iw-ai-core-testing/SKILL.md`. Two-copy rule from `iw sync-skills` discipline. After editing both, run:

```bash
diff skills/iw-ai-core-testing/SKILL.md .claude/skills/iw-ai-core-testing/SKILL.md
```

The two files must be byte-identical (the diff should be empty).

### 6. `ai-dev/work/TESTS_ENHANCEMENT.md` — tracker updates

**§8 (Phase 4 table)** — row 4.5 currently reads `TODO` with empty Link column. Change to:

```
| 4.5 | DB-column documentation gate | Keeps `docs/IW_AI_Core_Database_Schema.md` honest (InnoForge has the analogue) | CI check: every SQLAlchemy model column has a description; fail on undocumented columns. | CR | ✅ (CR-00085, 2026-05-24, warn-first burn-in) | CR-00085 |
```

**Add a new follow-up tracker row** under §8 (or in whichever sub-section the tracker lists open follow-ups; mirror `P1-CR-D-followup-semgrep-block` and `P2-CR-A-followup-mutation-block` placement). Suggested entry:

```
| 4.5.followup | Column-docs incremental scrub + flip gate blocking | The CR-00085 baseline freezes today's undocumented columns; this follow-up scrubs them per-module and flips `make check-column-docs` from warn-first to blocking. | Per-module backend-impl CRs (`models.py` first, then `migrations/versions/**`); a final direct-config CR removes the `|| true`. | CR + direct | TODO | CR-00085-followup-column-docs-scrub / CR-00085-followup-column-docs-gate-blocking |
```

**§11 (Changelog)** — add a dated entry at the top (newest first):

```
- **2026-05-24** — **CR-00085 drafted (Phase-4 item 4.5, DB-column documentation gate).** New scanner `scripts/check_db_column_docs.py` walks `Base.registry.mappers` → `mapper.local_table.columns` and flags every Column without a `doc=` argument; frozen baseline at `orch/db/column_docs_baseline.txt` (NNN entries — see S01 report). Wired as `make check-column-docs`, folded into `make quality` warn-first (`|| true`) during burn-in, and as a warn-first step in `.github/workflows/test-quality.yml`'s `lint-typecheck` job. RED-first library-form tests under `tests/orch/db/test_column_docs.py` cover the empty-baseline RED, the committed-baseline GREEN, the `DaemonEvent.metadata`/`event_metadata` reserved-name regression, a synthetic-mapper composability test, and a write-baseline roundtrip smoke. Scope (`allowed_paths`): scanner, baseline, test package, Makefile, GH workflow, strategy doc, testing skill (master + .claude/), TESTS_ENHANCEMENT.md — NO edits to `orch/db/models.py` (the per-column scrub is the follow-up CR's job), NO edits to `docs/IW_AI_Core_Database_Schema.md` (the doc the gate exists to keep honest, but the scrub is a separate effort), NO migrations, `browser_verification: false`. Structural sibling: CR-00046's assertion-scanner kit (`scripts/check_test_assertions.py` + `tests/assertion_free_baseline.txt`). Follow-up `CR-00085-followup-column-docs-scrub` + `CR-00085-followup-column-docs-gate-blocking` filed in §8 (not yet ID-reserved).
```

Use the exact `NNN` baseline-entry count from S01's report (do not invent — read it from `ai-dev/work/CR-00085/reports/CR-00085_S01_Backend_report.md`'s `tdd_red_evidence` field).

If the tracker has a header status block with a `Next pickup:` sentence, update it to reflect that 4.5 is now ✅ and the next Phase-4 candidate.

## Project Conventions

Read `CLAUDE.md` for project-specific patterns.

When editing the testing skill, remember the two-copy rule (`skills/` + `.claude/skills/`); when editing the tracker, keep the table column counts consistent with existing rows.

## TDD Requirement

This is a documentation / wiring step — no new behaviour code. Use:

`"tdd_red_evidence": "n/a — Makefile/CI/docs/skill/tracker wiring only, no production logic"`

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting completion:

1. **`make format`** — auto-fix any drift.
2. **`make lint`** — must report zero new errors (Makefile and YAML don't go through ruff but the strategy doc and skill markdown do go through `lint-templates`/`scripts/check_templates.py` only if they were Jinja; they're not — so this is mostly checking nothing regressed).
3. **`make typecheck`** — touched no Python code, but run it to confirm no incidental regression.

Then verify the wiring works:

```bash
make check-column-docs       # must exit 0 on the current tree (baseline shields)
make quality                 # must exit 0 (warn-first integration)
```

If `make check-column-docs` exits non-zero on an unchanged tree, your baseline drifted — fix S01's baseline OR your Makefile invocation.

Populate `preflight` in the result contract.

## Test Verification (NON-NEGOTIABLE)

Run the S01 test file once to confirm S02's wiring did not break it:

```bash
uv run pytest tests/orch/db/test_column_docs.py -v
```

Do NOT run the full suite — that's S05–S12's job.

## Scope discipline

- DO edit only the files in the design's `Impacted Paths` list excluding `scripts/check_db_column_docs.py`, `orch/db/column_docs_baseline.txt`, and the `tests/orch/db/` package (those are S01's; you may read them, you must NOT re-edit them in this step).
- DO NOT edit `orch/db/models.py`, `docs/IW_AI_Core_Database_Schema.md`, or any migration file.
- DO NOT flip `|| true` to blocking — that is the explicit job of the follow-up CR. The whole point of the burn-in policy is that this CR is non-disruptive.

If you discover S01's outputs need fixing, raise a blocker rather than editing them inline — the right move is a fix cycle on S01, not silent rework in S02.

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "backend-impl",
  "work_item": "CR-00085",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "Makefile",
    ".github/workflows/test-quality.yml",
    "docs/IW_AI_Core_Testing_Strategy.md",
    "skills/iw-ai-core-testing/SKILL.md",
    ".claude/skills/iw-ai-core-testing/SKILL.md",
    "ai-dev/work/TESTS_ENHANCEMENT.md"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "S01 tests still green; make check-column-docs exits 0; make quality exits 0",
  "tdd_red_evidence": "n/a — Makefile/CI/docs/skill/tracker wiring only, no production logic",
  "blockers": [],
  "notes": "Skill master+sync diff is empty (byte-identical). Tracker baseline count cited: <NNN> (from S01 report)."
}
```
