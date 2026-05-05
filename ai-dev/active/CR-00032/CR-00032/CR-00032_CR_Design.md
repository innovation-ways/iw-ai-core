# CR-00032: Add test-location and assertion-scoping guidance to Issue Design Template

**Type**: Change Request
**Priority**: Low
**Reason**: Process improvement — prevent recurrence of I-00067 S01's wasted retry budget on test-location and over-broad CSS class assertions
**Created**: 2026-05-05
**Status**: Draft

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This CR adds no migrations — content-only change to design templates.)

---

## Description

The `Issue_Design_Template.md` is silent on two test-authoring concerns that cost
I-00067's S01 two retries (3 runs total): (1) **where** to put the regression
test file, and (2) **how** to scope CSS-class assertions so they don't match the
class name embedded in JS strings or `data-*` payloads. This CR adds inline
guidance in the existing **Test to Reproduce** and **TDD Approach** sections of
the master template at `templates/design/Issue_Design_Template.md`, then
propagates the change to every registered project's `ai-dev/templates/` copy via
`uv run iw sync-templates`.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules.
The orch CLI's `sync-templates` command (in `orch/cli/skills_commands.py`) is
the canonical mechanism for distributing master templates to every entry in
`projects.toml`.

## Current Behavior

`templates/design/Issue_Design_Template.md` (the master) and the four
per-project copies under `ai-dev/templates/Issue_Design_Template.md` (in
`innoforge`, `iw-ai-core`, `cv`, `Podforger`) currently contain:

- A **Test to Reproduce** section with a generic Python TDD scaffold that
  doesn't say which directory the test should live in.
- A **TDD Approach** section that lists `Reproducing test`, `Unit tests`, and
  `Integration tests` with no guidance on assertion granularity for HTML
  responses.

I-00067's S01 had to discover by trial that:
1. The `client` fixture used to drive Jinja2 fragments lives in
   `tests/dashboard/conftest.py`, not in `tests/unit/conftest.py`. A test placed
   under `tests/unit/` raised `fixture 'client' not found` and burned run #1.
2. `assert "activity-message-truncated" in html` matched the bare class-name
   string emitted by an inline `<script>` tag's JSON blob, not the HTML element
   actually carrying the class. The assertion passed without the production
   change. Run #2 was wasted on this false positive before the assertion was
   tightened to `class="activity-message-truncated"`.

Evidence: `ai-dev/active/I-00067/reports/I-00067_self_assess_report.md` finding [1],
quoting `.worktrees/I-00067/ai-dev/logs/I-00067_S01_run1.log:42` and `:498`.

## Desired Behavior

`templates/design/Issue_Design_Template.md` includes two short callouts that
every Issue prompt drafted from the template inherits going forward:

1. **Test location** — when the regression test exercises a Jinja2 template /
   FastAPI route via the dashboard `client` fixture, place it under
   `tests/dashboard/`. When it exercises a pure Python function with no
   FastAPI/template dependency, place it under `tests/unit/`. Integration tests
   that hit the testcontainer DB go under `tests/integration/`.
2. **Assertion scoping for CSS classes** — when asserting that a CSS class
   reaches the rendered HTML, scope the assertion to the attribute form
   (`class="..."`, including the leading `class="` and the closing `"` or space
   boundary) or use a regex that matches the attribute. Do **not** assert on
   the bare class name as a substring of the response body — JS strings,
   `data-*` payloads, comments, and CSS source maps can all carry the same
   token and produce false positives.

After the master is updated, `uv run iw sync-templates` is run (no flags) so
all four project copies become byte-identical to the master.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `templates/design/Issue_Design_Template.md` | "Test to Reproduce" + "TDD Approach" sections silent on directory + assertion scoping | Two paragraphs added with explicit guidance + a positive/negative assertion example |
| `ai-dev/templates/Issue_Design_Template.md` (×4 projects) | Out-of-sync copy | Refreshed by `iw sync-templates` to match the master byte-for-byte |

### Breaking Changes

None. The change is additive prose inside an in-development design template;
no in-flight Issue work item embeds a frozen copy of the template. (Issues
already drafted under `ai-dev/active/I-*/` retain their existing wording —
they were copied at draft time; this CR does not retroactively edit them.)

### Data Migration

Not applicable. Markdown content change only; no DB rows, no schema, no
on-disk artifact format changes.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | template-impl | Edit the master template; run `uv run iw sync-templates`; verify all four project copies match the master | — |
| S02 | code-review-impl | Per-step review of S01: wording is unambiguous, both rules are present, the example contrasts right-vs-wrong assertion form, and `iw sync-templates` left zero diff on all four target copies | — |
| S03 | code-review-final-impl | Cross-step final review against the design doc's acceptance criteria | — |
| S04 | qv-gate (lint) | `make lint` | — |
| S05 | qv-gate (format) | `make format-check` | — |
| S06 | qv-gate (typecheck) | `make typecheck` | — |
| S07 | qv-gate (arch-check) | `make arch-check` | — |
| S08 | qv-gate (security-sast) | `make security-sast` | — |
| S09 | qv-gate (unit-tests) | `make test-unit` | — |
| S10 | qv-gate (integration-tests) | `make test-integration` | — |
| S11 | self-assess-impl | iw-item-analyze post-mortem | — |

