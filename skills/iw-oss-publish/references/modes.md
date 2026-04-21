# Modes — Detailed Walkthroughs

This file expands on the three modes defined in `SKILL.md`. It covers the exact sub-steps, decision points, and error-handling behavior for each mode.

---

## Shared Pre-flight (every mode)

Before any mode executes, the skill must:

1. **Validate target is a git repo**: `git -C {target} rev-parse --git-dir` (abort if fails).
2. **Detect visibility**: `gh repo view --json isPrivate,visibility 2>/dev/null` — record `private|public|unknown`. "unknown" when gh is not authenticated or the repo has no GitHub remote yet.
3. **Detect ecosystems present**: look for `pyproject.toml` / `setup.py` / `requirements*.txt` (Python), `package.json` (Node), `go.mod` (Go), `Cargo.toml` (Rust), `pom.xml` / `build.gradle*` (JVM).
4. **Load config**: per `SKILL.md` Step 2.
5. **Verify tool availability**: record which Tier-1 and Tier-2 tools are installed (`command -v {tool}`). Do not install — `install_tools.sh` is a separate explicit step.
6. **Ensure output dir**: `mkdir -p {target}/.iw`. Add `.iw/` to `.gitignore` if missing.

If any Tier-1 tool is missing, print the exact install command and abort the mode (no partial runs).

---

## `scan` Mode

### Purpose

Read-only audit. Answers "where does this repo stand against the OSS-release bar?" without touching working-tree or history.

### Algorithm

```
1. Pre-flight (shared).
2. Run check catalog in dependency order (see checks.md "Execution order").
3. Aggregate findings by severity: MUST / SHOULD / MAY.
4. Emit artifacts:
   - .iw/oss-publish-report.md     (markdown report)
   - .iw/oss-publish-findings.json (machine-readable)
   - .iw/gitleaks.sarif            (from the secrets check)
   - .iw/sbom.spdx.json            (from syft)
   - .iw/sbom.cyclonedx.json       (from syft)
5. Print the report body to console.
6. Exit 1 if any MUST finding unresolved, else 0.
```

### Exit contract

| Outcome | Exit code | Notes |
|---------|-----------|-------|
| No MUST unresolved, no SHOULD | 0 | Clean |
| No MUST unresolved, SHOULD present | 0 | Warning-level; scan succeeded |
| Any MUST unresolved | 1 | Blocker present; user must remediate |
| Tool missing / config invalid / git not found | 2 | Setup error, not a compliance finding |

### Idempotency

`scan` is pure and idempotent. Re-running overwrites `.iw/*` artifacts. No commits, no stash, no branch changes.

### Running on an already-public repo

`scan` works identically regardless of visibility. When `isPrivate=false`, some checks change their advisory text (e.g., secret-scanning: "enabled — verify push protection" vs "enable after flip"). Severity does not change.

---

## `make_oss` Mode

### Purpose

Prepare a private repo for OSS release by applying every auto-fixable check on a dedicated branch and handing the user a punchlist of remaining human-judgment items.

### Algorithm

```
1. Pre-flight (shared).
2. Abort if repo is already public (the user should use `scan` for ongoing
   compliance). Override with --force if the user really means it.
3. Verify working tree is clean:
     git status --porcelain
   If not, abort and instruct user to commit/stash first.
4. Create prep branch:
     git checkout -b iw-oss-publish/prep-{YYYY-MM-DD}
5. Run `scan` to capture baseline findings.
6. For each SHOULD/MUST finding with an auto-fix recipe in fix_recipes.md:
     a. Render template / run tool / make file edit
     b. Write the new/updated file in the working tree (not committed)
     c. Log the fix to a running transcript
7. Re-run `scan` to verify fixes did not introduce regressions.
8. Generate compliance-punchlist.md:
     - All remaining MUST findings (non-auto-fixable) grouped by check
     - All remaining SHOULD findings (non-auto-fixable or user-overrideable)
     - All human-judgment items (crypto classification, name collision,
       trademark search, history rewrite preference, CoC contact email)
9. Stage all changes:
     git add -A
10. Print the summary of changes + path to punchlist.
11. Tell the user: "Review staged changes with `git diff --cached`, then commit."
12. Exit 1 if any MUST finding remains unresolved after auto-fix, else 0.
```

