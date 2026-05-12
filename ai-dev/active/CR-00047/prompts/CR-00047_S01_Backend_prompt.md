# CR-00047_S01_Backend_prompt

**Work Item**: CR-00047 -- Coverage gates — raise the floor, ratchet it, and gate diff-coverage on PRs (P1-CR-B)
**Step**: S01
**Agent**: backend-impl

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

- **Runtime step state** — for the current step list, status, prompt paths, gate commands, etc., prefer `uv run iw item-status CR-00047 --json`. The `workflow-manifest.json` file is a design-time snapshot and may be out of date (CR-00023).
- `ai-dev/work/CR-00047/CR-00047_CR_Design.md` -- Design document
- Previous step reports (if applicable): `ai-dev/work/CR-00047/reports/  (none — S01 is the first step)`

## Output Files

- `ai-dev/work/CR-00047/reports/CR-00047_S01_Backend_report.md` -- Step report

## Context

You are implementing **CR-00047 — Coverage gates (P1-CR-B)** — the only implementation step in the manifest. **Read `ai-dev/work/CR-00047/CR-00047_CR_Design.md` first** — the "Current Behavior", "Desired Behavior", "Acceptance Criteria" (AC1–AC8), "Impacted Paths", and "Notes" sections are the source of truth and contain detail this prompt summarises. Also skim `docs/IW_AI_Core_Testing_Strategy.md` §1/§5/§9 and `skills/iw-workflow/SKILL.md`'s "QV Gate Steps" block. Read `CLAUDE.md` for project conventions.

This change is config (`pyproject.toml`/`uv.lock`), a Makefile target, a skill-canon edit, a GH-workflow edit, a dependency add, doc updates, and `iw sync-skills` — plus, optionally, one small config-assertion test. There is no new production logic, so `tdd_red_evidence` is the `"n/a — config / Makefile / skill / workflow edits + dependency add; no production logic"` form **unless** you add the optional guard test (deliverable 0), in which case write it RED-first and record the real RED snippet. Don't contrive a test just to populate the field.

## Requirements

### 0. (Optional) RED-first guard test

