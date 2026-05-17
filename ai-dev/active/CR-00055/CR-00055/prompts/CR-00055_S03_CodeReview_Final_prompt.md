# CR-00055_S03_CodeReview_Final_prompt

**Work Item**: CR-00055 -- Re-enable `pytest-randomly` by default via per-test PostgreSQL template-clone
**Step**: S03
**Agent**: code-review-final-impl

---

## Input Files

- `ai-dev/active/CR-00055/CR-00055_CR_Design.md` -- ACs (AC1–AC6).
- `ai-dev/active/CR-00055/reports/CR-00055_S01_Backend_report.md` and `..._S02_CodeReview_report.md` -- prior step reports.
- `docs/research/R-00077-pytest-randomly-isolation-strategy.md` -- strategy rationale.

## Output Files

- `ai-dev/active/CR-00055/reports/CR-00055_S03_CodeReview_Final_report.md` -- Final-review report.

## Context

You are the final cross-agent reviewer. Your job is to **independently verify** the AC-claimed outcomes, not just spot-check S01's and S02's reports. The critical AC to verify hands-on is **AC2** — the 4-seed sweep must genuinely be green from your invocation, not just S01's.

## Required verifications

### AC1: `-p no:randomly` removed

```bash
grep -n 'no:randomly' pyproject.toml || echo "OK: no matches"
grep -n 'strict-markers' pyproject.toml | head -2  # must still be present
grep -n 'pgtestdbpy' pyproject.toml | head -3  # must appear in [dependency-groups] dev
```

### AC2: 4-seed sweep green (DO THIS YOURSELF — do not trust S01's report)

