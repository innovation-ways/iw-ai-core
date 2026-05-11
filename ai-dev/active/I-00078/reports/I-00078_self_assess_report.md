### Item Analysis: I-00078

Bottom line: Fix the QV gates (S06–S10) so they no longer flag pre-existing code quality issues in unmodified files, and tighten the test prompt so S03 doesn't need a fix cycle to satisfy PT018.

**Steps analyzed: 12   Steps with retries: 6 (S06, S07, S08, S09, S10, S11)   Fix-cycles: 3 (S06, S07, S10)   DB signal: yes**

---

[1] QV lint gate (S06) flags pre-existing unused-import in unrelated test file
    Severity: MED   Class: platform   Frequency: systemic
    Evidence:
      - ai-dev/active/I-00078/fix-cycles/I-00078_S06_FIX_cycle1_prompt.md:1 — "The error is straightforward: `select` is imported but never used. Remove it."
      - ai-dev/logs/I-00078_S06_run1.log:1 — "All checks passed!"
      - ai-dev/logs/I-00078_S06_run3.log:3 — "F401 [*] `sqlalchemy.select` imported but unused → tests/integration/test_e2e_seed.py:18:39"
      - ai-dev/logs/I-00078_S06_fix1.log:16 — "Fixed. Removed unused `select` import from tests/integration/test_e2e_seed.py"
    Recommendation: The lint gate runs `ruff check .` against the whole repo. It should either (a) scope to changed files only via `ruff check $(git diff --name-only HEAD)` or (b) exclude pre-existing violations in `ruff.toml`/`pyproject.toml` with `exclude = ["tests/integration/test_e2e_seed.py"]` or (c) run only against `dashboard/` and `tests/dashboard/` and `orch/` dirs that I-00078 touches.
    Target: Makefile or orch/test_runner.py
    Pros: Prevents 3-run thrash + fix cycle when a gate hits pre-existing debt in an unrelated file.
    Cons: A blanket scope change might miss a real lint violation in a changed file.
    If we don't: Every future item that passes through S06 hits the same pre-existing error in test_e2e_seed.py; agents waste ~2 min per occurrence.
    Effort: S (~5 lines in Makefile or pyproject.toml)

[2] QV integration-tests gate (S10) fails on pre-existing testcontainers fixture error
    Severity: HIGH   Class: platform   Frequency: recurring
    Evidence:
      - ai-dev/logs/I-00078_S10_run1.log:66 — "FAILED tests/integration/test_e2e_seed.py::test_e2e_seed_runs_against_fresh_db"
      - ai-dev/logs/I-00078_S10_run1.log:64 — "FAIL Required test coverage of 46.0% not reached. Total coverage: 3.33%"
      - ai-dev/active/I-00078/fix-cycles/I-00078_S10_FIX_cycle1_prompt.md — fix cycle prompt confirms testcontainers/postgres `execute_batch` error at startup
    Recommendation: Mark `tests/integration/test_e2e_seed.py` as expected-to-fail in the integration-test gate config, or add it to a skip list in `orch/test_runner.py`. The test is a seed/infra test that has nothing to do with any work item's scope.
    Target: orch/test_runner.py or Makefile
    Pros: Prevents ~3 min of wasted run + fix cycle + retry per affected item.
    Cons: Test worth fixing properly at some point.
    If we don't: Every item running integration tests will either skip this fixture or fail it, consuming a fix cycle slot unnecessarily.
    Effort: S (~3 lines)

