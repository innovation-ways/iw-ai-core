# CR-00092_S04_Database_prompt

**Work Item**: CR-00092 -- Column-docs baseline scrub (wave 4: remainder + baseline removal + gate flip + docs/tracker)
**Step**: S04
**Agent**: database-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY docker commands that change container/volume/network state. Testcontainers from pytest fixtures and read-only introspection are the only exceptions. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This step adds NO migration. Do NOT run alembic. Do NOT touch `orch/db/migrations/versions/**`.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00092 --json`.
- `ai-dev/active/CR-00092/CR-00092_CR_Design.md` — Design document (re-read Acceptance Criteria — every AC1–AC8 is exercised here).
- `ai-dev/work/CR-00092/reports/CR-00092_S0{1,2,3}_Database_report.md` — prior wave reports.
- `orch/db/column_docs_baseline.txt` — baseline (shrunk to ~134 entries by S01+S02+S03).
- `docs/IW_AI_Core_Database_Schema.md` — primary source for column descriptions.
- `orch/db/models.py` — the file you will edit for the wave-4 scrub.
- `Makefile` — for the gate-flip (`|| true` removal).
- `.github/workflows/test-quality.yml` — for the gate-flip (`|| true` removal).
- `docs/IW_AI_Core_Testing_Strategy.md` — §5 gate-row update.
- `ai-dev/work/TESTS_ENHANCEMENT.md` — §8 row 4.5.followup update + §11 changelog entry.

## Output Files

- `ai-dev/work/CR-00092/reports/CR-00092_S04_Database_report.md`.
- Edits in the six files listed above.
- Deletion of `orch/db/column_docs_baseline.txt`.

## Context

You are implementing **wave 4 of 4** — the closing wave. This step does FIVE distinct things in this order:

1. **Wave 4 scrub** (~134 columns across 22 remaining classes).
2. **Baseline regeneration + deletion** (confirm scanner sees zero violations against `/dev/null`, then `git rm orch/db/column_docs_baseline.txt`).
3. **Gate flip** in `Makefile` and `.github/workflows/test-quality.yml` (remove `|| true` from both surfaces) AND update the `check-column-docs:` target recipe to drop the now-deleted `--baseline orch/db/column_docs_baseline.txt` argument (otherwise the scanner crashes with `FileNotFoundError`).
4. **Strategy doc + tracker updates** (`docs/IW_AI_Core_Testing_Strategy.md` §5, `ai-dev/work/TESTS_ENHANCEMENT.md` §8 row 4.5.followup, §11 changelog).
5. **AC8 deliberate-break demonstration** (temporarily remove one `doc=`, confirm `make check-column-docs` exits non-zero, restore — record in your report).

DO NOT do them out of order. The gate flip MUST come AFTER the baseline is empty — otherwise the gate fails immediately and the rest of the step can't be tested.

## Requirements

### 1. Read prior reports and the design

Confirm S01/S02/S03 each reported `completion_status: complete`. Confirm cumulative scrub through S03 = 316. If any prior step is partial / blocked, STOP and raise a blocker.

Re-read the design's **Acceptance Criteria** (AC1–AC8) and **Notes** (the description-sourcing rule + the gate-surface trade-off).

### 2. Wave 4 scrub — all 22 remaining classes

Add a `doc="..."` argument to every undocumented `Column(...)` declaration in these 22 classes (~134 columns total). Sourcing rule: schema doc first, inferred second. Same edit-shape rules as S01–S03.

| Class | Entries | Notes |
|-------|---------|-------|
| `WorkItemEvidence` (line 1120) | 10 | Evidence rows attached at approve / step-done hooks (CR-00025). |
| `KeepAliveRun` (line 2402) | 10 | Per-run row in the keep-alive scheduler (see I-00112). |
| `Project` (line 406) | 9 | Top-level managed-project record (one row per `projects.toml` entry). |
| `OssToolRun` (line 2211) | 9 | One row per scanner invocation inside an OSS scan. |
| `OssFindingDetail` (line 2237) | 8 | Per-finding detail payload. |
| `DaemonEvent` (line 1470) | 8 | **CRITICAL** — the python attribute `event_metadata` aliases the SQL column `metadata` because SQLAlchemy reserves the python name. The `doc=` lives on the `Column(...)` declaration regardless. The scanner reports the SQL column name. |
| `BatchOverlapIgnore` (line 1381) | 8 | Cross-batch overlap allowlist (F-00076). |
| `ProjectDocVersion` (line 1758) | 7 | Versioned project-doc snapshots. |
| `ChatMessage` (line 2598) | 7 | Per-message row in a ChatConversation. |
| `TestHealthSnapshot` (line 2842) | 6 | Time-series snapshots for the self-dashboarding panel (CR-00086). |
| `QvBaseline` (line 1066) | 6 | Per-item baseline freeze for QV gates. |
| `MergeAutoVerdict` (line 1515) | 6 | Auto-merge dry-run verdicts (F-00084). |
| `MigrationLock` (line 1356) | 5 | Exclusive lock taken when a Database step is queued. |
| `KeepAliveSlot` (line 2374) | 5 | Per-slot row in the keep-alive scheduler. |
| `IdAllocation` (line 480) | 5 | Records each ID allocated by `iw next-id` (atomicity covered by CR-00060). |
| `DocSectionGuide` (line 1913) | 5 | Section-level editorial guidance for AI doc regen. |
| `AutoMergeProjectConfig` (line 1547) | 5 | Per-project auto-merge configuration (F-00084). |
| `KeepAliveConfig` (line 2353) | 4 | Global keep-alive scheduler config. |
| `IwCoreInstance` (line 1448) | 3 | DB-identity fingerprint row (CR-00014). |
| `DocTypeGuide` (line 1874) | 3 | Doc-type-level editorial guidance. |
| `DocInstanceGuide` (line 1892) | 3 | Per-instance doc guidance. |
| `IdSequence` (line 460) | 2 | Per-prefix sequence counter for `iw next-id`. |
| **Total** | **~134** | |

After editing, run a sanity check:

```bash
uv run python scripts/check_db_column_docs.py --baseline orch/db/column_docs_baseline.txt
# Expected: exit 0, no violations
```

### 3. Baseline regeneration + deletion

After the scrub, regenerate the baseline against `/dev/null` to confirm the live tree is fully documented:

```bash
uv run python scripts/check_db_column_docs.py --baseline /dev/null
# Expected: exit 0 (no violations against an empty baseline = every column has doc=)
```

If this exits non-zero, you missed columns. Fix them and re-run before continuing.

Then delete the baseline file:

```bash
git rm orch/db/column_docs_baseline.txt
```

### 4. Flip the gate from warn-first to blocking

**Edit `Makefile`** — at the `quality` target (around line 101), change:

```make
quality: lint format typecheck test-assertions dead-code dep-check
	@$(MAKE) check-column-docs || true
