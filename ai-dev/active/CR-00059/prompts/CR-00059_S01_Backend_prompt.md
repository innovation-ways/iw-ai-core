# CR-00059_S01_Backend_prompt

**Work Item**: CR-00059 -- Mutation testing spike + setup on `orch/daemon/` (P2-CR-A)
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Allowed exceptions:
  1. Testcontainers spun up by pytest fixtures (Ryuk handles teardown). mutmut's runner invokes pytest, which in turn spins up the existing session-scoped `pg_container` testcontainer — that path is allowed.
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets.

If your task seems to require a prohibited command, STOP and raise a blocker.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This CR adds **no** migrations. If your work seems to need one, you have gone outside scope — stop and raise a blocker.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status CR-00059 --json`. The `workflow-manifest.json` is a design-time snapshot (CR-00023).
- `ai-dev/active/CR-00059/CR-00059_CR_Design.md` -- **Source of truth** for scope, ACs (AC1–AC9), and the spike measurement-table requirement. Read first.
- `ai-dev/active/CR-00059/CR-00059_Functional.md` -- Human-facing summary.
- `iw-doc-plan/main/iw-doc-plan/Makefile` lines 444–500 — the InnoForge mutmut Makefile pattern you port.
- `iw-doc-plan/main/iw-doc-plan/pyproject.toml` lines 256–262 — the `[tool.mutmut]` config block being ported.
- `pyproject.toml` — current file. `[dependency-groups] dev` is at lines 76–104; `[tool.deptry]` ends at line ~213 (your insertion point for `[tool.mutmut]`).
- `Makefile` — current file. `.PHONY` lines 5–13 (add 4 new target names); `diff-coverage` recipe at lines 110–141 is the model for "self-contained slow target".
- `docs/IW_AI_Core_Testing_Strategy.md` — §5 (gate table), §8 ("Mutation testing awareness", currently says "not yet set up"), §9 (known-gaps table, row "Mutation testing": ❌).
- `ai-dev/work/TESTS_ENHANCEMENT.md` — §5 (CR grouping table; you add a `P2-CR-A-followup-mutation-block` row), §6 (item 2.1 row; flip TODO → IN PROGRESS), §11 (dated changelog).
- `orch/daemon/` — 26 source files; the spike target. Survey first to confirm what mutmut will mutate.
- `tests/unit/daemon/` (9 test files) + `tests/integration/daemon/` (7 test files) — the matching tests that the mutmut runner invokes.
- `tests/conftest.py` — the live-DB write guard (`IW_CORE_TEST_CONTEXT=true`, hijacked `IW_CORE_DB_*`). mutmut subprocesses must inherit those env vars; the spike report calls out any guard misfire.
- `tests/integration/conftest.py` — testcontainer + FTS trigger setup. Relevant infrastructure-blocker checks during the spike.
- `CLAUDE.md` for project-wide rules.

## Output Files

- `ai-dev/active/CR-00059/reports/CR-00059_S01_Backend_report.md` -- Step report (MUST include the spike measurement table inline — see deliverable 5).
- `ai-dev/active/CR-00059/evidences/pre/cr-00059-spike-measurements.txt` -- the spike's measurement table (also embedded in step report; this file is the canonical artefact reviewers compare against).
- `tests/unit/test_mutmut_setup.py` -- new RED-first guard test.
- `pyproject.toml` -- patched (`mutmut` dev dep + `[tool.mutmut]` block).
- `uv.lock` -- regenerated.
- `Makefile` -- patched (4 new `mutation-*` recipes + 4 names added to `.PHONY`).
- `docs/IW_AI_Core_Testing_Strategy.md` -- patched §5/§8/§9.
- `ai-dev/work/TESTS_ENHANCEMENT.md` -- patched §5 (+ follow-up row) / §6 (item 2.1) / §11 (new changelog entry).

## Context

You are implementing **CR-00059 — Mutation testing spike + setup on `orch/daemon/` (P2-CR-A)**, the first Phase-2 CR. **Read `ai-dev/active/CR-00059/CR-00059_CR_Design.md` first.** Its "Current Behavior" (no mutmut, no config, no recipes, strategy §8 says "not yet set up"), "Desired Behavior" (dep + config + 4 recipes + spike measurement + doc updates), "Acceptance Criteria" (AC1–AC9), and "Notes" (especially the `-x --tb=no -q` runner convention, the bounded `orch/daemon/` scope, and the no-PR-gate operator decision) are the source of truth.

This is the **only** implementation step in this CR. Scope is `pyproject.toml` + `Makefile` + one new guard test + four docs/plan files. **No production code** under `orch/`, `dashboard/`, or `executor/` may be touched.

## Requirements

Do these in order. Deliverable 0 is your RED capture; deliverables 1–6 are the implementation; deliverable 7 is the spike measurement (the actual mutmut audit run); deliverable 8 is the doc/plan updates.

### 0. RED — write the guard test FIRST, run it, confirm it fails

Create `tests/unit/test_mutmut_setup.py` with two tests:

```python
"""Pins the mutmut configuration so future edits don't silently drift away.

Written RED-first for CR-00059 (P2-CR-A): both tests fail before [tool.mutmut]
and the Makefile mutation-* recipes exist, and pass after S01 lands them.
"""
import subprocess
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_pyproject_tool_mutmut_block_pins_orch_daemon_target():
    """[tool.mutmut] must exist with the three expected keys scoped to orch/daemon/."""
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())

    assert "mutmut" in data["tool"], (
        "[tool.mutmut] block missing — CR-00059 requires it for mutation testing"
    )
    block = data["tool"]["mutmut"]

    assert block["paths_to_mutate"] == "orch/daemon/", (
        f"paths_to_mutate must be 'orch/daemon/' (spike scope per CR-00059); got {block['paths_to_mutate']!r}"
    )
    assert block["tests_dir"] == "tests/unit/daemon/ tests/integration/daemon/", (
        f"tests_dir must scope to daemon test dirs; got {block['tests_dir']!r}"
    )
    assert "pytest" in block["runner"] and "-x" in block["runner"], (
        f"runner must invoke pytest with -x (stop-on-first-fail per mutmut convention); got {block['runner']!r}"
    )


