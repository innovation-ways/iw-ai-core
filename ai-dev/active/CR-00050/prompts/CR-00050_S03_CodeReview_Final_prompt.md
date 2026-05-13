# CR-00050_S03_CodeReview_Final_prompt

**Work Item**: CR-00050 -- Security gates — gitleaks (blocking) + Semgrep (nightly-first) (P1-CR-D)
**Review Step**: S03

---

## ⛔ Docker is off-limits

Standard policy. No Docker commands allowed except read-only introspection or via `./ai-core.sh` / `make`.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This CR adds **no** migrations. Flag any migration in `files_changed` as a CRITICAL scope violation.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00050 --json`.
- `ai-dev/active/CR-00050/CR-00050_CR_Design.md` -- Design (source of truth)
- `ai-dev/active/CR-00050/reports/CR-00050_S0[12]_*_report.md` -- S01 + S02 reports
- All files in S01's `files_changed`
- `ai-dev/active/CR-00050/evidences/pre/cr-00050-gitleaks-pre.json` -- the 109-finding RED baseline

## Output Files

- `ai-dev/active/CR-00050/reports/CR-00050_S03_CodeReview_Final_report.md`

## Context

You are performing the **final cross-agent review** of ALL implementation work for **CR-00050 — Security gates (P1-CR-D)**. The CR has one implementation step (S01) followed by S02's per-agent review; your job is the cross-cutting view S02 could not have. Specifically:

1. Verify the change is **complete** — gitleaks wired on all three surfaces (pre-commit, GH job, daemon QV gate); Semgrep wired with burn-in; the 109-finding triage is resolved; the docs/plan/skill flips are internally consistent.
2. Verify **the secret scanner actually scans secrets** — re-run the gitleaks scan independently. **0 findings**. This is the single most important check; if it passes, the gate works; if it fails, the entire CR is moot.
3. Verify the **`# why` comments tell a coherent story.** Read every new `.gitleaks.toml` allowlist entry's rationale. Does the project's allowlist now read like a knowable list of "things that are openly safe" — or like a black hole of unexplained suppressions?
4. Verify **no chicken-and-egg failures.** S11 is the new `security-secrets` daemon QV gate running on this CR's own changes. It must pass without a fix cycle. If a fix cycle runs on S11, that's a sign deliverable 0's triage missed something.

## Read the Design Document FIRST

- AC1–AC9 are mandatory checks.
- "Impacted Paths" defines scope. Any file in S01's `files_changed` outside the list = CRITICAL scope violation (especially production code under `orch/`, `dashboard/`, `executor/`).
- The "Notes" section explains why bandit stays in `security-deps`, why S11 is chicken-and-egg, and why Semgrep is burn-in. Verify S01 honoured each.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Any NEW violation = CRITICAL.

## Review Checklist

### 1. Completeness vs Design Document

- **AC1**: `pre-commit run gitleaks --all-files` exits 0. Run it.
- **AC2**: `secrets-scan` job in `security-scan.yml` present, pinned actions, SARIF upload with private-repo-skip comment, runs on push + pull_request + schedule.
- **AC3**: `skills/iw-workflow/SKILL.md` lists 8 canonical gates with `security-secrets` last. `.claude/skills/iw-workflow/SKILL.md` byte-equal to master.
- **AC4**: `make security-secrets` exits 0. Folded into `security-all`. In `.PHONY`.
- **AC5**: `make security-sast` actually runs Semgrep (not `@echo`). Bandit unmoved in `security-deps`.
- **AC6**: `semgrep` GH job with `continue-on-error: true` at JOB level. `P1-CR-D-followup-semgrep-block` row filed in plan §5.
- **AC7**: Re-run the gitleaks scan independently — must be 0 findings. Compare against the 109-finding RED baseline in `evidences/pre/cr-00050-gitleaks-pre.json`. The triage counts (FP_PATH + FP_VALUE + REAL = 109) in S01's report must add up.
- **AC8**: Strategy doc §5 has new rows; §9 rows flipped; testing skill §8 mentions both gates; `TESTS_ENHANCEMENT.md` §5 P1-CR-D SHIPPED + items 1.6/1.9 DONE + follow-up row filed + §11 changelog entry.
- **AC9**: This step's own independent gate runs (1–8 below) all pass — proxy for S04–S11.

### 2. Cross-Agent Consistency

Single-impl-step CR, so consistency is cross-file:

- The "Secret scan (gitleaks)" prose in strategy doc §5 + §9 + testing skill §8 + plan §5 + plan §11 all describe the same wiring (pre-commit + GH job + daemon gate + make target). If one source says "blocking on every PR" and another says "informational," that's a HIGH consistency finding.
- The 109-finding triage counts in S01's notes must equal the count in §11's changelog entry. If they don't match (e.g., notes say 109 → 80 FP_PATH + 25 FP_VALUE + 4 REAL but changelog says 109 → 75 + 30 + 4), that's a HIGH finding — the changelog must match the reality.
- The pinned gitleaks/Semgrep action SHAs in `security-scan.yml` use the same `# vX.Y.Z` comment style as the existing `actions/checkout` and `astral-sh/setup-uv` lines.

