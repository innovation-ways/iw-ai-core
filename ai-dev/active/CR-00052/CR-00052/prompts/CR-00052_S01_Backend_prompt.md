# CR-00052_S01_Backend_prompt

**Work Item**: CR-00052 -- Allure reporting recipes + curated smoke layer with SLA (P1-CR-E)
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

Allowed exceptions:
  1. Testcontainers spun up by pytest fixtures (Ryuk handles teardown).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets.

If your task seems to require a prohibited command, STOP and raise a blocker.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This CR adds **no** migrations. If your work seems to need one, you have gone outside scope — stop and raise a blocker.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status CR-00052 --json`. The `workflow-manifest.json` is a design-time snapshot (CR-00023).
- `ai-dev/active/CR-00052/CR-00052_CR_Design.md` -- **Source of truth** for scope, ACs (AC1–AC9), and the audit-table requirement. Read first.
- `ai-dev/active/CR-00052/CR-00052_Functional.md` -- Human-facing summary.
- `iw-doc-plan/main/iw-doc-plan/Makefile` lines 318–348 — the InnoForge Allure pattern you port (verified 2026-05-14).
- `Makefile` — current file with the 6 empty `.PHONY` allure stubs + existing `make smoke` at line 107–108.
- `pyproject.toml` line 152 — current smoke marker description (`"~10 covering core flows"`).
- All current `@pytest.mark.smoke` test files (7 files, 16 markers total — verified 2026-05-14 by `grep -rc "@pytest.mark.smoke" tests/`):
  - `tests/unit/test_smoke.py` (7), `tests/integration/test_db_identity_integration.py` (3), `tests/integration/test_dashboard_remaining.py` (2), `tests/integration/test_dashboard_pages.py` (1), `tests/integration/test_cli_batches.py` (1), `tests/unit/test_daemon_core.py` (1), `tests/unit/dashboard/test_coverage_service.py` (1).
- `.gitignore` — current entries for the build artefact dirs.
- `tests/CLAUDE.md` — current structure (you add a "Smoke layer SLA" subsection).
- `docs/IW_AI_Core_Testing_Strategy.md` — §5/§6 area (you extend with the same SLA prose).
- `ai-dev/work/TESTS_ENHANCEMENT.md` — §5 P1-CR-E row + items 1.8 + 1.11 + §11 changelog (you update all four).
- `CLAUDE.md` for project-wide rules.

## Output Files

- `ai-dev/active/CR-00052/reports/CR-00052_S01_Backend_report.md` -- Step report (MUST include the audit table — see deliverable 3).

## Context

You are implementing **CR-00052 — Allure recipes + smoke SLA (P1-CR-E)**, Phase 1's last grouping CR. **Read `ai-dev/active/CR-00052/CR-00052_CR_Design.md` first.** Its "Current Behavior" (empty stubs + 16-smoke-test baseline), "Desired Behavior" (real recipes + ≤15 + <60 s + SLA prose), "Acceptance Criteria" (AC1–AC9), and "Notes" (especially S09 being the first real integration-tests gate run + the audit table being the deliverable) are the source of truth.

The only implementation step in this CR. Scope is Makefile + tests/markers + docs.

## Requirements

Do these in order. Deliverable 0 is your RED capture; deliverables 1-7 are the implementation.

### 0. RED — capture the current state

Two parts to RED:

**(a) Allure stubs prove they're no-ops:**

```bash
# Each of these should exit 0 with no output (proof of empty .PHONY stub).
for t in allure-unit allure-integration allure-all allure-report allure-serve allure-clean; do
  echo "=== make $t ==="
  make -n $t 2>&1 | head -3
done
```

Record the output verbatim. This is half your `tdd_red_evidence`: "the 6 allure-* targets are `.PHONY` stubs that exit 0 trivially without doing any work."

**(b) Smoke layer's current baseline:**

```bash
# Count smoke markers + measure wall-clock
echo "=== smoke marker count by file ==="
grep -rc "@pytest.mark.smoke" tests/ | grep -v ":0$" | sort