def test_makefile_exposes_four_mutation_targets():
    """All four `mutation-*` targets must parse via `make -n`."""
    for target, extra in [
        ("mutation-check", ["MODULE=orch/daemon/auto_merge.py"]),
        ("mutation-audit", []),
        ("mutation-results", []),
        ("mutation-show", ["ID=1"]),
    ]:
        result = subprocess.run(
            ["make", "-n", target, *extra],
            cwd=REPO_ROOT, capture_output=True, text=True, check=False,
        )
        assert "No rule to make target" not in result.stderr, (
            f"make -n {target} {extra}: target missing — CR-00059 must land all four recipes\n{result.stderr}"
        )
        assert result.returncode == 0, (
            f"make -n {target} {extra}: parse failed (rc={result.returncode})\n{result.stderr}"
        )
```

Run it:

```bash
uv run pytest tests/unit/test_mutmut_setup.py -v
```

Both tests MUST fail (the first with `KeyError`/`AssertionError` because `[tool.mutmut]` isn't there yet; the second with the "No rule to make target" check or the parse-failure check). Capture the exact failure (test id + AssertionError line) for `tdd_red_evidence` in your result contract — `tdd_red_evidence` MUST quote one real failure line, not the literal string "n/a".

If the test errors out with `ImportError`/`SyntaxError`/collection-error, that's a broken test, not a real RED — fix the test and re-run before proceeding.

### 1. Add mutmut to dev deps

Edit `pyproject.toml` `[dependency-groups] dev` (lines 76–104). Add the line:

```
    "mutmut>=2.5,<3.0",
```

Place it alphabetically near `mypy` or after `freezegun` — match the surrounding ordering style.

Then regenerate the lockfile:

```bash
uv lock
```

Verify mutmut is installed and resolves:

```bash
uv sync
uv run mutmut --version
```

Should print a 2.x version (e.g. `2.5.0`). If not, STOP and raise a blocker.

### 2. Add the `[tool.mutmut]` config block

Edit `pyproject.toml`. After the `[tool.deptry]` block (ends around line 213), append:

```toml

