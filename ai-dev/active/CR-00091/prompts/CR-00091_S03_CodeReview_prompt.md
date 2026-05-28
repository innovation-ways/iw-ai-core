# CR-00091_S03_CodeReview_prompt

**Work Item**: CR-00091 — Alembic PENDING Sentinel
**Step**: S03
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits

Read-only docker introspection (`docker ps`, `docker logs`) is permitted. No container/volume/network management.

## ⛔ Migrations: agents generate, daemon applies

Do not apply any migration to the live DB on port 5433.

## Context

Read `CLAUDE.md` and `orch/CLAUDE.md`. Review the S01 and S02 reports and all files changed in those steps.

**Design doc**: `ai-dev/active/CR-00091/CR-00091_CR_Design.md` — use the Acceptance Criteria as your review checklist.

## Pre-review gate

Run lint and format-check on all changed files before reviewing:
```bash
make lint
make format-check
```

Report any failures as CRITICAL findings.

## Review Checklist

### scripts/rewrite_down_revision.py (S01)

- [ ] **AC5 idempotency**: the script must not change a file that already has `down_revision = "PENDING"`. Trace the regex replacer — does it produce `"PENDING"` when the input is already `"PENDING"`? If not, that is a CRITICAL bug.
- [ ] **Type-annotated form**: the regex handles `down_revision: str | tuple[str, ...] | None = "abc"`. Write out the match against a sample string to confirm.
- [ ] **None form**: `down_revision = None` (no quotes) is correctly rewritten to `"PENDING"` (with quotes). The value changes from Python None to the string sentinel.
- [ ] **No side-effects on other lines**: the regex uses `re.MULTILINE` and replaces only the first match. Confirm a file with `down_revision` appearing in a comment or docstring does not get rewritten.
- [ ] **Exit codes**: 0 on success, 1 on missing file, 1 on missing `down_revision` line.
- [ ] **No project imports**: the script must be usable without the project virtual environment (only stdlib). Check imports.

### Makefile migration-pending target (S01)

- [ ] **MSG guard**: if `MSG` is not set, the target errors before running alembic. Verify with `$(error ...)`.
- [ ] **File selection**: `ls -t orch/db/migrations/versions/*.py | grep -v __pycache__ | head -1` correctly picks the newest file after `alembic revision --autogenerate`. Confirm the sort order is by mtime (most recent first).
- [ ] **Pipe to xargs**: the path is passed correctly to `rewrite_down_revision.py`. No quoting issues with spaces in paths (unlikely for migration files but worth confirming).

### scripts/resolve_pending_migration.py (S02)

- [ ] **Head computation excludes PENDING files**: the head is computed from the real (non-PENDING) migration chain. A PENDING file whose `down_revision` is `"PENDING"` must not be treated as a chain node when computing the real head.
- [ ] **Single PENDING at the end of a real chain**: assert the resolved value equals the most recent real revision, not the initial revision.
- [ ] **Single PENDING with no real chain** (resolver AC for chain-root case): the resolved file contains the substring `down_revision = None` (bare Python `None`, unquoted). The substring `down_revision = "None"` (quoted) MUST be absent — a quoted `"None"` is a string literal that Alembic would attempt to resolve as a revision ID, causing `Can't locate revision identified by 'None'`. Open the resolver source and confirm the chain-root branch writes `None` without surrounding quotes. Verify test 3 in `test_resolve_pending_migration.py` asserts the exact unquoted form.
- [ ] **Pre-existing fork detection**: if the real chain already has multiple heads, the script exits 1 with a clear message. It does NOT attempt to resolve — that would mask a pre-existing problem.
- [ ] **Multi-PENDING out of scope**: confirm the resolver leaves PENDING→PENDING links unresolved (only the root PENDING is rewritten). This matches the design doc Notes.
- [ ] **No project imports**: stdlib only, same rule as the rewrite script.

### Makefile migration-check update (S02)

- [ ] **Resolver runs before pytest**: the target calls `resolve_pending_migration.py` first. If the resolver exits 1 (pre-existing fork), `make migration-check` should fail before running the testcontainer. Verify make propagates the exit code (no `@-` prefix suppressing failures).
- [ ] **AC4 regression**: running `make migration-check` against the existing migration chain (no PENDING files) must produce the same result as before. The resolver's "nothing to do" path must not alter any files.

### orch/daemon/migration_rebase.py (S02)

- [ ] **Comment only**: confirm no logic was changed. Diff the file and verify only a comment was added in Step 8.
- [ ] **Comment accuracy**: the comment correctly identifies `"PENDING"` as the CR-00091 sentinel and correctly states why no special-casing is needed.

### Tests (S01 + S02)

- [ ] **tdd_red_evidence**: both S01 and S02 reports contain a plausible `AssertionError` snippet from the RED run, not an `ImportError` or collection error.
- [ ] **Test isolation**: all unit tests use `tmp_path` — no tests read from `orch/db/migrations/versions/` directly.
- [ ] **Mutation-test heuristic**: for each assertion, ask "would this assertion fail if the production code it covers regressed?" Flag any assertions that would pass even if the implementation were broken (e.g., asserting only that the file exists, not its content).
- [ ] **Integration test scope**: `test_migration_check_resolves_pending_before_round_trip` does NOT spin a testcontainer — it only validates the resolver produces a valid chain. Verify it does not import `PostgresContainer` or similar.
- [ ] **Existing round-trip test unchanged**: the existing `upgrade head → schema parity → downgrade → upgrade` test sequence is unmodified and still passes.

## Findings Format

Report findings as: `CRITICAL | HIGH | MEDIUM | LOW — <file>:<line> — <description>`.

CRITICAL: logic bug, wrong exit code, PENDING not idempotent, resolver corrupts real chain.
HIGH: missing test case for a documented AC, no-project-import rule violated.
MEDIUM: comment inaccurate, makefile fragility, suboptimal regex.
LOW: style, naming, missing docstring.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "code-review-impl",
  "work_item": "CR-00091",
  "completion_status": "complete|blocked",
  "files_reviewed": [
    "scripts/rewrite_down_revision.py",
    "scripts/resolve_pending_migration.py",
    "Makefile",
    "orch/daemon/migration_rebase.py",
    "tests/unit/test_rewrite_down_revision.py",
    "tests/unit/daemon/test_migration_rebase.py",
    "tests/unit/test_resolve_pending_migration.py",
    "tests/integration/test_migrations_round_trip.py"
  ],
  "findings": [],
  "blockers": [],
  "notes": ""
}
```