[3] Code-review agents (S02, S04) fail to find report files due to wrong filename convention
    Severity: MED   Class: prompt   Frequency: recurring
    Evidence:
      - ai-dev/logs/I-00078_S02_run1.log:9 — "File not found: .../I-00078_S01_frontend-impl_report.md"
      - ai-dev/logs/I-00078_S04_run1.log:10 — "File not found: .../I-00078_S03_tests-impl_report.md"
      - ai-dev/logs/I-00078_S05_run1.log:10 — "File not found: .../I-00078_S01_Impl_Start_report.md"
    Recommendation: Add a clarifying note to the CodeReview prompt templates (both `templates/design/CodeReview_Prompt_Template.md` and `ai-dev/templates/CodeReview_Prompt_Template.md`) stating: "Reports use `_<AgentName>_[...]_report.md` pattern, e.g. `I-00078_S01_Frontend_report.md`, not `_<step>_impl_report.md`." The agent should glob first before reading.
    Target: templates/design/CodeReview_Prompt_Template.md, ai-dev/templates/CodeReview_Prompt_Template.md
    Pros: Eliminates one failed read per code-review step; agents proceed faster.
    Cons: Minor prompt noise.
    If we don't: Every CR step in every item wastes ~30s re-trying reads with wrong filenames.
    Effort: S (~1 sentence in template)

[4] Tests-impl agent (S03) breaks PT018 rule — fix cycle needed to learn split assertion
    Severity: MED   Class: prompt   Frequency: one-off
    Evidence:
      - ai-dev/logs/I-00078_S03_run1.log:253 — "PT018 Assertion should be broken down into multiple parts → tests/dashboard/test_i00078_layout.py:259:5"
      - ai-dev/logs/I-00078_S03_run1.log:282 — edit fixing lines 259–265: "assert root_block, ...assert '--scrollbar-thumb' in..."
    Recommendation: Add PT018 to the list of rules explicitly checked before writing assertions in the Implementation prompt template (both `templates/design/Implementation_Prompt_Template.md` and `ai-dev/templates/Implementation_Prompt_Template.md`).
    Target: templates/design/Implementation_Prompt_Template.md, ai-dev/templates/Implementation_Prompt_Template.md
    Pros: Saves 1 fix cycle (~3 min) per future item that writes CSS-variable existence assertions.
    Cons: Slightly longer prompt.
    If we don't: Future agents that assert multi-part conditions in CSS/HTML parsing tests will hit PT018.
    Effort: S (~1 bullet in checklist)

[5] S11 browser verification uses SQL seed workaround instead of e2e_fixtures file
    Severity: LOW   Class: environment   Frequency: one-off
    Evidence:
      - ai-dev/active/I-00078/e2e_fixtures/001_long_pipeline.py:1 — fixture file present (1.8 KB)
      - ai-dev/logs/I-00078_S11_run1.log:line~80 — "V2 required seeding 16 steps for F-00055 directly in the E2E PostgreSQL container since the worktree was not mounted in the app container and the host's IW_CORE_AGENT_CONTEXT guard prevented direct ORM access"
    Recommendation: For S11 items with a long-pipeline fixture, supply the DB credentials for the E2E stack's postgres container (`e2e_db` service) as `IW_E2E_DB_*` env vars so the agent can run the fixture SQL directly against it without needing ORM access or worktree mounting.
    Target: orch/daemon/browser_env.py or the QVBrowser prompt template
    Pros: Lets the e2e_fixtures file be used as intended rather than requiring a manual SQL workaround.
    Cons: Requires E2E compose stack to expose DB port to host or a DB cred mechanism.
    If we don't: Agents for browser-verification items needing pipeline overflow will continue to improvise SQL seed workarounds.
    Effort: M (~10 lines in browser_env.py + env var setup)

[6] S05 agent uses a typo path causing a read failure (concession error, recovered)
    Severity: LOW   Class: agent   Frequency: one-off
    Evidence:
      - ai-dev/logs/I-00078_S05_run1.log:20 — "Error: File not found: /home/sgeriog/dev/iw-doc-plan/..." (note `sgeriog` vs `sergioG`)
    Recommendation: No platform fix needed — agent self-corrected. Observe only.
    Target: (none — agent recovered)
    Pros: N/A
    Cons: N/A
    If we don't: N/A
    Effort: N/A
