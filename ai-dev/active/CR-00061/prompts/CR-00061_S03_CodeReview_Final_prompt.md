# CR-00061_S03_CodeReview_Final_prompt

**Work Item**: CR-00061 -- Flaky test quarantine workflow (P2-CR-C)
**Step Being Reviewed**: Global cross-agent (S01 backend-impl + S02 code-review-impl)
**Review Step**: S03

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

No migrations.

## Input Files

- `uv run iw item-status CR-00061 --json`
- `ai-dev/active/CR-00061/CR-00061_CR_Design.md`
- `ai-dev/active/CR-00061/CR-00061_Functional.md`
- `ai-dev/active/CR-00061/reports/CR-00061_S01_Backend_report.md`
- `ai-dev/active/CR-00061/reports/CR-00061_S02_CodeReview_report.md`
- All files in S01's `files_changed`
- (Cross-CR context) `ai-dev/active/CR-00059/`, `ai-dev/active/CR-00060/` — Phase-2's two predecessor CRs

## Output Files

- `ai-dev/active/CR-00061/reports/CR-00061_S03_CodeReviewFinal_report.md`

## Context

Global cross-agent review. **This CR closes Phase 2** of the testing-enhancement plan (CR-00059 mutation + CR-00060 Hypothesis + CR-00061 quarantine). Beyond the per-checklist verification, S03's report should include a Phase-2 closing summary that informs Phase-3 sizing.

Budget: **1800 s**. Independently exercising the aggregator + the deselection + `make quality` + `make test-unit` should fit comfortably.

## Pre-Review Lint Gate

```bash
make lint
make format-check
```

NEW violations = CRITICAL.

## Review Checklist

### 1. Independent `make test-quarantine` end-to-end

```bash
make test-quarantine
```

