# CR-00046_S01_Backend_prompt

**Work Item**: CR-00046 -- AST assertion-scanner gate — block tests that can't fail (P1-CR-A)
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

- **Runtime step state** — for the current step list, status, prompt paths, gate commands, etc., prefer `uv run iw item-status CR-00046 --json`. The `workflow-manifest.json` file is a design-time snapshot and may be out of date (CR-00023).
- `ai-dev/work/CR-00046/CR-00046_CR_Design.md` -- Design document
- Previous step reports (if applicable): `ai-dev/work/CR-00046/reports/  (none — S01 is the first step)`

## Output Files

- `ai-dev/work/CR-00046/reports/CR-00046_S01_Backend_report.md` -- Step report

## Context

You are implementing **CR-00046 — AST assertion-scanner gate (P1-CR-A)** — the only implementation step in the manifest. **Read `ai-dev/work/CR-00046/CR-00046_CR_Design.md` first** — the "Current Behavior", "Desired Behavior", "Scanner contract" table, "Acceptance Criteria" (AC1–AC9), "Impacted Paths", and "Notes" sections are the source of truth and contain detail this prompt summarises. Also skim `docs/IW_AI_Core_Testing_Strategy.md` §6–§9 and `skills/iw-ai-core-testing/SKILL.md` §1 (the anti-patterns this scanner enforces). Read `CLAUDE.md` for project conventions.

The starting structural reference is InnoForge's scanner at `/home/sergiog/dev/iw-doc-plan/main/iw-doc-plan/scripts/check_test_assertions.py` (~5 KB, has the no-assert check and a baseline mechanic). Port + **extend**; do not blindly copy. InnoForge's baseline file is at `/home/sergiog/dev/iw-doc-plan/main/iw-doc-plan/tests/assertion_free_baseline.txt` (77 entries — useful as a format reference).

## Requirements