```

to:

```make
quality: lint format typecheck test-assertions dead-code dep-check
	@$(MAKE) check-column-docs
```

Also update the comment block above the `check-column-docs:` target (around line 102–107) to reflect that the gate is now blocking — remove the "Warn-first during burn-in; a follow-up CR flips it blocking" sentence, replace with "Blocking — every Column declaration must carry doc=" or similar.

**CRITICAL — you MUST also update the `check-column-docs:` target recipe.** Step 3 deletes `orch/db/column_docs_baseline.txt`, but the target's current recipe hardcodes that path:

```make
check-column-docs:
	uv run python scripts/check_db_column_docs.py --baseline orch/db/column_docs_baseline.txt
```

The scanner raises `FileNotFoundError` (uncaught → non-zero exit) when `--baseline` points at a missing file. If you leave the recipe as-is, `make check-column-docs` — and therefore `make quality` (AC5) — will crash with a traceback on every run, NOT pass. Drop the `--baseline` argument so the scanner runs in pure-audit mode (no allowlist; every column must carry `doc=`):

```make
check-column-docs:
	uv run python scripts/check_db_column_docs.py
```

After this edit, confirm `make check-column-docs` exits 0 cleanly (no `FileNotFoundError` traceback) on the fully-scrubbed tree.

**Edit `.github/workflows/test-quality.yml`** — find the line `- run: make check-column-docs || true` (around line 32) and change to `- run: make check-column-docs`. Also update the burn-in comment above it.

### 5. Update strategy doc and tracker

**`docs/IW_AI_Core_Testing_Strategy.md` §5 (gate table)** — find the row for `check-column-docs` and flip its status column from warn-first / burn-in to blocking. If the row mentions "follow-up CR will flip blocking", replace that note with "Blocking since CR-00092 (2026-05-28)". Also scan the rest of the doc for any OTHER row referencing the column-docs gate's warn-first / burn-in status (notably the §9 "already shipped" roadmap table, which currently says "warn-first during burn-in; follow-up CR-00085-followup-column-docs-gate-blocking will flip to blocking") and flip those to blocking + CR-00092 as well — no stale "will flip to blocking" note should survive.

**`ai-dev/work/TESTS_ENHANCEMENT.md` §8 row 4.5.followup** — change the Status column from TODO to:

```
✅ (CR-00092, 2026-05-28, blocking)
```

and update the Link column to `CR-00092`.

**`ai-dev/work/TESTS_ENHANCEMENT.md` §11 (changelog)** — add a new entry at the TOP of the changelog (above the existing 2026-05-28 entries):

```markdown
- **2026-05-28** — **CR-00092 shipped (Phase-4 item 4.5.followup — column-docs baseline scrub + gate flip).** 450 columns across 41 model classes in `orch/db/models.py` gained one-line `doc="..."` arguments sourced from `docs/IW_AI_Core_Database_Schema.md` where present and inferred from column name/type/usage otherwise; `orch/db/column_docs_baseline.txt` deleted (`git ls-files` returns nothing for that path). `make check-column-docs` flipped from warn-first (`|| true`) to blocking in both `make quality` (Makefile) and `.github/workflows/test-quality.yml`'s `lint-typecheck` job. Strategy doc §5 row + tracker §8 row 4.5.followup updated. Wave breakdown: S01 = 103 (WorkItem/StepRun/ProjectDoc/BatchItem), S02 = 90 (WorkflowStep/DocGenerationJob/CodeIndexJob/TestRun/Batch), S03 = 123 (10 OSS/chat/runtime classes), S04 = 134 (22 remainder classes) + baseline removal + gate flip + docs/tracker. Test-only / metadata-only change — no schema change, no migration, no runtime behaviour change. **Known trade-off (per operator choice)**: gate stays folded into `make quality`, NOT promoted to a canonical daemon QV gate; enforcement happens at the GH `test-quality.yml` workflow on push/PR. AC8 deliberate-break-then-revert demonstrated in S04 report.
```

Also bump the header `> **Status**: living plan — v1.8 (2026-05-28)` to `> **Status**: living plan — v1.9 (2026-05-28)` and update the "Current status" paragraph to mention that the column-docs follow-up is done.

### 6. AC8 deliberate-break demonstration (MANDATORY)

After everything above is committed (or staged in your worktree), demonstrate that the gate actually fires:

```bash
# Pick one column — e.g., orch/db/models.py::Project.id — and temporarily remove its doc= argument.
# Re-run the gate:
make check-column-docs
# Expected: exits non-zero, output names the column you broke.

