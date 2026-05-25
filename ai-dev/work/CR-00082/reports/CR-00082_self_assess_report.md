### Item Analysis: CR-00082

**Bottom line:** The code-review step (S04) burned 5 fix cycles and 13 total runs — the single most costly inefficiency — largely because the reviewer's own prompt (S04 prompt) referenced a non-existent directory path (`ai-dev/work/CR-00082/`) that the reviewer then incorrectly flagged as scope-creep, and because the assertion-scanner gate (S07) does not yet know that `pytest.fail()` is a valid test pattern (no bare `assert` required).

**Steps analyzed:** 13 (S01–S13) | **Steps with retries:** S02 (4 runs), S04 (13 runs incl. 5 fix cycles), S06 (2 runs), S07 (1 fix cycle) | **Total fix-cycles:** 6 | **DB signal:** yes (full telemetry via `iw item-status --json`)

---

[1] S04 reviewer consumed 5 fix cycles and 13 total runs due to prompt path typo → false scope-creep findings
    Severity: HIGH   Class: prompt   Frequency: systemic
    Evidence:
      - ai-dev/active/CR-00082/prompts/CR_00082_S04_CodeReview_prompt.md:10 — "ai-dev/work/CR-00082/CR_00082_CR_Design.md" (path does not exist; correct path is ai-dev/active/CR-00082/CR_00082_CR_Design.md)
      - ai-dev/logs/CR-00082_S04_fix1.log — "Out-of-scope deletion (`docs/IW_AI_Core_Architecture.pdf`) was present in working tree" + "Restored out-of-scope deleted file" (agent acted on false positive)
      - ai-dev/logs/CR-00082_S04_fix3.log — "Removed out-of-scope artefacts: Deleted untracked directory `ai-dev/work/CR-00082/`" (wrong directory; ai-dev/work/CR-00082/ does not exist as a standard path; correct is ai-dev/active/CR-00082/)
      - ai-dev/logs/CR-00082_S04_fix4.log — "ai-dev/active/CR-00082/reports/CR-00082_S01_Backend_report.md was missing" (still misinterpreting scope after 3 cycles)
    Recommendation: Fix the design-doc path in the S04 prompt template (`templates/design/`) from `ai-dev/work/<ID>/<ID>_CR_Design.md` to `ai-dev/active/<ID>/<ID>_CR_Design.md`. Add a verification step: if the design doc is not found at the stated path, abort with a clear error rather than proceeding with a guessed path and generating false findings.
    Target: templates/design/ (and any AI-dev step prompts that inherit the same broken path)
    Pros: Eliminates 3–4 wasted fix cycles per affected CR/Feature that has an S04 review step; reviewer stops generating false scope-creep findings.
    Cons: Requires updating the prompt template; needs a sync pass across all in-flight items.
    If we don't: Every CR/Feature with an S04 step continues burning 3–5 unnecessary fix cycles, and agents delete the wrong directories based on incorrect reviewer feedback.
    Effort: S (~2 lines in 1 template file)

[2] Assertion scanner (S07) flags `pytest.fail()` without bare `assert` as a violation — forces awkward `assert` after `pytest.fail()` to satisfy gate
    Severity: MED   Class: environment   Frequency: one-off
    Evidence:
      - ai-dev/active/CR-00082/fix-cycles/CR_00082_S07_FIX_cycle1_prompt.md — "ruff-assertions (the `test-assertions` make target) flagged `no-assert` on both visual-regression test functions — they contained `pytest.fail()` branches but no bare `assert` statement"
      - ai-dev/logs/CR-00082_S07_fix1.log — "Added `assert diff_fraction <= __MAX_DIFF_FRACTION__` after the `pytest.fail()` block in both functions" (artificial `assert` added just to satisfy scanner)
    Recommendation: Update the assertion-scanner rule (`ruff-assertions` or the custom scanner config) to treat `pytest.fail()` as an implicit assertion for the purposes of the `no-assert` rule. The `pytest.fail()` call IS the assertion — it compares a computed value against a threshold and terminates the test if the threshold is exceeded. Alternatively, document in CLAUDE.md or the testing skill that visual-regression test functions MUST contain a bare `assert` statement (even if redundant with the `pytest.fail()` guard) to satisfy the scanner.
    Target: pyproject.toml ([tool.ruff.lint] or the custom assertion scanner config), OR skills/iw-ai-core-testing/SKILL.md
    Pros: Prevents unnecessary S07 fix cycle for any future test that uses `pytest.fail()` as its assertion mechanism.
    Cons: Small config change or documentation addition; scanner change has low risk.
    If we don't: Every new visual-regression test (and any other test using `pytest.fail()` as its assertion mechanism) will trigger a spurious assertion-scanner violation requiring a fix cycle.
    Effort: S (~5 lines in pyproject.toml OR ~3 lines in SKILL.md)

