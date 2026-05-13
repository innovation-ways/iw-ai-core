# CR-00049_S01_Backend_prompt

**Work Item**: CR-00049 -- Re-enable `pytest-randomly` by default (P1-CR-C-followup-randomly)
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

This CR adds **no** migrations. If your work seems to need one, you have
gone outside scope — stop and raise a blocker.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — for the current step list, status, prompt paths, gate commands, etc., prefer `uv run iw item-status CR-00049 --json`. The `workflow-manifest.json` file is a design-time snapshot and may be out of date (CR-00023).
- `ai-dev/active/CR-00049/CR-00049_CR_Design.md` -- **Source of truth** for scope, ACs, and the failure list. Read first.
- `ai-dev/active/CR-00049/CR-00049_Functional.md` -- Human-facing summary.
- `ai-dev/work/TESTS_ENHANCEMENT.md` §5 row `P1-CR-C-followup-randomly`, item 1.4 row, and the §11 changelog entry dated 2026-05-12 / 2026-05-13 (CR-00048's fallback story).
- `tests/CLAUDE.md` §7 (current off-by-default state + opt-in recipe + cleanup contract — you will flip this).
- `docs/IW_AI_Core_Testing_Strategy.md` §3 (pytest-randomly subsection) and §9 row "Test-order randomisation (`pytest-randomly`)" — both currently ⚠️; you will flip them to ✅.
- `skills/iw-ai-core-testing/SKILL.md` §2 — current opt-in recipe; will be flipped.
- `pyproject.toml` lines 132–155 — the `[tool.pytest.ini_options]` block (`addopts` is line 148; the `order_dependent` marker is line 154).
- `tests/conftest.py` line 28 (autouse session fixture — prime suspect for the leak).
- `tests/integration/conftest.py` lines 181 + 192 (session-scoped fixtures — prime suspects).
- `tests/unit/test_browser_env.py:423` (existing `@pytest.mark.order_dependent` + `xfail(strict=False)` — the established quarantine pattern; mirror it byte-for-byte).
- `CLAUDE.md` for project-wide rules (testcontainer-only, `monkeypatch.delenv` over `importlib.reload`, FTS DDL, `event_metadata`, per-worktree-DB caveats).

## Output Files

- `ai-dev/active/CR-00049/reports/CR-00049_S01_Backend_report.md` -- Step report

## Context

You are implementing **CR-00049 — Re-enable `pytest-randomly` by default**. This is the cleanup follow-up filed by CR-00048 (merged `a789701`, 2026-05-13) when its `make diff-coverage` gate burned 5 fix cycles on order-dependent integration fixture failures and we shipped with `-p no:randomly` off-by-default per CR-00048's AC1 escape clause.

**Read `ai-dev/active/CR-00049/CR-00049_CR_Design.md` first.** Its "Current Behavior", "Desired Behavior", "Acceptance Criteria" (AC1–AC5), "Impacted Paths", and "Notes" sections are the source of truth. The Notes section in particular explains why CR-00048 missed this (S01's bounded sweep used `make test-unit` + `make test-integration`, never `make diff-coverage` — and `make allure-integration` is a no-op stub today, so the integration suite was effectively only exercised by the diff-coverage gate).

The only implementation step in this CR. No Database / API / Frontend / Pipeline / Template steps. Scope is tests + configs + docs only.

## Requirements

Do these in order. Deliverable 0 is your RED reproduction; deliverables 1–4 are the fix; deliverables 5–8 are documentation, plan updates, and sync.

### 0. RED — reproduce the order-dependent failures

Run the exact reproduction recipe documented in the design's *Current Behavior* section:

```bash
uv run pytest tests/integration/ tests/dashboard/ --ignore=tests/dashboard/browser -p randomly --randomly-seed=12345 -q 2>&1 | tail -120
```

Confirm the run produces collection-time `ERROR` lines (NOT `FAIL` — these are setup-phase errors, the `sqla…` truncations are the signature) across (most of) these 12 modules:

- `tests/integration/test_cli_steps.py`
- `tests/integration/test_dashboard_fragments.py`
- `tests/integration/test_history_sorting.py`
- `tests/integration/test_code_qa_routes.py`
- `tests/integration/test_doc_job_log_endpoints.py`
- `tests/integration/test_step_monitor_lifecycle.py`
- `tests/integration/test_register_persists_dependencies.py`
- `tests/integration/test_invariants_f00060.py`
- `tests/integration/test_phantom_gate_auto_skip.py`
- `tests/integration/test_project_onboarding_api.py`
- `tests/integration/daemon/test_batch_manager_scope_gate.py`
- `tests/integration/dashboard/test_F00077_enqueue_idempotency.py`

Capture the full failure list (module → list of failing test names) and the **untruncated first stack trace** from one of the `sqla…` errors — this is your `tdd_red_evidence` and the diagnostic data deliverable 1 needs. If a module is *missing* from the failure list (the leak depends on which modules co-collect, which depends on the seed), note that — it may pass under seed 12345 and fail under another. The full RED set is what deliverable 4 must turn green; for now just record what seed 12345 produces.

**Do not just trust the design's list — verify it.** If your reproduction surfaces *additional* modules not on the design's list, add them to your tracking and treat them with the same triage. If it surfaces *fewer*, note which seed-12345-specific modules failed.

### 1. Diagnose the leak

The truncated `sqla…` pattern + the fact every offender errors at collection/setup (not at assertion) + the cross-module spread strongly suggests **a shared `conftest.py` fixture with hidden ordering dependence — most likely a session-scoped fixture in `tests/conftest.py` (autouse session at line 28) or `tests/integration/conftest.py` (sessions at lines 181 + 192)**. Read those fixtures. The suspects to investigate, in priority order:

1. The session-scoped Postgres testcontainer / engine + the FTS DDL hook (per `CLAUDE.md`: "**MUST** run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()` in tests"). If the FTS hook depends on a particular import order or a module-level side effect, randomising file order can mean it runs against a not-yet-fully-built schema.
2. The autouse session fixture in `tests/conftest.py:28` — what does it touch? An autouse fixture running before tests collect can mutate module-level state that another module's collection then depends on.
3. The live-DB write guard (`CLAUDE.md`: "**NEVER** connect tests to live DB (port 5433) — use testcontainers only"). If the guard is armed via a module-level statement rather than a fixture, the order in which test modules import determines whether it's armed before or after a class-level fixture builds an engine.
4. `IW_CORE_PER_WORKTREE_DB` leakage (see CR-00048 S01 deliverable 6 — `test_safe_migrate.py` had this exact class of bug).

Read the full traceback you captured in deliverable 0 — it will name the actual file/line where collection blew up. Trace back to which fixture produced the `sqla…` object. That fixture (or its session-scoped neighbour) is the leak.

### 2. Fix the leak where reasonable

If a single fixture fix cascades through many of the 12 modules (likely), land the fixture fix first, then re-run the reproduction recipe. Common fix patterns:

- A session-scoped fixture missing a teardown that resets a module-level cache or environment variable.
- An autouse fixture relying on a module's import-time side effect (e.g., a module that mutates `os.environ` at import). Replace with `monkeypatch` inside the fixture.
- A fixture that builds an engine before `FTS_FUNCTION_SQL`/`FTS_TRIGGER_SQL` are installed when called in the "wrong" order. Make the install idempotent or move it to a higher-scoped fixture that always runs first.
- An autouse fixture that uses `clear=False` patch.dict and inherits ambient `IW_CORE_PER_WORKTREE_DB=true` only in some orders. Add an explicit `delenv`.

**Test-isolation fixes only — no behavioural test changes, no weakened assertions, no production code changes.** Document any fixture fix at the fixture site with a comment: `# CR-00049: …` naming what was leaking and why.

### 3. Quarantine the residue

For any offender that survives the fixture fix (or that you cannot fix at the fixture level within budget), apply the established quarantine pattern from `tests/unit/test_browser_env.py:423` byte-for-byte:

```python
@pytest.mark.order_dependent
@pytest.mark.xfail(strict=False, reason="<one-line: which fixture/state is leaking, and what other test(s) it depends on>")
def test_x(...):
    # NOTE(P1-CR-C-followup-randomly): <leak source>; file a sub-follow-up if non-trivial
    ...
```

Hard rules for quarantines:

- The `order_dependent` marker is **already registered** in `pyproject.toml` line 154 — do NOT duplicate the registration.
- The `xfail` MUST be `strict=False` (because the test passes in alphabetical order — strict=True would make a green run xpass-fail).
- The `reason` string MUST name what's leaking, not just "order-dependent" (e.g. `reason="depends on test_X running first to seed the FTS index"`).
- Do NOT use `@pytest.mark.skip` or comment the test out. Quarantined tests must still run.
- Every quarantine added in this CR is filed as a one-line bullet in `ai-dev/work/TESTS_ENHANCEMENT.md` §5 under a new "P1-CR-C-followup-randomly residue" sub-row (or as individual rows if the count is small).

### 4. Iterate the multi-seed sweep until clean

Run the reproduction across 4 seeds:

```bash
for seed in 12345 67890 11111 42424; do
  echo "=== seed $seed ==="
  uv run pytest tests/integration/ tests/dashboard/ --ignore=tests/dashboard/browser -p randomly --randomly-seed=$seed -q 2>&1 | tail -10
done
```

End state (mandatory): **all 4 runs exit 0**. (Quarantined tests show as `xfailed` — that counts as passing.) If a 5th seed surfaces a new offender after you've declared victory on 4, treat that as additional triage and either fix or quarantine.

**Time budget**: this step carries a **2400-second** timeout, and the multi-seed sweep is expensive. Allocate roughly: 5 min reading + diagnosing (deliverables 0–1), 15 min fixing fixtures (deliverable 2), 10 min quarantining residue (deliverable 3), 5 min sweep verification (this deliverable), 5 min docs (5–7). If you're at minute 30 and the sweep still has >5 modules failing, **stop trying to fix more leaks and quarantine the rest** — that's the explicit pressure-relief valve.

Do NOT re-run `make test-integration` or `make diff-coverage` here — those are S09 / S10's job (and `make test-integration` is the same costly invocation). Targeted `pytest` runs with `-p randomly` only.

### 5. Remove `-p no:randomly` from `addopts`

Once deliverable 4's sweep is clean, edit `pyproject.toml` `[tool.pytest.ini_options]`:

- Remove `-p no:randomly` from the `addopts` string.
- Rewrite the comment block above `addopts` to reflect the new state: `pytest-randomly` is default-on; the fallback paragraph becomes a brief historical note ("Earlier fallback (CR-00048): `-p no:randomly` was added because S01's bounded sweep missed `make diff-coverage`'s integration-collection failures; this CR cleaned up the underlying leaks and re-enabled randomisation by default.").
- Confirm the line still ends with `--strict-markers` (do not regress S01's marker change).

### 6. Documentation flips

For each of these files, flip the prose from "off-by-default + opt-in recipe" to "default-on + reproduce recipe + quarantine policy". Move the old fallback paragraph into a short "Earlier fallback (CR-00048)" historical note at the end of the section — do NOT silently delete it:

- `tests/CLAUDE.md` §7 ("pytest-randomly — test-order randomisation")
- `docs/IW_AI_Core_Testing_Strategy.md` §3 subsection ("pytest-randomly — test-order randomisation (CR-00048, P1-CR-C — fallback)" → rename and rewrite for CR-00049)
- `docs/IW_AI_Core_Testing_Strategy.md` §9 row "Test-order randomisation (`pytest-randomly`)" — flip ⚠️ to ✅; new prefix `"✅ (CR-00049, YYYY-MM-DD) — default-on; suite robust to randomisation; …"`
- `skills/iw-ai-core-testing/SKILL.md` §2 ("pytest-randomly — test-order randomisation (currently OFF-by-default)" → rename and rewrite)

Reproduce recipe in the new prose:

```bash
# Default — runs are randomised; seed prints at the top
make test-unit

# Reproduce a specific failure
pytest --randomly-seed=<N> ...

# Temporarily disable for triage of a single ad-hoc run
pytest -p no:randomly ...
```

### 7. Plan + changelog updates

Edit `ai-dev/work/TESTS_ENHANCEMENT.md`:

- **§5 grouping table** — find the row `**P1-CR-C-followup-randomly — Re-enable `pytest-randomly` by default**` and update its status column from open/in-progress to **DONE (CR-00049, YYYY-MM-DD)** with the fix-vs-quarantine counts (e.g. `"<N> fixture-leak fixes; <M> tests quarantined with @pytest.mark.order_dependent + xfail(strict=False)"`). If you filed any sub-follow-up for individual quarantines that warrant their own future cleanup, add them as new rows below.
- **Item 1.4 row** — change the status column from `⚠️ **PARTIAL (CR-00048, 2026-05-13) — fallback used**` to `✅ **DONE (CR-00049, YYYY-MM-DD)**` with a one-liner naming what changed: `"removed -p no:randomly from addopts; fixture leak in tests/<conftest path> fixed; <M> integration tests quarantined; suite green across 4 seeds + S08 + S10."`
- **§11 changelog** — add a new entry dated YYYY-MM-DD. Format: "**YYYY-MM-DD** — **Item 1.4 completed → CR-00049 (P1-CR-C-followup-randomly).** `-p no:randomly` removed from `pyproject.toml [tool.pytest.ini_options] addopts`. RED reproduction: `pytest tests/integration/ tests/dashboard/ -p randomly --randomly-seed=12345 -q` produced <N> collection-time `sqla…` errors across <list of modules from your deliverable 0>. Root cause: <one-line — fixture name + leak mechanism, e.g. 'tests/conftest.py:28 autouse session fixture left IW_CORE_PER_WORKTREE_DB in os.environ after the worktree compose tests ran first'>. Fixes: <N> fixture-level (list at the fixture sites). Quarantines: <M> tests marked `@pytest.mark.order_dependent` + `@pytest.mark.xfail(strict=False)` (list inline). Seeds 12345/67890/11111/42424 all green. Docs flipped to default-on. `iw sync-skills --force iw-ai-core-testing` ran. Item 1.4 → DONE. P1-CR-C-followup-randomly → DONE."

### 8. Sync skills + targeted re-runs

- Run `uv run iw sync-skills --force iw-ai-core-testing`. The `--force` is required because `iw-ai-core-testing` is registered as a project override on iw-ai-core itself (the master and the deployed copy coexist).
- Verify with `git diff` that `.claude/skills/iw-ai-core-testing/SKILL.md` matches `skills/iw-ai-core-testing/SKILL.md` byte-for-byte.
- Targeted re-run each modified test file to confirm it still passes in deterministic order: `uv run pytest <file> -p no:randomly -q`. Then re-run under randomisation: `uv run pytest <file> -p randomly --randomly-seed=12345 -q`. Both must exit 0.
- **Do NOT** run `make check`, `make test-integration`, or `make diff-coverage` here — that's S08/S09/S10's job and re-running them risks a step timeout (the I-00073 lesson; also CR-00048's S01 had the same exception and worked correctly).
- **Do NOT** run `iw sync-templates` — this CR makes no template edits.

## Scope discipline

Touch ONLY the files in the design's "Impacted Paths":

- `pyproject.toml` (addopts edit + comment block rewrite)
- `tests/**` (fixture fixes + quarantine markers — no behavioural test changes)
- `docs/IW_AI_Core_Testing_Strategy.md` (§3 + §9 row flips)
- `skills/iw-ai-core-testing/SKILL.md` (§2 flip)
- `.claude/skills/iw-ai-core-testing/SKILL.md` (re-synced from above)
- `ai-dev/work/TESTS_ENHANCEMENT.md` (§5 row, item 1.4 row, §11 changelog)

Plus this CR's `ai-dev/active/CR-00049/**` (reports, evidence). **Diffs under `tests/` must be ONLY test-isolation fixes (fixture fixes) and quarantine markers — no behavioural test changes, no weakened assertions, no new test files.** Do **not** touch production code (`orch/`, `dashboard/`, `executor/`). Do **not** flip `vulture`/`deptry` to hard gates. Do **not** fix the `integration-tests` no-op gate (P1-CR-E). Do **not** port to sibling projects. Do **not** scrub the assertion baseline.

## Project Conventions

Read the project's `CLAUDE.md` for:

- Architecture patterns and layer boundaries
- Coding conventions and naming rules
- Test organization and fixtures
- Build and run commands

Follow all rules defined there exactly. When in doubt, match existing code.

## TDD Requirement

This CR's TDD anchor is **the RED reproduction itself** — deliverable 0's failing seed-12345 sweep. Record the exact `pytest` invocation + the top of the truncated `sqla…` traceback as `tdd_red_evidence`. The GREEN evidence is deliverable 4's 4-seed sweep ending all-clean. No new test files are needed; this CR fixes the test-infrastructure that already exists.

Do **not** write new tests to "prove" the fix — the existing 50-odd tests, now passing under randomisation, are the proof.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, you MUST run these in order and fix any issues they report. Skipping any of these wastes a fix-cycle slot when the QV gate steps catch the same issue downstream:

1. **`make format`** — auto-fixes formatting drift. If it reformats files, inspect the diff and re-stage; do NOT skip.
2. **`make typecheck`** — must report zero errors involving the files you touched.
3. **`make lint`** — must report zero errors.

If a tool isn't available in your worktree, STOP and raise a blocker — do not silently skip.

In your Subagent Result Contract, populate the `preflight` object recording the result of each command:
- `"ok"` — ran cleanly, no changes / no errors
- `"fixed"` — applies to `format` only; the tool auto-fixed something
- `"skipped:<reason>"` — only if you raised a blocker explaining why

## Test Verification (NON-NEGOTIABLE)

> **Bounded exception — this is a testing-infrastructure CR.** The standard rule is "an implementation step never runs the full suite, never touches `make test-integration` — that's the QV gates' job" (I-00073/S03 timeout lesson). CR-00049's *deliverable* is making the full integration + dashboard suite robust to `pytest-randomly` — provable only by running it under several seeds. Deliverables 0 + 4 are **explicitly allowed** to run `pytest tests/integration/ tests/dashboard/ --ignore=tests/dashboard/browser -p randomly --randomly-seed=<N>` (×4 seeds total). Outside those two deliverables the standard rule still applies in full — no `make check`, no `make test-integration`, no `make diff-coverage`, targeted runs only.

After implementation, verify your own changes — but **DO NOT run the full test suite** beyond the bounded sweep above. Full-suite execution is owned by the QV gate steps downstream (`unit-tests` S08, `integration-tests` S09 stub, `diff-coverage` S10).

Scope rules:

1. **This step** — bounded multi-seed sweep allowed (deliverables 0 + 4). Plus targeted `pytest <file>` runs for any file you edited (deliverable 8).
2. Run lint and type checking on your touched files (`make lint`, `make typecheck`).
3. Do **NOT** report `tests_passed: true` unless your deliverable-4 sweep is all-green AND your targeted re-runs pass.
4. If a seed surfaces a new offender mid-sweep, fix or quarantine it before reporting completion.

## Subagent Result Contract

When your work is complete, report results in this JSON structure:

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "CR-00049",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "pyproject.toml",
    "tests/<the conftest you fixed>",
    "tests/integration/<the modules you quarantined>",
    "tests/CLAUDE.md",
    "docs/IW_AI_Core_Testing_Strategy.md",
    "skills/iw-ai-core-testing/SKILL.md",
    ".claude/skills/iw-ai-core-testing/SKILL.md",
    "ai-dev/work/TESTS_ENHANCEMENT.md"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "Multi-seed sweep (12345/67890/11111/42424) of tests/integration/ + tests/dashboard/ under -p randomly: all four exit 0 (<N> passed, <M> xfailed-as-quarantined). Targeted file re-runs all green.",
  "tdd_red_evidence": "uv run pytest tests/integration/ tests/dashboard/ --ignore=tests/dashboard/browser -p randomly --randomly-seed=12345 -q  →  <N> ERROR lines at collection across <list of modules>; first stack trace: <one-line: file:line + the sqla… truncation>.",
  "blockers": [],
  "notes": "Removed -p no:randomly from pyproject.toml addopts. Root-cause leak: <fixture path + mechanism>. Fixes: <N> fixture-level (list with file:line). Quarantines: <M> tests marked @pytest.mark.order_dependent + @pytest.mark.xfail(strict=False, reason=...) — list with file:test_name. Docs (tests/CLAUDE.md §7, strategy §3 + §9 row, skill §2) flipped to default-on; old fallback prose preserved as 'Earlier fallback (CR-00048)' historical note. iw sync-skills --force iw-ai-core-testing ran (.claude/skills/ in sync). TESTS_ENHANCEMENT.md: §5 row + item 1.4 → DONE (CR-00049); §11 changelog appended."
}
```

- `tdd_red_evidence`: deliverable 0's failing seed-12345 sweep. Do not write `"n/a"`.
- `completion_status`: `complete` if all 8 deliverables done + sweep all-green; `partial` if you needed to quarantine a sub-set and filed sub-follow-ups; `blocked` if the leak resists both fixture fix and quarantine (extremely unlikely given the pressure-relief valve).
- `blockers`: List any issues that prevented full completion.
- `notes`: Counts, file paths, follow-ups filed.