echo "=== wall-clock measurement ==="
time make smoke
```

Record: total count (expected 16), the wall-clock from `time make smoke`. This is the other half of `tdd_red_evidence`: "16 smoke-marked tests, X.Y s wall-clock, no written SLA contract." Save the full output to `ai-dev/active/CR-00052/evidences/pre/cr-00052-smoke-baseline.txt`.

### 1. Wire the 6 Allure recipes

Edit `Makefile`. Define a new variable near the top, alongside existing similar variables (look for `SECURITY_DIR :=` if present, or near the variable-declaration block):

```make
ALLURE_RESULTS := tests/output/allure-results
ALLURE_REPORT  := tests/output/allure-report
```

Then implement each of the 6 targets, modeled exactly on `iw-doc-plan/main/iw-doc-plan/Makefile:318–348` (don't reinvent — port). Adapt for this project's invocation style (`uv run pytest` not `$(VENV)/bin/pytest`):

```make
allure-unit:
	@command -v uv >/dev/null 2>&1 || { echo "ERROR: 'uv' not found. Install: see uv docs"; exit 1; }
	@rm -rf $(ALLURE_RESULTS)
	@mkdir -p $(ALLURE_RESULTS)
	@echo "[allure-unit] Running unit tests with Allure reporting..."
	@uv run pytest tests/unit/ -v --alluredir=$(ALLURE_RESULTS)
	@echo "[allure-unit] Run 'make allure-serve' to view report"

allure-integration:
	@command -v uv >/dev/null 2>&1 || { echo "ERROR: 'uv' not found."; exit 1; }
	@rm -rf $(ALLURE_RESULTS)
	@mkdir -p $(ALLURE_RESULTS)
	@echo "[allure-integration] Running integration tests with Allure reporting..."
	@uv run pytest tests/integration/ tests/dashboard/ --ignore=tests/dashboard/browser -v --alluredir=$(ALLURE_RESULTS)
	@echo "[allure-integration] Run 'make allure-serve' to view report"

allure-all:
	@command -v uv >/dev/null 2>&1 || { echo "ERROR: 'uv' not found."; exit 1; }
	@rm -rf $(ALLURE_RESULTS)
	@mkdir -p $(ALLURE_RESULTS)
	@echo "[allure-all] Running all tests with Allure reporting..."
	@uv run pytest tests/unit/ -v --alluredir=$(ALLURE_RESULTS)
	@uv run pytest tests/integration/ tests/dashboard/ --ignore=tests/dashboard/browser -v --alluredir=$(ALLURE_RESULTS)
	@echo "[allure-all] Run 'make allure-serve' to view report"

allure-report:
	@command -v allure >/dev/null 2>&1 || { \
		echo "ERROR: 'allure' CLI not found."; \
		echo "Install: brew install allure   (or)   see https://allurereport.org/docs/install/"; \
		exit 1; \
	}
	@mkdir -p $(ALLURE_REPORT)
	@echo "[allure-report] Generating HTML report..."
	@allure generate $(ALLURE_RESULTS) -o $(ALLURE_REPORT) --clean
	@echo "[allure-report] Report written to $(ALLURE_REPORT)/"

allure-serve:
	@command -v allure >/dev/null 2>&1 || { \
		echo "ERROR: 'allure' CLI not found."; \
		echo "Install: brew install allure   (or)   see https://allurereport.org/docs/install/"; \
		exit 1; \
	}
	@echo "[allure-serve] Starting Allure dashboard (press Ctrl+C to stop)..."
	@allure serve $(ALLURE_RESULTS)

allure-clean:
	@echo "[allure-clean] Cleaning Allure artefacts..."
	@rm -rf $(ALLURE_RESULTS) $(ALLURE_REPORT)
	@echo "[allure-clean] Done"