If — and only if — you judge it meaningful, create `tests/unit/test_coverage_gate_config.py` with **real** assertions on parsed values: parse `pyproject.toml` and assert `[tool.coverage.report].fail_under` is `>=` the floor you set in deliverable 1 and `> 46`; assert `diff-cover` appears in the dev dependency group; read `Makefile` and assert it contains a `diff-coverage:` target. Run `uv run pytest tests/unit/test_coverage_gate_config.py -v` first and confirm it fails (the `pyproject.toml`/`Makefile` edits aren't in yet) — capture that RED line as `tdd_red_evidence`. Use specific assertions (`assert fail_under == 70`, not `assert fail_under is not None`) — the `assertions` QV gate (S05) runs against this file. If you skip this test, `tdd_red_evidence` is the `"n/a — …"` form.

### 1. Measure current coverage (BOTH slices), then raise & ratchet `fail_under`

Run `make test` — it runs `make test-unit` (covers `tests/unit/`) then `make test-integration` (covers `tests/integration/ tests/dashboard/`). These are **two different coverage slices** of `orch+dashboard+executor` and the second run *overwrites* `coverage.json`/`coverage.xml`, so the leftover artefact is the integration+dashboard slice only — **do not** read just that. Capture the **line % and branch % from BOTH terminal summaries** (the unit-suite run's and the integration-suite run's) and **record both pairs in your step report**.

Why both: `fail_under` in `[tool.coverage.report]` is re-checked by `pytest --cov` at the end of *every* run that picks up `addopts` — that includes the `unit-tests` QV gate (S08, `make test-unit`), the CI `integration` job (`make test-integration`), and the intermediate `--cov`/`--cov-append` runs inside `make diff-coverage`. A floor pinned just below the *higher* slice would make the *lower*-slice run fail. So set `[tool.coverage.report] fail_under` in `pyproject.toml` to a value a few points *below* the **lower** of the two measured **branch** %s. Rule of thumb: floor = (lower branch %) rounded down to the nearest 5, minus 0–5 more if the measurement felt noisy. (Examples: branch slices 73%/65% → set 60; 70%/68% → set 65.) Keep `skip_covered`/`show_missing`. **Do not** set it to the measured value (a ratchet, not a guillotine).

After the edit, re-run `make test-unit` once to confirm the new floor passes (QV gates get no fix cycles — a too-high floor would fail S08 and kill the item). `make quality` must also still pass (note: `make quality` does not run pytest, so it won't catch a too-high floor — `make test-unit` is the real check here).

### 2. Coverage-plumbing audit (1.10) — add `relative_files`

Add `relative_files = true` to `[tool.coverage.run]` in `pyproject.toml` (it's currently missing — needed so coverage paths align when the build runs in a worktree rather than the main checkout). Confirm the other gotchas and **record findings in your step report**: `addopts` uses `pytest --cov` not `coverage run -m pytest` (already correct); no GH workflow uploads the raw `.coverage` file (only `coverage.xml`), so `include-hidden-files` is N/A; subprocess coverage (`COVERAGE_PROCESS_START`) — the `iw` CLI / daemon subprocesses don't contribute coverage today; document as a known limitation, **do not** wire it up here.

### 3. Add `diff-cover` dev dependency

Add `diff-cover` to `pyproject.toml`'s dev dependency group (the same group that has `pytest`, `ruff`, etc.) and regenerate `uv.lock` (`uv lock` or `uv sync`). Pin loosely (`>=X`) consistent with the rest of the dev group.

### 4. Add `make diff-coverage` — self-contained combined-coverage gate

Add a `diff-coverage:` target to the `Makefile` (and to `.PHONY`). It must be **self-contained** — produce its own *combined* unit+integration coverage rather than reusing a `coverage.xml` left behind by a preceding step or relying on the `integration-tests` QV gate (which is currently a no-op stub). Mechanism is your choice — e.g. run the unit suite and the integration suite with `--cov-append` into one `.coverage` file (`pytest tests/unit ... --cov ... ; pytest tests/integration tests/dashboard --ignore=tests/dashboard/browser ... --cov ... --cov-append`), then `coverage xml -o <path>`; or `coverage run -p` parallel + `coverage combine`. Then run `uv run diff-cover <combined coverage.xml> --compare-branch=origin/main --fail-under=90` (N ≈ 90 — new/changed Python lines must be ≥90% covered). Exit non-zero if changed-line coverage < N. Add a short header comment explaining what it does and the combined-coverage rationale.

Implementation gotchas to handle:
- The existing `test-integration` target does *not* pass `--cov-append`, so you can't just chain `make test-unit` then `make test-integration` — write your own `pytest` invocations (mirror `test-integration`'s path args + `--ignore=tests/dashboard/browser`).
- Each intermediate `pytest --cov` run re-checks `[tool.coverage.report] fail_under`. The unit-only run, taken alone, may fall below the (raised) floor — pass `--cov-fail-under=0` on the intermediate runs (or otherwise suppress the per-run check) and let the *final* combined `coverage xml`/`coverage report` be the one that matters; `diff-cover`'s own `--fail-under=90` is the gate's verdict, separate from `[tool.coverage.report] fail_under`.
- This is a **slow** gate (it re-runs unit + integration + dashboard suites) — that's the trade-off for robustness; document it in the target comment. Because of this, the QV-gate step that runs it needs a generous timeout (see deliverable 5: use `"timeout": 1800` on the `diff-coverage` gate entry, not the 900 that `integration-tests` uses).

### 5. Add the `diff-coverage` daemon QV gate to `skills/iw-workflow/SKILL.md`

In the "QV Gate Steps" JSON block (currently 6 gates ending with `integration-tests`), add a 7th entry **after** `integration-tests`:

```json
{"step": "S{NN}", "agent": "qv-gate", "gate": "diff-coverage", "command": "make diff-coverage", "description": "QV: Diff coverage (new/changed lines must be well-covered)", "timeout": 1800}
```

(The `1800` timeout — vs the `900` `integration-tests` uses — is deliberate: `make diff-coverage` re-runs unit + integration + dashboard suites *plus* `diff-cover`, so it strictly dominates the integration gate's runtime.)

Update the prose: "The 6 canonical QV gates are: lint → assertions → format → typecheck → unit-tests → integration-tests" → "The 7 canonical QV gates are: lint → assertions → format → typecheck → unit-tests → integration-tests → diff-coverage" and add a sentence noting the `diff-coverage` gate (added by CR-00047, P1-CR-B) runs `make diff-coverage` (self-contained combined coverage, compares to `origin/main`, fails on changed-line coverage < ~90%; generous timeout because it re-runs the suites).

### 6. Add the GH `Run diff coverage` step to `.github/workflows/test-quality.yml`

In the `unit` job, after the `make test-unit` step (and the coverage-XML artefact upload), add a step conditional on `pull_request` events: `if: github.event_name == 'pull_request'`, running `diff-cover` against `tests/output/coverage/coverage.xml` (the unit coverage already produced — that's fine for the GH check; the daemon's `diff-coverage` gate is the authoritative combined one) with `--compare-branch` pointing at the PR base (`origin/main` for PRs targeting main, or `${{ github.event.pull_request.base.sha }}`) and `--fail-under=90`. You will likely need `fetch-depth: 0` on the `actions/checkout` step (or an explicit `git fetch origin main`) so the base ref is available — handle that. On `push` to main the step is skipped (no diff). Do NOT add a new job.

### 7. Update `docs/IW_AI_Core_Testing_Strategy.md`

- §1 (the principles table): the "Coverage is a floor on what's exercised" row already exists — keep the principle and add a one-line note that the floor is set just below measured coverage and **ratchets up over time, never down** (AC6 requires §1 to reflect the new floor + ratchet rule).
- §5 (the gate table): update the Coverage row — new `fail_under` value, mention it's enforced via `pytest --cov` *and* there's now a `diff-coverage` gate; add a `Diff coverage` row to the table (`diff-cover` / `>=90% on changed lines` / `make diff-coverage` (daemon QV gate) + the PR check).
- Add a short paragraph (in §5 near the gate table, or a §8 sibling) titled "Coverage floor & diff-coverage": the floor is just below measured branch coverage and ratchets up; the `diff-coverage` gate checks changed lines are ≥~90% covered; run it locally with `make diff-coverage`; **coverage-source caveat** — the daemon `diff-coverage` gate builds its own combined unit+integration coverage; the GH PR check uses the unit `coverage.xml` (cheaper); regenerate-the-floor guidance.
- §9 (the gaps table): flip "Coverage failure floor" and "Diff/patch coverage on PRs" rows to ✅ (CR-00047).

### 8. Update `skills/iw-ai-core-testing/SKILL.md` §8 (Quality gates)

Add `diff-coverage` to the gate list and a line noting the `fail_under` floor (and that the floor ratchets up). Keep it brief.

### 9. Run `iw sync-skills`

So `.claude/skills/iw-workflow/SKILL.md` and `.claude/skills/iw-ai-core-testing/SKILL.md` reflect the master edits. Verify with `git diff` that those two synced files match their masters. **Do NOT run `iw sync-templates`** — no `templates/design/*.md` edits. Note in your report that the sibling repos (iw-doc-plan/podforger/cv) will pick up the new `diff-coverage` gate at their next `iw sync-skills` — not done from this worktree.

### 10. Update `ai-dev/work/TESTS_ENHANCEMENT.md`

Tick items **1.2**, **1.3**, and the **1.10 audit** as DONE with `(CR-00047)` link/status. In §5's CR-grouping table: mark **P1-CR-B SHIPPED** and move "*(start here)*" to **P1-CR-C**. Add a changelog entry at the bottom (the measured coverage %, the chosen `fail_under`, `diff-cover` + `make diff-coverage` + the new gate, the cov-plumbing audit, what was deferred).

### 11. GREEN + REFACTOR

- Run the optional guard test (if added) — `uv run pytest tests/unit/test_coverage_gate_config.py -v` — must pass.
- Run `make test-unit` once — must pass with the new `fail_under` (this is the run that enforces the floor; if it fails, your floor is too high — lower it). [Already done in deliverable 1's re-verify step; re-run here only if you've touched `pyproject.toml` since.]
- Run `make diff-coverage` once — it should exit 0. This CR adds ≈0 new production Python lines; `tests/` is in `[tool.coverage.run] omit`, so the optional guard-test file isn't in the coverage data and `diff-cover` simply has no changed lines to judge → exit 0. If `make diff-coverage` *fails*, something unexpected happened — investigate, don't paper over it.
- Run `make quality` — must pass (lint, format-check, typecheck, the `test-assertions` step). (Note: `make quality` does *not* run pytest, so it does not exercise the new `fail_under` — `make test-unit` above is that check.)
- Targeted-run the unit suite for any file you added (not the whole suite — those are the QV gates downstream).

**Scope discipline**: touch only the files in the design's "Impacted Paths" list (plus this CR's `ai-dev/active|work/CR-00047/**`). Do **not** fix the `integration-tests` no-op gate (P1-CR-E). Do **not** add `mutmut`/`vulture`/`deptry`/`gitleaks`/`semgrep`/`pytest-randomly` (subsequent CRs). Do **not** scrub the assertion baseline (P1-CR-A-followup). Do **not** raise `fail_under` to the *measured* value (headroom). Do **not** change the workflow-manifest schema. Do **not** restructure the existing `--cov-report` config beyond adding `relative_files`. Do **not** wire up subprocess coverage.

## Project Conventions

Read the project's `CLAUDE.md` for:

- Architecture patterns and layer boundaries
- Coding conventions and naming rules
- Framework-specific patterns (ORM style, API patterns, etc.)
- Test organization and fixtures
- Build and run commands

Follow all rules defined there exactly. When in doubt, match existing code in the repository.

## TDD Requirement

Follow TDD (Red-Green-Refactor):

1. **RED**: Write failing tests first that define the expected behavior.
   Then **run the new failing test** — a *targeted* run only
   (`uv run pytest tests/.../test_x.py -v`), never the full suite.
   **Confirm the failure is for the expected reason** — an
   `AssertionError` or `NotImplementedError`/`AttributeError` from
   missing implementation, *not* an `ImportError`, `SyntaxError`,
   fixture error, or collection error (those mean the test itself is
   broken, not RED). Capture the failing line(s).
2. **GREEN**: Write the minimal implementation to make tests pass.
3. **REFACTOR**: Improve code structure while keeping all tests green.

Do not skip the RED phase. Tests must exist before implementation code.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, you MUST run these in order
and fix any issues they report. Skipping any of these wastes a fix-cycle slot
when the QV gate steps catch the same issue downstream — see I-00041 finding
[3] for the cost case (S05/S01 shipped unformatted code and an `object not
callable` mypy regression that S09 and S10 caught later, each burning a
fix-cycle).

1. **`make format`** — auto-fixes formatting drift. If it reformats files,
   inspect the diff and re-stage; do NOT skip.
2. **`make typecheck`** — must report zero errors involving the files you
   touched. Errors elsewhere are pre-existing — note them in your report but
   do not ignore your own.
3. **`make lint`** — must report zero errors.

If a tool isn't available in your worktree, STOP and raise a blocker — do not
silently skip.

In your Subagent Result Contract, populate the new `preflight` object recording
the result of each command:
- `"ok"` — ran cleanly, no changes / no errors
- `"fixed"` — applies to `format` only; the tool auto-fixed something
- `"skipped:<reason>"` — only if you raised a blocker explaining why

## Test Verification (NON-NEGOTIABLE)

After implementation, verify your own changes — but **DO NOT run the full
test suite**. Full-suite execution is owned by the dedicated QV gate steps
downstream (`unit-tests`, `integration-tests`, `frontend-tests`); duplicating
them here burns this step's budget and is a common cause of step timeouts
(see I-00073/S03 post-mortem, 2026-05-08).

Scope rules:

1. **Tests step (`tests-impl`)** — run only the test file(s) **you wrote or
   modified** in this step:
   ```bash
   uv run pytest tests/integration/path/to/your_new_test.py -v
   ```
   That is sufficient to prove your tests work. Do **NOT** run
   `make test-integration` or `make test-unit` — those are the QV-gate
   steps downstream and will run with their own (longer) budgets.

   **Exception for THIS step**: deliverable 1 requires running `make test`
   once to *measure* current coverage (both slices) — that's a deliberate
   measurement, not a "be safe" re-run — and re-running `make test-unit`
   once afterward to confirm the new `fail_under` still passes. Plus
   deliverable 11 runs `make diff-coverage` once (it re-runs the suite by
   design). Those are the deliberate full/unit runs for this step; do not
   add others, and never run `make test-integration` at large.

2. **Implementation steps (Backend / API / Database / Frontend / Pipeline /
   Template)** — run the **targeted** unit tests that exercise the code
   path you changed:
   ```bash
   uv run pytest tests/unit/path/to/affected_module/ -v
   ```
   If you cannot identify a narrow target, run the full unit suite — but
   **never** the full integration suite. Integration-suite verification is
   the QV gate's job.

3. Run lint and type checking on your touched files (check Makefile or
   `CLAUDE.md` for project-specific commands).

4. Do **NOT** report `tests_passed: true` unless your targeted tests pass
   with zero failures.

5. If your targeted tests fail, fix them before reporting completion. If
   they pass but you suspect a wider regression, note it in your report
   under `notes` — do not pre-emptively run the full suite to "be safe".

6. **CSS class renames — required test update.** When the design renames a
   CSS class name, grep the test suite for the old class name and update
   every assertion to match the new name before reporting
   `tests_passed: true`. Stale CSS class assertions in tests are a
   code-review failure mode (see CR-00039 self-assess finding [3]).

## Migration Verification (Database steps only — NON-NEGOTIABLE)

If your step generated or modified an alembic migration under
`orch/db/migrations/versions/**`, you MUST run **`make migration-check`**
before reporting completion. This spins a fresh testcontainer Postgres,
runs `alembic upgrade head` from base, asserts the resulting schema matches
`Base.metadata.create_all()` (catches model↔migration drift), and
round-trips through `downgrade base → upgrade head` (catches broken
`downgrade()` bodies).

If `make migration-check` fails, fix the migration file (or the model) so
both halves agree, and re-run until green. Do not report
`tests_passed: true` while this gate is red — downstream agents will inherit
a wrong schema and waste fix-cycles diagnosing the symptom (see F-00079
post-mortem for the cost case: four S19 attempts spent debugging a JS
"e.map is not a function" that traced back to a missing column in a stack
that hadn't applied the new migration).

## Subagent Result Contract

When your work is complete, report results in this JSON structure:

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "CR-00047",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "path/to/file1.py",
    "path/to/file2.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "n/a — config (pyproject.toml/uv.lock) + Makefile target + skill canon + GH workflow + docs edits + diff-cover dependency add; no production logic. [OR, if the optional guard test was added: tests/unit/test_coverage_gate_config.py — RED before edits: AssertionError: assert 46 >= 70 (fail_under not raised yet); GREEN after deliverables 1 & 3-4]",
  "blockers": [],
  "notes": "Measured coverage — unit slice (`make test-unit`): line <Lu>%, branch <Bu>%; integration+dashboard slice (`make test-integration`): line <Li>%, branch <Bi>%. Set fail_under = <floor> (= min(<Bu>,<Bi>) rounded down to nearest 5, minus headroom); re-ran `make test-unit` to confirm it passes. Added relative_files = true. Cov-plumbing audit: pytest --cov OK; raw-.coverage-artefact N/A; subprocess coverage = known limitation, not wired. `make diff-coverage` builds combined unit+integration coverage (intermediate runs use --cov-fail-under=0) then diff-cover --fail-under=90 vs origin/main; diff-coverage QV gate timeout = 1800. Ran `iw sync-skills` (.claude/skills/iw-workflow & iw-ai-core-testing in sync). Did NOT run iw sync-templates (no template edits). Sibling repos pick up the new diff-coverage gate at their next iw sync-skills. Items 1.2/1.3/1.10-audit ticked DONE."
}
```

- `tdd_red_evidence`: this is fundamentally config + a Makefile target + a skill edit + a dependency add — **no production logic** — so the `"n/a — …"` form is correct **unless** you added the optional guard test (`tests/unit/test_coverage_gate_config.py`, deliverable 0), in which case record its real RED-run snippet. Do not contrive a test to populate this field.

- `completion_status`: Use `complete` when all deliverables are done and tests pass. Use `partial` if some deliverables are done but others remain. Use `blocked` if external dependencies prevent progress.
- `blockers`: List any issues that prevented full completion. Include enough detail for the orchestrator to decide next steps.
- `notes`: Any context the next step or reviewer should know.
