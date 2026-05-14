# CR-00050: Security gates — gitleaks (blocking) + Semgrep (nightly-first) (P1-CR-D)

**Type**: Change Request
**Priority**: High
**Reason**: Phase-1 P1-CR-D from `ai-dev/work/TESTS_ENHANCEMENT.md` — bundles items **1.6** (gitleaks secret scanning, blocking on every PR per plan §9) and **1.9** (Semgrep SAST alongside bandit, nightly-first then gate). Secret scanning's not-having cost is unbounded (one leaked credential ⇒ full incident response); the cost of having it is one pre-commit hook + one CI job + one daemon QV gate.
**Created**: 2026-05-13
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. This CR only touches CI configuration / tooling / docs — no new Docker usage. The existing Trivy IaC scan job and bandit job are untouched.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This CR adds, modifies, and removes **no** Alembic migrations. No DB schema changes whatsoever.

## Description

Wire `gitleaks` as a blocking gate on **three surfaces** — a pre-commit hook, a GH Actions job, and a daemon QV gate (`security-secrets`, the 8th canonical gate) — using the project's existing `.gitleaks.toml` (placed by `iw-oss-publish`). S01's first deliverable is triaging the **109 pre-existing findings** on `main` (mostly false positives in test fixtures and `dev@example.local`-style example domains); each unique RuleID+path-pattern is either widened into the existing `[allowlist].paths` regex OR added as a per-finding `[[rules.allowlists]]` entry with a `# why` comment naming what it is. Real-looking secrets are escalated, not silently allowlisted. Concurrently, replace the `make security-sast` no-op alias with a real Semgrep invocation (`p/python` + `p/owasp-top-ten` + `p/security-audit`) and add a `semgrep` GH job with `continue-on-error: true` during burn-in; a follow-up `P1-CR-D-followup-semgrep-block` is filed to flip blocking after the noise is triaged.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Read `tests/CLAUDE.md` for testing rules. Read `skills/iw-oss-publish/scripts/checks/secrets.py` (lines 38–55 + 176–191) for the convention this CR aligns with — `gitleaks detect --no-git --config <abs path>` with the project-level `.gitleaks.toml`. Read `skills/iw-workflow/SKILL.md` for the canonical 7-gate QV chain this CR extends to 8.

## Current Behavior

Three observations form the baseline:

**1. `.gitleaks.toml` already exists at repo root** (placed by `iw-oss-publish/scripts/lib/fixes.py:171`). It uses `[extend] useDefault = true` (inherits gitleaks' ~150 built-in detectors), adds three IW-specific rules (`iw-internal-email`, `iw-internal-fqdn`, `iw-rfc1918-ip`), and has a path allowlist for `docs/`, `tests/fixtures/`, `examples/`, `.iw/`, `.git/`, `.venv/`, `venv/`, `node_modules/`, `dist/`, `build/`, `__pycache__/`, `logs/`, `allure-report/`, `allure-results/`. **It does not cover `tests/unit/` or `tests/integration/`**, which is where most of the false positives below live.

**2. Running `gitleaks detect --no-git --config .gitleaks.toml -v` against current `main` produces 109 findings.** A representative sample (gathered 2026-05-13):

- `tests/unit/test_browser_env.py:70` — `dev@example.local` (RuleID `iw-internal-fqdn` — false positive: example domain in a test for browser-env parsing).
- `tests/unit/test_oss_secrets_parser.py:94` — `sk-abcd1234ZZZZ9999XY` (RuleID `generic-api-key` — false positive: test fixture string for the secrets-parser test itself).
- The rest are similar: example-data strings in unit test fixtures, doc-example secret-looking strings, RFC-1918 IPs in test-data, internal-FQDN-shaped strings in tests for the OSS-publish gitleaks-workflow code.

Triage estimate: most of the 109 findings collapse into ~6–10 unique RuleID+path-pattern groups. Per the operator's chosen strategy ("Mixed strategy: fix real leaks; allowlist false positives in `.gitleaks.toml`"), this is the bulk of S01's work — not the CI wiring.

**3. No gitleaks pre-commit hook, no gitleaks GH job, no daemon QV gate.** Specifically:

- `.pre-commit-config.yaml` has 12 hooks (trailing-whitespace, end-of-file-fixer, check-yaml, check-json, check-toml, check-added-large-files, detect-private-key, check-merge-conflict, check-case-conflict, ruff, ruff-format, mypy). **No gitleaks hook.**
- `.github/workflows/security-scan.yml` has 2 jobs: `deps-audit` (pip-audit + bandit -ll on `orch dashboard executor`) and `iac-scan` (Trivy config, HIGH/CRITICAL only, SARIF upload). **No gitleaks job, no Semgrep job.**
- `Makefile` has: `security-deps` (pip-audit + bandit, both `|| true`-tolerant for report-collection use), `security-iac` (Trivy), `security-image-dashboard` (no-op stub: `@echo "no built image — N/A for this project"`), `security-all` (= deps + iac), `security-sast: security-deps` (**just an alias — the recipe is `@echo "[security-sast] complete"` and nothing else**), `security-report` (`scripts/security_report.py`). The plan explicitly calls out `make security-sast` as "currently just a bandit alias."
- `skills/iw-workflow/SKILL.md` canonical QV gate list (extended by CR-00046 / CR-00047) is now 7 gates: `lint → assertions → format → typecheck → unit-tests → integration-tests → diff-coverage`. **No `security-secrets` gate.**

The three required tools (`pre-commit`, `gitleaks`, `semgrep`) are already installed in the dev environment (verified 2026-05-13: pre-commit 4.5.1, gitleaks 8.30.1, semgrep 1.158.0).

## Desired Behavior

After this CR ships:

**Gitleaks (blocking on every PR + every commit + every per-item merge gate):**

- `.gitleaks.toml` is updated so `gitleaks detect --no-git --config .gitleaks.toml -v` against the working tree produces **0 findings**. Every false positive added between the original `iw-oss-publish`-generated baseline and this CR's run is documented inline with a one-line `# why` comment naming the file/pattern and why it is safe.
- A `gitleaks` hook in `.pre-commit-config.yaml` (using the `gitleaks/gitleaks` repo's pre-commit shim) blocks commits with new findings.
- A `gitleaks` (or `secrets-scan`) job in `security-scan.yml` runs on `push`, `pull_request`, and the existing `schedule` cron; uploads SARIF to Code Scanning with the same "skip-when-private-repo-no-Advanced-Security" caveat as `iac-scan` (per the existing comment block on the trivy-iac upload step).
- A `make security-secrets` target (recipe: `gitleaks detect --no-git --config .gitleaks.toml`) is added to the `Makefile`, folded into `make security-all`, listed in `.PHONY`.
- The `security-secrets` gate is the **8th canonical daemon QV gate** in `skills/iw-workflow/SKILL.md`, immediately after `diff-coverage`. `.claude/skills/iw-workflow/SKILL.md` is byte-equal to its master after `iw sync-skills`.

**Semgrep (nightly first, gate later):**

- `make security-sast` actually runs Semgrep against `orch dashboard executor` with `--config p/python --config p/owasp-top-ten --config p/security-audit` (Semgrep managed rulesets). No longer a `@echo` alias.
- A `semgrep` job in `security-scan.yml` runs on `push`, `pull_request`, and the existing `schedule` cron with `continue-on-error: true` during burn-in; uploads SARIF mirroring the trivy-iac/gitleaks pattern. A `P1-CR-D-followup-semgrep-block` row is filed in `ai-dev/work/TESTS_ENHANCEMENT.md` §5 to flip blocking after the noise is triaged.
- bandit stays in `security-deps` (no change to where it runs — it remains the deep Python-specific complement to Semgrep's broader rulesets).

**Docs and plan:**

- `docs/IW_AI_Core_Testing_Strategy.md` §5 gate table grows two rows: "Secret scan (gitleaks)" (✅) and "Semgrep SAST" (⚠️ burn-in). §9 gaps table — `gitleaks` row flipped ❌→✅, Semgrep row flipped ❌→⚠️.
- `skills/iw-ai-core-testing/SKILL.md` §8 mentions both new gates and the burn-in policy. `.claude/skills/iw-ai-core-testing/SKILL.md` synced.
- `ai-dev/work/TESTS_ENHANCEMENT.md` §5 row P1-CR-D marked **SHIPPED (CR-00050, YYYY-MM-DD)**; items 1.6 + 1.9 flipped to DONE; new `P1-CR-D-followup-semgrep-block` row filed; §11 changelog entry.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `.gitleaks.toml` (root) | `iw-oss-publish`-generated baseline; 109 findings against current main | Allowlists extended to cover `tests/unit/`, `tests/integration/`, `tests/dashboard/`, and per-finding stopwords/regexes for genuine false-positive secret-like strings in test fixtures. 0 findings against main. |
| `.pre-commit-config.yaml` | 12 hooks, no gitleaks | +1 hook: `gitleaks/gitleaks` (recent stable tag, pinned). Hard fail. |
| `.github/workflows/security-scan.yml` | 2 jobs: `deps-audit`, `iac-scan` | +2 jobs: `secrets-scan` (gitleaks, blocking) and `semgrep` (continue-on-error during burn-in). Both upload SARIF with the same private-repo-skip caveat as `iac-scan`. |
| `Makefile` `security-sast` target | `@echo "[security-sast] complete"` — pure no-op alias of `security-deps` | Real Semgrep invocation: `uv run semgrep --config p/python --config p/owasp-top-ten --config p/security-audit orch dashboard executor --error`. Output also routed to `$(SECURITY_DIR)/semgrep.json` for `security-report`. |
| `Makefile` `security-secrets` target | does not exist | New: `uv run gitleaks detect --no-git --config .gitleaks.toml` (plus a JSON output to `$(SECURITY_DIR)/gitleaks.json` for `security-report`). Folded into `security-all`. Added to `.PHONY`. |
| `skills/iw-workflow/SKILL.md` canonical QV gate list | 7 gates: lint → assertions → format → typecheck → unit-tests → integration-tests → diff-coverage | 8 gates: same + **security-secrets** (after `diff-coverage`). |
| `.claude/skills/iw-workflow/SKILL.md` | mirror of master | re-synced via `iw sync-skills` |
| `skills/iw-ai-core-testing/SKILL.md` §8 | no mention of gitleaks/Semgrep | + new gates listed with the burn-in note |
| `.claude/skills/iw-ai-core-testing/SKILL.md` | mirror of master | re-synced via `iw sync-skills --force iw-ai-core-testing` |
| `docs/IW_AI_Core_Testing_Strategy.md` §5 + §9 | no gitleaks/Semgrep rows | +2 rows in §5 gate table; flip 2 rows in §9 gaps table |
| `ai-dev/work/TESTS_ENHANCEMENT.md` §5 + §11 | P1-CR-D row open, items 1.6/1.9 TODO | P1-CR-D row SHIPPED (CR-00050, YYYY-MM-DD); items 1.6/1.9 DONE; +1 new follow-up row `P1-CR-D-followup-semgrep-block`; +1 §11 changelog entry |

### Breaking Changes

**None.** Additive security gates.

One operational note: the `gitleaks` pre-commit hook fetches the binary automatically the first time `pre-commit run` runs after this CR lands, via the `repos: - repo: https://github.com/gitleaks/gitleaks` block in `.pre-commit-config.yaml`. No manual install step required for committers.

### Data Migration

**None.** No DB tables, rows, or migrations touched.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | `backend-impl` | RED-first 109-finding scan → triage (allowlist false positives; escalate real leaks) → wire pre-commit hook + GH job + daemon QV gate + `make security-secrets`; rewrite `make security-sast` with Semgrep; add `semgrep` GH job (continue-on-error); update strategy doc / skills / plan / changelog; run `iw sync-skills`. Extended 2400 s timeout for the triage workload. | — |
| S02 | `code-review-impl` | Review S01: gitleaks scan against the patched tree returns 0 findings; every `.gitleaks.toml` allowlist diff carries a `# why` comment; no real-looking secrets silently allowlisted; pre-commit + GH job + daemon QV gate + make target all wired; Semgrep wired (not the old alias); SARIF uploads mirror trivy-iac's private-repo-skip pattern; `.claude/skills/` byte-equal to masters; no out-of-scope edits. | — |
| S03 | `code-review-final-impl` | Global review: re-run gitleaks independently — 0 findings; re-run `make security-sast` — Semgrep actually executes (not echoes); `make security-secrets` is in the canonical gate list; `make quality` + `make check` pass; no scope creep. | — |
| S04 | `qv-gate` (`lint`) | `make lint` | — |
| S05 | `qv-gate` (`assertions`) | `make test-assertions` | — |
| S06 | `qv-gate` (`format`) | `make format-check` | — |
| S07 | `qv-gate` (`typecheck`) | `make type-check` | — |
| S08 | `qv-gate` (`unit-tests`) | `make test-unit` | — |
| S09 | `qv-gate` (`integration-tests`) | `make allure-integration` | — |
| S10 | `qv-gate` (`diff-coverage`) | `make diff-coverage` | — |
| S11 | `qv-gate` (`security-secrets`) | `make security-secrets` — **the new gate this CR introduces; runs as the inaugural exercise on this CR's own changes** | — |
| S12 | `self-assess-impl` | SelfAssess via `iw-item-analyze` (project has `self_assess = true`) | — |

S11 chicken-and-egg: the gate is added by this CR's S01. The daemon's QV-gate registry is read from `skills/iw-workflow/SKILL.md` at item-launch time *and* the worktree's `skills/iw-workflow/SKILL.md` is the version in the running worktree, so the new gate is executable within CR-00050 itself once S01 lands the skill change. Same pattern CR-00046 used when it introduced the `assertions` gate.

Agent slugs verified against `skills/iw-workflow/SKILL.md` and `executor/step_executor_lib.sh`.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: No migrations.

### API Changes

- **New endpoints**: None
- **Modified endpoints**: None
- **Removed endpoints**: None

### Frontend Changes

- **New components**: None
- **Modified components**: None
- **Removed components**: None
- `browser_verification` = **false** (no UI surface).

## File Manifest

All files for this work item live under `ai-dev/active/CR-00050/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00050_CR_Design.md` | Design | This document |
| `CR-00050_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for the daemon |
| `prompts/CR-00050_S01_Backend_prompt.md` | Prompt | S01 implementation instructions |
| `prompts/CR-00050_S02_CodeReview_prompt.md` | Prompt | S02 code-review instructions |
| `prompts/CR-00050_S03_CodeReview_Final_prompt.md` | Prompt | S03 cross-agent review instructions |
| `prompts/CR-00050_S12_SelfAssess_prompt.md` | Prompt | S12 self-assess instructions |

(S04–S11 are QV gates — command-only, no prompt files.)

Reports are created during execution in `ai-dev/active/CR-00050/reports/`.

## Acceptance Criteria

### AC1: gitleaks pre-commit hook is wired and clean

```
Given a clean checkout at this CR's merge SHA
When `pre-commit run gitleaks --all-files` is executed
Then the hook reports zero findings and exits 0
And the hook configuration in .pre-commit-config.yaml uses the gitleaks/gitleaks repo at a pinned recent stable tag
```

### AC2: gitleaks GH job runs on all relevant triggers and uploads SARIF

```
Given a PR or push to main against the merged tree
When the security-scan.yml workflow runs
Then a `secrets-scan` (or `gitleaks`) job appears in the run
And it executes `gitleaks detect --no-git --config .gitleaks.toml --report-format sarif --report-path gitleaks.sarif` (or equivalent)
And it uploads the SARIF to Code Scanning, with the same private-repo-skip comment block as the existing trivy-iac upload step
And the job runs on push, pull_request, and the existing schedule cron at .github/workflows/security-scan.yml:14
```

### AC3: gitleaks daemon QV gate is the 8th canonical gate

```
Given `skills/iw-workflow/SKILL.md` after this CR
When the canonical QV gate list is inspected
Then the order is: lint → assertions → format → typecheck → unit-tests → integration-tests → diff-coverage → security-secrets
And `.claude/skills/iw-workflow/SKILL.md` is byte-equal to `skills/iw-workflow/SKILL.md` (verifies iw sync-skills ran)
And new design templates (from `ai-dev/templates/`) pick up the new gate without further edits
```

### AC4: gitleaks make target works locally and is folded into security-all

```
Given the patched Makefile
When `make security-secrets` is run from the repo root
Then it executes `uv run gitleaks detect --no-git --config .gitleaks.toml [+ JSON report to $(SECURITY_DIR)/gitleaks.json]`
And it exits 0 against the current patched tree
And `make security-all` includes security-secrets as a prerequisite or recipe
And `security-secrets` is listed in `.PHONY`
```

### AC5: Semgrep make target actually runs Semgrep

```
Given the patched Makefile
When `make security-sast` is run from the repo root
Then it executes `uv run semgrep --config p/python --config p/owasp-top-ten --config p/security-audit orch dashboard executor [+ JSON report to $(SECURITY_DIR)/semgrep.json]`
And the recipe is no longer `@echo "[security-sast] complete"`
And bandit's place in `security-deps` is unchanged (bandit remains the deep Python-specific complement)
```

### AC6: Semgrep GH job runs with burn-in policy and follow-up filed

```
Given the patched .github/workflows/security-scan.yml
When the workflow runs on push or pull_request
Then a `semgrep` (or `sast`) job appears with `continue-on-error: true`
And it uploads SARIF mirroring trivy-iac/gitleaks's private-repo-skip pattern
And `ai-dev/work/TESTS_ENHANCEMENT.md` §5 contains a new row `P1-CR-D-followup-semgrep-block` describing the flip-to-blocking work
```

### AC7: All 109 pre-existing findings are addressed honestly

```
Given the captured RED scan from S01's deliverable 0 (`gitleaks detect --no-git --config .gitleaks.toml -v` against pre-patch main)
When the same scan is re-run against the patched tree
Then it exits 0 (zero findings)
And every `.gitleaks.toml` allowlist addition between the RED and GREEN runs carries a one-line `# why` comment naming what the false positive is (path/pattern/rationale)
And no finding that S01 classified as "looks like a real secret" has been silently allowlisted — those are surfaced in S01's blockers list for operator escalation; the CR does not merge while any such finding is pending
```

### AC8: Docs and plan flipped consistently

```
Given S01's edits
When the reviewer reads docs/IW_AI_Core_Testing_Strategy.md §5 (gate table) and §9 (gaps table)
Then §5 has new "Secret scan (gitleaks)" and "Semgrep SAST" rows
And §9's "Secrets scanning (`gitleaks`)" row reads "✅ (CR-00050, YYYY-MM-DD)"
And §9's "Semgrep SAST" row reads "⚠️ (CR-00050, YYYY-MM-DD) — managed rulesets; continue-on-error during burn-in; follow-up P1-CR-D-followup-semgrep-block flips blocking"
And skills/iw-ai-core-testing/SKILL.md §8 mentions both new gates
And TESTS_ENHANCEMENT.md §5 P1-CR-D row is SHIPPED, items 1.6 and 1.9 are DONE, P1-CR-D-followup-semgrep-block is filed, and §11 has a new changelog entry
```

### AC9: All canonical QV gates pass

```
Given the patched worktree at S01 completion
When the daemon runs steps S04–S11
Then S04 (lint), S05 (assertions), S06 (format-check), S07 (typecheck), S08 (test-unit), S09 (integration-tests stub), S10 (diff-coverage), S11 (security-secrets) all exit 0
And no fix cycle is required on S11 (the gate that this CR introduces) — if S11 needs a fix cycle, that's a sign deliverable 0's triage missed something
```

## Rollback Plan

- **Database**: Not applicable (no DB changes).
- **Code**: Revert the squash-merge commit. `.gitleaks.toml` returns to the `iw-oss-publish`-generated baseline (109 findings); `.pre-commit-config.yaml` and `security-scan.yml` lose their gitleaks/semgrep additions; `Makefile`'s `security-sast` returns to its `@echo` alias; the canonical QV gate list shrinks back to 7. The 109 pre-existing findings are still in `main`'s history, but no longer blocking anyone because no gate references them. No data loss possible.
- **Data**: No data loss possible (tooling/config-only CR).

A partial rollback path also exists: keep gitleaks landed, revert Semgrep only. The gitleaks block is the truly load-bearing one; Semgrep is informational during burn-in and can be backed out without affecting committers.

## Dependencies

- **Depends on**: None hard. Reads the existing `.gitleaks.toml` (from `iw-oss-publish` history) and the existing `skills/iw-workflow/SKILL.md` 7-gate canon (extended by CR-00046 and CR-00047). Compatible with CR-00049 (in flight); their `allowed_paths` do not overlap (CR-00049 touches `tests/**` + `pyproject.toml` addopts; this touches `.gitleaks.toml`, `.pre-commit-config.yaml`, `.github/workflows/`, `Makefile`, skills, docs).
- **Blocks**: P1-CR-E (Allure + smoke + integration-tests no-op-gate fix) is the next *(start here)* once this lands. Eventually `P1-CR-D-followup-semgrep-block` flips Semgrep to hard-block after burn-in.

## Impacted Paths

- `.gitleaks.toml`
- `.pre-commit-config.yaml`
- `.github/workflows/security-scan.yml`
- `Makefile`
- `pyproject.toml`
- `skills/iw-workflow/**`
- `.claude/skills/iw-workflow/**`
- `skills/iw-ai-core-testing/**`
- `.claude/skills/iw-ai-core-testing/**`
- `docs/IW_AI_Core_Testing_Strategy.md`
- `ai-dev/work/TESTS_ENHANCEMENT.md`

## TDD Approach

- **RED-first** evidence is the failing pre-patch gitleaks scan itself: `gitleaks detect --no-git --config .gitleaks.toml -v` against the worktree at S01's start, producing **109 findings** with the per-RuleID breakdown captured as text/JSON. S01 records this verbatim into `tdd_red_evidence` per CR-00045's contract.
- **Unit tests**: None new. The gitleaks tool itself is the assertion engine; the allowlist additions are the "fix"; the post-patch zero-finding run is the "GREEN".
- **Integration tests**: None new. The existing 7 QV gates remain unchanged; only the new `security-secrets` gate is added.
- **Updated tests**: None — no existing tests test the security-scanning behaviour (those tests would belong to a future "security test module" item per the plan §3.5, out of scope here).
- **GREEN evidence** for the gitleaks half: the post-patch scan exits 0 (captured in S01's report and re-verified by S03 independently).
- **GREEN evidence** for the Semgrep half: `make security-sast` runs and reports findings (zero or non-zero depending on what Semgrep flags). If non-zero on managed rulesets against the existing code, S01 must triage each (rule false positive ⇒ Semgrep-side `# nosemgrep:` inline comment + a comment naming the finding; real issue ⇒ filed as a separate incident, this CR is informational-only on Semgrep per the burn-in policy).

## Notes

- **Triage is the bulk of S01's work.** The CI wiring (pre-commit hook, GH job, daemon QV gate, make target) is straightforward boilerplate. The judgement is in the 109-finding triage: deciding for each unique RuleID+path-pattern whether it's a false positive (widen the path allowlist or add a per-rule stopwords/regex entry), a noise pattern (widen the rule's regex with a `\b(?:example\.local|invalid\.local)\b` exclusion), or a real secret (escalate to operator, do not allowlist). S01's prompt walks through the triage rubric and gives an explicit pattern budget.

- **Why the daemon QV gate for gitleaks AND not for Semgrep.** Plan §9 lists gitleaks as "Blocking on every PR" — it's a *secret detector*, false-positive rate is manageable, the cost of letting a real leak through is unbounded. Semgrep is listed as "Periodic (nightly/weekly, informational → alert on regression)" — managed rulesets are noisier, especially for an LLM-written codebase, so a burn-in is warranted before hard-blocking. The follow-up CR (`P1-CR-D-followup-semgrep-block`) flips the bit once we have a sense of the noise floor.

- **The Semgrep GH job in this CR is the burn-in.** Setting `continue-on-error: true` while still uploading SARIF means findings are visible in Code Scanning but never block a merge. The plan's "nightly first, gate after" language is implemented by running on `push + pull_request + schedule` from day one (so we get fast feedback on whether the rules are sane) but never blocking until the follow-up CR explicitly flips the bit.

- **S11 chicken-and-egg.** The new `security-secrets` daemon QV gate is added to `skills/iw-workflow/SKILL.md` by this CR's S01, then runs as this CR's own S11. The daemon reads the worktree's local `skills/iw-workflow/SKILL.md` for its gate definitions at gate-launch time, so the new gate IS executable inside CR-00050 itself. This is the same pattern CR-00046 used when it introduced the `assertions` gate (which then ran as CR-00046's own S05). If S11 fails for any reason, the gate definition is provably broken — and a fix cycle on S11 would correctly catch that.

- **Sibling repos** (`iw-doc-plan`/`podforger`/`cv`) pick up the new `security-secrets` daemon QV gate at their next `iw sync-skills` — explicitly out of scope here.

- **Bandit's place is unchanged.** It stays in `security-deps` because (a) it's a deep Python-specific SAST tool that complements Semgrep's broader rule packs, (b) it's already wired with a `[tool.bandit]` config in `pyproject.toml`, and (c) moving it would scope-creep this CR. A future CR can decide whether to consolidate.
