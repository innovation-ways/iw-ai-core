# CR-00032_S01_Template_prompt

**Work Item**: CR-00032 — Add test-location and assertion-scoping guidance to Issue Design Template
**Step**: S01
**Agent**: template-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following or any command that changes Docker
container/volume/network state. Allowed: testcontainers spun up by pytest
fixtures, read-only introspection (`docker ps`, `docker inspect`,
`docker logs`), and invoking `./ai-core.sh` / `make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Not applicable — this CR adds no migrations. Do not run any `alembic` command
during this step.

## Input Files

- `ai-dev/active/CR-00032/CR-00032_CR_Design.md` — design document (read **Current Behavior**, **Desired Behavior**, and **Acceptance Criteria** sections)
- `templates/design/Issue_Design_Template.md` — master template you will edit (line ~88 "Test to Reproduce" section, line ~153 "TDD Approach" section)
- `ai-dev/active/I-00067/reports/I-00067_self_assess_report.md` — finding [1] is the source incident; quote it lightly so future readers see the provenance
- `orch/cli/skills_commands.py:155-219` — the `sync-templates` implementation; consult to confirm the command's semantics (it does a `filecmp.cmp(..., shallow=False)` and `shutil.copy2` per project)

## Output Files

- `templates/design/Issue_Design_Template.md` — modified (master)
- `ai-dev/templates/Issue_Design_Template.md` — modified (this project's copy, written by `iw sync-templates`)
- `ai-dev/active/CR-00032/reports/CR-00032_S01_Template_report.md` — your step report

The other three registered projects (`innoforge`, `cv`, `Podforger`) will also
receive copies via `iw sync-templates`, but those land outside this repo's
worktree and are not part of `files_changed` from this step's perspective.

## Context

You are editing the **master** copy of the Issue Design Template. The template
currently says nothing about test-file location or HTML assertion scoping,
which let I-00067 S01 burn two retries on preventable mistakes. Your job is
to add two short, prescriptive paragraphs into the existing template
sections, then run `uv run iw sync-templates` so every registered project
gets the refreshed copy.

This is a **content-only** edit. You are not adding code, fixtures, or
tests; you are not touching CLAUDE.md; you are not touching any other
template file (Feature, CR, Functional, Implementation, etc.).

## Requirements

### 1. Edit the master template

Open `templates/design/Issue_Design_Template.md` and apply two edits.

**Edit A — inside the "Test to Reproduce" section (currently lines 88–103),
immediately under the section heading, before the existing `def test_...`
fenced code block.** Add a paragraph that:

- Names `tests/dashboard/`, `tests/unit/`, and `tests/integration/` as the
  three regression-test homes.
- States the rule: tests that drive a FastAPI route or render a Jinja2
  template via the dashboard `client` fixture **must** live under
  `tests/dashboard/` because the `client` fixture is registered in
  `tests/dashboard/conftest.py`. A test placed elsewhere will fail with
  `fixture 'client' not found`.
- States: tests for pure Python helpers with no FastAPI/template dependency
  go under `tests/unit/`. Tests that exercise the testcontainer DB go under
  `tests/integration/`.
- Briefly cites I-00067 (one short parenthetical) so the provenance is
  discoverable.

**Edit B — inside the "TDD Approach" section (currently lines 153–157),
under the existing bullet list.** Add a paragraph (or a fourth bullet
followed by a short paragraph) that:

- Names the failure mode: "asserting a bare CSS class name as a substring of
  the response body can match the same string emitted by an inline `<script>`
  tag's JSON, a `data-*` attribute, a comment, or a CSS source map — and
  produce a false-positive PASS even when the production change isn't
  applied."
- Shows the **unsafe** form as an example: `assert "my-class" in html`.
- Shows the **safe** form as an example: `assert 'class="my-class"' in html`
  (or equivalent: a regex that anchors on `class\s*=\s*"...my-class..."`).
- Briefly cites I-00067 (one short parenthetical, can share the same
  citation as Edit A).

Both new paragraphs should be 4–8 lines each. Match the surrounding prose
style: declarative sentences, code spans for path/identifier names, no
headings. Do NOT introduce a new H3 — the rules belong inside the existing
sections.

### 2. Sync to all registered projects

After saving the master file, run from the repo root:

```bash
uv run iw sync-templates
```

The command iterates every project in `projects.toml` and copies the
12 templates from `templates/design/` to each project's
`ai-dev/templates/`. Confirm the command exits 0 and reports `Issue_Design_Template.md`
under the "updated" list for each of the four projects (`innoforge`,
`iw-ai-core`, `cv`, `Podforger`). Capture the full stdout in your step
report.

### 3. Verify the local copy is byte-identical

After the sync, run:

```bash
diff -q templates/design/Issue_Design_Template.md ai-dev/templates/Issue_Design_Template.md
```

Expected output: empty (files are identical, exit 0). Capture this in your
report.

For the other three projects' copies, you do NOT need to verify by reading
the files — they live outside this repo's worktree. The `sync-templates`
command's own `filecmp.cmp(..., shallow=False)` check is the source of
truth; quote the command's stdout in your report as evidence.

### 4. Do NOT touch anything else

- Do NOT edit `Feature_Design_Template.md`, `CR_Design_Template.md`,
  `Functional_Design_Template.md`, or any prompt template.
- Do NOT edit `CLAUDE.md`.
- Do NOT edit any test file, fixture, conftest, or production code.
- Do NOT edit existing `ai-dev/active/I-*/` issue designs (those are frozen
  copies of the template at draft time — retroactive edits are out of
  scope).
- Do NOT add a new test that greps the template for the new strings (see the
  design doc's "TDD Approach" — such a test couples prose wording to a
  test assertion and is fragile).

If `uv run iw sync-templates` raises any error or modifies a file you didn't
expect, STOP and raise a blocker.

## Project Conventions

Read `CLAUDE.md` for project-wide rules. Specifically relevant here:

- The `iw` CLI is the canonical orchestration entry point — never bypass it
  with manual `cp` of templates.
- Template edits under `templates/design/` are the master; `ai-dev/templates/`
  copies are derived and must be regenerated via `iw sync-templates` after
  every master edit (see the `feedback_templates_sync.md` memory entry).

## TDD Requirement

This step has **no** RED→GREEN→REFACTOR cycle because no behavioural code is
added. The verification is by inspection (acceptance criteria AC1–AC4) and
by `diff -q` after sync. Document this in your step report under "TDD
Approach: not applicable — content-only template edit; verification is by
inspection and filecmp".

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`, run these in order:

