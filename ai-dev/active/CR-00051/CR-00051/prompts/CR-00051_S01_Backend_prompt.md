# CR-00051_S01_Backend_prompt

**Work Item**: CR-00051 — Semgrep baseline cleanup
**Step**: S01
**Agent**: Backend (`backend-impl`)

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network state. Testcontainer fixtures spun up by pytest are exempt. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This step adds **no migrations**. If you find yourself needing to change schema, STOP and raise a blocker — CR-00051 is comment-and-config only.

## Input Files

- **Runtime step state** (authoritative): `uv run iw item-status CR-00051 --json`.
- `ai-dev/active/CR-00051/CR-00051_CR_Design.md` — design doc (read in full, especially "Current Behavior" Classes A/D/E/F/G/H and the Invariants).
- The Python files listed under "Targets" below.
- `Makefile` — read the `security-sast` target (lines ~226–236); you will add four `--exclude-rule` flags to both `semgrep` invocations.
- `docs/IW_AI_Core_Testing_Strategy.md` — append a new section near the end.

## Output Files

- `ai-dev/active/CR-00051/reports/CR-00051_S01_Backend_report.md` — Step report.

## Context

You are adding documented Semgrep suppressions to a set of Python lines and adding four `--exclude-rule` flags to the `Makefile` `security-sast` target. The Python annotations cover three high-signal rule classes where each finding has been individually inspected and confirmed safe (Class A: trusted constructed shell commands; Class D: Jinja env that renders YAML; Class E: logger format-string false positive). The Makefile flags cover four template-noise rules where the entire population of findings is false positives and per-line annotation would create unsustainable churn (Class C: 26 sites at `write_button_attrs(request)` macro callers — empirically verified that in-macro `{# nosemgrep #}` does NOT propagate; Class F: 31 `var-in-href` sites; Class G: 5 `var-in-script-tag` sites; Class H: 1 `plaintext-http-link` site).

**No behavioural code change is permitted in this step.**

Read `CLAUDE.md` (root + `orch/CLAUDE.md`) before opening any file.

## Requirements

### 1. Class A — `subprocess-shell-true` (12 sites, 7 files)

For each of the following 12 lines, append a `# nosemgrep` marker on the same line as the existing `# nosec B602`. The result on each line is **both** markers, ending with a short rationale:

```python
shell=True,  # nosec B602  # nosemgrep: python.lang.security.audit.subprocess-shell-true.subprocess-shell-true — trusted constructed command, no untrusted input on argv
```

Sites (line numbers may have drifted by ±2 after recent merges; rely on the `# nosec B602` marker as your anchor on each line):

- `dashboard/routers/staleness.py:178`
- `orch/archive/batch_archiver.py:325`
- `orch/daemon/batch_manager.py:875`
- `orch/daemon/batch_manager.py:1302`
- `orch/daemon/browser_env.py:421`
- `orch/daemon/browser_env.py:650`
- `orch/daemon/doc_job_poller.py:248`
- `orch/daemon/fix_cycle.py:1258`
- `orch/test_runner.py:115`
- `orch/test_runner.py:338`
- `orch/test_runner.py:396`
- `orch/test_runner.py:643`

Open each file, find the `shell=True,  # nosec B602` line, and append the `# nosemgrep` marker. Preserve indentation. **DO NOT remove `# nosec B602`** — Invariant I1 forbids it.

For the rationale string, prefer wording specific to the call site if it's quick to determine (e.g., for `browser_env.py` it's a `docker compose` invocation; for `batch_manager.py` it's an executor script launch; for `test_runner.py` it's a test-suite invocation). If you can't tell in 30 seconds, use the generic wording above.

### 2. Class D — Jinja autoescape on YAML output (1 site)

`orch/daemon/worktree_compose.py:219`:

Current line:
```python
autoescape=False,  # noqa: S701  YAML output, not HTML
```

