# CR-00031 S01 Backend Report

## What Was Done

Added a single new bullet to the `## Critical Rules` section of `CLAUDE.md`, immediately before the `## Configuration` section (line 56).

The new bullet reads:

> **MUST** append plain CSS rules directly to `dashboard/static/styles.css` when `make css` reports "Nothing to be done" or the Tailwind CLI fails (e.g., missing `postcss-selector-parser`) — plain CSS is served as-is, so no Tailwind recompile is required. Temporary mitigation until the Tailwind toolchain is repaired in worktrees (see I-00067).

## Files Changed

| File | Change |
|------|--------|
| `CLAUDE.md` | Added 1 bullet to `## Critical Rules` section |

## Diff Verification

```
- **NEVER** run `docker compose up` (with or without `-d db`) against the orchestration DB ...
+- **MUST** append plain CSS rules directly to `dashboard/static/styles.css` when `make css` ...
```

Only the new bullet was added. No other section of `CLAUDE.md` was touched. No reformatting of existing content.

## Acceptance Criteria Check

| AC | Description | Status |
|----|-------------|--------|
| AC1 | Critical Rule exists with symptom + action | ✅ |
| AC2 | Rule references I-00067 inline | ✅ |
| AC3 | Only CLAUDE.md changed; only Critical Rules section modified | ✅ |
| AC4 | Uses **MUST**, consistent with surrounding NEVER/MUST/CRITICAL/NEW style | ✅ |
| AC5 | Explicitly marked as temporary mitigation until Tailwind toolchain repaired (see I-00067) | ✅ |

## Preflight Quality Gates

| Gate | Result | Notes |
|------|--------|-------|
| `make format` | ❌ pre-existing | Lint errors in `ai-dev/active/I-00070/...` pre-exist and are unrelated to this change |
| `make lint` | ❌ pre-existing | Same pre-existing errors in `I-00070` fixture, not touched by this change |
| `make typecheck` | not run | Python files not touched by this change |

The lint/format failures are in `ai-dev/active/I-00070/e2e_fixtures/001_seed_self_assess_finding.py` — a file not modified by this CR. The diff against `CLAUDE.md` is a single-line bullet addition with no Python or formatting impact.

## Test Results

- **Unit tests**: skipped (doc-only change, no runtime behavior)
- **Integration tests**: skipped (doc-only change, no runtime behavior)

## Blockers

None.

## Notes

The lint/format issues are pre-existing in the worktree (I-00070 fixture file) and are unrelated to CR-00031. The diff confirms a clean, single-bullet addition to `CLAUDE.md` satisfying all five acceptance criteria.