# Restore the doc= argument.
make check-column-docs
# Expected: exits 0.
```

Capture both invocations' output in your S04 report under a section titled "AC8 deliberate-break demonstration". Confirm `git diff` is empty after the restore (no leftover damage).

### 7. Verify the full picture

```bash
# AC1
uv run python scripts/check_db_column_docs.py --baseline /dev/null  # exit 0

# AC2
git ls-files orch/db/column_docs_baseline.txt  # nothing

# AC4
grep -n "check-column-docs" .github/workflows/test-quality.yml  # no || true on the match

# AC5
make quality  # exit 0

# Scope (AC7)
git diff main...HEAD --name-only
# Expected list (apart from ai-dev/active/CR-00092/** and ai-dev/work/CR-00092/**):
#   orch/db/models.py
#   orch/db/column_docs_baseline.txt   (D — deletion)
#   Makefile
#   .github/workflows/test-quality.yml
#   docs/IW_AI_Core_Testing_Strategy.md
#   ai-dev/work/TESTS_ENHANCEMENT.md
# NOT in the list: docs/IW_AI_Core_Database_Schema.md, any file under orch/db/migrations/versions/, any other file.
```

### 8. Targeted test verification

```bash
uv run pytest tests/orch/db/test_column_docs.py -v
```

All tests must pass.

## Pre-flight Quality Gates

1. `make format` 2. `make typecheck` 3. `make lint`

## TDD Requirement

```
"tdd_red_evidence": "n/a — content-only doc= additions + Makefile/GH-workflow config flip + docs/tracker updates; no new behavioural tests (scanner tests in tests/orch/db/test_column_docs.py already cover the gate, unchanged). AC8 deliberate-break-then-revert demonstrated in report."
```

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "database-impl",
  "work_item": "CR-00092",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/models.py",
    "orch/db/column_docs_baseline.txt",
    "Makefile",
    ".github/workflows/test-quality.yml",
    "docs/IW_AI_Core_Testing_Strategy.md",
    "ai-dev/work/TESTS_ENHANCEMENT.md"
  ],
  "preflight": {"format": "...", "typecheck": "...", "lint": "..."},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed (tests/orch/db/test_column_docs.py)",
  "tdd_red_evidence": "n/a — content-only doc= additions + Makefile/GH-workflow config flip + docs/tracker updates; AC8 deliberate-break-then-revert demonstrated in report",
  "wave_scrub_count": "<actual remainder count, ~134>",
  "cumulative_scrub_count": 450,
  "remaining_baseline_count": 0,
  "baseline_deleted": true,
  "gate_flipped_in_makefile": true,
  "gate_flipped_in_gh_workflow": true,
  "ac8_demonstrated": true,
  "blockers": [],
  "notes": "Wave 4 of 4 complete. All 450 columns documented across 41 classes. orch/db/column_docs_baseline.txt deleted. make quality + GH workflow flipped from warn-first to blocking. Strategy doc §5 + tracker §8/§11 updated. AC8 demonstrated: removing doc= from <CLASS>.<column> made `make check-column-docs` exit <N>; restoring made it exit 0."
}
```
