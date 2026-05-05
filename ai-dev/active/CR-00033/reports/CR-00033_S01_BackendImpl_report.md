# CR-00033 S01 BackendImpl Report

## What was done

Edited `docs/IW_AI_Core_Tech_Stack.md` with three targeted changes:

1. **Added "Tailwind CLI fallback strategy" subsection** (§2.4 Dashboard, inserted between "Why not the current custom CSS from InnoForge dashboard" and "### 2.4. Compression"). The ~100-word subsection covers:
   - Why fallback is needed: incomplete `node_modules` in agent worktrees causes Tailwind CLI failures (cited I-00067)
   - Current state of `make css`: declared in `.PHONY` with no rule body, exits `Nothing to be done`
   - The operative rule: *"When new styling is required and the Tailwind CLI cannot run, append plain CSS rules directly to `dashboard/static/styles.css`."*
   - Why it's safe: the file is served as-is without compilation
   - When NOT to use the fallback: when CLI is known-good and `make css` produces output
   - Forward-looking note: future changes may give `make css` a real rule body; until then this subsection is authoritative guidance

2. **Updated "Why Tailwind CSS via CDN" prose** (~line 95): replaced the original sentence that implied CLI compilation was a routine production path with: *"A standalone Tailwind CLI binary exists for compiling a static stylesheet, but it is not reliable inside agent worktrees today — see 'Tailwind CLI fallback strategy' below."*

3. **Added D3a row to §10 Decisions Log**: `| D3a | Tailwind CLI fallback | Append plain CSS to dashboard/static/styles.css | Tailwind CLI, make css | CLI unreliable in agent worktrees due to incomplete node_modules; plain CSS is served as-is without compilation. |`

## Files changed

- `docs/IW_AI_Core_Tech_Stack.md` (documentation only — no Python, JS, CSS, or Makefile touched)

## Preflight results

| Check | Result | Notes |
|-------|--------|-------|
| `make format-check` | **FAILED** | Pre-existing: `ai-dev/active/I-00068/e2e_fixtures/001_batch_archive_events.py` missing trailing newline. Not touched by this CR. |
| `make typecheck` | **OK** | Zero errors in 224 source files |
| `make lint` | **FAILED** (same pre-existing issue) | `ai-dev/active/I-00068/...` missing trailing newline. Not touched by this CR. |

## Test results

```
make test-unit: 2 failed, 2579 passed
```

Both failing tests (`test_safe_migrate.py::TestApply::test_apply_refuses_in_agent_context` and `test_safe_migrate.py::TestRollback::test_rollback_refuses_in_agent_context`) are **pre-existing failures on `main`** — verified by checking out `main` and running the same tests with identical results. No Python code was modified by this CR, so these failures are unrelated to the documentation change.

## Acceptance criteria verification

- **AC1** (fallback subsection): ✅ Subsection exists with exact header text "### Tailwind CLI fallback strategy", all six content points present including the verbatim rule sentence.
- **AC2** (CDN prose no longer implies CLI reliability): ✅ Original sentence replaced with qualified wording pointing to fallback subsection.
- **AC3** (Decisions Log entry): ✅ D3a row added immediately after D3 with one-line rationale referencing the fallback.
- **AC4** (doc consistency): ✅ §2.4 now references fallback; §10 updated; §6 Makefile is read-only reference only.
- **AC5** (no code changes): ✅ Only `docs/IW_AI_Core_Tech_Stack.md` modified.

## Blockers

None.

## Notes

This is a documentation-only change. TDD (RED/GREEN/REFACTOR) does not apply — there is no testable runtime behavior. The test suite was run as a safety net only.
