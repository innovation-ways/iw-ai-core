# CR-00059_S02_CodeReview_prompt

**Work Item**: CR-00059 -- Mutation testing spike + setup on `orch/daemon/` (P2-CR-A)
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

Standard policy. No Docker commands except read-only introspection or via `./ai-core.sh` / `make`.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This CR adds **no** migrations. Flag any migration in `files_changed` as a CRITICAL scope violation.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `uv run iw item-status CR-00059 --json` — runtime step state.
- `ai-dev/active/CR-00059/CR-00059_CR_Design.md` -- Design (source of truth)
- `ai-dev/active/CR-00059/reports/CR-00059_S01_Backend_report.md` -- Impl step report (**must contain the spike measurement table inline**)
- `ai-dev/active/CR-00059/evidences/pre/cr-00059-spike-measurements.txt` -- canonical spike measurement artefact
- All files in S01's `files_changed`
- `iw-doc-plan/main/iw-doc-plan/Makefile:444–500` + `iw-doc-plan/main/iw-doc-plan/pyproject.toml:256–262` — InnoForge precedent

## Output Files

- `ai-dev/active/CR-00059/reports/CR-00059_S02_CodeReview_report.md`

## Context

You are reviewing S01's implementation of **CR-00059 — Mutation testing spike + setup on `orch/daemon/` (P2-CR-A)**, the first Phase-2 CR. The CR has three parts: (a) install + config mutmut; (b) four `make mutation-*` recipes ported from InnoForge; (c) the **spike** — one run of `make mutation-audit` on `orch/daemon/` whose measurement table is the deliverable. The biggest CRITICAL risks are: (1) spike numbers that are placeholders (TBD / —) instead of real measurements — the entire CR's value rests on those numbers; (2) any production code under `orch/`, `dashboard/`, `executor/` modified (the CR is tooling/docs only); (3) silent expansion of `paths_to_mutate` beyond `orch/daemon/` (operator decided spike scope is bounded).

Read the design first. ACs are AC1–AC9.

## Read the Design Document FIRST

- AC1–AC9 are mandatory checks.
- "Impacted Paths" defines scope. Any file in `files_changed` outside that list = CRITICAL.
- The "Notes" section explains: bounded `orch/daemon/` scope is deliberate; no PR gate this CR; runner uses `-x --tb=no -q`; expected infrastructure blockers (testcontainer per-mutant cost, FTS replay, live-DB guard).

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

NEW violations = CRITICAL with `"category": "conventions"`.

## Review Checklist

### 1. mutmut dep + config block correctness — exercise them

```bash
# Dep present and resolves
grep -n 'mutmut' pyproject.toml | grep -v '^#'
uv run mutmut --version
# uv.lock contains mutmut
grep -n '^name = "mutmut"' uv.lock | head -3
```