Change to:
```python
autoescape=False,  # noqa: S701  # nosemgrep: python.jinja2.security.audit.autoescape-disabled-false.incorrect-autoescape-disabled — YAML output, not HTML
```

(Merges the existing rationale into the new marker; the comment now lives next to the rule it silences. The `# noqa: S701` marker is retained — Invariant I1.)

### 3. Class E — logger credential disclosure false positive (2 sites)

`orch/rag/chat_repo.py`. Two `logger.warning(...)` calls flagged because the format string contains the literal word "model". The substituted value is just a model name string — not a credential.

Site 1 (line 53):
```python
logger.warning(
    "tiktoken does not support model '%s', using heuristic fallback", model_name
)
```

Site 2 (line 63):
```python
logger.warning(
    "tiktoken encode failed for model '%s', using heuristic fallback", model_name
)
```

Add a `# nosemgrep` marker on whichever line lets ruff/format keep its current shape. The clean option is to add the marker on the closing `)` line:

```python
logger.warning(
    "tiktoken does not support model '%s', using heuristic fallback", model_name
)  # nosemgrep: python.lang.security.audit.logging.logger-credential-leak.python-logger-credential-disclosure — false positive, only model name is logged
```

If `make format` reformats the trailing comment, alternative placement on the call's start line also works (Semgrep matches on the start line of the function call):

```python
logger.warning(  # nosemgrep: python.lang.security.audit.logging.logger-credential-leak.python-logger-credential-disclosure — false positive, only model name is logged
    "tiktoken does not support model '%s', using heuristic fallback", model_name
)
```

Pick whichever survives `make format`. Confirm by running `make security-sast` and observing the two findings are gone.

### 4. Classes C/F/G/H — Makefile `--exclude-rule` flags (project-wide rule excludes)

The four rules being excluded:
- `generic.html-templates.security.unquoted-attribute-var.unquoted-attribute-var` (26 false-positive findings, all at `{{ write_button_attrs(request) }}` macro callsites — the macro emits a constant pre-quoted attribute string with no user input; empirically verified that in-macro `{# nosemgrep #}` does NOT silence the call-site findings and `|safe`/`Markup` wrap introduces a new finding without silencing the originals)
- `generic.html-templates.security.var-in-href.var-in-href` (31 false-positive findings across 29 template files)
- `generic.html-templates.security.var-in-script-tag.var-in-script-tag` (5 false-positive findings in `fragments/item_files.html`, all `{{ ... | tojson }}` calls inside a `<script>` tag — Semgrep does not model the `tojson` filter)
- `html.security.plaintext-http-link.plaintext-http-link` (1 false-positive: a dev-only localhost link in `fragments/worktree_table.html:229`)

Open `Makefile`. The `security-sast` target lives at approximately lines 226–236 and contains **two** `uv run semgrep ...` invocations (one writes JSON output, one re-runs for the `--error` exit code).

Add the four `--exclude-rule` flags to **both** invocations. The flags must come after the `--config` flags and before the path arguments (`orch dashboard executor`).

Add a rationale comment block immediately above the `security-sast:` target line. Use Makefile comment syntax (`#`). The block must enumerate each excluded rule and the reason in one or two lines each.

Final shape (line numbers approximate — anchor on `security-sast:`):