1. **`make format`** — should be a no-op (no `.py`/`.js` files changed). Confirm
   it doesn't unexpectedly modify any unstaged file.
2. **`make typecheck`** — should be a no-op for your changes (no Python touched).
   Pre-existing typecheck errors elsewhere are not yours to fix; note them in
   your report but do not silence them.
3. **`make lint`** — should be a no-op for your changes.

If any of these surfaces a NEW error attributable to your edits, fix it
before completion.

In your `preflight` block:
- `format`: `"ok"` (or `"fixed"` only if the tool unexpectedly reformatted
  something).
- `typecheck`: `"ok"`.
- `lint`: `"ok"`.

## Test Verification (NON-NEGOTIABLE)

Run `make test-unit` once after the edit to confirm no test regression
(none expected, since no Python changed). Report the count.

`make test-integration` is not required at this step — the QV gates (S10)
will run it later.

Do **NOT** report `tests_passed: true` unless `make test-unit` runs to
completion with zero failures.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "template-impl",
  "work_item": "CR-00032",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "templates/design/Issue_Design_Template.md",
    "ai-dev/templates/Issue_Design_Template.md"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed (make test-unit)",
  "blockers": [],
  "notes": "iw sync-templates output: <summary>; diff -q master vs. local copy: empty (identical)."
}
```

- Set `completion_status: complete` only if all four ACs are satisfiable by
  inspection of the changed files plus the `iw sync-templates` stdout you
  captured.
- If `iw sync-templates` failed for any project, set
  `completion_status: blocked` and put the failing project + error in
  `blockers`.