### What `make_oss` will auto-fix

(See `fix_recipes.md` for the full playbook.)

- Missing `LICENSE` → render from template based on `config.license` (MUST fix).
- Missing `NOTICE` (Apache-2.0 only) → render with `{company_legal_name}` and aggregated third-party attributions.
- Missing `README.md` → render stub with project name, description, install/usage placeholders, license badge.
- Missing `CONTRIBUTING.md` → render with DCO sign-off instructions.
- Missing `CODE_OF_CONDUCT.md` → render Contributor Covenant v3 with `{company_contact_email}`.
- Missing `SECURITY.md` → render with supported-versions placeholder + PVR link + `{company_contact_email}`.
- Missing `CODEOWNERS` → render `* @innovation-ways/maintainers`.
- Missing `TRADEMARK.md` → render with `{company_brand}` + `{company_legal_name}`.
- Missing `PULL_REQUEST_TEMPLATE.md` / `.github/ISSUE_TEMPLATE/*` → render stubs.
- Missing `.github/workflows/scorecard.yml` / `codeql.yml` / `release-please.yml` / `compliance-scan.yml` → render.
- Missing `.github/dependabot.yml` → render.
- Missing `.gitleaks.toml` → render with IW-specific patterns (internal FQDN, employee emails).
- Missing `.pre-commit-config.yaml` → render referencing gitleaks, pinact, conventional-commits.
- Outdated GitHub Actions references → `pinact run` to SHA-pin.
- Missing `THIRD_PARTY_LICENSES.md` → regenerate from `pip-licenses` / `license-checker` / `go-licenses` per detected ecosystems.
- Missing `.gitignore` entries for `.env`, `*.tfstate`, `.iw/oss-publish-*.json` etc. → append.
- Missing `.iw/oss-publish.toml` → write the resolved config so future runs are reproducible.

### What `make_oss` will NOT auto-fix

Must be done by the human (these land in the punchlist):

- Real secrets in history (requires history rewrite decision).
- Real PII in test fixtures (requires code review).
- GPL/AGPL/unknown inbound deps (requires dep replacement or license change).
- Non-standard crypto classification (requires legal judgment).
- Project name collision on PyPI/npm/crates.io (requires rename decision).
- USPTO/WIPO trademark search (external, manual).
- Contributor email exposure (requires author rewrite decision; only offered for the nuke strategy).
- DCO app installation on the org (out-of-band GitHub App install).
- Populating content inside template stubs (e.g., filling `README.md` installation steps).

### Idempotency

`make_oss` is idempotent within a single prep branch — re-running only fixes new drift without recreating already-present files. If the prep branch exists from a prior run, the skill reuses it (does not create `prep-YYYY-MM-DD-2`).

---

## `publish` Mode

### Purpose

Flip a verified private repo to public. **Never touches operational state automatically** — emits commands for the user to run.

### Algorithm

