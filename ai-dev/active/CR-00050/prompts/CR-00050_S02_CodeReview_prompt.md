# CR-00050_S02_CodeReview_prompt

**Work Item**: CR-00050 -- Security gates — gitleaks (blocking) + Semgrep (nightly-first) (P1-CR-D)
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

Standard policy. No Docker commands allowed except read-only introspection or via `./ai-core.sh` / `make`.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This CR adds **no** migrations. Flag any migration in `files_changed` as CRITICAL scope creep.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00050 --json`. The `workflow-manifest.json` is a design-time snapshot.
- `ai-dev/active/CR-00050/CR-00050_CR_Design.md` -- Design (source of truth)
- `ai-dev/active/CR-00050/reports/CR-00050_S01_Backend_report.md` -- Impl step report
- All files in `files_changed`
- The pre-patch evidence in `ai-dev/active/CR-00050/evidences/pre/` — particularly `cr-00050-gitleaks-pre.json` and `cr-00050-gitleaks-summary.md`. These are the RED baseline you re-verify against.

## Output Files

- `ai-dev/active/CR-00050/reports/CR-00050_S02_CodeReview_report.md`

## Context

You are reviewing S01's implementation of **CR-00050 — Security gates (P1-CR-D)**. S01's job: triage 109 pre-existing gitleaks findings (FALSE_POSITIVE_PATH → allowlist paths; FALSE_POSITIVE_VALUE → per-rule stopwords/regexes; REAL_OR_SUSPICIOUS → escalate, NEVER silently allowlist); wire gitleaks on three surfaces (pre-commit + GH job + daemon QV gate `security-secrets` + `make security-secrets`); rewrite `make security-sast` as a real Semgrep invocation; add a `semgrep` GH job with `continue-on-error: true`; flip docs/plan/skill; file the follow-up; run `iw sync-skills`.

Read the design first. ACs are AC1–AC9. The most important checks for you:

1. **Did S01 silently allowlist a real-looking secret?** This is the worst possible outcome and the one this CR is structurally built to prevent. Every new `.gitleaks.toml` entry must carry a `# why` comment that names the file/value/pattern AND why it is provably safe (test fixture, RFC-reserved example, doc literal).
2. **Did S01 mismark a real secret as FALSE_POSITIVE_VALUE?** This is subtler. Inspect each new `[[rules.allowlists]]` block individually: is the regex/stopwords entry scoped tightly enough that a *real* future secret won't slip past it?

## Read the Design Document FIRST

- AC1–AC9 are mandatory checks, not suggestions.
- "Impacted Paths" defines scope. Any file in S01's `files_changed` outside that list is a **CRITICAL** scope violation. Particularly check that no production code (`orch/`, `dashboard/`, `executor/`, `bin/`, `scripts/`) was touched — this CR's design says explicitly "no production code change."

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading any code:

```bash
make lint
make format-check
```

Any NEW violation in `files_changed` is a CRITICAL finding with `"category": "conventions"`.

## Review Checklist

### 1. The 109-finding triage is honest

For every new entry in `.gitleaks.toml` (compare against `git show HEAD:.gitleaks.toml`):

- **Has a `# why` comment immediately above it** naming the file/value/pattern and the safety rationale. Missing comment = HIGH finding.
- **The justification is plausibly correct.** Spot-check at least 5 random new entries: open the file/line they cover, look at the actual secret-shaped value, judge whether the rationale holds. A "test fixture" rationale on a value that's a 32-char-random-with-letters-and-digits and lives outside an obvious test file is suspect → flag as HIGH.
- **The scope is tight.** A `[[rules.allowlists]] regexes = ['''.+''']` (matches anything) is a CRITICAL finding — that would suppress all instances of the rule, defeating the gate. Per-rule stopwords/regexes should match only specific values, not whole categories.
- **Path allowlists don't widen to production code.** Any new `[allowlist].paths` regex matching `orch/`, `dashboard/`, `executor/`, `bin/`, or `scripts/` is a CRITICAL finding — production code must remain in scope.