Run **at least 2 of the 4 reference seeds independently** (S01's report claims all 4 green; verify by re-running the 2 fastest from the spike — 12345 and 67890 — both should exit 0 in ~10–11 min single-process):

```bash
for seed in 12345 67890; do
  echo "=== seed $seed ==="
  uv run pytest tests/integration/ tests/dashboard/ --ignore=tests/dashboard/browser \
    -p randomly --randomly-seed=$seed -q --no-cov 2>&1 | tail -5
done
```

Both must exit 0 with ~2520 passed + 0 failures + ~3–6 xfailed/xpassed.

**If either fails, file as CRITICAL — S08/S09/S10 will inherit the same failure**.

You may optionally run a 5th seed (e.g. 99999) to catch any seed-specific gap not exercised by the standard 4 — but if 12345 + 67890 are green and the design's quarantines + autouse + teardowns are present, additional seeds are likely overkill.

### AC3: Wall-clock budget

The per-seed wall-clock from your AC2 verification must be ≤ 12 min (the spike measured 10m54s on seed 12345 alone, 12–14 min when seeds run in parallel). If a single-process invocation overruns 13 min, flag as MEDIUM — S09's 1 200 s budget will be tight.

### AC4: Doc flips consistent across all 4 locations

For each of the 4 doc locations, verify (a) the prose describes default-on with the mechanism (per-test template-clone via pgtestdbpy + IW_CORE_DB_* monkeypatch for subprocess inheritance); (b) a brief "Earlier fallback (CR-00048)" historical note is preserved at section end (not silently deleted); (c) the §9 row prefix starts with `"✅ (CR-00055, 2026-05-16) — default-on; ..."`:

- `tests/CLAUDE.md` §7
- `docs/IW_AI_Core_Testing_Strategy.md` §3 subsection
- `docs/IW_AI_Core_Testing_Strategy.md` §9 row "Test-order randomisation"
- `skills/iw-ai-core-testing/SKILL.md` §2

If any location silently deletes the CR-00048 historical note — MEDIUM fixable.

### AC5: Plan + changelog internally consistent

`ai-dev/work/TESTS_ENHANCEMENT.md`:
- §5 row `P1-CR-C-followup-randomly` → DONE (CR-00055, 2026-05-16).
- Item 1.4 row → DONE (CR-00055, 2026-05-16) (was PARTIAL).
- §11 changelog entry dated 2026-05-16 references CR-00055, the per-test template-clone strategy, the WAL_LOG override, the 1 autouse + 2 teardowns + 3 quarantines, the 4-seed verification numbers, and R-00077.
- Counts in §11 must match §5 must match item 1.4.

### AC6: Skill in sync

```bash
diff -q skills/iw-ai-core-testing/SKILL.md .claude/skills/iw-ai-core-testing/SKILL.md
```

Must produce no output. If `diff` shows changes, the implementing agent forgot `iw sync-skills --force iw-ai-core-testing` — CRITICAL fixable.

### CRITICAL hinge re-checks (orthogonal to ACs, but if broken the whole thing fails downstream)

1. **WAL_LOG override**:
   ```bash
   grep -n "pgtestdbpy.QRY_DB_CLONE" tests/integration/conftest.py
   ```
   Must show the assignment without `STRATEGY=FILE_COPY`. If S01 forgot this, S09 will time out — CRITICAL.

2. **`_pgtestdb_setup` re-export**:
   ```bash
   grep -n "_pgtestdb_setup" tests/dashboard/conftest.py
   ```
   Must appear in the `from tests.integration.conftest import (...)` block. If missing, S09 hits hundreds of fixture-not-found errors — CRITICAL.

3. **Exactly 3 quarantines** with the registered triad (`@pytest.mark.order_dependent` + `@pytest.mark.xfail(strict=False, reason=...)` + `# NOTE(P1-CR-C-followup-randomly):`):
   ```bash
   grep -rn "P1-CR-C-followup-randomly" tests/integration/ | head -10
   ```
   Should appear in 3 test files (test_db_identity_integration.py, test_pending_migration_log_migration.py, test_i_00062_migration.py) + possibly the module-level autouse fixture in test_db_identity_integration.py.

### Scope creep audit (reject if any present)

- Production code touched (orch/, dashboard/ outside `tests/dashboard/conftest.py`, executor/, bin/, scripts/).
- New behavioural tests added.
- Test assertions weakened.
- Makefile / .github / pre-commit / migrations changes.
- 4th quarantine added without operator approval (the spike was definitive — 3 quarantines).
- Sibling project ports.

### Quarantine quality audit

Each new `@pytest.mark.xfail` must have:
- `strict=False` (otherwise green runs xpass-fail).
- A `reason` string that names the leak source (not just "order-dependent").
- A `# NOTE(P1-CR-C-followup-randomly):` tracking comment inside the test body.

### make quality

```bash
make quality
```

Must pass. (Warn-only steps like `dead-code` / `dep-check` don't fail.)

### What NOT to run

- `make check` — that's the QV gates' job.
- `make test-integration` — S09's job.
- `make diff-coverage` — S10's job (and 1 800 s budget; you don't need to wait that long here).

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "code-review-final-impl",
  "work_item": "CR-00055",
  "completion_status": "complete",
  "review_outcome": "pass|pass_with_fixable|reject",
  "findings_by_severity": {
    "critical": [],
    "high": [],
    "medium": [],
    "low": []
  },
  "verifications": {
    "ac1_no_randomly_removed": "pass|fail",
    "ac2_four_seed_sweep_green": "pass:seeds_verified=[12345,67890]|fail:<details>",
    "ac3_wall_clock_under_budget": "pass:seed12345_walltime=<N>min|fail:<details>",
    "ac4_docs_flipped_consistently": "pass|fail",
    "ac5_plan_changelog_consistent": "pass|fail",
    "ac6_skill_in_sync": "pass|fail",
    "wal_log_override_present": "pass|fail",
    "pgtestdb_setup_reexported": "pass|fail",
    "quarantines_count": "3 (expected)|<other>",
    "scope_creep": "none|<list>"
  },
  "blockers": [],
  "notes": ""
}
```

## Lifecycle Commands

```bash
uv run iw step-start CR-00055 --step S03
# ... independent AC verification ...
uv run iw step-done CR-00055 --step S03 --report ai-dev/active/CR-00055/reports/CR-00055_S03_CodeReview_Final_report.md
```
