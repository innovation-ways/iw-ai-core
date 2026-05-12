# CR-00047 — S03 (CodeReviewFinal) report

**Work item**: CR-00047 — Coverage gates — raise the floor, ratchet it, and gate diff-coverage on PRs (P1-CR-B)
**Step**: S03 (`code-review-final-impl`) — global cross-agent review of S01 (`backend-impl`) + S02 (`code-review-impl`)
**Verdict**: **pass** — 0 CRITICAL, 0 HIGH, 0 MEDIUM(fixable); `mandatory_fix_count = 0`

---

## What was done

Read the design doc (`ai-dev/active/CR-00047/CR-00047_CR_Design.md`) end-to-end — Acceptance Criteria AC1–AC8, the TDD Approach (names exactly one *optional* test file, `tests/unit/test_coverage_gate_config.py`), the Notes, and the Impact/File manifests — then the S01 + S02 reports, then every file in S01's `files_changed`. Ran the pre-review lint/format gate, the full test suite (unit + integration), and dogfooded `make diff-coverage`.

### Pre-review lint & format gate
- `make lint` → `All checks passed!` (ruff + `scripts/check_templates.py` + `lint-js`) — exit 0.
- `make format` (`ruff format --check .`) → `676 files already formatted` — no drift, exit 0.
- **No new `conventions` violations** in any changed file.