```

Verify all 6 are in the existing `.PHONY` line (they already are; check anyway). Don't add them again — don't create a duplicate `.PHONY` line.

### 2. Update `.gitignore`

Add (if not already present):

```
tests/output/allure-results/
tests/output/allure-report/
```

Match the placement of any existing `tests/output/` entries (e.g. `tests/output/coverage/` may already be there from CR-00047).

### 3. The smoke-layer audit table — your most important deliverable

The operator has set a **strict** bar: **≤15 tests** covering **all 5 plan paths**:

1. **daemon-worktree-start** — daemon launches a worktree end-to-end
2. **dashboard-main-pages** — dashboard serves Queue / Batches / Code / Docs / Tests / Quality / Jobs / Worktrees / Research without 5xx
3. **iw-next-id** — `iw next-id` command works and is atomic
4. **work-item-queue** — a work item can be queued (register → approve → batch-create flow up to "ready to run")
5. **healthz** — the dashboard `/healthz` endpoint returns a sane response

For each of the 16 existing `@pytest.mark.smoke` decorators, build an audit row:

| File | Test name | Covers path(s) | Decision | Reason |
|------|-----------|----------------|----------|--------|
| tests/unit/test_smoke.py | test_X | iw-next-id | **keep** | mapped to iw-next-id |
| tests/unit/test_smoke.py | test_Y | (none) | **remove** | exercises an internal helper, not a critical path |
| ... | ... | ... | ... | ... |

Rules:

- **Read each test's body** to determine what it actually exercises. Don't trust the test name.
- Every keeper must map to **≥1 plan path**. Tests that don't map to any plan path → **remove the `@pytest.mark.smoke` decorator** (the test stays as a regular unit/integration test; only the marker is removed).
- For any plan path that has **0 keepers** after the first pass → identify an existing test that covers that path and **add** `@pytest.mark.smoke` to it (you may need to look outside the current 7 files for a test that exercises e.g. `/healthz`). Re-audit. Goal: each of the 5 paths has ≥1 smoke test mapped to it, total count ≤15.
- **Removed markers** don't delete the test. **Added markers** don't create new tests. Net: same test files, same total test count in the repo; only the smoke set shrinks/curates.
- Write the audit table into your S01 step report **in full**. Reviewers in S02/S03 will check every row.

After the audit, count the final smoke markers: `grep -rc "@pytest.mark.smoke" tests/ | grep -v ":0$" | awk -F: '{s+=$2} END {print s}'`. Must be ≤15.

### 4. Measure smoke wall-clock

```bash
# Run twice to warm caches, take the second measurement
time make smoke
time make smoke
```

Record both. The second time is the SLA measurement (cache-warmed). Must be **<60 s**. If it isn't:

- Profile with `uv run pytest -m smoke --durations=0 -v` and identify the slowest test(s).
- Either remove the `@pytest.mark.smoke` decorator from a slow test (if it's not critical-path-essential), or accept the cost (if it IS critical-path-essential — but explain in the report).
- Re-measure. If still over 60 s with all 5 paths covered, escalate via `blockers` — the SLA may need to be loosened, or the slow path needs a faster proxy test.

### 5. Update pyproject.toml smoke marker description

Edit `pyproject.toml:152` to match the new contract:

```toml
"smoke: fast critical-path tests; ≤5 critical paths, ≤15 tests, <60s wall-clock; documented in tests/CLAUDE.md; run via `make smoke`",
```

(Use ASCII `<=` if escape sequences cause TOML lint errors — `<=15` is fine.)

### 6. Write the SLA prose

**`tests/CLAUDE.md`** — add a new "## Smoke layer SLA" subsection (probably near the existing pytest-randomly section). Contents:

```markdown
## Smoke layer SLA (CR-00052, P1-CR-E)

`make smoke` runs the curated `@pytest.mark.smoke` set. **Contract:**

- **≤15 tests** total (count by `grep -rc "@pytest.mark.smoke" tests/`).
- **<60 s** wall-clock on a clean dev environment (measured 2026-05-14: <TIME>s).
- **Covers 5 critical paths**: daemon-worktree-start, dashboard-main-pages, iw-next-id, work-item-queue, /healthz.

