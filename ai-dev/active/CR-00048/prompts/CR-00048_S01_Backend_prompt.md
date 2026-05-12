# CR-00048_S01_Backend_prompt

**Work Item**: CR-00048 -- Test hygiene — randomized test order, strict markers, dead-code & dep-hygiene gates (P1-CR-C)
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

- **Runtime step state** — for the current step list, status, prompt paths, gate commands, etc., prefer `uv run iw item-status CR-00048 --json`. The `workflow-manifest.json` file is a design-time snapshot and may be out of date (CR-00023).
- `ai-dev/work/CR-00048/CR-00048_CR_Design.md` -- Design document
- Previous step reports (if applicable): `ai-dev/work/CR-00048/reports/  (none — S01 is the first step)`

## Output Files

- `ai-dev/work/CR-00048/reports/CR-00048_S01_Backend_report.md` -- Step report

## Context

You are implementing **CR-00048 — Test hygiene (P1-CR-C)** — the only implementation step in the manifest. **Read `ai-dev/work/CR-00048/CR-00048_CR_Design.md` first** — the "Current Behavior", "Desired Behavior", "Acceptance Criteria" (AC1–AC7), "Impacted Paths", and "Notes" sections are the source of truth and contain detail this prompt summarises. Also skim `docs/IW_AI_Core_Testing_Strategy.md` §3/§5/§6/§9, `tests/CLAUDE.md`, and `skills/iw-ai-core-testing/SKILL.md`. Read `CLAUDE.md` for project conventions. InnoForge's `make dead-code` (`vulture src/innoforge/ --min-confidence 80`) / `make dep-check` (`deptry .`) + its `[tool.vulture]`/`[tool.deptry]` `pyproject.toml` sections (`/home/sergiog/dev/iw-doc-plan/main/iw-doc-plan/`) are good port references.

This change is config (`pyproject.toml`/`uv.lock`), Makefile targets, test-isolation fixes, a whitelist file, doc/skill updates, a GH-workflow edit, and `iw sync-skills`. The behavioural anchor is the `test_safe_migrate.py` fix (deliverable 0 / 6) — that's your `tdd_red_evidence`.

## Requirements

Do these in order. Deliverable 0 is your RED reproduction; deliverable 6 is its GREEN fix.

### 0. RED — reproduce the `test_safe_migrate` failure

Run `IW_CORE_PER_WORKTREE_DB=true uv run pytest tests/unit/test_safe_migrate.py::TestApply::test_apply_refuses_in_agent_context tests/unit/test_safe_migrate.py::TestRollback::test_rollback_refuses_in_agent_context -v` and confirm both **fail** (`Failed: DID NOT RAISE AgentContextForbiddenError`, or similar — *not* an import/collection error). Capture the failing line(s) — this is your `tdd_red_evidence`. (You may need to also unset/clear `IW_CORE_AGENT_CONTEXT` from your shell first so the test's own `patch.dict` is what's in effect; the point is to simulate the agent-worktree environment where `IW_CORE_PER_WORKTREE_DB=true` leaks in via `clear=False`.)

### 1. Add `pytest-randomly`, `vulture`, `deptry` dev deps

Add all three to `pyproject.toml`'s `[dependency-groups] dev` group (loose pins, `>=X`, consistent with the group's style — e.g. `pytest-randomly>=3.15`, `vulture>=2.11`, `deptry>=0.20`). Regenerate `uv.lock` (`uv lock` then `uv sync`). `pytest-randomly` is default-on once installed — it randomizes test-file/class/function order and seeds RNGs with a per-run seed it prints.

### 2. Make the suite robust to randomization