```make
# security-sast: SAST gate via Semgrep. Four rules are project-wide-excluded
# because their false-positive density is 100% in this codebase:
#   generic.html-templates.security.unquoted-attribute-var.unquoted-attribute-var
#     — fires at every {{ write_button_attrs(request) }} macro callsite (26 sites
#       in 12 files). The macro emits a constant pre-quoted attribute string with
#       no user input. In-macro {# nosemgrep #} does NOT silence the rule (verified
#       empirically); per-line annotation across 12 caller files would be churny
#       and re-fired by every new caller. The macro's constant-output invariant is
#       locked by tests/unit/test_db_guard_macro.py — if a future edit introduces
#       user-input interpolation, that test will fail and this exclude flag must
#       be re-justified.
#   generic.html-templates.security.var-in-href.var-in-href
#     — fires on every <a href="{{ ... }}">; in this codebase, every flagged value
#       is a route-supplied URL, hardcoded route path, or template-author macro
#       parameter. The rule cannot prove safety statically. Per-line annotation
#       across 31 sites in 29 files would be unsustainable.
#   generic.html-templates.security.var-in-script-tag.var-in-script-tag
#     — fires on {{ ... }} inside <script>; in this codebase, every flagged value
#       passes through Jinja's tojson filter which emits a valid JSON literal.
#   html.security.plaintext-http-link.plaintext-http-link
#     — fires on http://-prefixed hrefs; in this codebase the one flagged site is
#       a dev-only localhost link, never reachable in production.
# Triage convention: docs/IW_AI_Core_Testing_Strategy.md "Semgrep finding triage".
security-sast:
	@command -v semgrep >/dev/null 2>&1 || { \
		echo "ERROR: 'semgrep' not found."; \
		echo "Install: uv add --dev semgrep   (or)   pip install semgrep"; \
		exit 1; \
	}
	@mkdir -p $(SECURITY_DIR)
	@echo "[security-sast] semgrep ..."
	@uv run semgrep --config p/python --config p/owasp-top-ten --config p/security-audit \
		--exclude-rule generic.html-templates.security.unquoted-attribute-var.unquoted-attribute-var \
		--exclude-rule generic.html-templates.security.var-in-href.var-in-href \
		--exclude-rule generic.html-templates.security.var-in-script-tag.var-in-script-tag \
		--exclude-rule html.security.plaintext-http-link.plaintext-http-link \
		orch dashboard executor --error --json --output $(SECURITY_DIR)/semgrep.json || true
	@uv run semgrep --config p/python --config p/owasp-top-ten --config p/security-audit \
		--exclude-rule generic.html-templates.security.unquoted-attribute-var.unquoted-attribute-var \
		--exclude-rule generic.html-templates.security.var-in-href.var-in-href \
		--exclude-rule generic.html-templates.security.var-in-script-tag.var-in-script-tag \
		--exclude-rule html.security.plaintext-http-link.plaintext-http-link \
		orch dashboard executor --error
	@echo "[security-sast] OK"
```

Use **tabs** (not spaces) for the recipe lines that follow `security-sast:` — Makefile syntax requires it. Use `\` line continuations as shown.

Do NOT touch any other Makefile target. The change is confined to the `security-sast:` block and the preceding comment block.

### 5. Triage convention doc

Append a new H2 section to `docs/IW_AI_Core_Testing_Strategy.md` titled `## Semgrep finding triage (CR-00051)`. The section must:

- State that `# nosec` (bandit) does **not** silence Semgrep — `# nosemgrep: <rule-id>` (Python) or `{# nosemgrep: <rule-id> #}` (Jinja2) is the marker the project uses.
- Note that in-macro `{# nosemgrep #}` does NOT propagate to call-site analyses (empirically verified during CR-00051) — when a rule fires at many call sites of the same macro, the right tool is Makefile `--exclude-rule`, not an in-macro comment.
- Give the canonical comment syntax for: a same-line `# nosemgrep` on a Python statement; a Jinja2 `{# nosemgrep #}` comment immediately before the template line; a Makefile `--exclude-rule <rule-id>` flag accompanied by a rationale comment block above the target.
- Briefly enumerate the four reasons to suppress rather than fix: confirmed false positive (rule misfires on a pattern that's safe at this call site), trusted-source rendering (Markdown→HTML produced server-side from internal documents, `| safe` on such output), deliberate-but-audited pattern (`shell=True` on constructed commands that take no user input on argv), and project-wide structural false positive (use Makefile `--exclude-rule`).
- Require every per-line suppression to carry a same-line rationale comment after `—`. Require every Makefile `--exclude-rule` to carry a rationale comment above the target.
- Keep the section to roughly 30–50 lines. Do NOT re-document the full Semgrep CLI.

Place the new section after the last existing H2 in the file. Do not reorganise existing content.

### 6. Verify locally with Semgrep

After all edits, run `make security-sast` from the repo root and confirm:

- The 12 Class A findings are gone.
- The 1 Class D finding is gone.
- The 2 Class E findings are gone.
- The 26 Class C (`unquoted-attribute-var`) findings are gone.
- The 31 Class F (`var-in-href`) findings are gone.
- The 5 Class G (`var-in-script-tag`) findings are gone.
- The 1 Class H (`plaintext-http-link`) findings are gone.
- The remaining findings are exactly **16** — all Class B (`template-unescaped-with-safe`) — to be silenced by S03.

If any Class A/D/E finding persists, the per-line marker is in the wrong place (most commonly: indented on a line Semgrep doesn't associate with the offending expression). Try the `# nosemgrep` on the previous or next line until the tool reports the finding suppressed. Do NOT change the underlying code to silence it.

If any of Classes C/F/G/H persist, the Makefile flags are mis-placed or mis-spelled. Confirm the rule IDs are character-for-character identical to those above, and that both `semgrep` invocations carry all four flags.

If `semgrep` is not installed in your worktree, run `uv sync --dev` once to pick it up (CR-00050 added it to dev deps). If it still isn't there, STOP and raise a blocker.

## Project Conventions

Read `orch/CLAUDE.md`. This is a comments-and-Makefile-flags-only change — no architectural or naming concerns apply. Conventions you must respect:

- Preserve existing `# nosec` / `# noqa` markers (Invariant I1).
- Makefile recipe lines start with a literal tab (not spaces). Misuse of spaces will break the build silently.

## TDD Requirement

This step adds **no behavioural code**. Use `tdd_red_evidence: "n/a — comments, Makefile flags, and doc-only edits, no production logic"` in your result contract.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

1. `make format` — must report "Nothing to format" or auto-format trailing-comment placement. If it reformats, accept the result and verify the suppressions still fire as expected.
2. `make typecheck` — must report zero NEW errors on the files you touched.
3. `make lint` — must report zero NEW errors.

## Test Verification (NON-NEGOTIABLE)

After implementation, verify by running `make security-sast` and confirming Classes A/D/E/F/G/H findings are gone (expected residual: 42 findings, all in Classes B and C, which S03 will handle). Do NOT run `make test-unit` or `make test-integration` — those are downstream QV gate steps (S12, S14).

If you also want quick assurance no Python behaviour drifted, run a targeted set:
```bash
uv run pytest tests/unit/test_archive.py tests/unit/test_chat_repo.py tests/unit/test_worktree_compose.py tests/unit/test_test_runner.py tests/unit/test_staleness.py -v 2>/dev/null || true
```
(Targeted, lightweight — fine if a test file doesn't exist.)

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "Backend",
  "work_item": "CR-00051",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/staleness.py",
    "orch/archive/batch_archiver.py",
    "orch/daemon/batch_manager.py",
    "orch/daemon/browser_env.py",
    "orch/daemon/doc_job_poller.py",
    "orch/daemon/fix_cycle.py",
    "orch/daemon/worktree_compose.py",
    "orch/rag/chat_repo.py",
    "orch/test_runner.py",
    "Makefile",
    "docs/IW_AI_Core_Testing_Strategy.md"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "make security-sast: Classes A/C/D/E/F/G/H now report 0 findings; Class B (16) remains for S03",
  "tdd_red_evidence": "n/a — comments, Makefile flags, and doc-only edits, no production logic",
  "blockers": [],
  "notes": "Record exact Semgrep finding counts before vs. after as a sanity check in the report body."
}
```
