# CR-00032_S02_CodeReview_Template_prompt

**Work Item**: CR-00032 — Add test-location and assertion-scoping guidance to Issue Design Template
**Step Being Reviewed**: S01 (template-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following or any command that changes Docker
container/volume/network state. Allowed: testcontainers spun up by pytest
fixtures, read-only introspection (`docker ps`, `docker inspect`,
`docker logs`), and invoking `./ai-core.sh` / `make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Not applicable — this CR adds no migrations. Do not run any `alembic` command.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status CR-00032 --json` over the manifest snapshot (CR-00023).
- `ai-dev/active/CR-00032/CR-00032_CR_Design.md` — design document (acceptance criteria are in this file)
- `ai-dev/active/CR-00032/reports/CR-00032_S01_Template_report.md` — implementation report
- `templates/design/Issue_Design_Template.md` — file changed by S01
- `ai-dev/templates/Issue_Design_Template.md` — file changed by S01 (via `iw sync-templates`)

## Output Files

- `ai-dev/active/CR-00032/reports/CR-00032_S02_CodeReview_report.md` — review report

## Context

You are reviewing a markdown-only edit to the master Issue Design Template,
plus the propagation of that edit to the local project's `ai-dev/templates/`
copy via `iw sync-templates`. There is no Python code, no test, no schema
change to review. Your review is **prose-and-process focused**:

1. Did the wording satisfy the design's AC1 and AC2 unambiguously?
2. Did the sync step propagate cleanly (AC3)?
3. Did S01 stay within the allowed file scope (AC4)?

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run on the files in S01's `files_changed`:

```bash
make lint          # ruff check
make format        # ruff format --check
```

Both should be no-ops for `.md` files. If either reports a NEW violation
(not present on `main` before S01), classify it CRITICAL with category
`conventions` per the standard contract.

If `make` is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. AC1 — Test-location rule (in "Test to Reproduce" section)

Open `templates/design/Issue_Design_Template.md` and confirm:

- [ ] A new paragraph is present in the "Test to Reproduce" section.
- [ ] The paragraph names all three directories: `tests/dashboard/`,
      `tests/unit/`, `tests/integration/`.
- [ ] The paragraph names the `client` fixture and states that
      FastAPI/Jinja2-driven tests must live under `tests/dashboard/` because
      that's where the fixture is registered.
- [ ] The paragraph names `tests/unit/` for pure-Python helpers and
      `tests/integration/` for testcontainer-DB tests.
- [ ] I-00067 is cited (parenthetical or footnote-style is fine).

If any bullet above is missing, classify the gap as **HIGH** category
`completeness` (the design's AC1 is the binding contract).

### 2. AC2 — Assertion-scoping rule (in "TDD Approach" section)

Confirm:

- [ ] A new paragraph (or fourth bullet + paragraph) is present in the
      "TDD Approach" section.
- [ ] The paragraph names the failure mode: substring matches in JS
      strings, `data-*` attributes, comments, or CSS source maps.
- [ ] The unsafe form is shown: e.g., `assert "my-class" in html`.
- [ ] The safe form is shown: e.g., `assert 'class="my-class"' in html`
      or an equivalent attribute-anchored regex.
- [ ] I-00067 is cited (can share the AC1 citation).

If any bullet above is missing, classify as **HIGH** category `completeness`.

### 3. AC3 — Sync propagated cleanly

From S01's report `notes` field, confirm `iw sync-templates` ran cleanly
and reported `Issue_Design_Template.md` under "updated" for all four
projects (`innoforge`, `iw-ai-core`, `cv`, `Podforger`).

Then independently re-verify:

```bash
diff -q templates/design/Issue_Design_Template.md ai-dev/templates/Issue_Design_Template.md
```

Expected: empty output, exit 0. If the files differ, classify as **CRITICAL**
category `consistency` — the local sync didn't take effect.

You CANNOT diff against the other three projects' copies from this worktree
(they live outside the repo). Accept S01's captured stdout as evidence and
note in the review whether the captured stdout claims success for all four
projects.

### 4. AC4 — Diff scope is bounded

Run:

```bash
git diff --name-only main..HEAD
```

Files outside the manifest's `scope.allowed_paths` are CRITICAL findings
(category `architecture`). The allow list is:

- `templates/design/Issue_Design_Template.md`
- `ai-dev/templates/Issue_Design_Template.md`
- `ai-dev/active/CR-00032/**`
- `ai-dev/archive/CR-00032/**`

If S01 modified anything else (test file, fixture, CLAUDE.md, another
template, etc.), file a CRITICAL.

### 5. Wording quality (prose-level)

- [ ] Tone matches the surrounding template (declarative, second person, no
      jargon the template doesn't already use).
- [ ] No conflicting guidance with elsewhere in the template (e.g., the
      template's TDD section and the new paragraph must agree).
- [ ] No literal AI-isms ("Let's", "I'll", "we'll see") — the template is
      addressed to a human author, not first person.
- [ ] No new heading was introduced (the rules belong inside the existing
      sections).

Wording problems are typically **MEDIUM (fixable)** category `code_quality`,
unless they actually contradict an AC, in which case they bump to HIGH.

### 6. Out-of-scope edits the agent might have been tempted to make

Flag CRITICAL if any of these were touched:

- A new test file under `tests/` that asserts the template contains the new
  strings (the design doc explicitly forbids this).
- Other design templates (`Feature_*`, `CR_*`, `Functional_*`, prompt
  templates).
- `CLAUDE.md`.
- Any production source file.

## Test Verification (NON-NEGOTIABLE)

Run `make test-unit` and confirm no regression. Markdown-only changes
should not affect tests; if they do, that's a CRITICAL signal that
something else was touched.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | AC violation, scope leak, sync didn't take effect | Must fix |
| **HIGH** | Missing required wording, missing citation | Must fix |
| **MEDIUM (fixable)** | Wording could be clearer, code-span style off | Should fix |
| **MEDIUM (suggestion)** | Alternative phrasing | Optional |
| **LOW** | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "CR-00032",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|consistency|completeness",
      "file": "templates/design/Issue_Design_Template.md",
      "line": 0,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed (make test-unit)",
  "notes": ""
}
```

- `verdict: pass` requires zero CRITICAL/HIGH/MEDIUM_FIXABLE findings.
- `mandatory_fix_count` = count of CRITICAL + HIGH + MEDIUM_FIXABLE.