Each path has ≥1 smoke test mapped to it (audit table in CR-00052's S01 report). Adding a new `@pytest.mark.smoke` decorator requires:

1. Identifying which critical path it covers (or adding a new path to the contract and updating this doc).
2. Re-auditing the count — if it would push the total over 15, **remove** a redundant existing decorator or **don't add** the new one.
3. Re-measuring wall-clock — if it would push over 60 s, profile and trim.

The contract is currently **prose-enforced** — no `make smoke-sla` command. A future follow-up may add mechanical enforcement if drift happens (see TESTS_ENHANCEMENT.md §5 / P1-CR-E-followup-sla-enforcement, not yet filed).
```

**`docs/IW_AI_Core_Testing_Strategy.md`** — add the same SLA prose in §5 or §6 (wherever the smoke layer is already mentioned). Keep the two locations consistent: same count, same wall-clock measurement, same 5 path names.

### 7. Plan + changelog

**`ai-dev/work/TESTS_ENHANCEMENT.md`:**

- §5 grouping table — `P1-CR-E` row → **SHIPPED (CR-00052, YYYY-MM-DD)** with one-liner. Move *(start here)* marker off (Phase 1 is done modulo CR-00049 lingering draft and the low-urgency baseline-scrub follow-up).
- §5 item 1.8 row → **DONE (CR-00052, YYYY-MM-DD)** with one-liner naming what landed (6 recipes).
- §5 item 1.11 row → **DONE (CR-00052, YYYY-MM-DD)** with one-liner naming the audit result (final count + wall-clock).
- §11 changelog — new dated entry. Include: 16 → final_count audit summary; M markers removed (redundant); K markers added (gap coverage); wall-clock measurement; 6 Allure recipes added; SLA prose in 3 places (tests/CLAUDE.md, strategy doc, pyproject marker).

### 8. Pre-flight + targeted verification

Run `make format`, `make typecheck`, `make lint` — all must pass. Targeted verification:

```bash
# Allure recipes exist and are non-trivial
make allure-clean  # should print [allure-clean] Done, exit 0
make allure-unit   # should write *-result.json files to tests/output/allure-results/
ls tests/output/allure-results/ | head -5  # confirm files exist

# Smoke SLA holds
time make smoke    # must exit 0, <60s
grep -rc "@pytest.mark.smoke" tests/ | grep -v ":0$" | awk -F: '{s+=$2} END {print s}'  # must be ≤15
```

Do **NOT** run `make check`, `make test-integration`, `make diff-coverage` — that's S08–S11's job.

## Scope discipline

Touch ONLY:

- `Makefile`
- `.gitignore`
- `pyproject.toml` (smoke marker description only — no other section)
- `tests/**` (only `@pytest.mark.smoke` decorators — add/remove only; no test-body changes)
- `tests/CLAUDE.md`
- `docs/IW_AI_Core_Testing_Strategy.md`
- `ai-dev/work/TESTS_ENHANCEMENT.md`

Plus this CR's `ai-dev/active/CR-00052/**` (reports, evidence).

**Do not** touch production code (`orch/`, `dashboard/`, `executor/`, `bin/`, `scripts/`). **Do not** add new test files. **Do not** change test bodies (only decorators). **Do not** add `make smoke-sla` enforcement (operator's call — out of scope). **Do not** add CI artefact upload for Allure. **Do not** port to sibling projects.

## Project Conventions

Read the project's `CLAUDE.md` for project-wide rules. Follow all rules exactly. When in doubt, match existing code.

## TDD Requirement

This CR's TDD anchor is **the RED capture** in deliverable 0: the empty-stub proof + the 16-tests / no-SLA proof. GREEN evidence: deliverables 1-6's real recipes + ≤15-count + <60 s measurement + SLA prose. Record both in `tdd_red_evidence`.

No new tests — the Allure tooling and the smoke marker re-balancing are themselves the assertion.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`:

1. `make format` — auto-fixes formatting drift; re-stage if changes.
2. `make typecheck` — zero errors on touched files.
3. `make lint` — zero errors.

If any tool isn't available, STOP and raise a blocker. Populate the `preflight` object accordingly.

## Test Verification (NON-NEGOTIABLE)

Targeted verification only:

1. The 6 Allure targets work (`make allure-clean` + `make allure-unit` produces output).
2. `make smoke` wall-clock <60 s, count ≤15.

Do **NOT** run full suites. S04-S11 own that.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "CR-00052",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "Makefile",
    ".gitignore",
    "pyproject.toml",
    "tests/<the test files whose @pytest.mark.smoke decorators changed>",
    "tests/CLAUDE.md",
    "docs/IW_AI_Core_Testing_Strategy.md",
    "ai-dev/work/TESTS_ENHANCEMENT.md"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "make allure-unit: ok (produces results in tests/output/allure-results/). make smoke: <N> tests, <T> s. Targeted checks all green.",
  "tdd_red_evidence": "make -n allure-unit (pre-patch): no recipe (empty .PHONY stub, exits 0 trivially). make smoke (pre-patch): 16 tests, <T> s, no written SLA. Captured evidence: ai-dev/active/CR-00052/evidences/pre/cr-00052-smoke-baseline.txt.",
  "blockers": [],
  "notes": "Allure: 6 stubs replaced with real recipes (InnoForge pattern). Smoke audit: 16 -> <N> tests (M removed redundant, K re-marked for gap coverage). Final count: <N>. Wall-clock: <T>s (cache-warmed). All 5 plan paths covered (audit table in step report). SLA prose added to tests/CLAUDE.md + docs/IW_AI_Core_Testing_Strategy.md; pyproject.toml smoke marker description updated. P1-CR-E shipped, items 1.8 + 1.11 DONE."
}
```

- `tdd_red_evidence`: both the empty-stub proof AND the 16-tests / no-SLA baseline. Do not write `"n/a"`.
- `completion_status`: `complete` if all 8 deliverables done AND audit lands at ≤15 with all 5 paths AND wall-clock <60 s; `partial` if the audit can't hit ≤15 cleanly (file a follow-up); `blocked` if the wall-clock can't go under 60 s with all 5 paths covered (operator escalation).
- `blockers`: any path that has 0 keepers and no existing test to re-mark; any escalation about the 60 s SLA.
