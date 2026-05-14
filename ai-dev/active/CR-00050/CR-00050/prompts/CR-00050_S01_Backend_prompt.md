# CR-00050_S01_Backend_prompt

**Work Item**: CR-00050 -- Security gates — gitleaks (blocking) + Semgrep (nightly-first) (P1-CR-D)
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope.

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets.

If your task seems to require a prohibited command, STOP and raise a
blocker.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This CR adds **no** migrations. If your work seems to need one, you have
gone outside scope — stop and raise a blocker.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — for the current step list, status, prompt paths, gate commands, etc., prefer `uv run iw item-status CR-00050 --json`. The `workflow-manifest.json` file is a design-time snapshot and may be out of date (CR-00023).
- `ai-dev/active/CR-00050/CR-00050_CR_Design.md` -- **Source of truth** for scope, ACs (AC1–AC9), and the failure analysis. Read first.
- `ai-dev/active/CR-00050/CR-00050_Functional.md` -- Human-facing summary.
- `.gitleaks.toml` (already exists at repo root — placed by `iw-oss-publish`'s `scripts/lib/fixes.py:171`). Read it first; you will extend it.
- `skills/iw-oss-publish/scripts/checks/secrets.py` lines 38–55 and 176–191 — the convention you align with for `gitleaks detect --no-git --config .gitleaks.toml`.
- `.github/workflows/security-scan.yml` — current 2 jobs (`deps-audit` line 22, `iac-scan` line 53); read both for the SARIF-upload-with-private-repo-skip pattern you mirror.
- `.pre-commit-config.yaml` — current 12 hooks; add the gitleaks hook in the right place (after `detect-private-key` reads naturally).
- `Makefile` lines 179–220 — current security-* targets including the `security-sast: security-deps` + `@echo "[security-sast] complete"` no-op alias you replace.
- `pyproject.toml` line 182 `[tool.bandit]` — bandit's place is unchanged; don't refactor.
- `skills/iw-workflow/SKILL.md` — canonical 7-gate QV list (extended by CR-00046 + CR-00047). You add an 8th gate.
- `.claude/skills/iw-workflow/SKILL.md` — synced copy; will be updated via `iw sync-skills`.
- `skills/iw-ai-core-testing/SKILL.md` §8 — gate documentation.
- `docs/IW_AI_Core_Testing_Strategy.md` §5 (gate table) + §9 (gaps table) — both grow rows.
- `ai-dev/work/TESTS_ENHANCEMENT.md` §5 (P1-CR-D row + items 1.6/1.9 + new follow-up row) + §11 (new changelog entry).
- `CLAUDE.md` for project-wide rules.

## Output Files

- `ai-dev/active/CR-00050/reports/CR-00050_S01_Backend_report.md` -- Step report

## Context

You are implementing **CR-00050 — Security gates (P1-CR-D)**, bundling items 1.6 (gitleaks) and 1.9 (Semgrep) from the Phase-1 plan. **Read `ai-dev/active/CR-00050/CR-00050_CR_Design.md` first.** Its "Current Behavior" (the 109-finding baseline), "Desired Behavior" (three-surface gitleaks wiring + Semgrep burn-in), "Acceptance Criteria" (AC1–AC9), and "Notes" (especially the chicken-and-egg explanation for S11 running this CR's own new gate) are the source of truth.

The only implementation step in this CR. The bulk of the work is **triaging 109 pre-existing findings**, not the CI wiring (which is straightforward boilerplate).

## Requirements

Do these in order. Deliverable 0 is your RED reproduction; deliverables 1–8 are the implementation.

### 0. RED — capture the 109-finding baseline

Run gitleaks against the current pre-patch tree:

```bash
uv run gitleaks detect --no-git --config .gitleaks.toml --report-format json --report-path /tmp/cr-00050-red.json -v 2>&1 | tail -60
```

Also capture a summary by RuleID and by path-pattern. Examples that exist on main as of 2026-05-13 (verify, don't assume):

- `tests/unit/test_browser_env.py:70` — `dev@example.local` (RuleID `iw-internal-fqdn`)
- `tests/unit/test_oss_secrets_parser.py:94` — `sk-abcd1234ZZZZ9999XY` (RuleID `generic-api-key`)

Total finding count is the headline `WRN leaks found: <N>` line. Record:

- Total count
- Top 10 RuleIDs by frequency (`jq -r '.[] | .RuleID' /tmp/cr-00050-red.json | sort | uniq -c | sort -rn | head -10`)
- Top 15 file paths by frequency (`jq -r '.[] | .File' /tmp/cr-00050-red.json | sort | uniq -c | sort -rn | head -15`)
- For each unique (RuleID, file-glob) group, one representative finding with its `Match` and `Secret` fields

This RED-first capture is your `tdd_red_evidence`. Save the full JSON to `ai-dev/active/CR-00050/evidences/pre/cr-00050-gitleaks-pre.json` and the summary to `evidences/pre/cr-00050-gitleaks-summary.md`.

### 1. Triage the findings

Per the operator's chosen strategy (**Mixed: fix real leaks; allowlist false positives**):

For each unique (RuleID, file-glob) group from deliverable 0:

**Step 1: classify.** Open the file(s), inspect the matched line(s), and assign one of three labels:

- **FALSE_POSITIVE_PATH** — the entire file/directory is test data, doc example, or fixture (e.g., `tests/unit/test_oss_secrets_parser.py` exists *to* test parsing secret-shaped strings). Action: extend the `[allowlist].paths` list in `.gitleaks.toml` with a new regex matching the file or its directory. Each new path regex gets a `# why` comment naming the directory and reason. Prefer broad paths (e.g., `(?:^|/)tests/unit/`) over per-file regexes — but only if the entire directory is genuinely test code. Do NOT widen to `tests/**` blindly; some integration tests may legitimately handle real secrets in their setup.

- **FALSE_POSITIVE_VALUE** — the value itself is well-known example data (e.g., `192.168.1.1`, `example.local`, `dev@example.com`, the literal string `sk-abcd1234ZZZZ9999XY`). Action: add a per-rule `[[rules.allowlists]]` block in `.gitleaks.toml` matching only that value (via `stopwords` or `regexes`), with a `# why` comment naming the value and where it appears. This is preferred when the value is example-shaped but appears across multiple file types.

- **REAL_OR_SUSPICIOUS** — high entropy, looks like an actual credential, doesn't match a documented example pattern. Action: **do NOT allowlist.** Add to your `blockers` list in the result contract: `{"file": "...", "line": ..., "RuleID": "...", "snippet": "<redacted>", "recommendation": "rotate + remove + re-scan"}`. The operator must rotate the credential and remove it from history before this CR can merge. **This is a hard stop.**

**Step 2: minimise the allowlist churn.** Before adding each new entry, check whether widening an *existing* `[allowlist].paths` regex would cover it without losing tightness elsewhere. The existing list (`docs/`, `tests/fixtures/`, `examples/`, `.iw/`, `.git/`, `.venv/`, `venv/`, `node_modules/`, `dist/`, `build/`, `__pycache__/`, `logs?/`, `allure-report/`, `allure-results/`) is conservative; many test files are NOT under `tests/fixtures/` and DO host example secrets. Decide case-by-case.

**Step 3: write the diff with comments.** Every new entry — every new path regex and every new `[[rules.allowlists]]` block — carries a one-line `# why` comment immediately above it. Format:

```toml
# why: tests/unit/test_oss_secrets_parser.py — fixtures for the OSS secrets-parser tests; values are intentionally secret-shaped
"(?:^|/)tests/unit/test_oss_secrets_parser\\.py$",
```

For per-rule stopwords/regexes:

```toml
[[rules.allowlists]]
description = "Example .local FQDNs in test fixtures and docs"
# why: dev@example.local, foo.local, etc. — RFC 6761 reserved test domains, never reachable
regexes = ['''\b(?:example|dev|foo|bar|baz)\.local\b''']
```

**Step 4: post-triage scan.** Re-run the same gitleaks command. Expected outcome: **0 findings**. If non-zero, return to Step 1 for the residue. If non-zero after a second pass and the remaining findings look real, escalate via `blockers`.

### 2. Wire the pre-commit hook

Edit `.pre-commit-config.yaml`. Add the gitleaks hook after the existing `detect-private-key` hook (line 13 area), in its own `repos:` entry. Use the upstream `gitleaks/gitleaks` repo with the recent stable tag (check https://github.com/gitleaks/gitleaks/releases — `v8.30.x` line as of 2026-05; pin a specific tag, never `main`/`HEAD`). Use the pre-commit hook id documented by the upstream repo (typically `gitleaks`). The hook should run on staged changes (the default — fast for committers) and use the project's `.gitleaks.toml` automatically (gitleaks discovers it at repo root).

Verify locally: `pre-commit run gitleaks --all-files` — must exit 0. (This is the gate for AC1.)

### 3. Wire the GH `secrets-scan` job

Edit `.github/workflows/security-scan.yml`. Add a new job named `secrets-scan` (or `gitleaks`) — placement: after `deps-audit`, before `iac-scan`, alphabetically. The job:

- Runs on `push`, `pull_request`, and the existing `schedule` cron (already at line 14 — inherits).
- Checkout step uses the same pinned `actions/checkout` SHA and `persist-credentials: false` as the other jobs.
- Installs gitleaks via the official upstream — either `gitleaks/gitleaks-action` (preferred — it's the upstream-maintained pattern) at a pinned SHA, OR `curl`-installs the binary if the action is unavailable. Pick `gitleaks/gitleaks-action` if its license / GHAS-private-repo behaviour is compatible (check; if not, use the binary download).
- Runs `gitleaks detect --no-git --config .gitleaks.toml --report-format sarif --report-path gitleaks.sarif`. Exit code: nonzero on findings = job fails (this IS the blocking gate).
- Uploads SARIF via `github/codeql-action/upload-sarif` (same action the existing `iac-scan` would use, except `iac-scan` currently uses the trivy action's built-in upload via `aquasecurity/trivy-action`). Mirror the **comment block** from `iac-scan`'s SARIF upload step explaining the private-repo / GitHub Advanced Security caveat (private repos auto-skip).

### 4. Wire the daemon QV gate

Edit `skills/iw-workflow/SKILL.md`:

- Find the canonical QV gate list. Today (after CR-00046 + CR-00047) it's 7 gates: `lint → assertions → format → typecheck → unit-tests → integration-tests → diff-coverage`.
- Add an 8th gate: `security-secrets`, with command `make security-secrets` and a brief description ("Secret scan via gitleaks against the working tree using the project's .gitleaks.toml allowlist"). Placement: after `diff-coverage`.
- Update any "the canonical list is 7 gates" prose to "the canonical list is 8 gates" with the new ordering enumerated.
- Run `uv run iw sync-skills` (no `--force` needed because `iw-workflow` is a project-shared skill, not a project-override). Verify `.claude/skills/iw-workflow/SKILL.md` matches its master with `diff -q skills/iw-workflow/SKILL.md .claude/skills/iw-workflow/SKILL.md`.

This change makes the new gate available for new items via the design templates. Existing in-flight items don't get retrofitted (CR-00046's precedent). This CR's own S11 gate IS the new gate (chicken-and-egg per the design's Notes section).

### 5. Wire `make security-secrets` + rewrite `make security-sast`

Edit `Makefile`. Add a new target:

```make
security-secrets:
	@command -v gitleaks >/dev/null 2>&1 || { \
		echo "ERROR: 'gitleaks' not found."; \
		echo "Install: brew install gitleaks   (or)   curl -sSfL https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_linux_x64.tar.gz | tar -xz -C /tmp && sudo mv /tmp/gitleaks /usr/local/bin/"; \
		exit 1; \
	}
	@mkdir -p $(SECURITY_DIR)
	@echo "[security-secrets] gitleaks ..."
	@gitleaks detect --no-git --config .gitleaks.toml --report-format json --report-path $(SECURITY_DIR)/gitleaks.json
	@echo "[security-secrets] OK"
```

Mirror the `command -v ... || exit 1` pattern from the existing `security-deps` and `security-iac` targets (lines 180–190 and 200–204). The recipe MUST exit non-zero on findings (so the daemon QV gate fails on findings) — gitleaks does this by default.

Fold into `security-all`:

```make
security-all: security-deps security-iac security-secrets
	@echo "[security-all] complete (image scans run separately if images are built)"
```

Add `security-secrets` to `.PHONY`.

Rewrite `security-sast` from its current alias `security-sast: security-deps` + `@echo "[security-sast] complete"` to a real Semgrep recipe:

```make
security-sast:
	@command -v semgrep >/dev/null 2>&1 || { \
		echo "ERROR: 'semgrep' not found."; \
		echo "Install: uv add --dev semgrep   (or)   pip install semgrep"; \
		exit 1; \
	}
	@mkdir -p $(SECURITY_DIR)
	@echo "[security-sast] semgrep ..."
	@uv run semgrep --config p/python --config p/owasp-top-ten --config p/security-audit orch dashboard executor --error --json --output $(SECURITY_DIR)/semgrep.json || true
	@uv run semgrep --config p/python --config p/owasp-top-ten --config p/security-audit orch dashboard executor --error
	@echo "[security-sast] OK"
```

The double-invocation pattern matches what `security-deps` does for `bandit`: one writes the JSON report for `security-report` to consume, one provides the human-readable output. The trailing `--error` makes Semgrep exit non-zero on findings (so locally `make security-sast` IS a gate, even though the GH job is `continue-on-error` for now).

Note: keep bandit where it is (in `security-deps`). Do NOT move bandit to `security-sast`. (Out of scope.)

### 6. Wire the GH `semgrep` job (burn-in, continue-on-error)

Edit `.github/workflows/security-scan.yml`. Add a new job named `semgrep`. Placement: after `iac-scan`, alphabetically reasonable. The job:

- Runs on `push`, `pull_request`, and the existing `schedule` cron.
- `continue-on-error: true` at the job level for burn-in.
- Checkout + setup-uv steps mirror `deps-audit`.
- Runs `uv run semgrep --config p/python --config p/owasp-top-ten --config p/security-audit orch dashboard executor --sarif --output semgrep.sarif`. Trailing `--error` is NOT required (the job's `continue-on-error: true` handles non-blocking).
- Uploads `semgrep.sarif` via `github/codeql-action/upload-sarif`, mirroring the private-repo-skip comment from `iac-scan`.

### 7. Docs + plan + skill

**`docs/IW_AI_Core_Testing_Strategy.md`:**

- §5 (gate table) — add two new rows:
  - "Secret scan (gitleaks)" — gates: pre-commit + GH `secrets-scan` + daemon `security-secrets`; status: ✅; reference: CR-00050.
  - "Semgrep SAST" — gates: GH `semgrep` (burn-in, `continue-on-error`); local `make security-sast`; status: ⚠️ burn-in; reference: CR-00050.
- §9 (gaps table) — flip two rows:
  - "Secrets scanning (`gitleaks`)" — change from ❌ (or current ⚠️) to ✅ (CR-00050, YYYY-MM-DD).
  - "Semgrep SAST" — change from ❌ to ⚠️ (CR-00050, YYYY-MM-DD) — managed rulesets, continue-on-error, follow-up `P1-CR-D-followup-semgrep-block` flips blocking.

**`skills/iw-ai-core-testing/SKILL.md`:**

- §8 (gates) — add a paragraph or rows noting:
  - `security-secrets` is the 8th canonical QV gate (gitleaks).
  - `security-sast` runs Semgrep; non-blocking in CI during burn-in.
  - The pre-commit hook is the developer's first line of defense.

Run `uv run iw sync-skills --force iw-ai-core-testing` (project override requires `--force`). Verify `.claude/skills/iw-ai-core-testing/SKILL.md` matches its master.

### 8. Plan + changelog

**`ai-dev/work/TESTS_ENHANCEMENT.md`:**

- §5 grouping table — find the row `**P1-CR-D — Security gates** *(start here)* | 1.6 + 1.9`. Update its status to **SHIPPED (CR-00050, YYYY-MM-DD)**; move the *(start here)* marker to **P1-CR-E**.
- §5 — add a new row below P1-CR-A-followup and P1-CR-C-followup-randomly:
  - `**P1-CR-D-followup-semgrep-block — Flip Semgrep to hard-block after burn-in** | (cleanup) | After ~2 weeks of `continue-on-error: true` burn-in, triage the noise floor: any rule that's consistently noisy gets a custom exclusion or moved to nightly-only; the remaining rules flip to blocking (`continue-on-error: false`). Also consider adding a `make security-sast` daemon QV gate at that point. | Low urgency until we have noise-floor data. |`
- §5 items 1.6 + 1.9 sub-rows (lines 102 + 103 area) — flip status to **DONE (CR-00050, YYYY-MM-DD)** with a one-liner.
- §11 (changelog) — add a new dated entry. Format mirrors prior CR-00046/47/48/49 entries: list what S01 did (the 109-finding triage with counts FP_PATH/FP_VALUE/REAL by RuleID; gitleaks wired on three surfaces; Semgrep wired with `continue-on-error: true`; the new daemon QV gate; doc/plan updates; `iw sync-skills` ran; sibling repos pick up the new daemon QV gate on their next sync — not done here).

### 9. Pre-flight + targeted verification

Run `make quality` — must pass (lint + format + typecheck + test-assertions all pass; `vulture`/`deptry` print but don't block). Run `make security-secrets` — must exit 0 (this is the gate this CR introduces; its inaugural exercise on this CR's own changes). Run `make security-sast` — exit code depends on what Semgrep finds (zero or non-zero). If non-zero on managed rulesets against the existing code, triage each finding: rule false positive ⇒ Semgrep-side `# nosemgrep: <rule-id>` inline comment + a `# why` comment naming the FP; real issue ⇒ filed as a separate incident via `blockers`, do not silently `# nosemgrep` real issues.

**Do NOT** run `make check`, `make test-integration`, or `make diff-coverage` here — those are S08/S09/S10's job. Targeted verification only.

## Scope discipline

Touch ONLY the files in the design's "Impacted Paths":

- `.gitleaks.toml`
- `.pre-commit-config.yaml`
- `.github/workflows/security-scan.yml`
- `Makefile`
- `pyproject.toml` (only if you genuinely need to add Semgrep as a dev dep — check whether it's already in `[dependency-groups] dev`)
- `skills/iw-workflow/**` + `.claude/skills/iw-workflow/**`
- `skills/iw-ai-core-testing/**` + `.claude/skills/iw-ai-core-testing/**`
- `docs/IW_AI_Core_Testing_Strategy.md`
- `ai-dev/work/TESTS_ENHANCEMENT.md`

Plus this CR's `ai-dev/active/CR-00050/**` (reports, evidence).

**Do not touch production code** (`orch/`, `dashboard/`, `executor/`, `bin/`, `scripts/`). **Do not move bandit** out of `security-deps`. **Do not add Trivy image scan** (out of scope). **Do not add Semgrep custom rules** (start with managed rulesets). **Do not port to sibling projects**. **Do not flip Semgrep to blocking** in this CR — that's the explicit follow-up.

## Project Conventions

Read the project's `CLAUDE.md` for project-wide rules and the convention catalog. Follow all rules defined there exactly. When in doubt, match existing code.

## TDD Requirement

This CR's TDD anchor is the **109-finding pre-patch gitleaks scan** in deliverable 0 — the failing condition that motivated and shaped the work. GREEN evidence: the zero-finding post-patch scan in deliverable 1 step 4. Record both in `tdd_red_evidence`.

Do not write new tests to "prove" the fix — the gitleaks tool itself is the assertion engine, and the existing 7 QV gates plus the new `security-secrets` gate are the regression net.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, run these in order and fix any issues:

1. **`make format`** — auto-fixes formatting drift. If it reformats files, inspect the diff and re-stage; do NOT skip.
2. **`make typecheck`** — zero errors involving files you touched.
3. **`make lint`** — zero errors.

If a tool isn't available, STOP and raise a blocker.

In your Subagent Result Contract, populate the `preflight` object:
- `"ok"` — ran cleanly
- `"fixed"` — applies to `format` only
- `"skipped:<reason>"` — only if you raised a blocker

## Test Verification (NON-NEGOTIABLE)

After implementation, verify your own changes — but **DO NOT run the full test suite**. Full-suite execution is owned by S08/S09/S10 downstream.

Targeted verification for this CR:

1. `pre-commit run gitleaks --all-files` — exits 0. (AC1.)
2. `make security-secrets` — exits 0. (AC4.)
3. `make security-sast` — runs Semgrep against `orch dashboard executor` (no longer an echo alias). Exit code reflects findings. (AC5.)
4. `gitleaks detect --no-git --config .gitleaks.toml -v` — 0 findings on the patched tree. (AC7.)
5. `diff -q skills/iw-workflow/SKILL.md .claude/skills/iw-workflow/SKILL.md` — files match. (AC3.)
6. `diff -q skills/iw-ai-core-testing/SKILL.md .claude/skills/iw-ai-core-testing/SKILL.md` — files match.

Do **NOT** run `make check`, `make test-integration`, or `make diff-coverage` — that's S08/S09/S10's job.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "CR-00050",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    ".gitleaks.toml",
    ".pre-commit-config.yaml",
    ".github/workflows/security-scan.yml",
    "Makefile",
    "skills/iw-workflow/SKILL.md",
    ".claude/skills/iw-workflow/SKILL.md",
    "skills/iw-ai-core-testing/SKILL.md",
    ".claude/skills/iw-ai-core-testing/SKILL.md",
    "docs/IW_AI_Core_Testing_Strategy.md",
    "ai-dev/work/TESTS_ENHANCEMENT.md"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "pre-commit gitleaks: ok (0 findings). make security-secrets: ok (0 findings). make security-sast: <exit code> (<N> findings, <M> triaged as nosemgrep:<rule>, <K> escalated). gitleaks detect (manual): 0 findings.",
  "tdd_red_evidence": "gitleaks detect --no-git --config .gitleaks.toml -v on pre-patch tree → '<N>' leaks found across <M> unique RuleIDs (top: <RuleID-1>=<count-1>, <RuleID-2>=<count-2>, …). Evidence: ai-dev/active/CR-00050/evidences/pre/cr-00050-gitleaks-pre.json + cr-00050-gitleaks-summary.md. Post-patch: 0 findings.",
  "blockers": [],
  "notes": "Triage: <N> findings → <X> FALSE_POSITIVE_PATH (allowlist paths extended in .gitleaks.toml) + <Y> FALSE_POSITIVE_VALUE (per-rule stopwords added) + <Z> REAL_OR_SUSPICIOUS (escalated via blockers above — if 0, omit; if >0, this CR cannot merge until operator rotates+removes). gitleaks: pre-commit hook (gitleaks/gitleaks @ <pinned tag>), GH job `secrets-scan` (SARIF upload, private-repo-skip caveat preserved), daemon QV gate `security-secrets` (8th canonical, added to skills/iw-workflow/SKILL.md), make security-secrets (folded into security-all). Semgrep: make security-sast rewritten (no longer echo alias), GH job `semgrep` with continue-on-error: true, SARIF upload. P1-CR-D-followup-semgrep-block filed in TESTS_ENHANCEMENT.md §5. iw sync-skills (--force iw-ai-core-testing) ran; .claude/skills/ copies in sync."
}
```

- `tdd_red_evidence`: the 109-finding (or whatever current count is) RED scan + the 0-finding GREEN. Do not write `"n/a"`.
- `completion_status`: `complete` if all 9 deliverables done + post-patch scan is 0 + no REAL_OR_SUSPICIOUS findings remain unresolved; `partial` if you made progress but had to leave some triage to a follow-up (file the follow-up via §5); `blocked` if REAL_OR_SUSPICIOUS findings exist that require operator rotation before merge.
- `blockers`: list any REAL_OR_SUSPICIOUS findings with file:line, RuleID, snippet (redacted to first 8 chars + `…`), and recommendation. Each is a hard stop.