### Test verification
- `make test-unit` → **first run: 1 failure** — `tests/unit/test_browser_env.py::test_pick_free_offset_returns_hash_offset_when_free`. Re-ran in isolation: **PASS**. Re-ran the full `make test-unit`: **2800 passed, 4 skipped, 5 xfailed, 1 xpassed, 0 failed**; coverage gate `Required test coverage of 50.0% reached. Total coverage: 51.82%` ✓. → **flaky port-binding race, pre-existing, unrelated to CR-00047** (this CR changes no production Python — only config / Makefile / skills / docs / workflow + one config-only test). Relevant to P1-CR-C (test hygiene / `pytest-randomly`), not actionable here.
- `make test-integration` → **2261 passed, 33 skipped, 3 xfailed, 0 failed**; coverage `Total coverage: 61.23%` ≥ 50% ✓ (≈9m24s).
- `make diff-coverage` → **exit 0**. Built its own combined unit+integration+dashboard coverage (`Total coverage: 75%`), wrote `tests/output/coverage/coverage-combined.xml`, then `diff-cover … --compare-branch=origin/main --fail-under=90` → *"No lines with coverage information in this diff."* → exit 0. **AC5 (dogfood) verified.** (This CR's only changed `.py` is `tests/unit/test_coverage_gate_config.py`, and `tests/*` is in `[tool.coverage.run] omit`, so `diff-cover` has no changed lines to judge.)
- The 2 `tests/unit/test_safe_migrate.py` failures S01/S02 flagged did **not** reproduce here — `IW_CORE_PER_WORKTREE_DB` is not set in this env (only `IW_CORE_AGENT_CONTEXT=true`). Pre-existing, out of scope for CR-00047; see "Observations".

### Cross-agent / integration consistency — the coverage-config ↔ Makefile ↔ skill canon ↔ GH workflow ↔ docs chain
- **`pyproject.toml`** — `[tool.coverage.report] fail_under` 46 → **50** (with a ratchet comment); `[tool.coverage.run] relative_files = true` added (with a worktree-path-alignment comment); `diff-cover>=9` added to `[dependency-groups] dev`. `uv.lock` regenerated → `diff-cover==10.2.0` (+ `chardet` transitive); `uv run diff-cover --version` → `10.2.0` ✓.
- **`Makefile`** — new self-contained `diff-coverage:` target (`pytest tests/unit/ --cov-fail-under=0` → `pytest tests/integration/ tests/dashboard/ --ignore=tests/dashboard/browser --cov-append --cov-fail-under=0` → `coverage xml -o tests/output/coverage/coverage-combined.xml` → `diff-cover … --compare-branch=origin/main --fail-under=90`), added to `.PHONY`, with a header comment explaining the self-contained rationale, the `--cov-fail-under=0` opt-out on the intermediate runs, and the slow-gate trade-off. Does **not** reuse a leftover `coverage.xml` or depend on the (no-op) `integration-tests` gate. `coverage-combined.xml` lands under `tests/output/` (gitignored — confirmed `git check-ignore`).
- **`skills/iw-workflow/SKILL.md`** — canon now lists **7** gates `lint → assertions → format → typecheck → unit-tests → integration-tests → diff-coverage`; the new entry is `{"step": "S16", "agent": "qv-gate", "gate": "diff-coverage", "command": "make diff-coverage", "description": "QV: Diff coverage (new/changed lines must be well-covered)", "timeout": 1800}` placed right after `integration-tests`; the "N canonical QV gates" prose says **7** and a sentence describes the new gate. `.claude/skills/iw-workflow/SKILL.md` is **byte-identical** to the master (`diff` → IDENTICAL) — `iw sync-skills` ran. The live manifest for this very CR (`iw item-status CR-00047`) confirms S09=`integration-tests`, S10=`diff-coverage` (`make diff-coverage`, timeout 900 in the manifest — the canon's 1800 is the going-forward value).
- **`skills/iw-ai-core-testing/SKILL.md`** §8 — adds `diff-coverage`, the 7-gate canon line, and the `fail_under`-floor/ratchet note. `.claude/skills/iw-ai-core-testing/SKILL.md` byte-identical (`diff` → IDENTICAL) — sync ran.
- **`.github/workflows/test-quality.yml`** — `unit` job: `fetch-depth: 0` on `actions/checkout` (commented), and a `Run diff coverage` step after the `coverage-xml` artefact upload — `if: github.event_name == 'pull_request'`, `git fetch --no-tags origin "${{ github.base_ref }}:refs/remotes/origin/${{ github.base_ref }}"` then `diff-cover tests/output/coverage/coverage.xml --compare-branch="origin/${{ github.base_ref }}" --fail-under=90`. Uses the unit `coverage.xml` already produced by `make test-unit` in the same job (cheap); a comment points to the strategy doc and notes the daemon gate is the authoritative combined one. No new job; skipped on `push` to main. ✓
- **`docs/IW_AI_Core_Testing_Strategy.md`** — §1 principle row notes the ratchet + the `diff-coverage` gate; §5 gate table Coverage row updated (`fail_under = 50`, ratchet note, "enforced via `pytest --cov` at the end of *every* run") + a new **Diff coverage** row + a new "**Coverage floor & diff-coverage (CR-00047, P1-CR-B)**" sub-section (the floor & how to re-derive it; what `diff-coverage` checks + `make diff-coverage` locally; the **coverage-source caveat** — daemon gate = combined, GH PR step = unit `coverage.xml`, daemon gate authoritative); §9 gaps table "Coverage failure floor" + "Diff/patch coverage on PRs" rows → ✅ (CR-00047, 2026-05-12).
- **`ai-dev/work/TESTS_ENHANCEMENT.md`** — items **1.2** / **1.3** / the **1.10 audit** marked DONE (CR-00047) with the audit findings inline on the 1.10 row; §5 grouping table — **P1-CR-B → SHIPPED (CR-00047, 2026-05-12)**, "*(start here)*" moved to **P1-CR-C**, sequencing rationale updated; the "Coverage floor starting value" open question resolved; top-of-doc status blurb refreshed (2026-05-12); a detailed changelog entry added (measured slices, the chosen `fail_under = 50`, `diff-cover` + `make diff-coverage` + the 7th gate, the cov-plumbing audit findings, what was deferred, the pre-existing-test-failure note).
- **`tests/unit/test_coverage_gate_config.py`** (new, optional guard test) — parses `pyproject.toml`/`Makefile` and pins real values: `fail_under == 50` and `> 46` and `< 100`; `relative_files is True`; `diff-cover` in `[dependency-groups] dev`; exactly one `diff-coverage:` Makefile target whose recipe runs `diff-cover --compare-branch=origin/main --fail-under=90`. Not vacuous. RED-first evidence in S01's contract (`AssertionError: assert 46 == 50`); the `assertions` scanner flagged the original all-`in` assert as a tautology and it was fixed to `makefile.count("\ndiff-coverage:") == 1` — scanner now clean.

### Acceptance-criteria roll-up

| AC | Result |
|----|--------|
| AC1 — floor raised & documented | ✔ `fail_under = 50` (> 46; just below the *lower* — unit 51.82–51.84% — slice; integration+dashboard 61.23%). §1 + §5 state the floor + the "never drop; ratchet up" rule. `make test-unit` passes the new floor; `make quality` passes. |
| AC2 — diff-coverage self-contained | ✔ `diff-cover` in dev deps + `uv.lock`; `make diff-coverage` builds its own combined coverage and runs `diff-cover … --compare-branch=origin/main --fail-under=90`; doesn't reuse a leftover `coverage.xml` or depend on the `integration-tests` gate; exits non-zero on shortfall; in `.PHONY`. |
| AC3 — wired into both CI surfaces | ✔ 7-gate canon with `diff-coverage` last, `{agent: qv-gate, gate: diff-coverage, command: make diff-coverage}`, prose says 7, `.claude/` copy synced; `test-quality.yml` `unit` job has the `pull_request`-conditional `Run diff coverage` step after `make test-unit`, comparing to the PR base, with `fetch-depth: 0`. |
| AC4 — cov-plumbing audit fixes | ✔ `relative_files = true` added; audit findings recorded in the design's `## Notes`, S01 §2, and `TESTS_ENHANCEMENT.md` item 1.10 (`pytest --cov` already correct; raw-`.coverage`/`include-hidden-files` N/A; subprocess coverage documented as a known limitation, not wired). |
| AC5 — dogfood diff-coverage gate | ✔ Ran `make diff-coverage` here → exit 0 ("No lines with coverage information in this diff"). |
| AC6 — plan & strategy doc | ✔ `TESTS_ENHANCEMENT.md` items 1.2/1.3/1.10-audit DONE (CR-00047), P1-CR-B SHIPPED, "*(start here)*" → P1-CR-C, changelog entry; `IW_AI_Core_Testing_Strategy.md` §1/§5/§9 + the new sub-section. |
| AC7 — testing skill | ✔ `skills/iw-ai-core-testing/SKILL.md` §8 + `.claude/` copy in sync. |
| AC8 — tdd_red_evidence honest | ✔ Real RED snippet (`AssertionError: assert 46 == 50`) for a non-vacuous parsed-value guard test — not a contrived test to populate the field. |

### Scope discipline
`git diff HEAD --stat` + the one untracked test file are all within the design's "Files changed by the implementation" list / `workflow-manifest.json:scope.allowed_paths`. No `integration-tests` no-op-gate fix (P1-CR-E), no `mutmut`/`vulture`/`deptry`/`gitleaks`/`semgrep`/`pytest-randomly`, no assertion-baseline scrub, no workflow-manifest schema change, no `--cov-report` restructure beyond `relative_files`, `fail_under` left below the measured value (headroom kept). ✔ (Note: `git diff main -- dashboard/routers/system.py` shows a 1-line comment delta — that's `main` having moved *ahead* of this worktree's base commit, **not** an edit by S01; `git diff HEAD` shows no change to it. Not a CR-00047 concern; the daemon rebases pre-merge.)

## Files changed (by S01, reviewed here)
`pyproject.toml` · `uv.lock` · `Makefile` · `skills/iw-workflow/SKILL.md` · `.claude/skills/iw-workflow/SKILL.md` · `skills/iw-ai-core-testing/SKILL.md` · `.claude/skills/iw-ai-core-testing/SKILL.md` · `.github/workflows/test-quality.yml` · `docs/IW_AI_Core_Testing_Strategy.md` · `ai-dev/work/TESTS_ENHANCEMENT.md` · `tests/unit/test_coverage_gate_config.py` (new). This step (S03) adds only this report.

## Test results
- `make lint` → pass · `make format` (`ruff format --check`) → pass (676 files).
- `make test-unit` → **2800 passed, 0 failed** (coverage 51.82% ≥ 50%) after a re-run; one flaky `test_browser_env.py::test_pick_free_offset_returns_hash_offset_when_free` on the first run (passes in isolation; pre-existing, unrelated).
- `make test-integration` → **2261 passed, 0 failed** (coverage 61.23% ≥ 50%).
- `make diff-coverage` → **exit 0** (combined coverage 75%; `diff-cover`: no changed lines to judge).

## Findings

| # | Severity | Category | File:line | Issue | Suggestion | Cross-cutting |
|---|----------|----------|-----------|-------|------------|---------------|
| 1 | MEDIUM (suggestion) | integration | `.github/workflows/test-quality.yml:78` | `Run diff coverage`'s `if: github.event_name == 'pull_request'` overrides GitHub Actions' implicit `success()`, so the step also runs when `make test-unit` failed — on a *collection* failure `tests/output/coverage/coverage.xml` may not exist and the step would fail with a confusing file-not-found instead of being skipped. Low practical impact (the job is already red). Same as S02 finding #1. | `if: success() && github.event_name == 'pull_request'`. Author's call. | yes |
| 2 | LOW | architecture | `pyproject.toml:163` | `fail_under = 50` leaves only ~1.8 pts of headroom over the measured unit slice (51.82–51.84%); a routine coverage wobble on the unit slice could trip the S08 `unit-tests` QV gate (no fix cycle). It is exactly the design's rule-of-thumb value (lower slice rounded down to the nearest 5) and within AC1. | Informational — per the ratchet rule the right response if it ever fires is to add coverage, not lower the floor (already documented). A more conservative 48–49 was also acceptable per the design. | no |
| 3 | LOW | testing | `tests/unit/test_browser_env.py` | `test_pick_free_offset_returns_hash_offset_when_free` failed once under the full `make test-unit` (port-binding race), passes in isolation. **Pre-existing, not caused by CR-00047** (which touches no production code). Could intermittently red the S08/S10 QV gates. | Out of scope here; relevant to P1-CR-C (test hygiene / `pytest-randomly` / port-isolation). Worth a follow-up. | no |
| 4 | LOW | testing | `tests/unit/test_safe_migrate.py` | The 2 `TestApply/TestRollback::test_*_refuses_in_agent_context` failures S01 flagged surface only when `IW_CORE_PER_WORKTREE_DB=true` leaks into a `patch.dict(..., clear=False)` test — they did not reproduce in this review's env. **Pre-existing, out of scope** (`test_safe_migrate.py` is not in this CR's paths); could red S08/S10 in a daemon env that has that var set. | Follow-up incident scoped to `test_safe_migrate.py` (`monkeypatch.delenv("IW_CORE_PER_WORKTREE_DB", raising=False)` / `clear=True`). | no |

## Observations
- **Untracked nested-dup directory** `ai-dev/active/CR-00047/CR-00047/` — a duplicate of `ai-dev/active/CR-00047/` that predates this step (visible in `git status` at session start; same artefact CR-00046 saw). Not created or modified by S01/S02/S03; flag for orchestrator cleanup before merge.
- The pre-existing pytest `Unknown config option: env` warning (`[tool.pytest.ini_options] env = [...]` with `pytest-env` not installed) is unrelated to this CR.
- Sibling repos (iw-doc-plan / podforger / cv) will pick up the new `diff-coverage` gate at their next `iw sync-skills` — a post-merge operator step, not done from this worktree (same pattern as CR-00046).

## Result contract

```json
{
  "step": "S03",
  "agent": "CodeReview_Final",
  "work_item": "CR-00047",
  "steps_reviewed": ["S01", "S02"],
  "verdict": "pass",
  "findings": [
    {
      "severity": "MEDIUM_SUGGESTION",
      "category": "integration",
      "file": ".github/workflows/test-quality.yml",
      "line": 78,
      "description": "The `Run diff coverage` step's `if: github.event_name == 'pull_request'` overrides GitHub Actions' implicit `success()`, so it runs even when `make test-unit` failed; on a collection failure tests/output/coverage/coverage.xml may not exist and the step fails with file-not-found instead of being skipped. Low practical impact (job already red). Same as S02 finding #1.",
      "suggestion": "Use `if: success() && github.event_name == 'pull_request'`. Author's call.",
      "cross_cutting": true
    },
    {
      "severity": "LOW",
      "category": "architecture",
      "file": "pyproject.toml",
      "line": 163,
      "description": "fail_under = 50 leaves only ~1.8 points of headroom over the measured unit-suite branch coverage (51.82-51.84%); a routine coverage wobble on the unit slice could trip the S08 unit-tests QV gate (no fix cycle). It is the design's rule-of-thumb value (lower slice rounded down to the nearest 5) and within AC1.",
      "suggestion": "Informational. If it ever fires, add coverage per the ratchet rule rather than lowering the floor (already documented). 48-49 was also acceptable per the design.",
      "cross_cutting": false
    },
    {
      "severity": "LOW",
      "category": "testing",
      "file": "tests/unit/test_browser_env.py",
      "line": 1,
      "description": "test_pick_free_offset_returns_hash_offset_when_free failed once under the full `make test-unit` (port-binding race), passes in isolation. Pre-existing, not caused by CR-00047 (which changes no production code). Could intermittently red the S08/S10 QV gates.",
      "suggestion": "Out of scope here; relevant to P1-CR-C (test hygiene / pytest-randomly / port isolation). Worth a follow-up.",
      "cross_cutting": false
    },
    {
      "severity": "LOW",
      "category": "testing",
      "file": "tests/unit/test_safe_migrate.py",
      "line": 1,
      "description": "The 2 TestApply/TestRollback::test_*_refuses_in_agent_context failures S01 flagged surface only when IW_CORE_PER_WORKTREE_DB=true leaks into a patch.dict(..., clear=False) test (did not reproduce in this review's env). Pre-existing, out of scope (test_safe_migrate.py is not in this CR's paths); could red S08/S10 in a daemon env that sets that var.",
      "suggestion": "Follow-up incident scoped to test_safe_migrate.py (monkeypatch.delenv(\"IW_CORE_PER_WORKTREE_DB\", raising=False) / clear=True).",
      "cross_cutting": false
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "make test-unit: 2800 passed, 4 skipped, 5 xfailed, 1 xpassed, 0 failed (coverage 51.82% >= 50%) after a re-run (1 flaky pre-existing test_browser_env failure on the first run, passes in isolation). make test-integration: 2261 passed, 33 skipped, 3 xfailed, 0 failed (coverage 61.23% >= 50%). make diff-coverage: exit 0 (combined coverage 75%; diff-cover: no changed lines to judge). make lint / make format / (via S01/S02) make test-assertions / make type-check / make quality: all pass.",
  "missing_requirements": [],
  "notes": "All 8 acceptance criteria met. Coverage-config <-> Makefile <-> skill canon (7 gates, diff-coverage last) <-> GH workflow (pull_request-conditional unit-coverage diff step) <-> strategy doc + plan chain is internally consistent. .claude/skills/iw-workflow/SKILL.md and .claude/skills/iw-ai-core-testing/SKILL.md byte-identical to masters (iw sync-skills ran). make diff-coverage dogfooded end-to-end -> exit 0 (AC5). Cov-plumbing audit findings recorded in the design Notes + S01 report + TESTS_ENHANCEMENT.md item 1.10. No scope creep (no integration-gate fix, no other Phase-1 deps, no baseline scrub, no manifest-schema change). 0 CRITICAL / 0 HIGH / 0 MEDIUM(fixable). Untracked nested-dup dir ai-dev/active/CR-00047/CR-00047/ predates this step -- flag for orchestrator cleanup. The 2 pre-existing test_safe_migrate.py failures and the flaky test_browser_env test are pre-existing, out of scope, and warrant a follow-up incident."
}
```