# Mutation testing (CR-00059, P2-CR-A) — runs on-demand, NOT in CI yet.
# Usage: make mutation-check MODULE=orch/daemon/auto_merge.py
#        make mutation-audit (currently scoped to orch/daemon/; expand in follow-up CR P2-CR-A-followup-mutation-block)
[tool.mutmut]
paths_to_mutate = "orch/daemon/"
tests_dir = "tests/unit/daemon/ tests/integration/daemon/"
runner = "uv run pytest tests/unit/daemon/ tests/integration/daemon/ -x --tb=no -q"
```

Verify it parses:

```bash
python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['tool']['mutmut'])"
```

### 3. Add the four `make mutation-*` recipes

Edit `Makefile`.

**3a.** Update the `.PHONY` line (lines 5–13). Add a new logical line:

```
          mutation-check mutation-audit mutation-results mutation-show \
```

Insert it near `test-assertions diff-coverage \` to keep test-quality targets grouped.

**3b.** Add the four recipes near the end of the file (model on the existing `diff-coverage` block at lines 110–141 — comment header explaining the on-demand-not-CI semantics). Ported from `iw-doc-plan/main/iw-doc-plan/Makefile:444–500`:

```make
# =============================================================================
# MUTATION TESTING (CR-00059, P2-CR-A) — on-demand, NOT a CI gate yet
# =============================================================================
# mutmut runs mutmut against orch/daemon/ — the spike target. Each mutant
# temporarily edits a single line of production code and re-runs the matching
# daemon tests (`tests/unit/daemon/` + `tests/integration/daemon/`). A mutant
# is "killed" when some test fails (good — the tests caught the bug); it
# "survives" when all tests still pass (bad — no test would have caught
# the regression).
#
# Runtime budget for `make mutation-audit` over orch/daemon/ is measured by
# the CR-00059 spike; expect on the order of tens of minutes. NOT wired into
# `make quality` / `make check` / any QV gate. Follow-up CR
# `P2-CR-A-followup-mutation-block` will widen scope and flip to blocking
# once the spike numbers inform thresholds.

mutation-check: ## Mutation test a single daemon module (usage: make mutation-check MODULE=orch/daemon/auto_merge.py)
	@if [ -z "$(MODULE)" ]; then \
		echo "Usage: make mutation-check MODULE=orch/daemon/<file>.py"; \
		echo "  Tip: the matching test files are auto-detected from the module path."; \
		exit 1; \
	fi
	@echo "Running mutation testing on $(MODULE)..."
	@rm -f .mutmut-cache
	@UNIT_TEST=$$(echo "$(MODULE)" | sed 's|orch/daemon/|tests/unit/daemon/test_|'); \
	INT_TEST=$$(echo "$(MODULE)" | sed 's|orch/daemon/|tests/integration/daemon/test_|'); \
	TARGETS=""; \
	[ -f "$$UNIT_TEST" ] && TARGETS="$$TARGETS $$UNIT_TEST"; \
	[ -f "$$INT_TEST" ] && TARGETS="$$TARGETS $$INT_TEST"; \
	if [ -z "$$TARGETS" ]; then \
		echo "No matching test files for $(MODULE) — running all daemon tests"; \
		TARGETS="tests/unit/daemon/ tests/integration/daemon/"; \
	else \
		echo "Using test files:$$TARGETS"; \
	fi; \
	echo "(Code is modified temporarily — originals are always restored.)"; \
	uv run mutmut run \
		--paths-to-mutate $(MODULE) \
		--runner "uv run pytest $$TARGETS -x --tb=no -q" \
		--tests-dir "tests/unit/daemon/ tests/integration/daemon/" \
		--simple-output
	@echo ""
	@echo "Results:"
	@uv run mutmut results
	@echo ""
	@echo "Use 'make mutation-show ID=N' to inspect surviving mutants."

mutation-audit: ## Mutation test all daemon modules (slow — spike target)
	@echo "Running mutation audit on orch/daemon/..."
	@echo "This may take 30–120 minutes depending on module count and test cost."
	@for MODULE in $$(find orch/daemon/ -name "*.py" -not -name "__init__.py" -not -path "*/__pycache__/*" | sort); do \
		echo ""; \
		echo "--- Mutating: $$MODULE ---"; \
		rm -f .mutmut-cache; \
		uv run mutmut run \
			--paths-to-mutate "$$MODULE" \
			--runner "uv run pytest tests/unit/daemon/ tests/integration/daemon/ -x --tb=no -q" \
			--tests-dir "tests/unit/daemon/ tests/integration/daemon/" \
			--simple-output --no-progress 2>&1 | tail -5; \
		uv run mutmut results 2>/dev/null; \
	done
	@echo ""
	@echo "Audit complete. Review surviving mutants with 'make mutation-show ID=N'."

