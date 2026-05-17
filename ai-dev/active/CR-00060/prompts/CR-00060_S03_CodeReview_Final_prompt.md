# CR-00060_S03_CodeReview_Final_prompt

**Work Item**: CR-00060 -- Hypothesis property-based tests on the state machines (P2-CR-B)
**Step Being Reviewed**: Global cross-agent (S01 backend-impl + S02 code-review-impl)
**Review Step**: S03

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures are allowed (the next-id property test + the deep-profile run will spin one up).

## ⛔ Migrations: agents generate, daemon applies

No migrations.

## Input Files

- `uv run iw item-status CR-00060 --json`
- `ai-dev/active/CR-00060/CR-00060_CR_Design.md`
- `ai-dev/active/CR-00060/CR-00060_Functional.md`
- `ai-dev/active/CR-00060/reports/CR-00060_S01_Backend_report.md`
- `ai-dev/active/CR-00060/reports/CR-00060_S02_CodeReview_report.md`
- `ai-dev/active/CR-00060/evidences/pre/cr-00060-profile-wall-clock.txt`
- All files in S01's `files_changed`

## Output Files

- `ai-dev/active/CR-00060/reports/CR-00060_S03_CodeReviewFinal_report.md`

## Context

Global cross-agent review. The headline deliverable for S03 is **running the deep profile end-to-end** — the one thing S02 doesn't do. The deep profile is where property tests prove their value beyond the merge-gate `ci` profile. If `deep` surfaces a real bug, that's a Phase-2 success story (file a separate incident; do NOT block this CR — finding a bug is the system working as designed). If `deep` passes too, that's strong evidence the property tests are well-constructed and won't be flaky at the gate.

Budget: **1800 s**. Deep profile run on 5 modules at max_examples=1000 each is the big-ticket item.

## Pre-Review Lint Gate

```bash
make lint
make format-check
```

NEW violations = CRITICAL.

## Review Checklist

### 1. Independent `make test-properties` (ci profile)

```bash
time make test-properties
```

- Exits 0. Failure = CRITICAL.
- Wall-clock matches the evidence file ±20%. Wildly slower = HIGH (machine variance, or a recent change made the suite slower).

### 2. Deep-profile end-to-end run (THE marquee step)

```bash
time IW_HYPOTHESIS_PROFILE=deep uv run pytest tests/unit/properties/ -v --no-cov --timeout=900 2>&1 | tee /tmp/cr-00060-deep-run.log
```

