# CR-00091_S05_CodeReview_Final_prompt

**Work Item**: CR-00091 — Alembic PENDING Sentinel
**Step**: S05
**Agent**: code-review-final-impl

---

## ⛔ Docker is off-limits

Read-only introspection only. No container management.

## ⛔ Migrations: agents generate, daemon applies

No migration application to the live DB.

## Context

Read `CLAUDE.md` and `orch/CLAUDE.md`. Read the reports for S01, S02, S03, S04 and all changed files across the entire CR. This is the global cross-step review.

**Design doc**: `ai-dev/active/CR-00091/CR-00091_CR_Design.md`.

## Scope

Run the following targeted tests to confirm all work is consistent end-to-end:

```bash
uv run pytest tests/unit/test_rewrite_down_revision.py \
              tests/unit/test_resolve_pending_migration.py \
              tests/unit/daemon/test_migration_rebase.py \
              tests/integration/test_migrations_round_trip.py \
              -v
```

Any failure is CRITICAL.

## Cross-Step Review Checklist

### AC1 — migration-pending target (S01)

- [ ] `make migration-pending MSG="test"` would: (a) run alembic autogenerate, (b) rewrite the newest file's `down_revision` to `"PENDING"`. Trace the Makefile target to confirm both steps run in sequence and the error guard for missing MSG is in place.

### AC2 — migration-check resolves PENDING (S02)

- [ ] `make migration-check` calls `resolve_pending_migration.py` before pytest. Confirm the Makefile line order. Confirm the resolver exits 0 when no PENDING files are present (no disruption to existing pipeline).
- [ ] The integration test `test_resolver_produces_valid_chain_against_real_versions_dir` correctly asserts that after resolution, no file in the scratch area contains `"PENDING"`.
- [ ] The resolver writes `down_revision = None` (unquoted) for the chain-root case — never `"None"` (quoted). Inspect the resolver source and confirm the unit test `test_resolves_pending_when_it_is_the_only_migration` asserts on the exact unquoted substring.

### AC3 — migration_rebase.py PENDING path (S02)

- [ ] The unit test `test_pending_sentinel_is_always_rewritten` covers the full path: PENDING → main head. Confirm the assertion checks the on-disk file content, not just the `RebaseResult.rewrites` list.
- [ ] The documentation comment in `migration_rebase.py` Step 8 is present. Confirm no logic was changed (diff shows only the comment addition).

### AC4 — No regression on real migrations (S02)

- [ ] The existing `test_migrations_round_trip.py` tests are unmodified and pass. Confirm by reading the S02 report and the test file diff.
- [ ] The new AC4 guard test `test_ac4_resolver_is_noop_on_clean_versions_dir` exists, asserts byte-identical content before and after the resolver runs on a no-PENDING versions dir, and passes.

### AC5 — Idempotency (S01)

- [ ] `test_idempotent_pending` asserts the file content after running the script on an already-PENDING file is identical to the content before. Confirm the assertion is content-level, not just exit-code-level.

### AC6 — Documentation coverage (S04)

- [ ] `CLAUDE.md` critical rules section contains the `make migration-pending` instruction.
- [ ] `orch/CLAUDE.md` contains the migration generation note.
- [ ] All three skills (`iw-new-cr`, `iw-new-feature`, `iw-new-incident`) contain the PENDING convention blockquote in their migration sections.
- [ ] The `.claude/skills/` mirrors match the `skills/` master copies exactly (run `diff -r skills/iw-new-cr/ .claude/skills/iw-new-cr/` etc.).
- [ ] `ai-dev/templates/Implementation_Prompt_Template.md` references `make migration-pending`.

### Cross-cutting checks

- [ ] Both resolver and rewrite scripts use stdlib only — no `from orch import ...` or any project import.
- [ ] The `migration-pending` Makefile target does not modify `make migration-check` behaviour for non-PENDING chains (AC4).
- [ ] S03's CRITICAL and HIGH findings (if any) were addressed by S03 fix or confirmed non-applicable. List any open findings from S03 that were not resolved and flag as CRITICAL if still valid.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "code-review-final-impl",
  "work_item": "CR-00091",
  "completion_status": "complete|blocked",
  "files_reviewed": ["all CR-00091 changed files"],
  "findings": [],
  "open_s03_findings": [],
  "tests_run": "uv run pytest tests/unit/test_rewrite_down_revision.py tests/unit/test_resolve_pending_migration.py tests/unit/daemon/test_migration_rebase.py tests/integration/test_migrations_round_trip.py -v",
  "tests_passed": true,
  "blockers": [],
  "notes": ""
}
```