Do these in order. **Apply TDD: deliverable 1 is your RED test set — write the unit tests for the scanner first, run them, watch them fail (ImportError / FileNotFoundError on the not-yet-existing scanner module), then deliverables 2–11 make them GREEN.** Record `tdd_red_evidence` from this RED run in your final result-contract JSON (per CR-00045's contract).

### 1. RED — write `tests/unit/test_assertion_scanner.py`

Cover **each** of the four detected categories with one positive case and one negative case (the negative case must not be flagged), using `ast.parse` on inline strings or `tmp_path`-written files:

- **no-assert**: `def test_x(): result = foo()` → flagged; `def test_x(): result = foo(); assert result == 42` → not flagged.
- **tautology** — one sub-case per pattern: `assert True` / `assert <bare Name>` / `assert x == x` / `assert isinstance(x, T)` (whole assertion) / `assert x is not None` / `assert len(x) > 0` / `assert "k" in x`. Each: a positive (only that pattern in the body — flagged) + a negative (mixed with a specific assertion — not flagged).
- **mock-only**: `def test_x(): foo(); mock.assert_called_once()` → flagged; `def test_x(): result = foo(); assert result == 42; mock.assert_called_once()` → not flagged.
- **broad-raises**: `with pytest.raises(Exception): foo()` → flagged; `with pytest.raises(Exception, match="not found"): foo()` → not flagged; `with pytest.raises(ValueError): foo()` → not flagged.

Plus:
- A test that `--baseline <path>` lets through an existing offender but flags a new one (write a small test tree under `tmp_path`, generate a baseline with one offender, add a second, assert exit code 1 and only the new offender reported).
- A test that `--write-baseline <path>` regenerates the file from scratch with sorted, category-suffixed entries.
- A test that `--json` emits a `{"violations": [{"path", "line", "category", "test_name", "message"}, …]}` shape.
- A test that `--strict` ignores the baseline and flags every violation.
- A test that `# noqa: assertion-scanner` on the `def` line suppresses the report for that specific test (the local opt-out).

Run `uv run pytest tests/unit/test_assertion_scanner.py -v` and **confirm it fails for the right reason** — `ImportError` / `FileNotFoundError` on the scanner module/script, *not* a `SyntaxError` in the test file or a `fixture error`. Capture the failing line(s) — this is the `tdd_red_evidence` for your result JSON.

Use real, specific assertions in this file. The dogfood gate S05 (`make test-assertions`) runs against this very file — if you write a vacuous test here you will be caught by the tool you are building, which would be a *spectacular* own goal.

### 2. `scripts/check_test_assertions.py` — port + extend

Port InnoForge's scanner's structure (`_has_assertion`, the AST walk, the `--baseline-file` mechanic) and **extend** to cover all four categories per the design's "Scanner contract" table:

- **no-assert**: identical to InnoForge's check (a `test_*` function body contains no `assert`, no `pytest.raises`/`pytest.warns`, no `mock.assert_*` / `mock.assert_await*`).
- **tautology**: gather all `ast.Assert` nodes in the function body; if non-empty *and* every node's `test` matches one of the patterns (`assert True`, `assert <bare Name>`, `assert x == x` with `ast.Name(id=)` equality both sides, `assert isinstance(x, T)` whole, `assert x is not None` whole, `assert len(x) > 0`/`>= 1`/`!= 0` whole, `assert <expr> in <expr>` whole), flag with category `tautology`. Mixed = OK.
- **mock-only**: gather all assertion-bearing statements (`ast.Assert`, `pytest.raises`/`pytest.warns` calls, and attribute calls like `<name>.assert_called*` / `<name>.assert_await*`). If the set is non-empty *and* every entry is a `<name>.assert_called*` / `<name>.assert_await*` attribute call where the receiver name contains `mock`/`Mock` (case-insensitive `in` check), flag with category `mock-only`.
- **broad-raises**: visit every `ast.With` whose context-manager is `pytest.raises(<expr>)` (also handle direct call form). Flag if `<expr>` is `ast.Name(id="Exception")` or `ast.Name(id="BaseException")` **and** no `match=` keyword argument is present. Category `broad-raises`.

A single test may be flagged under multiple categories — emit one entry per (path, line, test_name, category). Skip `tests/conftest.py` and any `**/conftest.py` (fixtures aren't tests). Honour `# noqa: assertion-scanner` on the function's `def`/`async def` line as a local opt-out (skip that function entirely).

CLI: `python scripts/check_test_assertions.py [PATH...]` with:
- `--baseline <path>` — read the file (lines like `path::test_name # category` plus `#`-prefixed comment lines); a violation matching a baseline entry doesn't count toward exit code. Default: no baseline.
- `--write-baseline <path>` — run the scan and **overwrite** the file with the current violation set, sorted, with a comment header (see deliverable 3). Implies don't read an existing baseline. Exit 0 after writing.
- `--strict` — ignore any provided baseline; every violation contributes to exit code. Useful for `make test-assertions-strict` (don't add that target here — out of scope).
- `--json` — write `{"violations": [...]}` to stdout instead of the human-readable form. Exit code unchanged.
- Default human output (one line per violation): `path:line: <category>: <test_name>: <one-line explanation>`. Quiet on success.

Exit 0 if no new violations (after baseline), 1 otherwise.

### 3. `tests/assertion_free_baseline.txt` — generate

Run `python scripts/check_test_assertions.py --write-baseline tests/assertion_free_baseline.txt tests/`. Verify the file is sorted, entries look reasonable, and the comment header (which `--write-baseline` should write) explains: purpose, format, the cleanup-backlog framing, and the rule "the right way to silence the gate is to fix the test, not to add it to the baseline; run `--write-baseline` only when you've intentionally accepted that the listed tests stay weak (rare)."

If the baseline ends up very large (say >300 entries), still commit it as-is — this CR's job is the gate, not the cleanup. Note the size in your report under `notes`.

### 4. `Makefile` — `test-assertions` target + fold into `quality:`

Add a `test-assertions:` target that runs `uv run python scripts/check_test_assertions.py --baseline tests/assertion_free_baseline.txt tests/` (exits non-zero on new violations). Update the existing `quality: lint format typecheck` rule to `quality: lint format typecheck test-assertions`. Add `test-assertions` to the `.PHONY` list. Place the target near the other quality targets, with a short header comment explaining what it does and pointing at `scripts/check_test_assertions.py`.

### 5. Daemon QV gate canon — `skills/iw-workflow/SKILL.md`

In the canonical QV-gate enumeration (currently lines ~126–130: `lint` → `format` → `typecheck` → `unit-tests` → `integration-tests`), insert a new `assertions` gate **right after `lint`**:

```json
{"step": "S{NN}", "agent": "qv-gate", "gate": "assertions", "command": "make test-assertions", "description": "QV: Assertion scanner (forbid new vacuous tests)"}
```

Renumber following step numbers in the example accordingly (the example is illustrative — the real `S{NN}` is per-item). Update any prose in the skill that says "the 5 canonical QV gates" → "the 6 canonical QV gates" (search for similar wording).

### 6. GH workflow — `.github/workflows/test-quality.yml`

In the `lint-typecheck` job, immediately after the `- run: make lint` step, add `- run: make test-assertions`. Do **not** create a new job. Do **not** add `--strict` (we want the baseline behaviour in CI too). Keep the existing `format-check || format` and `typecheck` steps below it unchanged.

### 7. Strategy doc — `docs/IW_AI_Core_Testing_Strategy.md`

- §8 (or a new sibling subsection): add a short paragraph (≤8 lines) titled "Assertion scanner" describing what it flags (link to the four categories), how the baseline file works, how to regenerate it (`uv run python scripts/check_test_assertions.py --write-baseline tests/assertion_free_baseline.txt tests/`), and the rule "the right way to silence the gate is to fix the test, not to add it to the baseline".
- §9 row "AST assertion scanner": flip from `❌ (1.1)` to `✅ (CR-00046, 2026-05-11) — make test-assertions + baseline tests/assertion_free_baseline.txt`.

### 8. Testing skill cross-reference — `skills/iw-ai-core-testing/SKILL.md`

Add a one-line note at the end of §1 (the anti-patterns section) — something like: *"These bans are statically enforced: a violation in a new test file fails `make test-assertions` and the `assertions` QV gate. The right fix is to strengthen the test; the baseline file (`tests/assertion_free_baseline.txt`) is for tracking the existing cleanup backlog, not for silencing new violations."*

### 9. Sync the skill copies

Run `uv run iw sync-skills` so `.claude/skills/iw-workflow/SKILL.md` and `.claude/skills/iw-ai-core-testing/SKILL.md` pick up the master edits. Verify with `git diff` that those two synced files now match their masters. **Do NOT run `iw sync-templates`** — no templates were edited.

### 10. Plan doc — `ai-dev/work/TESTS_ENHANCEMENT.md`

In the Phase 1 table, set item **1.1**'s Status to `**DONE 2026-05-11 (CR-00046)**` and `Link` to `CR-00046`. Add a changelog entry at the bottom describing what shipped (the scanner, the baseline, the gate in both CI surfaces, the strategy-doc + testing-skill updates).

### 11. GREEN + REFACTOR

Re-run `uv run pytest tests/unit/test_assertion_scanner.py -v` — must pass. Run `make test-assertions` — must exit 0 (the baseline you just generated admits every current offender). Run `make quality` — must pass (lint + format-check + typecheck + the new test-assertions step). Targeted-run the unit suite for the new file only (not the whole suite — those are the QV gates downstream).

**Scope discipline**: touch only the files in the design's "Impacted Paths" list (plus this CR's `ai-dev/active|work/CR-00046/**`). Do **not** add `mutmut`/`vulture`/`deptry`/`gitleaks`/`semgrep`/`pytest-randomly`/`diff-cover` (subsequent Phase-1 CRs). Do **not** clean up the baseline (a separate item). Do **not** modify any existing test (other than to add `tests/unit/test_assertion_scanner.py`). Do **not** change the workflow-manifest schema. Do **not** propagate `skills/iw-ai-core-testing/` to sibling repos (project-specific). For `skills/iw-workflow/` cross-repo propagation, note in your report that the sibling repos' next `iw sync-skills` will pick up the new gate; do not attempt cross-repo edits.

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
  "work_item": "CR-00046",
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
  "test_summary": "X passed, 0 failed (tests/unit/test_assertion_scanner.py)",
  "tdd_red_evidence": "tests/unit/test_assertion_scanner.py — RED before deliverable 2: ModuleNotFoundError: No module named 'check_test_assertions' (no scanner script existed yet); GREEN after deliverable 2",
  "blockers": [],
  "notes": "Ran `iw sync-skills` after editing skills/iw-workflow/SKILL.md and skills/iw-ai-core-testing/SKILL.md — .claude/skills/ copies now match. Did NOT run `iw sync-templates` (no template edits). Item 1.1 ticked DONE in ai-dev/work/TESTS_ENHANCEMENT.md. Baseline file size at generation: <N> entries. Sibling repos (iw-doc-plan/podforger/cv) will pick up the new `assertions` gate in iw-workflow at their next `iw sync-skills` — not done from this worktree."
}
```

- `tdd_red_evidence`: **Required for this CR.** This step adds behavioural tests (`tests/unit/test_assertion_scanner.py`). Record the RED run output you captured in deliverable 1 — likely a `ModuleNotFoundError` / `FileNotFoundError` / `ImportError` because the scanner script doesn't exist yet. If the failure is anything else (e.g. `SyntaxError` in your test file, a fixture error, a collection error), that means the test itself is broken, not RED — fix it before continuing.

- `completion_status`: Use `complete` when all 11 deliverables are done and `make quality` (incl. the new `test-assertions` step) and the unit tests pass. Use `partial` if some deliverables are done but others remain. Use `blocked` if external dependencies prevent progress.
- `blockers`: List any issues that prevented full completion.
- `notes`: Replace `<N>` with the actual baseline-file line count. Mention any baseline entries that surprised you (a category showing up unexpectedly often, etc.) — useful signal for the eventual cleanup follow-up.