[3] S03 CI workflow install command used `--frozen` without `--all-groups` — would skip `[dependency-groups].dev` in CI
    Severity: MED   Class: prompt   Frequency: one-off
    Evidence:
      - ai-dev/logs/CR-00082_S04_fix4.log — "`.github/workflows/visual-regression.yml` — Changed install command: `uv sync --frozen` → `uv sync --all-groups --frozen`" (caught in S04 fix cycle 4)
    Recommendation: Add an explicit instruction in the S03 prompt: "Verify the CI workflow's install command uses `--all-groups` (not just `--frozen`) so that `[dependency-groups].dev` dependencies are installed." This is especially important when the step introduces new `[dependency-groups].dev` dependencies (like Pillow + pixelmatch). Also recommend adding a note: "Match the install pattern from existing CI workflows (e.g., `.github/workflows/quality.yml`)."
    Target: templates/design/ (S03 step prompt)
    Pros: Prevents CI from silently skipping dev-group dependencies; ensures visual-regression tooling is available in the CI run.
    Cons: Slightly longer prompt; no code risk.
    If we don't: CI workflow may fail silently (tests skip due to missing `playwright-cli` or `pdftoppm`) until caught in a later review or CI run.
    Effort: S (~3 lines in 1 prompt template)

[4] S02 had 2 empty run logs (S02_run1.log = 0 bytes, S02_run2.log = 0 bytes) before successful run4
    Severity: MED   Class: platform   Frequency: one-off
    Evidence:
      - ai-dev/logs/ — "0 CR-00082_S02_run1.log", "0 CR-00082_S02_run2.log" (empty logs from early S02 attempts; run4 is the success)
    Recommendation: Investigate why S02 produced empty run logs for the first two attempts. Likely causes: (a) agent process killed/exited before writing completion output to log, (b) log rotation or file-write buffering issue, (c) executor crashed or timed out before logging started. If this is reproducible, it's a platform issue in the executor/logging path. If it was a one-off (e.g., agent hit a hard limit and was retried by the daemon), document as transient.
    Target: executor/ (bash run-logging scripts) or orch/daemon/ (step execution)
    Pros: Identifies a potential silent failure mode where an agent step completes (or appears to) without producing a run log.
    Cons: May be non-reproducible; investigation effort may not yield actionable fix.
    If we don't: Empty logs continue to appear, making post-mortem analysis harder and potentially hiding real failures.
    Effort: M (investigation required; fix TBD)

[5] S04 reviewer repeated the same false-positive findings across 3 consecutive fix cycles
    Severity: MED   Class: prompt   Frequency: recurring
    Evidence:
      - ai-dev/logs/CR-00082_S04_fix1.log — "scope creep + Playwright token violation + dependency placement mismatch"
      - ai-dev/logs/CR-00082_S04_fix3.log — "format-check violation, scope creep under ai-dev/work/CR-00082" (same scope-creep finding, repeated)
      - ai-dev/logs/CR-00082_S04_fix4.log — "missing S01 report; CI workflow install command mismatch" (still hadn't resolved earlier findings)
    Recommendation: After a fix cycle resolves a finding (e.g., dependency moved to correct group, scope artefact removed), the next review run should NOT re-flag the same finding unless the fix was actually reverted. Add a "previously addressed findings" list to the fix-cycle prompt so the reviewer can skip re-checking findings that were confirmed resolved in the prior cycle. Alternatively, add a "converged verdict" rule: if 3 consecutive cycles flag the same finding class without new evidence, the reviewer must escalate rather than generate another fix-cycle.
    Target: templates/design/ (S04 fix-cycle prompt template)
    Pros: Reduces fix-cycle count when the same finding is re-flagged after being fixed; saves agent time.
    Cons: Requires prompt-template change; could suppress legitimate re-finding if the fix was reverted.
    If we don't: S04-type steps continue burning 5 fix cycles per CR, with most cycles addressing the same handful of findings.
    Effort: S (~10 lines in fix-cycle prompt template)
