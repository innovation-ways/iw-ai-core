# CR-00032 S02 Code Review Report

## Summary

Reviewed S01 (template-impl) output: two guidance paragraphs added to
`templates/design/Issue_Design_Template.md`, `uv run iw sync-templates` executed
for all 4 registered projects, and no out-of-scope files touched.

## Pre-Review Lint & Format Gate

`make lint` and `make format` were run on the worktree's `files_changed`
(`templates/design/Issue_Design_Template.md`). Both reported pre-existing
violations in `ai-dev/active/I-00068/e2e_fixtures/001_batch_archive_events.py`
— not from CR-00032's edits (that file was never touched by S01). Per the
review contract, this is classified as informational, not a CR-00032 failure.

## AC1 — Test-location rule (in "Test to Reproduce" section)

**Present and correct.** Line 92 of `templates/design/Issue_Design_Template.md`:

- ✅ Names all three directories: `tests/dashboard/`, `tests/unit/`,
  `tests/integration/`
- ✅ Names the `client` fixture and states that FastAPI/Jinja2-driven tests
  must live under `tests/dashboard/`
- ✅ Names `tests/unit/` for pure-Python helpers and `tests/integration/`
  for testcontainer-DB tests
- ✅ Cites I-00067

## AC2 — Assertion-scoping rule (in "TDD Approach" section)

**Present and correct.** Line 161 of `templates/design/Issue_Design_Template.md`:

- ✅ Names the failure mode: substring matches in JS strings, `data-*`
  attributes, comments, CSS source maps
- ✅ Shows the unsafe form: `assert "my-class" in html`
- ✅ Shows the safe form: `assert 'class="my-class"' in html` or equivalent regex
  `class\s*=\s*"[^"]*my-class[^"]*"`
- ✅ Cites I-00067

## AC3 — Sync propagated cleanly

**Evidence accepted; local worktree copy diverges (expected).**

S01's report captures `iw sync-templates` stdout confirming all four projects
(`innoforge`, `iw-ai-core`, `cv`, `Podforger`) reported "0 updated, 13 up to
date" — meaning the master and all four project copies were byte-identical
at the time S01 ran the command.

However, in this CR-00032 worktree, `ai-dev/templates/Issue_Design_Template.md`
**differs** from `templates/design/Issue_Design_Template.md`. Running:

```bash
diff -q templates/design/Issue_Design_Template.md ai-dev/templates/Issue_Design_Template.md
```

from the worktree root returns "Files differ".

**This is expected behavior.** Per S01's report notes (and confirmed by
`orch/cli/skills_commands.py:155-219`), `iw sync-templates` writes to each
project's `repo_root` from the database — which points to the main project
directories, not to git-worktree directories. The CR-00032 worktree's
`ai-dev/templates/` is a separate directory outside the repo, untouched by
`sync-templates`. The S01 report acknowledges this explicitly.

For the purposes of AC3 verification from this worktree, the S01-captured
stdout (showing success for all four projects) is accepted as sufficient
evidence. The design doc's AC3 explicitly acknowledges that "copies in other
registered projects' worktrees live outside this repo" and cannot be
diff-checked from here.

## AC4 — Diff scope is bounded

**Clean.** `git diff --name-only main..HEAD` shows only
`templates/design/Issue_Design_Template.md` as a modified tracked file.
The `ai-dev/templates/` directory is untracked in this worktree (as expected
for a worktree). No file outside the manifest's `scope.allowed_paths` was
touched.

## Wording Quality (prose-level)

- Tone is declarative and matches the surrounding template (second person,
  no jargon the template doesn't already use).
- No first-person AI-isms ("Let's", "I'll", "we'll see").
- No new heading was introduced; both rules are inline callouts within the
  existing "Test to Reproduce" and "TDD Approach" sections.
- The two paragraphs do not conflict with each other or with any other
  guidance in the template.

## Out-of-Scope Edits

None detected. S01 did not:

- Add a test file under `tests/` asserting the template contains the new strings
  (the design doc explicitly forbids this)
- Modify any other design template (`Feature_*`, `CR_*`, `Functional_*`, etc.)
- Modify `CLAUDE.md`
- Modify any production source file

## Test Verification

`make test-unit` result:

```
= 2581 passed, 4 skipped, 5 xfailed, 1 xpassed, 47 warnings in 67.04s (0:01:07) =
```

No regression. The markdown-only change did not affect any test.

## Findings

All review checklist items pass. Zero CRITICAL/HIGH/MEDIUM_FIXABLE findings.

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "CR-00032",
  "step_reviewed": "S01",
  "verdict": "pass",
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "2581 passed, 4 skipped, 5 xfailed, 1 xpassed, 47 warnings in 67.04s (make test-unit)",
  "notes": "ai-dev/templates/Issue_Design_Template.md in the CR-00032 worktree differs from the master — this is expected because sync-templates targets project repo_roots, not worktree directories. S01's captured stdout confirms all four registered projects synced successfully. The pre-existing lint/format violations in I-00068 are unrelated to CR-00032."
}
```