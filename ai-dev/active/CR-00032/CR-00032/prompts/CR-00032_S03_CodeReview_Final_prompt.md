# CR-00032_S03_CodeReview_Final_prompt

**Work Item**: CR-00032 — Add test-location and assertion-scoping guidance to Issue Design Template
**Review Step**: S03 (Final Review)
**Implementation Steps Reviewed**: S01..S02

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

- **Runtime step state** — `uv run iw item-status CR-00032 --json` is authoritative (CR-00023).
- `ai-dev/active/CR-00032/CR-00032_CR_Design.md` — design document
- `ai-dev/active/CR-00032/CR-00032_Functional.md` — functional design
- `ai-dev/active/CR-00032/reports/CR-00032_S01_Template_report.md` — S01 implementation report
- `ai-dev/active/CR-00032/reports/CR-00032_S02_CodeReview_report.md` — S02 review report
- `templates/design/Issue_Design_Template.md` — primary changed file
- `ai-dev/templates/Issue_Design_Template.md` — secondary changed file (sync'd from master)

## Output Files

- `ai-dev/active/CR-00032/reports/CR-00032_S03_CodeReview_Final_report.md` — final review report

## Context

You are performing the **final cross-step review** of CR-00032. The CR has only
one implementation step (S01) and one per-step review (S02), so the cross-step
surface is small — but you must still validate the work *as a whole* against
the design's acceptance criteria, the manifest's `scope.allowed_paths`, and
the project's rule that template edits must be propagated through
`iw sync-templates`.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

Both should be no-ops for `.md` changes. Any NEW violation in changed files
is a CRITICAL finding (`category: conventions`).

If `make` is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. Completeness vs. Design Document

Walk each acceptance criterion and confirm it's satisfied:

- **AC1** (test-location rule): paragraph present in "Test to Reproduce",
  names all three directories, names the `client` fixture, cites I-00067.
- **AC2** (assertion-scoping rule): paragraph present in "TDD Approach",
  names the failure mode, shows unsafe + safe forms.
- **AC3** (byte-identical local copy): `diff -q templates/design/Issue_Design_Template.md ai-dev/templates/Issue_Design_Template.md`
  returns exit 0 with empty output.
- **AC4** (bounded diff): `git diff --name-only main..HEAD` reveals only
  the four allowed paths.

Any AC not satisfied is automatically a CRITICAL finding (treat as
`missing_requirements`).

### 2. Cross-Step Consistency

- The S02 review's `verdict` should be `pass`. If it's `fail` and S01 was
  re-run via fix cycles, confirm the latest S01 report supersedes the
  earlier ones and the file is now correct.
- The S01 report's `files_changed` should match exactly:
  `templates/design/Issue_Design_Template.md` and
  `ai-dev/templates/Issue_Design_Template.md`. Anything else is a scope
  leak (CRITICAL, category `architecture`).

### 3. Sync Verification (cross-project, best-effort)

You cannot reach the other three projects' worktrees from here, but you can
re-run the dry check:

```bash
uv run iw sync-templates --check --project iw-ai-core
```

Expected output: `Issue_Design_Template.md` under "up_to_date" (already
sync'd). If it appears under "needs_update", S01's sync didn't take, which
is a CRITICAL finding category `consistency`.

For the other three projects:

```bash
uv run iw sync-templates --check
```

Read the output carefully. Any project where `Issue_Design_Template.md` is
under "needs_update" means that project's worktree has a stale copy. That's
expected on first run if S01 wrote only locally without `iw sync-templates`,
but S01 was instructed to run the full sync — so a stale entry here is a
CRITICAL category `consistency`.

### 4. Functional Doc Alignment

Open `CR-00032_Functional.md` and confirm:

- The "What Changed (for the User)" bullets correspond to AC1+AC2.
- The "Out of Scope" entry matches the design's "Notes" section
  (Feature/CR template extension is deferred).
- No file paths, code fences, or implementation jargon (the iw-review-design
  skill flags those as warnings).

### 5. CLAUDE.md / Convention Compliance

- The CR did NOT add a memory-style "ALWAYS run `iw sync-templates`" hook in
  CLAUDE.md (out of scope; that would be a separate CR).
- The CR did NOT modify `Feature_Design_Template.md` or
  `CR_Design_Template.md` (out of scope per the design's Notes section).
- The CR did NOT add a test that greps the template for the new strings
  (explicitly forbidden by the design's TDD Approach section).

Each of those is a CRITICAL finding category `architecture` if violated.

### 6. Security (cross-cutting)

No security surface — markdown content only. Skip unless a hardcoded
credential/path slipped into the prose somehow.

## Test Verification (NON-NEGOTIABLE)

Run the full unit test suite:

```bash
make test-unit
```

Markdown changes should not affect tests; a new failure here points at
something else having been touched (CRITICAL signal).

You do NOT need to run `make test-integration` here — the QV gates (S10)
will run it next. But if you do run it, report the result.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | AC violation, scope leak, sync didn't take effect, regression | Must fix |
| **HIGH** | Cross-step inconsistency, missing citation, functional doc out of sync with technical doc | Must fix |
| **MEDIUM (fixable)** | Wording could be clearer | Should fix |
| **MEDIUM (suggestion)** | Alternative phrasing | Optional |
| **LOW** | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S03",
  "agent": "code-review-final-impl",
  "work_item": "CR-00032",
  "steps_reviewed": ["S01", "S02"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "completeness|consistency|architecture|conventions",
      "file": "templates/design/Issue_Design_Template.md",
      "line": 0,
      "description": "What the issue is",
      "suggestion": "How to fix it",
      "cross_cutting": false
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```

- `verdict: pass` requires zero CRITICAL/HIGH/MEDIUM_FIXABLE findings.
- `missing_requirements` is the canonical place to list any AC that wasn't
  satisfied (each entry is automatically CRITICAL).
