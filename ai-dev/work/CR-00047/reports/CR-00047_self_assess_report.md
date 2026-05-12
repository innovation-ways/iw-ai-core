### Item Analysis: CR-00047

Bottom line: This item executed cleanly — zero retries, zero fix-cycles, every QV gate green on the first run; the only actionable pattern is a minor platform bug — the worktree carries a nested duplicate `ai-dev/active/<ID>/<ID>/` of the design package that every review step has to call out as out-of-scope noise.

Steps analyzed: 11   Steps with retries: 0   Total fix-cycles: 0   DB signal: yes (item-status JSON only)

CR-00047 (P1-CR-B — raise the coverage floor, add `diff-cover` dep + `make diff-coverage`, add the 7th `diff-coverage` daemon QV gate, add the GH `pull_request` diff-coverage step) ran S01→S11 with no agent thrash:

- **S01 backend-impl** — delivered the full package in one run; preflight (format/typecheck/lint) ok; optional guard test `tests/unit/test_coverage_gate_config.py` 4/4; `tdd_red_evidence` genuine (`AssertionError: assert 46 == 50` RED → GREEN after the `fail_under` raise). No env/install commands run inside the step. One self-flagged out-of-scope note: a pre-existing `tests/unit/test_safe_migrate.py` failure pair that only surfaces when `IW_CORE_PER_WORKTREE_DB=true` leaks into the env — it did **not** surface in the QV-gate env (S08 = 2800 passed), so it cost this item nothing.
- **S02 code-review-impl / S03 code-review-final-impl** — both `pass`, 0 mandatory fixes; 1 MEDIUM *suggestion* each (the GH `Run diff coverage` step's `if:` overrides the implicit `success()` — author's call, not a blocker).
- **S04–S10 qv-gate** — `make lint` ✅, `make test-assertions` ✅, `make format-check` ✅, `make type-check` ✅, `make test-unit` ✅ (2800 passed, coverage 51.82% ≥ 50% floor), `make allure-integration` ✅ (a deliberate no-op stub today — P1-CR-E will fill it in; not a defect), `make diff-coverage` ✅ (exit 0, "No lines with coverage information in this diff" — the AC5 dogfood). No gate flaked or needed a retry.

Two secondary observations, not promoted (don't clear the ≥2-step / HIGH bar, or are intentional-by-design):

- **S10 `make diff-coverage` ran 568 s** (`2261 passed … in 568.34s`) because the target deliberately re-runs the unit + integration + dashboard suites from scratch to build its own combined coverage. The Makefile comment justifies this (robust to the overwritten-`coverage.xml` artefact and to the current no-op `integration-tests` gate) and the new skill canon gives the daemon step a 1800 s timeout. *But this item's own `workflow-manifest.json` (generated at design time, before S01 raised the canon to 1800 s) gave S10 only `timeout_secs: 900`* — 568 s left ~5.5 min of slack, so it passed, but a slightly slower integration run would have timed it out. Self-healing for future items (they inherit the 1800 s canon); flagged here only so a reviewer knows the close call existed.
- The diff-coverage gate now structurally duplicates the work of the `unit-tests` (S08) and `integration-tests` (S09) gates — ~10 min added per workflow. Intentional today; once P1-CR-E makes `make allure-integration` real, the gate could reuse that combined coverage instead. Out of scope for an execution-analysis finding (it's a code-design call, already documented in the Makefile).

[1] Worktree carries a nested duplicate of the design package: `ai-dev/active/<ID>/<ID>/`
    Severity: LOW   Class: platform   Frequency: recurring
    Evidence:
      - ai-dev/logs/CR-00047_S01_run1.log:30 — "untracked nested-dup dir ai-dev/active/CR-00047/CR-00047/ predates this step (was in `git status` at session start) — not touched here; flagging for cleanup"
      - ai-dev/logs/CR-00047_S02_run1.log:18 — "The untracked `ai-dev/active/CR-00047/CR-00047/` nested-dup dir predates this step — flagged for orchestrator cleanup"  (also seen in S03)
      - ai-dev/logs/CR-00047_S03_run1.log:13 — "untracked nested-dup dir `ai-dev/active/CR-00047/CR-00047/` predates this step — flagged for orchestrator cleanup before merge"
      - filesystem (direct): `ai-dev/active/CR-00047/CR-00047/{workflow-manifest.json, CR-00047_CR_Design.md, CR-00047_Functional.md, prompts/*, evidences/}` — a full second copy of the package that already lives at `ai-dev/active/CR-00047/`
    Recommendation: Find the path-join that produces `ai-dev/active/<ID>/<ID>/` — almost certainly a `dest = ai-dev/active/<ID>` that then copies a source tree already rooted at `<ID>/` (the design-package staging dir or archive) into it instead of into `ai-dev/active/`. Likely sites: the item-approval / worktree-setup copy step in `orch/` (e.g. `orch/cli/item_commands.py` approve hook, or the executor's worktree-setup script under `executor/`). Either fix the join, or have worktree setup prune a `<ID>/<ID>/` nesting if it appears.
    Target: iw-ai-core (orch/ item-approval or executor/ worktree-setup — exact file TBD by the fix author)
    Pros: Removes recurring noise that three review agents independently spend words triaging every item; keeps the committed `ai-dev/active/<ID>/` tree clean (the dup is untracked today but is the kind of thing that gets `git add -A`-ed by accident and then archived as junk).
    Cons: Touches worktree-setup / approval plumbing — needs care + a regression test; the dup is currently harmless (untracked, ignored by the workflow), so priority is genuinely low.
    If we don't: Every future item keeps shipping a stray `ai-dev/active/<ID>/<ID>/` mirror; review agents keep burning a sentence each on "flagged for orchestrator cleanup"; small risk of it being committed/archived eventually.
    Effort: S (~1 path fix + 1 regression test, 1–2 files)