Then run the gitleaks scan independently to confirm the GREEN state:

```bash
uv run gitleaks detect --no-git --config .gitleaks.toml -v
```

Must exit 0 with `WRN leaks found: 0`. If it does not, that is a CRITICAL finding — S01 either missed findings or the post-patch scan wasn't actually clean.

### 2. The blockers list is accurate

If S01's report has any `blockers` entries flagged as REAL_OR_SUSPICIOUS:

- These represent findings S01 *refused* to allowlist because they looked real.
- Verify each one is actually surfaced (not silently swept into a `.gitleaks.toml` entry too).
- If S01 reports zero blockers AND the post-patch scan is 0, that's fine — every finding was triaged as FP_PATH or FP_VALUE.
- If S01 reports >0 blockers but the post-patch scan IS 0, that means S01 contradicted itself (allowlisted *and* flagged the same finding). Surface as CRITICAL.

### 3. Pre-commit hook is wired correctly

`.pre-commit-config.yaml`:

- New gitleaks hook present, using upstream `gitleaks/gitleaks` repo at a **pinned tag** (not `main`/`HEAD`). Pinning to floating refs is a HIGH finding (supply-chain risk + reproducibility).
- Hook id matches what the upstream pre-commit config declares (typically `gitleaks`).
- Run it locally: `pre-commit run gitleaks --all-files` — exits 0. (AC1.) If it fails, that's a CRITICAL finding.

### 4. GH `secrets-scan` job is wired correctly

`.github/workflows/security-scan.yml`:

- New `secrets-scan` (or `gitleaks`) job present.
- Pinned action SHAs (`actions/checkout`, `astral-sh/setup-uv` if used, `gitleaks/gitleaks-action` or equivalent). Unpinned action references are CRITICAL.
- Mirrors `iac-scan`'s private-repo-skip comment block for SARIF upload (the trivy-iac upload comment about GHAS). If the comment block is missing, that's HIGH — future maintainers won't know why the upload step is conditional.
- Runs on `push`, `pull_request`, AND the existing `schedule` cron.

### 5. Daemon QV gate is canonical and synced

`skills/iw-workflow/SKILL.md`:

- Canonical gate list now lists `security-secrets` as the 8th gate, after `diff-coverage`.
- Ordering: `lint → assertions → format → typecheck → unit-tests → integration-tests → diff-coverage → security-secrets`. Any other ordering is HIGH (deviates from the CR-00046/47 precedent for "added gates go at the end").
- `.claude/skills/iw-workflow/SKILL.md` byte-equal to master: `diff -q skills/iw-workflow/SKILL.md .claude/skills/iw-workflow/SKILL.md` must report "match" (or no output). If not, S01 forgot to run `iw sync-skills` — CRITICAL.

### 6. `make security-secrets` works locally

Run:

```bash
make security-secrets
```

Must exit 0 against the patched tree. (AC4.) If it fails:

- If gitleaks isn't installed in your worktree, that's a blocker for you — note it and let S01 know. (gitleaks 8.30+ should be available; check `command -v gitleaks`.)
- If gitleaks IS installed but the command exits non-zero, that's a CRITICAL finding — the gate is broken on the very CR that introduces it.

Also check the Makefile diff:

- Recipe uses `gitleaks detect --no-git --config .gitleaks.toml` (or close equivalent — must read the project config file).
- Has the `command -v gitleaks` install-check pattern matching the existing `security-deps` and `security-iac` targets.
- Folded into `security-all` as a prerequisite.
- Listed in `.PHONY`.

### 7. `make security-sast` actually runs Semgrep

Look at the Makefile diff:

- The new `security-sast:` recipe is NOT `@echo "[security-sast] complete"`. If it is, S01 lied — CRITICAL.
- The recipe calls `semgrep` with `--config p/python --config p/owasp-top-ten --config p/security-audit` (managed rulesets per the design).
- The recipe has the same `command -v` install-check pattern.