- `mutmut>=2.5,<3.0` line present in `[dependency-groups] dev` (AC1). Any other version pin (e.g. `>=3`) = HIGH (diverges from InnoForge precedent without justification).
- `uv run mutmut --version` prints a 2.x version. Failure = CRITICAL.
- `uv.lock` regenerated to include mutmut (verify with `grep`). Missing = HIGH (the dep won't install fresh).

```bash
python -c "import tomllib; b = tomllib.load(open('pyproject.toml','rb'))['tool']['mutmut']; print(b)"
```

- `paths_to_mutate == "orch/daemon/"` exactly (AC2). Any other value (e.g. `"orch/"`, `"orch/daemon"`) = CRITICAL — scope creep.
- `tests_dir == "tests/unit/daemon/ tests/integration/daemon/"` (AC2). Different scope = HIGH.
- `runner` contains `pytest`, `-x`, `--tb=no`, `-q` (the mutmut convention; CR design §Notes). Missing any of these = HIGH (changes mutmut runtime behaviour).

### 2. Four `make` targets parse and behave per spec

```bash
make -n mutation-check MODULE=orch/daemon/auto_merge.py | head -30
make -n mutation-audit | head -10
make -n mutation-results
make -n mutation-show ID=1

# Usage messages on missing args
make mutation-check 2>&1 | head -3
make mutation-show 2>&1 | head -3
```

- All four `make -n` invocations parse (AC3). "No rule to make target" = CRITICAL.
- `mutation-check` without `MODULE` prints usage and exits non-zero (AC3). Different behaviour = HIGH.
- `mutation-show` without `ID` prints usage and exits non-zero (AC3). Different behaviour = HIGH.
- Recipes invoke `uv run mutmut` (NOT `mutmut` directly — must use `uv run` for venv resolution). Direct invocation = HIGH.
- `mutation-audit` walks `orch/daemon/` (NOT `orch/`). Wider scope = CRITICAL.
- `.PHONY` line (Makefile:5–13) lists all 4 new targets. Missing any = HIGH (cosmetic but breaks `.PHONY` contract).

### 3. The spike measurement table — real numbers, not placeholders

The measurement table is the deliverable. Read **both** locations:

- `ai-dev/active/CR-00059/evidences/pre/cr-00059-spike-measurements.txt` (canonical artefact)
- The inline copy in `ai-dev/active/CR-00059/reports/CR-00059_S01_Backend_report.md`

The two MUST be byte-identical for the measurement portion. Drift = HIGH.

For the table (AC4):

- **Every numeric cell** (Total mutants, Killed, Survived, Timeout, Suspicious, Mutation score, Wall-clock, Modules covered) is a real number. Any `TBD` / `—` / `$VAR` / `<N>` / placeholder = **CRITICAL** — the entire CR's value rests on these being real.
- **Arithmetic check**: Mutation score == K / (K + S) × 100, within ±0.5 % rounding. Off by more than that = HIGH.
- Wall-clock is a real duration format (`h:mm:ss` or `m:ss`), not "fast" or "~30min". = HIGH if vague.
- Modules covered lists at least one `orch/daemon/*.py` file (typically all 26). Empty/missing = CRITICAL.
- Top 5 surviving mutants section is present and has file:line + brief diff (it's the queue for the follow-up CR). Missing = HIGH.
- Infrastructure blockers section is filled in — either with observations or "None observed". Empty = HIGH (we need to know whether mutmut tripped on our test infra).

### 4. RED-first guard test in the diff

```bash
ls -la tests/unit/test_mutmut_setup.py
uv run pytest tests/unit/test_mutmut_setup.py -v
```

- File exists in `files_changed`. Missing = CRITICAL.
- Both tests pass GREEN now. Failure = CRITICAL (broken test or implementation drifted from design).
- `tdd_red_evidence` in S01's result contract quotes one real failure line with a real test id (e.g. `tests/unit/test_mutmut_setup.py::test_pyproject_tool_mutmut_block_pins_orch_daemon_target FAILED: KeyError: 'mutmut'`). `"n/a"` / empty / "see report" = CRITICAL (CR-00045 contract: this is a behavioural step; n/a is reserved for pure refactor / config-only / doc-only steps, and this is a tooling step that introduces a guard test).

### 5. Strategy doc updates internally consistent

Read `docs/IW_AI_Core_Testing_Strategy.md`:

- §5 has a new "Mutation testing" row labelled on-demand (NOT blocking). If labelled blocking = CRITICAL (operator decision).
- §8 no longer says "not yet set up" (AC6). If still says so = CRITICAL.
- §8 quotes the spike's mutation score and wall-clock. The numbers MUST match `cr-00059-spike-measurements.txt` exactly. Drift = HIGH.
- §8 names the follow-up CR `P2-CR-A-followup-mutation-block`. Missing = HIGH.
- §9 row "Mutation testing" flipped from ❌ to ⚠️ with `CR-00059` named (AC6). Still ❌ = CRITICAL.

### 6. Plan + changelog updates internally consistent

Read `ai-dev/work/TESTS_ENHANCEMENT.md`:

- §6 item 2.1 row Status column updated to `IN PROGRESS — CR-00059 …` (AC7). Still `TODO` = CRITICAL.
- §5 has a new row `P2-CR-A-followup-mutation-block`. Missing = CRITICAL.
- §11 has a new dated entry whose mutant count, score, and wall-clock match `cr-00059-spike-measurements.txt` exactly (AC7). Drift = HIGH.
- §9 (in TESTS_ENHANCEMENT.md — if that doc has a §9) row matches §9 in the strategy doc. Inconsistency = HIGH.

### 7. Scope gate (CRITICAL on any violation)

```bash
git diff --name-only origin/main..HEAD
```

The diff MUST only touch files declared in `Impacted Paths`:

- `pyproject.toml`
- `uv.lock`
- `Makefile`
- `docs/IW_AI_Core_Testing_Strategy.md`
- `ai-dev/work/TESTS_ENHANCEMENT.md`
- `tests/unit/test_mutmut_setup.py`
- `ai-dev/active/CR-00059/**` (implicit)

Any file under `orch/` (other than referenced in the [tool.mutmut] block — but that block lives in `pyproject.toml`, NOT under `orch/`), `dashboard/`, `executor/`, `skills/`, `.claude/`, `.github/`, `.pre-commit-config.yaml` modified = **CRITICAL**. Any Alembic migration added = CRITICAL.

Specific anti-additions to check:

- No new daemon QV gate in `skills/iw-workflow/SKILL.md` canon block (operator decision — deferred to follow-up CR).
- No new step in `.github/workflows/test-quality.yml` referencing mutmut (operator decision).
- No `--paths-to-mutate orch/` (widening) in any recipe — must stay `$(MODULE)` for check, `orch/daemon/` walk for audit.
- No production code under `orch/daemon/` modified. The spike *mutates* daemon code temporarily but mutmut restores originals; the diff should show no `orch/daemon/*.py` changes.

### 8. mutmut works end-to-end on one file

Spot-check (don't repeat the full audit — that's a 3600s run):

```bash
# Pick the smallest daemon file
wc -l orch/daemon/*.py | sort -n | head -5
# Run mutation-check against one small file (budget: a few minutes)
make mutation-check MODULE=orch/daemon/container_info.py
```

- Exits 0 (or non-zero if all mutants killed — both are acceptable outcomes for the recipe; what's NOT acceptable is "No rule to make target" or a stack trace).
- Prints a results section.
- Failure to invoke = CRITICAL (recipe broken).
- Test infrastructure failures (live-DB guard, FTS missing) = note in review but only HIGH if S01 didn't already call them out as blockers in the spike report.

## Review Report Format

Standard CR-00046-style report. Sections: **Verdict** (APPROVED / NEEDS_FIX / BLOCKED), **Findings** (per-AC + per-checklist-item; each finding has `severity` ∈ CRITICAL/HIGH/MEDIUM/LOW/INFO, `category`, `description`, `file:line` if applicable, `recommendation`), **Spike measurement audit table** (your independent re-derivation of the K/(K+S) score; flag any drift from S01's table), **Scope audit** (full diff file-list with PASS/FAIL annotations).

Finish with the JSON contract block (CR-00046 shape — verdict, finding counts by severity, top 3 blocking findings if any).