- Three outcomes:
  - **Exit 0**: all 5 property modules hold at max_examples=1000. Strong evidence the tests are well-constructed.
  - **Exit non-zero with a Hypothesis-shrunk counterexample**: a property failed. This is a HIGH finding (NOT CRITICAL — the system worked as designed). Report:
    - Which property failed.
    - The shrunk minimal counterexample (from Hypothesis's output).
    - Whether the failure is in the implementation or in the test (an incorrect invariant).
    - Recommendation: file the bug as a separate incident; do NOT block this CR's merge.
  - **Hang / timeout**: the deep profile took >900s for one module. HIGH — flag for tuning in the report; recommend reducing `max_examples` on the slowest module to 500 in a follow-up CR.

### 3. Marker auto-apply verification

```bash
uv run pytest tests/unit/properties/ --collect-only -m properties 2>&1 | tail -30
uv run pytest tests/unit/properties/ --collect-only -m "not properties" 2>&1 | tail -10
```

- First lists all property tests (one per `@given`, multiple per `RuleBasedStateMachine`).
- Second lists 0 from `tests/unit/properties/` (lists outside-dir tests don't count). Any test under the dir not auto-marked = HIGH (conftest hook broken).

### 4. Profile selection verification

```bash
IW_HYPOTHESIS_PROFILE=ci  uv run pytest tests/unit/properties/test_work_item_lifecycle_properties.py --hypothesis-show-statistics 2>&1 | grep -E "examples|seed" | head -5
IW_HYPOTHESIS_PROFILE=dev uv run pytest tests/unit/properties/test_work_item_lifecycle_properties.py --hypothesis-show-statistics 2>&1 | grep -E "examples|seed" | head -5
```

- The `dev` run shows roughly an order-of-magnitude more examples than the `ci` run. If both show ~20 examples = CRITICAL (profile selection broken — `IW_HYPOTHESIS_PROFILE` env var isn't being read).
- The `ci` run shows the same seed each time (re-run twice; same seed = `derandomize=True` works). Different seed = HIGH (merge gate isn't deterministic).

### 5. Cross-doc-square

Same five module names + same three profile names appear identically in:

1. Strategy doc §3 sub-section.
2. Strategy doc §5 (2 rows).
3. Strategy doc §9 row.
4. `tests/CLAUDE.md` "Property tests" sub-section.
5. `skills/iw-ai-core-testing/SKILL.md` property-tests sub-section.

Any drift across these 5 locations = HIGH. Wrong CR number cited = HIGH.

Skill master ↔ `.claude/skills/` copy byte-identical:

```bash
diff skills/iw-ai-core-testing/SKILL.md .claude/skills/iw-ai-core-testing/SKILL.md
```

Non-empty diff = HIGH (re-run `iw sync-skills --force iw-ai-core-testing`).

### 6. (If batch_manager.py edited) pure-refactor verification

```bash
uv run pytest tests/integration/test_cli_batches.py tests/unit/daemon/ -v 2>&1 | tail -20
```

Same passes / skips / failures as before the CR. Any new failure or skip = CRITICAL (the helper extraction wasn't a pure refactor).

### 7. `make quality` and `make test-unit` final pass

```bash
make quality
make test-unit
```

- Both exit 0. Failure = CRITICAL.
- `make dep-check` (deptry) MUST NOT flag hypothesis as unused. If it does, the import is mis-placed (hypothesis is used in tests, so the [tool.deptry] config must list it under `pep621_dev_dependency_groups = ["dev"]` or equivalent; verify the existing config already handles this for `pytest` and friends).
- `make test-unit` includes the 5 new property modules. Verify by grep'ing the output for `tests/unit/properties/`. Missing = CRITICAL (the property tests aren't actually in the gate).

### 8. Scope-creep audit

```bash
git diff --name-only origin/main..HEAD | sort
```

Subset of `Impacted Paths`. Specifically:

- No files outside scope.
- No daemon QV gate added in `skills/iw-workflow/SKILL.md`.
- No GH workflow change.
- No behaviour change in `batch_manager.py` if edited.
- No production code change outside that one allowed file.

### 9. Phase-2 cumulative signal (advisory)

This is the 2nd Phase-2 CR (CR-00059 was the 1st). Report findings to inform P2-CR-C (item 2.3, flaky/quarantine):

- Was the **full-setup shape** (5 modules in one CR) effective vs CR-00059's **spike-then-setup shape**? If S01 hit fewer iterations than CR-00059's S01, the full-setup wins; if more, spike-shape wins for Phase 2.
- Did any property test surface a real production bug? (Either during S01's GREEN run or S03's deep run.) If yes, that's headline value-add.
- Was the marker auto-apply via conftest hook a clean pattern? Should P2-CR-C reuse it for a `quarantine` marker auto-apply?
- Cumulative Phase-2 cost so far (CR-00059 wall-clock + CR-00060 wall-clock + this S03 deep-run): informs whether P2-CR-C should be smaller-scoped.

These findings go in the report's "Phase-2 readiness" section, not as blocking findings.

## Review Report Format

Sections: **Verdict**, **Per-checklist findings** (1–9), **Deep-profile run summary** (per-module: examples generated, wall-clock, outcome — pass/fail/timeout — and the shrunk counterexample if any property failed), **Cross-doc-square audit** (table: module names ↔ 5 locations; PASS/FAIL per cell), **Scope diff**, **Phase-2 readiness notes** (advisory).

APPROVED only if: all checklist items ≤MEDIUM, scope strict, cross-doc-square holds, `make quality` + `make test-unit` pass, deep profile either passed OR found a real bug (flag as HIGH but don't block — file separately).