mutation-results: ## Show results from the last mutation testing run
	uv run mutmut results

mutation-show: ## Inspect a specific surviving mutant (usage: make mutation-show ID=42)
	@if [ -z "$(ID)" ]; then \
		echo "Usage: make mutation-show ID=42"; \
		exit 1; \
	fi
	uv run mutmut show $(ID)
```

Verify each recipe parses:

```bash
make -n mutation-check MODULE=orch/daemon/auto_merge.py 2>&1 | head -20
make -n mutation-audit 2>&1 | head -5
make -n mutation-results 2>&1
make -n mutation-show ID=1 2>&1
```

None should print "No rule to make target".

### 4. GREEN — re-run the guard test

```bash
uv run pytest tests/unit/test_mutmut_setup.py -v
```

Both tests MUST pass now. Record the GREEN result in the step report.

### 5. The SPIKE — run `make mutation-audit` against `orch/daemon/`

This is the central deliverable of this CR.

```bash
time make mutation-audit
```

Budget: **up to 3600 s** (the S01 timeout). If the run is going to exceed 3600 s, you should still let it complete because (a) the measurement is the entire point of the spike, and (b) the follow-up CR's design depends on knowing the actual cost. If it must be killed, treat the truncated result as the measurement (record the kill point), document it as an infrastructure blocker, and proceed.

While the audit runs, monitor:

- Does each per-module sub-run start a fresh testcontainer (slow) or reuse the session container? (Each mutant runs a fresh pytest subprocess, so each pays the testcontainer startup cost unless mutmut's `--runner` somehow shares the container.)
- Do any mutants fail with errors that aren't "test failed" — e.g. `LiveDbConnectionRefusedError` (the guard is firing on a mutmut subprocess that didn't inherit `IW_CORE_DB_*`), missing FTS trigger, etc.? Those are **infrastructure blockers**, not legitimate mutant kills.
- Track wall-clock per module to identify outliers.

After completion, build the measurement table. Save it BOTH inline in the step report AND as a text file at `ai-dev/active/CR-00059/evidences/pre/cr-00059-spike-measurements.txt`. Template:

```
CR-00059 — Mutation testing spike (P2-CR-A)
Date: <YYYY-MM-DD>
Scope: orch/daemon/ (audit via `make mutation-audit`)

| Metric                          | Value           |
|---------------------------------|-----------------|
| Total mutants generated         | <N>             |
| Killed                          | <K>             |
| Survived                        | <S>             |
| Timeout                         | <T>             |
| Suspicious                      | <Sus>           |
| Mutation score (K / (K+S) × 100)| <pct>%          |
| Wall-clock (total)              | <H:MM:SS>       |
| Modules covered                 | <count> of <N>  |

Modules covered (list):
- orch/daemon/auto_merge.py
- orch/daemon/batch_manager.py
- ...

Top 5 surviving mutants (queue for P2-CR-A-followup):
| ID  | File:Line                          | Mutation (brief)               |
|-----|------------------------------------|--------------------------------|
| <n> | orch/daemon/<f>.py:<L>             | <e.g. `> 0` → `>= 0`>          |
| ... | ...                                | ...                            |

Infrastructure blockers encountered:
- <free text — e.g. "testcontainer cold-start adds ~2.1s per mutant subprocess; this accounts for the bulk of wall-clock cost">
- <e.g. "FTS trigger replays cleanly per session — no false-kills observed">
- <e.g. "live-DB write guard inherited correctly by mutmut subprocesses — IW_CORE_DB_* env vars propagate">
- <or: "None observed">