**Time budget:** running the suites is expensive — keep the multi-seed sweep bounded. Run **`make test-unit` 3 times** with different `--randomly-seed` values (`uv run pytest tests/unit/ --randomly-seed=12345 -q`, `=67890`, `=11111`) and **`make test-integration` once** with one more seed (`uv run pytest tests/integration/ tests/dashboard/ --ignore=tests/dashboard/browser --randomly-seed=42424 -q`) — that's the whole sweep, no more. (The cheap unit suite is where most order-dependence surfaces; the QV gates downstream — S08 `make test-unit`, S10 `make diff-coverage` which re-runs unit+integration+dashboard — give you two more seeds for free, so don't burn this step's budget re-running the integration suite repeatedly.) Catalogue every order-dependent failure. Then **triage**:
- **Small backlog (≤ ~10 tests)** — fix them all here. Usual fixes: a test mutating module/global state without restoring it (use `monkeypatch`); a test depending on another's side effect (make it self-contained); an autouse fixture missing cleanup; a direct `app.state.x = …` that should be `monkeypatch.setattr(app.state, …)`. **Test-isolation fixes only — no behavioral test changes, no weakened assertions.**
- **Large backlog** — fix the easy ones; **quarantine** the rest with `@pytest.mark.order_dependent` (add `"order_dependent: test relies on test order; tracked for cleanup in P1-CR-C-followup"` to `pyproject.toml`'s `markers` list) + a one-line comment on each; **file `P1-CR-C-followup — fix the order-dependent test backlog`** in the plan's §5 grouping table (near `P1-CR-A-followup`). Note: quarantined tests still *run* (they're just marked) — they must still pass under random order, or be `xfail`-ed if genuinely broken.
- **Last-resort fallback** (only if the backlog is too large to even quarantine cleanly in this CR) — keep the `pytest-randomly` dep but add `-p no:randomly` to `addopts` (off by default), document why in the changelog + the design's Notes, and file the follow-up to flip it on. **Use this only if you genuinely can't get the suite green under randomization any other way.**

End state (mandatory): `make test-unit` (across the 3 seeds you ran) and `make test-integration` (the one seed you ran) exit 0 under randomization (fixed or quarantined), OR randomization is off-by-default per the fallback. **Do not merge with the suite failing under random order.**

Document the recipe in `tests/CLAUDE.md`: `pytest-randomly` is default-on; the per-run seed prints at the top; `pytest -p no:randomly …` disables it; `pytest --randomly-seed=<N> …` reproduces a failure. Also add it to `skills/iw-ai-core-testing/SKILL.md` §2 (infrastructure) and §7 (red-flags — a test that only passes in fixed order is a smell).

### 3. `--strict-markers` default

Add `--strict-markers` to `[tool.pytest.ini_options] addopts` in `pyproject.toml`. Run the suite; if it surfaces any unregistered/typo'd `@pytest.mark.<x>`, fix it (register a legitimate new marker in the `markers` list, or fix the typo). Then it's done — `--strict-markers` is the default everywhere now (not just `make smoke`).

### 4. `vulture` + `deptry` — warn-only targets

Add a `[tool.vulture]` section to `pyproject.toml` (e.g. `min_confidence = 70`, `paths = ["orch", "dashboard", "executor", "scripts"]`, and either `ignore_decorators`/`ignore_names` for the unavoidable false positives — FastAPI route handlers, pytest fixtures, Click commands, `__all__` exports, dynamically-referenced names — or point at a whitelist file). If you use a whitelist file, create `vulture_whitelist.py` at repo root (a file that "references" the false-positive names so vulture stops flagging them — `vulture --make-whitelist orch dashboard executor scripts` generates a starting point; prune it to genuine false positives). Add a `[tool.deptry]` section for `deptry`'s false positives (`extend_default_ignore_rules` / `ignore_*` entries for optional imports, plugin discovery, the `iw` CLI's lazy command loading, dev-deps-used-in-tests, etc.).

Add to the `Makefile`:
- `dead-code:` → `uv run vulture` (it picks up `[tool.vulture]` config; or pass the paths/flags explicitly).
- `dep-check:` → `uv run deptry .` (picks up `[tool.deptry]` config).
- Add both to `.PHONY`.
- Update `quality:` from `lint format typecheck test-assertions` to also run them **non-failing**: e.g. `quality: lint format typecheck test-assertions` with `dead-code` / `dep-check` appended such that their failure doesn't fail `quality` — the cleanest is to make `dead-code:`/`dep-check:` themselves end with `|| true` (so the *target* always succeeds) and add them to the `quality:` prerequisite list, OR add a separate recipe line `-$(MAKE) dead-code dep-check` (the `-` prefix ignores errors). Pick one; comment it clearly: "warn-only for now (Phase-1 P1-CR-C); flips to a hard gate in a follow-up after the noise is triaged."

Add to `.github/workflows/test-quality.yml`'s `lint-typecheck` job a step that runs `make dead-code` and `make dep-check` as **informational** — either a step with `continue-on-error: true`, or `run: make dead-code dep-check || true`. Do **not** create a new job. Do **not** add `dead-code`/`dep-check` as daemon QV gates (warn-only doesn't get a gate; a follow-up adds them when they flip to hard).

### 5. *(deleted — no broad dead-code deletion pass; vulture warn-only just reports. If its output is enlightening, list candidate deletions in your step report for a follow-up, but delete nothing here.)*

### 6. Fix the `test_safe_migrate.py` agent-context tests

