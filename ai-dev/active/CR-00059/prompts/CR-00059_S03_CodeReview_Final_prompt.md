# CR-00059_S03_CodeReview_Final_prompt

**Work Item**: CR-00059 -- Mutation testing spike + setup on `orch/daemon/` (P2-CR-A)
**Step Being Reviewed**: S01 (backend-impl) + S02 (code-review-impl) — global cross-agent review
**Review Step**: S03

---

## ⛔ Docker is off-limits

Standard policy. No Docker commands except read-only introspection or via `./ai-core.sh` / `make`. Note: the spike re-run in checklist 1 invokes mutmut → pytest → testcontainer fixture; that path is allowed (Ryuk teardown).

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This CR adds **no** migrations. Any migration in the diff = CRITICAL.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `uv run iw item-status CR-00059 --json` — runtime step state.
- `ai-dev/active/CR-00059/CR-00059_CR_Design.md` -- Design (source of truth)
- `ai-dev/active/CR-00059/CR-00059_Functional.md`
- `ai-dev/active/CR-00059/reports/CR-00059_S01_Backend_report.md`
- `ai-dev/active/CR-00059/reports/CR-00059_S02_CodeReview_report.md`
- `ai-dev/active/CR-00059/evidences/pre/cr-00059-spike-measurements.txt`
- All files in S01's `files_changed`
- `iw-doc-plan/main/iw-doc-plan/Makefile:444–500` + `iw-doc-plan/main/iw-doc-plan/pyproject.toml:256–262`

## Output Files

- `ai-dev/active/CR-00059/reports/CR-00059_S03_CodeReviewFinal_report.md`

## Context

Global cross-agent review. S02 reviewed S01 in isolation; your job is to (a) independently re-run mutmut end-to-end on one small daemon file to confirm the recipe truly works (not just `make -n` parses); (b) verify the spike measurement table's internal arithmetic; (c) verify cross-document consistency across the three doc surfaces; (d) confirm scope hasn't crept; (e) confirm `make quality` and `make test-unit` still pass.

**Budget**: this step has a 1800s timeout. The independent `make mutation-check` against one file (deliverable 1) plus `make quality` + `make test-unit` should fit comfortably within that.

## Pre-Review Lint Gate

```bash
make lint
make format-check
```

NEW violations = CRITICAL.

## Review Checklist

### 1. Independent end-to-end mutmut run

```bash
# Pick a small daemon file (≤200 lines)
wc -l orch/daemon/*.py | sort -n | head -5
make mutation-check MODULE=orch/daemon/container_info.py
```

- Recipe runs to completion (allow several minutes — single-file mutation-check is bounded). Hang or error = CRITICAL.
- Prints a non-empty results line ("Killed: N, Survived: M, …"). Empty results = HIGH (the runner may not be receiving the mutations properly).
- The spike's headline mutation-score from S01's table should be roughly consistent with this file's score (allowing for per-file variance). Wildly different score (e.g. spike says 80%, this run on one file shows 5%) = HIGH — worth investigating whether the test runner is actually exercising mutated code.

```bash
make mutation-results
```

- Prints the cached results from the run above. Empty = HIGH (cache write/read broken).

```bash
# Pick a surviving mutant ID from the results above (or from S01's spike table top-5)
make mutation-show ID=<n>
```

- Shows file:line:diff. Failure = HIGH (the show recipe is broken).

### 2. Spike measurement table arithmetic audit

Re-derive:

```
score = Killed / (Killed + Survived) × 100
```

against the numbers in `ai-dev/active/CR-00059/evidences/pre/cr-00059-spike-measurements.txt`. Drift > 0.5 % from S01's reported score = HIGH (math error in S01's table — discredits the deliverable).

Independently verify the Wall-clock format is real (`h:mm:ss` or `m:ss`), not vague. Vague = HIGH.

### 3. Cross-document consistency triangle

The same three numbers (mutation score, mutant count, wall-clock) MUST appear identically in:

1. `ai-dev/active/CR-00059/evidences/pre/cr-00059-spike-measurements.txt` (canonical)
2. `docs/IW_AI_Core_Testing_Strategy.md` §8
3. `ai-dev/work/TESTS_ENHANCEMENT.md` §11

Any drift between the three = **CRITICAL** — the doc is the only place future engineers will read these numbers; if the canonical and the doc disagree, the doc lies.

Also verify:

- Strategy §9 row "Mutation testing" names `CR-00059` exactly (not `CR59` / `CR-59`). Wrong format = HIGH (doc-search consistency).
- TESTS_ENHANCEMENT §5 has the `P2-CR-A-followup-mutation-block` row (exact name). Missing or differently named = HIGH.
- TESTS_ENHANCEMENT §6 item 2.1 row is `IN PROGRESS` (not `DONE` — the spike's the foundation; the blocking-gate flip is still future). `DONE` = HIGH (premature claim of completion).

### 4. `make quality` and `make test-unit` still pass

```bash
make quality   # lint + format-check + typecheck + test-assertions + dead-code + dep-check
make test-unit
```

- All exit 0. Failure = CRITICAL.
- Particularly: `make dep-check` (deptry) MUST NOT flag mutmut as an unused dep. If it does, S01 mis-declared mutmut's place in the dep-groups (mutmut goes in `[dependency-groups] dev`, not `[project] dependencies`). Flagged = HIGH.
- `make test-unit` MUST include `tests/unit/test_mutmut_setup.py` in the run (auto-discovered). Skipped or missing = HIGH.

### 5. Scope-creep audit (CRITICAL on any)

```bash
git diff --name-only origin/main..HEAD | sort
```

The file list MUST be a strict subset of:

- `pyproject.toml`
- `uv.lock`
- `Makefile`
- `docs/IW_AI_Core_Testing_Strategy.md`
- `ai-dev/work/TESTS_ENHANCEMENT.md`
- `tests/unit/test_mutmut_setup.py`
- `ai-dev/active/CR-00059/**`

Specific anti-additions:

- **No production code change** under `orch/`, `dashboard/`, `executor/`. CRITICAL.
- **No daemon QV gate** in `skills/iw-workflow/SKILL.md` canon. CRITICAL (operator decision — deferred to follow-up).
- **No GH workflow change** in `.github/workflows/test-quality.yml`. CRITICAL.
- **No widening of `paths_to_mutate`** beyond `orch/daemon/` in `[tool.mutmut]`. CRITICAL.
- **No skill changes** in `skills/iw-ai-core-testing/SKILL.md` (the per-project testing skill — adding a "mutation testing" section is deferred until the spike informs what to write). HIGH if touched, CRITICAL if it contradicts the strategy doc.
- **No sibling-repo sync** (no edits under `../../iw-doc-plan` / `../../podforger` / `../../cv`). HIGH.
- **No Alembic migration**. CRITICAL.

### 6. RED-first contract integrity

S01's `tdd_red_evidence` in the result contract must:

- Quote a real test id from `tests/unit/test_mutmut_setup.py` (one of the two test names).
- Quote a real failure line (AssertionError / KeyError, NOT ImportError / SyntaxError — those indicate a broken test).
- NOT be `"n/a"`. This is a behavioural step (introduces guard test + tooling); n/a is reserved for pure refactor / config-only / doc-only.

Violation = CRITICAL per CR-00045 contract.

### 7. Phase-2 readiness signal (advisory)

This is the first Phase-2 CR; surface findings to inform P2-CR-B (Hypothesis property tests, item 2.2) and P2-CR-C (flaky/quarantine, item 2.3):

- Did the spike's 3600s timeout hold? If yes by a wide margin (e.g. 600s used) — note Phase-2 spike steps may run shorter. If it bumped close to budget — note Phase-2 CRs may need higher per-step timeouts.
- Did mutmut surface infrastructure blockers that Phase-2 Hypothesis tests would also hit? (Both run pytest subprocesses; both depend on conftest fixtures applying.) If yes, P2-CR-B should anticipate them.
- Was the audit-table-as-deliverable pattern (S01 produces a measurement table; reviewers verify its arithmetic) effective? S02's spike-arithmetic check should give a clear yes/no.

These findings go into the report's "Phase-2 readiness" section, NOT as blocking findings.

## Review Report Format

Sections: **Verdict** (APPROVED / NEEDS_FIX / BLOCKED), **Per-checklist findings** (1–7 above, each with severity + recommendation), **Spike measurement re-audit** (your arithmetic + cross-doc-triangle check, with any drift flagged), **End-to-end recipe verification log** (the `make mutation-check` run's stdout summary), **Scope diff** (full file-list with PASS/FAIL annotations), **Phase-2 readiness notes** (advisory).

Finish with the JSON contract block. APPROVED only if every checklist item is at most MEDIUM severity AND scope is strictly within design AND the cross-doc triangle holds AND `make quality` + `make test-unit` pass.
