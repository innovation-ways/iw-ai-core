# {TYPE}{NNN}_S{NN}_CodeReview_prompt

**Work Item**: {ID} -- {Title}
**Step Being Reviewed**: S{NN} ({Agent})
**Review Step**: S{review_step_NN}

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run the following alembic commands against the live
orchestration DB (port 5433) from an agent context:

```
alembic upgrade head
alembic upgrade <revision>
alembic downgrade <anything>
alembic stamp <anything>
```

Your job in a Database step is to WRITE the migration FILE. The daemon
will apply it as part of the merge pipeline (pre-merge dry-run against
a testcontainer, post-merge apply to live DB). If the migration is
broken, the daemon will refuse to merge the batch.

Allowed for agents:
  - alembic revision --autogenerate -m "..."   (writes a file only)
  - alembic history / current / show           (read-only)
  - Running migrations inside testcontainer fixtures
    (tests/conftest.py does this — agents don't call it directly)

Allowed for OPERATORS only (not agents):
  - uv run iw migrations list-pending          (read-only, safe for anyone)
  - uv run iw migrations dry-run               (testcontainer, safe)
  - uv run iw migrations apply --i-am-operator (refuses if IW_CORE_AGENT_CONTEXT=true)
  - Direct invocation via ./ai-core.sh or make db-migrate (operator entry points)

If your task seems to require applying a migration to the live DB,
STOP and raise a blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — for the current step list, status, prompt paths, gate commands, etc., prefer `uv run iw item-status {ID} --json`. The `workflow-manifest.json` file is a design-time snapshot and may be out of date (CR-00023).
- `ai-dev/work/{ID}/{ID}_{Type}_Design.md` -- Design document
- `ai-dev/work/{ID}/reports/{ID}_S{NN}_{Agent}_report.md` -- Implementation step report
- All files listed in the implementation report's `files_changed`

## Output Files

- `ai-dev/work/{ID}/reports/{ID}_S{review_step_NN}_CodeReview_report.md` -- Review report

## Context

You are reviewing the implementation work done in step S{NN} by {Agent} for **{Work Item Title}**.

Read the design document to understand what was intended. Read the implementation report to understand what was done. Then review all changed files.

## Read the Design Document FIRST

Read the design document **before** running the lint/format gate and **before** opening any changed files. Specifically:

- Read the `## Acceptance Criteria` section in full — every criterion is a mandatory check, not a suggestion.
- Read the `## TDD Approach` section in full — note every test file the design names by path.
- Write down every test file the design doc mentions; carry these expectations into the `## Review Checklist` below as a first-class anchor.
- Cross-check every named test file against the implementation report's `files_changed`. If the design doc explicitly names a test file that should have changed and it does not appear in `files_changed`, that is a **CRITICAL** finding.
- **Distrust "no production code change needed" when the work introduces a new data shape.** If the design claims an existing render/code path is correct and untouched, *but* this item adds a fixture, seed, or migration that produces values that path has never seen before (a non-NULL timestamp where prod rows are NULL, a fix-cycle row, an enum value, an empty collection, …), independently re-trace the **whole** path that new shape flows through — not just the lines the feature touches. Latent crashes hide in the parts the design didn't think to mention (I-00075: a `"{}m{}s"|format(...)` line in a shared template that only 500-ed once a fixture seeded steps with real durations — the design said the render path was "correct"). If you find such a defect, flag it even though the design says "no change needed"; note whether the file is inside this item's `scope.allowed_paths` (if not, it needs a follow-up item, not a fix cycle).

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading any code, run these two commands on the files listed in the
implementation report's `files_changed`. Fix nothing yourself — only report.

```bash
make lint          # ruff check — catches ARG001, F811, unused imports, etc.
make format  # ruff format --check — catches formatting drift (does NOT auto-fix)
```

If either command reports NEW violations in the changed files (i.e., violations
that do not appear on the `main` branch before this step), classify each one as
a **CRITICAL** finding in your review result contract with:
- `"category": "conventions"`
- `"file"` and `"line"` from the tool output
- `"description"` quoting the exact violation code and message

If a command is unavailable (e.g., `make` not found), STOP and raise a blocker.
Do NOT skip this step or mark it as optional.

## Scope Discipline — Implicitly Allowed Paths (READ BEFORE FLAGGING SCOPE CREEP)

When checking the diff against `workflow-manifest.json` → `scope.allowed_paths`,
the daemon **also** allows these three paths implicitly (it writes them itself
during the workflow):

- `ai-dev/active/<ITEM_ID>/**` — the work item's prompts, manifest, design doc
- `ai-dev/archive/<ITEM_ID>/**` — archived assets
- `ai-dev/work/<ITEM_ID>/**` — reports, intermediate outputs, logs

Edits under these three paths are **NOT** scope-creep findings, even when the
manifest doesn't list them. The merge-time scope gate (`executor/scope_gate.py`)
and the fix-cycle reconciliation (`orch/daemon/fix_cycle.py:_implicit_allows`)
both whitelist them.

Flagging `ai-dev/work/<ID>/` as scope creep was a recurring failure pattern
(diagnosed 2026-05-25 from CR-00082's 11-run review thrash). Do not repeat it.

### Scope diff — use directional, not symmetric

When you check whether this step added anything outside `scope.allowed_paths`,
use a **directional** diff. `git diff main -- <paths>` is symmetric — it also
flags paths where `main` is *ahead* of the branch (CRs that merged while this
item was running), which is not a scope violation by this step.

```bash
# What this step + branch ADDS vs main (triple-dot = merge-base(main, HEAD)..HEAD):
git diff main...HEAD --name-only -- <forbidden-paths>
git status -s -- <forbidden-paths>          # also check uncommitted working tree
```

If both are empty for `<forbidden-paths>`, the step is in scope. If the design
doc's Invariant section quotes `git diff main` (two-dot), treat it as shorthand
for the directional form and run the commands above. Diagnosed 2026-05-26
from F-00089 S10's 11-run thrash on this exact mis-reading.

## Test Verification — Coverage Note

When the design's test verification step is a NARROW pytest target (e.g.
`uv run pytest tests/<module>/ -v`), that command will NOT hit the
project's coverage gate — coverage is opt-in via the make targets that own
full-suite gating (`make test-unit`, `make test-integration`, etc.). If a
prior version of the design embedded `pytest <narrow path>` AND that command
exits non-zero with a `coverage.exceptions.CoverageException` / "Total
coverage ... is less than fail_under", the design is referencing a stale
behaviour. Treat coverage failures on narrow targeted-test runs as a
project-config bug (not a code defect) and call it out under blockers.

## Review Checklist

### 1. Architecture Compliance

- Does the implementation match the design document's architecture?
- Are layer boundaries respected (no cross-layer imports)?
- Are the right patterns used for the project's framework?
- Read `CLAUDE.md` for project-specific architecture rules.

### 2. Code Quality

- Is the code clear, readable, and well-structured?
- Are there any obvious bugs, logic errors, or edge cases missed?
- Is error handling appropriate and consistent?
- Are there any performance concerns?
- Is there unnecessary duplication?

### 3. Project Conventions

- Read `CLAUDE.md` for all project conventions.
- Do naming conventions match the project's style?
- Is the code formatted according to project rules?
- Are imports organized correctly?

### 4. Security

- No hardcoded secrets, credentials, or API keys
- Input validation where user data enters the system
- No SQL injection, XSS, or other injection vulnerabilities
- Proper authorization checks where applicable

### 5. Testing

- Are all new public functions/methods tested?
- Do tests cover edge cases and error paths?
- Are tests isolated and deterministic?
- Do test names clearly describe what they verify?
- Do test files cover the assertions the design doc's TDD section calls out by name? If a TDD-section test file is missing from `files_changed`, raise a CRITICAL finding.

### 5a. TDD RED Evidence (behaviour-implementing steps only)

**Applies when the reviewed step is a behaviour-implementing step (notably Backend);
dedicated coverage steps (`tests-impl`) are exempt.**

1. **Confirm `tdd_red_evidence` is present and plausible.** For any new behavioural
   test added by the step, verify the report's `tdd_red_evidence` field records
   `run the new failing test` (the RED run) and shows a plausible failure snippet
   (`AssertionError` / `NotImplementedError`, not an `ImportError`, `SyntaxError`,
   or collection error). If the step added no behavioural test, verify the report
   uses `"n/a — <one-line reason>"`.
2. **Reason about whether the test would actually fail against pre-change code.** For
   at least one new behavioural test, evaluate whether it would fail against the
   production code *before* the change was applied. A test that passes without the
   new code is **not** a RED-first test — flag it as a HIGH finding.
3. **(Optional) Stash-recheck.** When quick and safe, you may scope-stash only the
   production-code hunks for that test's target, re-run the test to see it fail, then
   restore. State explicitly that this step was performed. This step is **optional**
   and **not mandatory** because a `git stash` mid-workflow in the worktree is risky.
   The mandatory parts are steps 1 and 2.

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. Run the project's unit test command to verify no regressions
2. Report test results accurately in the result contract

## Severity Levels

Classify each finding with one of these severities:

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Breaks functionality, data loss risk, security vulnerability | Must fix before merge |
| **HIGH** | Significant bug, missing requirement, architectural violation | Must fix before merge |
| **MEDIUM (fixable)** | Code quality issue, missing edge case, convention violation | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Design improvement, better pattern available | Optional, author decides |
| **LOW** | Nitpick, style preference, minor readability | Informational only |

## Review Result Contract

```json
{
  "step": "S{review_step_NN}",
  "agent": "CodeReview",
  "work_item": "{ID}",
  "step_reviewed": "S{NN}",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

- `verdict`: Use `pass` if there are zero CRITICAL or HIGH findings AND zero MEDIUM (fixable) findings. Use `fail` if any mandatory fixes are needed.
- `mandatory_fix_count`: Count of CRITICAL + HIGH + MEDIUM (fixable) findings.
- Only CRITICAL, HIGH, and MEDIUM (fixable) findings trigger a fix cycle. MEDIUM (suggestion) and LOW are informational.