```
1. Pre-flight (shared).
2. If visibility is already public: abort and direct user to `scan` mode.
3. Run `scan`. Hard-block if any MUST finding is unresolved:
     "Cannot publish. Run `iw-oss-publish make_oss` first."
4. Present publication summary to user:
     - Project name, target org, license, all MUST checks GREEN
     - Current branch, number of commits, date range of history
     - Number of distinct contributor emails (for the history rewrite decision)
5. Ask for history strategy (if config.history_strategy is unset):
     NUKE        — fresh squashed init commit; zero history preserved
     FILTER-REPO — surgical removal of specific paths/strings; history preserved
     PRESERVE    — publish history as-is
   (See history_rewrite.md for the decision tree.)
6. Print the EXACT commands for the chosen strategy. DO NOT EXECUTE.
     - For NUKE: full `git checkout --orphan`, `git add`, `git commit`, `git push --force` sequence.
     - For FILTER-REPO: `git filter-repo` invocations with path/replacement lists.
     - For PRESERVE: "no history changes; proceed to step 7."
7. Wait for user confirmation that history rewrite is done (or skipped).
8. Run `scan` one more time on the rewritten repo. Hard-block again if any MUST
   finding is present (secrets could theoretically have leaked into the new
   history even after rewrite).
9. Generate .iw/publish-playbook.sh containing:
     - gh repo edit --visibility public
     - gh repo edit (description, homepage, topics, merge settings)
     - gh api PUT /repos/{org}/{repo}/branches/main/protection
     - gh api PUT /repos/{org}/{repo}/vulnerability-alerts
     - gh api PUT /repos/{org}/{repo}/automated-security-fixes
     - gh api PUT /repos/{org}/{repo}/private-vulnerability-reporting
     - gh repo edit --enable-discussions (conditional)
     - OpenSSF Scorecard badge reminder
     - GitHub Support cache-purge reminder if any secrets were found in history
10. Emit the final checklist to console + .iw/publish-checklist.md:
     - [ ] Review staged changes and compliance-punchlist
     - [ ] Execute history rewrite (if chosen)
     - [ ] Run: bash .iw/publish-playbook.sh
     - [ ] Install cncf/dco2 GitHub App on the org
     - [ ] Manually verify name collision with USPTO/WIPO
     - [ ] Open GitHub Support ticket for SHA cache purge (if applicable)
11. Exit 0.
```

### Safety rails

- **No destructive command executes automatically.** The skill prints commands; the user runs them.
- **Two scans flank any history rewrite.** The second scan is the gate that catches leaks introduced by an incomplete rewrite.
- **Visibility flip (`gh repo edit --visibility public`) is a single command that the user runs.** The skill writes it to the playbook but does not pipe it to `bash`.
- **`--force` flag exists** for skipping some safety checks (e.g., re-publish a repo that's already public for playbook regeneration), but every `--force` path prompts for confirmation.

### Resumability

If `publish` is aborted mid-flow (e.g., user Ctrl-C's after step 6), re-running starts from step 1. The second scan (step 8) serves as the correctness check regardless of interruption. The playbook is idempotent — re-running `bash .iw/publish-playbook.sh` is safe.

---

## Mode Selection Cheat Sheet

| User goal | Mode | Example |
|-----------|------|---------|
| "Show me what's blocking OSS release" | `scan` | `iw-oss-publish scan` |
| "Check whether this public repo is still compliant" | `scan` | `iw-oss-publish scan ~/work/my-public-oss` |
| "Get this private repo OSS-ready on a review branch" | `make_oss` | `iw-oss-publish make_oss` |
| "Flip this verified repo public" | `publish` | `iw-oss-publish publish` |
| "I flipped public and want to ensure drift hasn't crept in" | `scan` | `iw-oss-publish scan` |

---

## Error-Handling Summary

| Situation | Behavior |
|-----------|----------|
| Target not a git repo | Abort, exit 2 |
| Tier-1 tool missing | Abort with install command, exit 2 |
| Config file malformed | Abort with parse error, exit 2 |
| `make_oss` on dirty working tree | Abort, exit 2 |
| `make_oss` on already-public repo | Abort unless `--force`, exit 2 |
| `publish` on already-public repo | Abort, exit 2 |
| `publish` with unresolved MUST finding | Abort with "run make_oss first", exit 1 |
| History rewrite canceled by user | Stop cleanly, preserve state, exit 0 |
| gh CLI not authenticated | Warn; skip GitHub-live checks; continue | 

Exit code 2 = setup/environment error (not a compliance verdict).
Exit code 1 = compliance failure (MUST unresolved).
Exit code 0 = clean or successful emission.