Read `orch/db/safe_migrate.py` to find exactly which env var(s) flip `apply()`/`rollback()` (and `_assert_not_agent_context()`) out of the "refuse" branch — likely `IW_CORE_PER_WORKTREE_DB` (per-worktree DB is a context where migrations *are* permitted even in agent context). Then fix `tests/unit/test_safe_migrate.py::TestApply::test_apply_refuses_in_agent_context` and `::TestRollback::test_rollback_refuses_in_agent_context` so they pass *both* in an agent worktree (where `IW_CORE_PER_WORKTREE_DB=true` is in the ambient env) *and* in CI/locally: control the leaking var — set `IW_CORE_PER_WORKTREE_DB` (to whatever value keeps the refuse path active) explicitly in the test's `env` dict, or use `patch.dict(..., clear=True)` with the full required env, or pop the leaking var before the `pytest.raises` block — match the conventions of the surrounding tests in that file. **Do not change production code in `orch/db/safe_migrate.py`** unless the test reveals a genuine production bug (it shouldn't — this is test isolation). Re-run deliverable 0's command and confirm the tests now pass; also run them without `IW_CORE_PER_WORKTREE_DB` set and confirm they still pass.

### 7. Doc / strategy / plan updates

- `docs/IW_AI_Core_Testing_Strategy.md`: §3 — note `pytest-randomly` is default-on + the reproduce recipe; §5 (gate table) — add a `dead-code` (vulture, warn-only) row and a `dep-check` (deptry, warn-only) row; §6 (conventions) — `--strict-markers` is the default; §9 (gaps table) — flip "Test-order randomisation (`pytest-randomly`)" and "`vulture` dead-code / `deptry` dep-hygiene" to ✅ (and "Flaky/quarantine workflow" to ⚠️ if you introduced `order_dependent`).
- `skills/iw-ai-core-testing/SKILL.md`: §2/§7 — the `pytest-randomly` recipe (also done in deliverable 2); §8 (gates) — add `dead-code`/`dep-check` (warn-only).
- `ai-dev/work/TESTS_ENHANCEMENT.md`: tick items **1.4**, **1.5**, **1.7** as DONE `(CR-00048)` (or "partial — cleanup follow-up filed" if you took the quarantine/fallback path); §5 grouping table — mark **P1-CR-C SHIPPED** (or "SHIPPED — cleanup follow-up filed") and move "*(start here)*" to **P1-CR-D**; add the `P1-CR-C-followup` row if you filed one; add a changelog entry at the bottom: the 3 dep adds, the order-dependent-failure **counts** (found / fixed / quarantined), the marker fixes, the `vulture`/`deptry` setup + warn-only status, the `test_safe_migrate` fix, any fallback used.

### 8. Sync skills