The full QV battery is included for parity with CR-00031 (the sibling I-00067
follow-up). None of those gates inspect markdown directly, but running them
keeps the audit trail uniform across self-assess-driven CRs.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: No migration. This CR does not touch `orch/db/`.

### API Changes

- **New endpoints**: None
- **Modified endpoints**: None
- **Removed endpoints**: None

### Frontend Changes

- **New components**: None
- **Modified components**: None
- **Removed components**: None

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `CR-00032_CR_Design.md` | Design | This document |
| `CR-00032_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions (design-time snapshot) |
| `prompts/CR-00032_S01_Template_prompt.md` | Prompt | S01 — Edit master template + sync |
| `prompts/CR-00032_S02_CodeReview_Template_prompt.md` | Prompt | S02 — Per-step review |
| `prompts/CR-00032_S03_CodeReview_Final_prompt.md` | Prompt | S03 — Cross-step final review |
| `prompts/CR-00032_S11_SelfAssess_prompt.md` | Prompt | S11 — Self-assessment |

QV gate steps (S04–S10) read their command from the manifest and do not need a
prompt file.

Reports are created during execution in `ai-dev/active/CR-00032/reports/` (the
executor stamps this path; not pre-created here).

## Acceptance Criteria

### AC1: Test-location rule is present in the master template

```
Given the master file `templates/design/Issue_Design_Template.md` after S01
When a reader scans the "Test to Reproduce" section
Then the section contains a paragraph that explicitly names tests/dashboard/, tests/unit/, and tests/integration/, and states which directory applies for FastAPI/template work driven by the dashboard `client` fixture
```

### AC2: Assertion-scoping rule is present with a contrasting example

```
Given the master file `templates/design/Issue_Design_Template.md` after S01
When a reader scans the "Test to Reproduce" or "TDD Approach" section
Then the section contains a paragraph that names the failure mode (substring matches in JS strings / `data-*` payloads), shows the unsafe form (bare class name), and shows the safe form (`class="..."` attribute match or equivalent regex)
```

### AC3: All four project copies are byte-identical to the master after sync

```
Given the master template has been updated
When `uv run iw sync-templates` is run
Then `filecmp.cmp(master, copy, shallow=False)` returns True for every project's `ai-dev/templates/Issue_Design_Template.md`, including innoforge, iw-ai-core, cv, and Podforger
```

### AC4: Diff scope is bounded to the template files

```
Given the CR is complete
When `git diff main..HEAD --name-only` is inspected
Then the only files outside `ai-dev/active/CR-00032/**` are `templates/design/Issue_Design_Template.md` and `ai-dev/templates/Issue_Design_Template.md` (this project's per-project copy; copies in other registered projects' worktrees live outside this repo)
```

## Rollback Plan

- **Database**: Not applicable.
- **Code**: `git revert <merge-commit>` on `main`. The reverted state restores
  the prior template wording in both the master and the local
  `ai-dev/templates/` copy. To roll back the *other* registered projects, the
  operator runs `uv run iw sync-templates` again from this repo after the
  revert.
- **Data**: No data loss on rollback. No artifacts regenerated, no DB rows
  written, no doc-job side effects.

## Dependencies

- **Depends on**: None. The `iw sync-templates` command already exists
  (verified at `orch/cli/skills_commands.py:155-219`).
- **Blocks**: None.

## Impacted Paths

- `templates/design/Issue_Design_Template.md`
- `ai-dev/templates/Issue_Design_Template.md`
- `ai-dev/active/CR-00032/**`
- `ai-dev/archive/CR-00032/**`

## TDD Approach

- **Unit tests**: None required. The change is markdown content; no Python
  code path is added or modified, so no behavioural unit test would have any
  signal. (We deliberately do **not** add a test that greps the template for
  the new strings — such a test ties prose wording to a unit-test assertion
  and creates fragility every time the template is edited.)
- **Integration tests**: None required.
- **Updated tests**: None.
- **Verification**: AC1 and AC2 are verified by inspection during S02
  per-step review. AC3 is verified by S01 running `filecmp.cmp` (or `diff -q`)
  between the master and each project copy after `iw sync-templates`. AC4 is
  verified by the QV gates running on the merge candidate.

## Notes

- **Why `template-impl` and not `backend-impl`**: CR-00031 used `backend-impl`
  for a similar markdown-only edit (CLAUDE.md). `template-impl` is the more
  semantically accurate slug for "edit a design template" — its agent
  description covers "document and template generation systems". Either
  works; we pick the more accurate one.
- **Why the full QV battery on a markdown change**: parity with CR-00031.
  Each gate is a no-op against `.md` files, but skipping any of them creates a
  bespoke manifest shape that the daemon's gate runner has to special-case.
  The cost of running them is negligible (each gate exits with status 0
  immediately after walking the changed-file list and finding no Python).
- **Out of scope**: This CR does **not** modify `Feature_Design_Template.md`
  or `CR_Design_Template.md`. Both have a different audience (feature/CR
  authors, not bug-fix authors) and different test-strategy sections; the
  I-00067 evidence is specifically about Issue work. If similar drift is
  observed on Feature/CR items in future self-assessments, a follow-up CR
  can extend the same guidance there.