Run it:

```bash
make security-sast
```

Exit code reflects findings. Any Semgrep finding S01 didn't address must EITHER carry an inline `# nosemgrep: <rule-id>` with a `# why` comment OR be in the `blockers` list. If a finding is silently passing without a `# nosemgrep:` comment, that means S01 either fixed the code (good) or the gate is broken (CRITICAL).

### 8. GH `semgrep` job is wired correctly with burn-in policy

`.github/workflows/security-scan.yml`:

- New `semgrep` job present.
- `continue-on-error: true` set at JOB level (not just step level — job-level is what the design specified).
- Pinned action SHAs.
- Uploads SARIF mirroring `secrets-scan` / `iac-scan` pattern.
- A `P1-CR-D-followup-semgrep-block` row IS filed in `ai-dev/work/TESTS_ENHANCEMENT.md` §5. If missing, CRITICAL (the design's AC6 is unmet).

### 9. Docs / plan / skill flips

- `docs/IW_AI_Core_Testing_Strategy.md` §5 has new "Secret scan (gitleaks)" and "Semgrep SAST" rows.
- §9 row "Secrets scanning (`gitleaks`)" → ✅ (CR-00050, YYYY-MM-DD).
- §9 row "Semgrep SAST" → ⚠️ (CR-00050, YYYY-MM-DD) — managed rulesets, continue-on-error, follow-up named.
- `skills/iw-ai-core-testing/SKILL.md` §8 mentions both new gates.
- `.claude/skills/iw-ai-core-testing/SKILL.md` byte-equal to master.
- `TESTS_ENHANCEMENT.md` §5 P1-CR-D row → SHIPPED (CR-00050, YYYY-MM-DD); items 1.6 + 1.9 → DONE; `P1-CR-D-followup-semgrep-block` row filed; §11 has a new changelog entry with the triage counts.

### 10. Scope discipline (no production code touched)

`grep` `files_changed` for any path under `orch/`, `dashboard/`, `executor/`, `bin/`, `scripts/`. Any hit = CRITICAL scope violation.

Other out-of-scope things to flag:

- Did S01 add Trivy image scan? (Out of scope.)
- Did S01 add Semgrep custom rules (anything beyond the three managed `--config p/*` packs)? (Out of scope.)
- Did S01 port to sibling projects? (Out of scope.)
- Did S01 flip Semgrep to blocking in CI? (Out of scope — that's the follow-up.)
- Did S01 move bandit out of `security-deps`? (Out of scope.)

### 11. RED evidence

S01's report `tdd_red_evidence` must record the 109-finding (or whatever current count is) pre-patch scan. If `"n/a"` — HIGH finding (this CR has a concrete RED anchor).

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. `pre-commit run gitleaks --all-files` — must exit 0.
2. `make security-secrets` — must exit 0.
3. `gitleaks detect --no-git --config .gitleaks.toml -v` — must report 0 findings.
4. `make lint && make format-check` — must exit 0.

Report results accurately. Do NOT run `make check` / `make test-integration` / `make diff-coverage` — that's S08/S09/S10.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Suppressed-real-leak, scope violation, AC failure, broken gate | Must fix before merge |
| **HIGH** | Pinned-tag missing, weak `# why` rationale, missing tracking comment, missing follow-up row | Must fix before merge |
| **MEDIUM (fixable)** | Code quality, convention violation | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Better pattern available | Optional |
| **LOW** | Style nit | Informational |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "CR-00050",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "pre-commit gitleaks: 0 findings. make security-secrets: 0 findings. independent gitleaks scan: 0 findings. lint+format-check: clean.",
  "notes": ""
}
```

- `verdict`: `pass` if zero CRITICAL + zero HIGH + zero MEDIUM (fixable). `fail` otherwise.
- `mandatory_fix_count`: CRITICAL + HIGH + MEDIUM (fixable).