Run `uv run iw sync-skills` (it'll pick up the `skills/iw-ai-core-testing/SKILL.md` edits; also `skills/iw-workflow/SKILL.md` only if you documented a new marker there — unlikely). Verify with `git diff` that `.claude/skills/iw-ai-core-testing/SKILL.md` matches its master. **Do NOT run `iw sync-templates`** — no `templates/design/*.md` edits. Note in your report which skills changed and that sibling repos (iw-doc-plan/podforger/cv) pick up any *shared*-skill (`iw-workflow`) change at their next `iw sync-skills` — not done from this worktree; `iw-ai-core-testing` is project-specific (not propagated).

### 9. GREEN + REFACTOR

Re-run the `test_safe_migrate` tests (deliverable 0's command) — must pass. Run `make quality` — must pass (lint + format-check + typecheck + test-assertions all pass; `dead-code`/`dep-check` print findings but **do not fail it** — this verifies the warn-only wiring). Targeted-run any test file you fixed/touched. **Do NOT also run `make check` or the full `make test-unit`/`make test-integration` again here** — deliverable 2 already ran the multi-seed sweep, and the full-suite-under-randomization verdict belongs to the QV gates (S08 `unit-tests`, S09 `integration-tests`, S10 `diff-coverage`); re-running them in this step risks a timeout (the I-00073 lesson).

**Scope discipline**: touch only the files in the design's "Impacted Paths" (`pyproject.toml`, `uv.lock`, `Makefile`, `vulture_whitelist.py`, `.github/workflows/test-quality.yml`, `tests/**`, `tests/CLAUDE.md`, `docs/IW_AI_Core_Testing_Strategy.md`, `skills/iw-ai-core-testing/SKILL.md` + its `.claude/` copy, `skills/iw-workflow/SKILL.md` + `.claude/` copy *only if a marker is documented there*, `ai-dev/work/TESTS_ENHANCEMENT.md`) plus this CR's `ai-dev/active|work/CR-00048/**`. **Diffs under `tests/` must be ONLY test-isolation fixes + the `test_safe_migrate` fix + quarantine markers — no behavioral test changes, no weakened assertions.** Do **not** fix the `integration-tests` no-op gate (P1-CR-E). Do **not** add `mutmut`/`gitleaks`/`semgrep` (subsequent CRs). Do **not** flip `vulture`/`deptry` to hard gates. Do **not** scrub the assertion baseline (P1-CR-A-followup). Do **not** do a dead-code deletion pass. Do **not** change the workflow-manifest schema. Do **not** change production code beyond what the `test_safe_migrate` fix genuinely requires (it shouldn't require any).

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

> **Bounded exception — this is a testing-infrastructure CR.** The standard
> rule is "an implementation step never runs the full suite, never touches
> `make test-integration` — that's the QV gates' job" (I-00073/S03 timeout
> lesson). CR-00048's *deliverable* is making the suite robust to
> `pytest-randomly`, which can only be proven by running the suite under
> several seeds — so deliverable 2 is **explicitly allowed** to run
> `make test-unit` (×3 seeds) and `make test-integration` (×1 seed), and
> *only* that. This is a designed, bounded exception, not licence to
> re-run suites "to be safe": outside deliverable 2 the standard rule
> still applies in full — no `make check`, no extra `make test-integration`,
> targeted runs only for your own verification (deliverable 9).

After implementation, verify your own changes — but **DO NOT run the full
test suite** beyond the bounded deliverable-2 sweep above. Full-suite
execution is otherwise owned by the dedicated QV gate steps downstream
(`unit-tests`, `integration-tests`, `frontend-tests`); duplicating them here
burns this step's budget and is a common cause of step timeouts (see
I-00073/S03 post-mortem, 2026-05-08).

Scope rules:

1. **Tests step (`tests-impl`)** — run only the test file(s) **you wrote or
   modified** in this step:
   ```bash
   uv run pytest tests/integration/path/to/your_new_test.py -v
   ```
   That is sufficient to prove your tests work. The QV-gate steps downstream
   re-run the full suites with their own (longer) budgets. (For *this* CR,
   the one extra allowance is deliverable 2's bounded multi-seed sweep —
   `make test-unit` ×3 + `make test-integration` ×1 — which is a required
   part of the change, not a "be safe" re-run; see the exception box above.)

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
  "work_item": "CR-00048",
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
  "test_summary": "X passed, 0 failed (under randomized order)",
  "tdd_red_evidence": "tests/unit/test_safe_migrate.py::TestApply::test_apply_refuses_in_agent_context (and ::TestRollback::test_rollback_refuses_in_agent_context) — RED with IW_CORE_PER_WORKTREE_DB=true in env: 'Failed: DID NOT RAISE AgentContextForbiddenError'; GREEN after deliverable 6 controls the leaking env var",
  "blockers": [],
  "notes": "Added pytest-randomly / vulture / deptry (uv.lock regenerated). Order-dependent failures under randomization: <N found> → <M fixed> + <K quarantined @pytest.mark.order_dependent> [+ filed P1-CR-C-followup] [OR: fell back to `-p no:randomly` off-by-default — see changelog]. Typo'd markers fixed: <list or 'none'>. vulture/deptry are warn-only (|| true in `make quality` + a continue-on-error GH step) — they print, they don't block. Ran `iw sync-skills` (iw-ai-core-testing [+ iw-workflow if a marker was documented there]). Did NOT run iw sync-templates (no template edits). Items 1.4/1.5/1.7 ticked. Sibling repos pick up any iw-workflow change at their next iw sync-skills; iw-ai-core-testing is project-specific."
}
```

- `tdd_red_evidence`: this step's behavioural anchor is the `test_safe_migrate.py` fix (deliverables 0 & 6). Record the RED run you captured in deliverable 0 — `Failed: DID NOT RAISE AgentContextForbiddenError` (not an import/collection error). The order-dependent test fixes are also test-side but the `test_safe_migrate` fix is the canonical one to cite. Do not write `"n/a"` — this CR has a real behavioural test fix.

- `completion_status`: Use `complete` when all deliverables are done and tests pass. Use `partial` if some deliverables are done but others remain. Use `blocked` if external dependencies prevent progress.
- `blockers`: List any issues that prevented full completion. Include enough detail for the orchestrator to decide next steps.
- `notes`: Any context the next step or reviewer should know.