Notes for follow-up CR (P2-CR-A-followup-mutation-block):
- <e.g. "Wall-clock budget for full-orch/ audit would be ~Nx larger (~M minutes) — viable for nightly cron, NOT for per-PR daemon gate">
- <e.g. "Recommended PR-gate scope: changed-files-only (cache-warmed from main) — keeps per-PR cost <5min">
- <e.g. "Recommended initial threshold: ≥<score>% mutation score (the spike measurement, ratcheting upward)">
```

All numeric cells MUST be real numbers, not placeholders. If you cannot fill a row, raise a blocker rather than emit "TBD" — the measurement table IS the deliverable.

### 6. Update strategy doc

Edit `docs/IW_AI_Core_Testing_Strategy.md`:

**§5 gate table.** Add a new row (after "Smoke" or grouped with on-demand items):

| Mutation testing | `mutmut>=2.5,<3.0` | on-demand only (NOT in CI); spike score on `orch/daemon/` = <pct>% (CR-00059); follow-up CR will wire blocking PR gate | `make mutation-check MODULE=...` / `make mutation-audit` |

**§8 ("Mutation testing awareness").** Replace the current "not yet set up" paragraph with factual prose:

> Mutation testing measures whether the test suite would actually fail when production code regresses. **Installed in CR-00059 (2026-MM-DD)** via `mutmut>=2.5,<3.0`. Four `make` targets are available: `mutation-check MODULE=<path>` (single module — quick), `mutation-audit` (currently scoped to `orch/daemon/` — slow, on-demand), `mutation-results` (re-display cached results), `mutation-show ID=<n>` (inspect one surviving mutant).
>
> **Spike measurement on `orch/daemon/` (CR-00059):** <N> mutants generated, <K> killed, <S> survived, score = <pct>%; wall-clock <H:MM:SS> on a typical dev box. The surviving-mutant list is the queue for `P2-CR-A-followup-mutation-block`, which will widen scope beyond the daemon and flip the measurement into a blocking PR gate once the spike numbers inform a sensible threshold and gate surface (daemon QV vs GH workflow).

**§9 known-gaps row "Mutation testing".** Flip from `❌ (2.1)` to `⚠️ (CR-00059, 2026-MM-DD) — foundation + spike landed; broader scope + blocking PR gate deferred to P2-CR-A-followup-mutation-block`.

### 7. Update TESTS_ENHANCEMENT.md

Edit `ai-dev/work/TESTS_ENHANCEMENT.md`:

**§5 CR grouping table.** Add a new follow-up row near the existing `P1-CR-A-followup` row:

| **P2-CR-A-followup-mutation-block — Widen mutation scope + flip to blocking PR gate** | (cleanup of 2.1) | After CR-00059's spike informs (a) per-mutant cost and (b) whether daemon-only is too narrow: widen `[tool.mutmut].paths_to_mutate` from `orch/daemon/` to all of `orch/`; pick gate surface (daemon QV `mutation-check` with cache-warm-from-main, OR GH workflow step) based on spike runtime; pick blocking threshold based on spike score; flip from `|| true` to blocking after a burn-in period. | Cost-of-running unknown until CR-00059 ships. Recommend a second small spike on the broader scope before flipping blocking. |

**§6 item 2.1 row.** Update Status column from `TODO` to:

`IN PROGRESS — CR-00059 shipped foundation (mutmut dep + config + 4 make targets + spike on orch/daemon/, score <pct>%, <H:MM:SS> wall-clock); follow-up CR P2-CR-A-followup-mutation-block will widen scope + flip to blocking`

**§11 changelog.** Add a new dated entry at the top of the changelog list:

> - **2026-MM-DD** — **CR-00059 shipped (P2-CR-A, mutation testing spike + setup).** Phase 2 begins. `mutmut>=2.5,<3.0` added to dev deps; `[tool.mutmut]` block in `pyproject.toml` scopes `paths_to_mutate = "orch/daemon/"` (spike target); 4 `make mutation-{check,audit,results,show}` recipes ported from InnoForge's `Makefile:444–500` pattern, all added to `.PHONY`; new RED-first guard test `tests/unit/test_mutmut_setup.py` (2 cases). **Spike on `orch/daemon/`**: <N> mutants generated, <K> killed, <S> survived, score = <pct>%, wall-clock <H:MM:SS>; full measurement table at `ai-dev/active/CR-00059/evidences/pre/cr-00059-spike-measurements.txt`. Infrastructure observations: <one-liner — e.g. "testcontainer per-mutant cost dominates; no guard misfires; FTS trigger replays cleanly">. Strategy doc §5/§8/§9 rewritten; item 2.1 → IN PROGRESS. Follow-up `P2-CR-A-followup-mutation-block` filed (§5) — widens scope to all `orch/` + flips to blocking PR gate, choice of surface (daemon QV vs GH workflow) informed by these spike numbers. Mutmut is **on-demand only** today — NOT a `make quality` step, NOT in `make check`, NOT a QV gate, NOT a GH workflow step. Sibling repos (`iw-doc-plan` already has mutmut; `podforger`/`cv` don't) pick up via their own cadence.

Replace `<N>`, `<K>`, `<S>`, `<pct>`, `<H:MM:SS>`, and the MM-DD with the actual values from your spike.

## Verification

### Pre-flight (mandatory)

Before reporting `completion_status: complete`:

1. `make format` — auto-fixes formatting drift; re-stage if changes.
2. `make typecheck` — zero errors on touched files.
3. `make lint` — zero errors.

If any tool isn't available, STOP and raise a blocker. Populate the `preflight` object accordingly.

## Test Verification (NON-NEGOTIABLE)

Targeted verification only:

1. `uv run pytest tests/unit/test_mutmut_setup.py -v` → 2 passes.
2. `make -n mutation-check MODULE=orch/daemon/auto_merge.py` → parses, prints a recipe.
3. `make -n mutation-audit && make -n mutation-results && make -n mutation-show ID=1` → all parse.
4. `uv run mutmut --version` → prints 2.x.

Do **NOT** run full suites. S04–S11 own that. The `make mutation-audit` run in deliverable 5 is the spike, not a verification — it's the deliverable.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "CR-00059",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "pyproject.toml",
    "uv.lock",
    "Makefile",
    "tests/unit/test_mutmut_setup.py",
    "docs/IW_AI_Core_Testing_Strategy.md",
    "ai-dev/work/TESTS_ENHANCEMENT.md"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "tests/unit/test_mutmut_setup.py: 2/2 pass. `make -n mutation-{check,audit,results,show}`: all parse. `uv run mutmut --version`: 2.x.x. SPIKE: make mutation-audit orch/daemon/ — <N> mutants, <K> killed, <S> survived, score <pct>%, wall-clock <H:MM:SS>.",
  "tdd_red_evidence": "tests/unit/test_mutmut_setup.py::test_pyproject_tool_mutmut_block_pins_orch_daemon_target FAILED (pre-patch): KeyError: 'mutmut' at line <L> — '[tool.mutmut]' block missing from pyproject.toml. tests/unit/test_mutmut_setup.py::test_makefile_exposes_four_mutation_targets FAILED (pre-patch): AssertionError at line <L> — 'make -n mutation-check' returned 'No rule to make target mutation-check'. Captured at ai-dev/active/CR-00059/evidences/pre/cr-00059-red-evidence.txt (optional).",
  "blockers": [],
  "notes": "Phase 2 inaugural CR. Spike scope: orch/daemon/ (26 source files). Spike numbers: <N> mutants, <pct>% score, <H:MM:SS>. Top surviving mutants: see ai-dev/active/CR-00059/evidences/pre/cr-00059-spike-measurements.txt. Infrastructure observations: <one-liner>. Follow-up CR P2-CR-A-followup-mutation-block filed in §5 — informs gate surface (daemon QV vs GH workflow) and threshold from these numbers."
}
```

- `tdd_red_evidence`: MUST quote a real test id + a real failure line from the RED run of `tests/unit/test_mutmut_setup.py`. Do not write `"n/a"` — this is a behavioural step (it introduces new test-quality infrastructure with a guard test).
- `completion_status`:
  - `complete` if deliverables 0–8 all done, both guard tests pass, the spike measurement table is populated with real numbers, the docs and plan are updated.
  - `partial` if the spike runs but truncates before completion (still record actual numbers up to truncation point; file a note for the follow-up CR).
  - `blocked` if (a) mutmut won't install (incompatible Python version, dep conflict), (b) every spike mutant fails due to an infrastructure blocker (live-DB guard misfire, missing FTS trigger, etc.), or (c) `uv lock` corrupts the lockfile. Raise a blocker — do not paper over with "TBD" values.
- `blockers`: any of the above OR any case where the spike's measurement cannot be made truthful.