- Exit 0 (no `@pytest.mark.quarantine` exists in the codebase at this point, per design — S01 reverted the smoke-test marker).
- If exit non-zero: investigate. Should not happen.
- If output shows ANY test collected (other than pytest's "no tests ran" notice) = CRITICAL — means a stray quarantine marker was left in the codebase. Cross-reference with the scope-creep audit (deliverable 6).

### 2. Independent aggregator exercise on fabricated logs

Repeat the fabricated-log test using a different shape than S02 used:

```bash
mkdir -p /tmp/cr-00061-s03-fake
# Flake on a different test name; introduce a SKIPPED row to verify we don't false-positive on SKIPPED→PASSED transitions
cat > /tmp/cr-00061-s03-fake/run1.log <<'EOF'
tests/integration/test_widget.py::test_create PASSED                       [ 33%]
tests/integration/test_widget.py::test_update FAILED                       [ 66%]
tests/integration/test_widget.py::test_delete SKIPPED                      [100%]
EOF
cat > /tmp/cr-00061-s03-fake/run2.log <<'EOF'
tests/integration/test_widget.py::test_create PASSED                       [ 33%]
tests/integration/test_widget.py::test_update PASSED                       [ 66%]
tests/integration/test_widget.py::test_delete SKIPPED                      [100%]
EOF
cat > /tmp/cr-00061-s03-fake/run3.log <<'EOF'
tests/integration/test_widget.py::test_create PASSED                       [ 33%]
tests/integration/test_widget.py::test_update PASSED                       [ 66%]
tests/integration/test_widget.py::test_delete SKIPPED                      [100%]
EOF
uv run python scripts/flake_detect_aggregate.py /tmp/cr-00061-s03-fake/run{1,2,3}.log; echo "exit=$?"
rm -rf /tmp/cr-00061-s03-fake
```

- Reports `test_update` as flaky (PASSED-then-FAILED-then-PASSED), exit 1.
- Does NOT report `test_delete` as flaky (all SKIPPED is consistent, not a flake). False-positive on SKIPPED = HIGH (parsing is too loose).
- Does NOT report `test_create` as flaky (all PASSED). False-positive on agreed = CRITICAL.

### 3. addopts deselection works end-to-end

```bash
uv run pytest tests/unit/test_smoke.py --collect-only -m quarantine 2>&1 | tail -5
```

- Output reports `0 tests collected` (NOT an error). If pytest errors with `'quarantine' not found in markers configuration` — marker not registered = CRITICAL.

```bash
uv run pytest tests/unit/ --collect-only 2>&1 | tail -3
```

- Reports a number of collected tests. Compare to pre-CR baseline (read S01's report or run `git stash && uv run pytest tests/unit/ --collect-only 2>&1 | tail -3 && git stash pop`). Same number, ±0 (no quarantines added by this CR, so no tests should be deselected by the new clause). Any drop = HIGH.

### 4. Cross-doc-square

The 5-rule list MUST be verbatim (or near-verbatim with the same key words) across:

1. `tests/CLAUDE.md` "Quarantine workflow" sub-section
2. `skills/iw-ai-core-testing/SKILL.md` quarantine sub-section
3. `docs/IW_AI_Core_Testing_Strategy.md` §3 sub-section (may be a summary; should at least mention "filing an Incident" and the recovery rule)

Drift = HIGH.

`diff skills/iw-ai-core-testing/SKILL.md .claude/skills/iw-ai-core-testing/SKILL.md` → empty. Non-empty = HIGH.

§9 row names `CR-00061` (not `CR61` / `CR-61`). Wrong format = HIGH.

§5 has 2 new rows (quarantine deselection + flake-detect on-demand). Missing either = HIGH.

### 5. `make quality` + `make test-unit` final pass

```bash
make quality
make test-unit
```

- Both exit 0. Failure = CRITICAL.
- `make dep-check` (deptry) MUST NOT flag `pytest-rerunfailures` as unused (it's a pytest plugin, auto-loaded). If it does, the [tool.deptry] config needs an `ignore_used_in_dev_groups` entry or similar — HIGH.

### 6. Scope-creep audit

```bash
git diff --name-only origin/main..HEAD | sort
```

Subset of `Impacted Paths`. Specifically:

- No production code (`orch/`, `dashboard/`, `executor/`). CRITICAL.
- No test bodies modified. The smoke-test temp marker on `tests/unit/test_smoke.py` MUST be absent (`git diff tests/unit/test_smoke.py` = empty). Non-empty = CRITICAL.
- No new daemon QV gate. CRITICAL.
- No GH workflow change. CRITICAL.

### 7. Phase-2 closing summary (REQUIRED for this CR)

This is the closing CR of Phase 2. The report MUST include a "Phase-2 close" section with:

- **Item status sweep**: read `ai-dev/work/TESTS_ENHANCEMENT.md` §6. Confirm items 2.1, 2.2, 2.3 are all `DONE`. Quote the row text for each.
- **Open follow-ups in TESTS_ENHANCEMENT.md**: list every row in §5 with status NOT `SHIPPED`/`DONE`. Expected after this CR: `P2-CR-A-followup-mutation-block` (filed by CR-00059, drafted but unrun); `P1-CR-A-followup` (assertion baseline scrub, low-urgency). Any others = note them.
- **Cumulative Phase-2 wall-clock**: sum of (CR-00059 S01–S12 total) + (CR-00060 S01–S12 total) + (CR-00061 S01–S12 total — including this S03). Useful to compare against Phase-1 cost in the next planning round.
- **Phase-3 recommendation**: based on item value (and any signals from CR-00059/CR-00060 self-assesses), recommend the first Phase-3 item to tackle. The plan §7 lists 3.1 E2E layer (largest), 3.2 contract sweep (moderate), 3.3 iw CLI contract (moderate), 3.4 cross-project isolation (moderate), 3.5 security module (small/medium), 3.6 data-layer module (partly done already). Recommend one as the next CR. State your reasoning in 2–3 sentences.

This section is informational — does NOT block APPROVED. But it MUST be present.

## Review Report Format

Sections: **Verdict**, **Per-checklist findings** (1–6), **Phase-2 close** (item sweep + open follow-ups + cumulative wall-clock + Phase-3 recommendation), **Independent aggregator re-verification** (S03's run on the SKIPPED-row fabricated logs), **addopts before/after** (final form), **Scope diff** (file-list).

APPROVED iff: all checklist items ≤MEDIUM, scope strict, marker deselection works end-to-end, smoke-test temp marker reverted, cross-doc-square holds, `make quality` + `make test-unit` pass.