### 3. The independent re-scan is clean

This is the linchpin. Run:

```bash
uv run gitleaks detect --no-git --config .gitleaks.toml -v
```

Expected: `WRN leaks found: 0`. If non-zero:

- If the missing finding is a NEW one not in the RED baseline → S01 introduced a file with a secret (CRITICAL — investigate).
- If it's a finding from the RED baseline → S01's triage missed it (CRITICAL — must fix before merge).

Also run:

```bash
uv run semgrep --config p/python --config p/owasp-top-ten --config p/security-audit orch dashboard executor --error 2>&1 | tail -30
```

This is `make security-sast`. Findings here are accepted IFF the GH `semgrep` job is `continue-on-error: true` (which AC6 mandates) — but for the **local** invocation, S01 should have triaged each finding (either fixed it, or added an inline `# nosemgrep: <rule-id>` with `# why` comment). If the local Semgrep run reports findings AND none of the matched lines have `# nosemgrep:` comments, that's a HIGH finding — the burn-in covers CI noise but isn't license to ignore local findings.

### 4. The allowlist tells a coherent story

Read every new `.gitleaks.toml` block. For each:

- **Is the `# why` comment substantive?** "test fixture" alone is HIGH — needs to name the file/value/usage. "Example domain in test_browser_env.py — example.local is RFC 6761 reserved" is good.
- **Is the regex/path tight?** A `regexes = ['''.*''']` would suppress everything for that rule — that's CRITICAL. A `regexes = ['''dev@example\.local''']` is appropriately tight.
- **Is the rationale plausibly correct?** Spot-check 5 random new entries: open the file/line they cover, look at the actual secret-shaped value, judge whether the rationale holds.

If the allowlist reads like a black hole — many entries, all vague, hard to audit — that's a structural CRITICAL finding even if every individual entry technically has a comment.

### 5. Scope discipline

- No files under `orch/`, `dashboard/`, `executor/`, `bin/`, `scripts/` in `files_changed`.
- bandit's `security-deps` placement unchanged.
- No Trivy image scan added.
- No Semgrep custom rules (only `--config p/python --config p/owasp-top-ten --config p/security-audit`).
- No sync to sibling projects.
- Semgrep GH job is `continue-on-error: true` (NOT flipped to blocking — that's the follow-up).

### 6. Architecture / Security cross-cut

Tests-and-CI-only CR. No architecture surface. Security checks ARE the deliverable; the meta-check is "does it work" which §3 covers.

## Test Verification (NON-NEGOTIABLE — definitive proof)

Run all of these. Any non-zero exit on 1–6 is a CRITICAL finding.

```bash
# 1. Independent gitleaks scan (the linchpin)
uv run gitleaks detect --no-git --config .gitleaks.toml -v

# 2. The make target
make security-secrets

# 3. The pre-commit hook
pre-commit run gitleaks --all-files

# 4. Lint + format
make lint
make format-check

# 5. Semgrep local run (findings OK if commented)
make security-sast

# 6. Sync verification
diff -q skills/iw-workflow/SKILL.md .claude/skills/iw-workflow/SKILL.md
diff -q skills/iw-ai-core-testing/SKILL.md .claude/skills/iw-ai-core-testing/SKILL.md
```

Do **NOT** run `make check` / `make test-integration` / `make diff-coverage` — that's S08/S09/S10/S11's job.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | AC failure, suppressed real leak, broken gate, scope violation, weak regex (suppresses too much), independent re-scan finds leaks | Must fix |
| **HIGH** | Weak `# why` rationale, missing pinned tag, count mismatch between notes and changelog, missing follow-up row, missing tracking note | Must fix |
| **MEDIUM (fixable)** | Convention violation, minor inconsistency | Should fix |
| **MEDIUM (suggestion)** | Better pattern available | Optional |
| **LOW** | Style nit | Informational |

## Review Result Contract

```json
{
  "step": "S03",
  "agent": "CodeReview_Final",
  "work_item": "CR-00050",
  "steps_reviewed": ["S01", "S02"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "completeness|consistency|integration|testing|architecture|security",
      "file": "path/to/file",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it",
      "cross_cutting": true
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "Independent gitleaks scan: 0 findings. make security-secrets: ok. pre-commit gitleaks: ok. make lint + format-check: clean. make security-sast: <findings or 0>. Skills synced (master == .claude/ copy).",
  "missing_requirements": [],
  "notes": ""
}
```

- `verdict`: `pass` if zero CRITICAL + zero HIGH + zero MEDIUM (fixable). `fail` otherwise.
- `missing_requirements`: any AC1–AC9 not met. Each is automatically CRITICAL.
- `cross_cutting`: set `true` on findings spanning multiple doc locations or affecting the consistency of the allowlist-rationale narrative.
