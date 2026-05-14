# CR-00051 — S01 Backend Report

**Step**: S01 (Backend)
**Status**: complete
**Work item**: CR-00051 — Semgrep baseline cleanup

## Summary

Documented Semgrep suppressions added to Python source for Class A (`subprocess-shell-true`) and Class E (`logger-credential-leak`), and the project-wide Makefile `--exclude-rule` flags pruned down to only the four template-noise rules (Class C/F/G/H). A new triage convention section was appended to `docs/IW_AI_Core_Testing_Strategy.md`. No behavioural code change.

## Starting state vs. final state (Semgrep finding counts)

Raw scan, **no** `--exclude-rule` flags, against `orch dashboard executor`:

| Rule (Class) | Baseline (pre-S01) | After S01 |
|---|---|---|
| `subprocess-shell-true` (A) | 8 firing + 4 silenced by malformed multi-line `# nosemgrep:` in `test_runner.py` | **0** (all 12 sites carry a proper single-line `# nosemgrep: <rule> — <rationale>` after `# nosec B602`) |
| `incorrect-autoescape-disabled` (D) | 0 (rule does not fire — `worktree_compose.py:219` was already changed upstream to `jinja2.select_autoescape()`; the line the prompt referenced no longer matches the `autoescape=False` pattern) | **0** (n/a — nothing to suppress) |
| `python-logger-credential-disclosure` (E) | 2 | **0** (both `chat_repo.py` sites carry `# nosemgrep:` after the existing `# noqa: B701`) |
| `unquoted-attribute-var` (C) | 26 | **0** (Makefile `--exclude-rule`) |
| `var-in-href` (F) | 31 | **0** (Makefile `--exclude-rule`) |
| `var-in-script-tag` (G) | 5 | **0** (Makefile `--exclude-rule`) |
| `plaintext-http-link` (H) | 1 | **0** (Makefile `--exclude-rule`) |
| `template-unescaped-with-safe` (B) | 17 | **17** (deliberately left for S03) |
| **Total raw findings** | **90** | **17** (all Class B) |

After S01, `make security-sast` (which runs Semgrep WITH the four template-noise excludes) reports exactly **17 blocking findings — all Class B (`template-unescaped-with-safe`)**. S03 will silence those template-side and that count will go to zero.

> Note: the design doc and prompt referenced "16" Class B findings; the actual raw baseline is **17**. The discrepancy is one extra `| safe` site that has appeared since the prompt was written (most likely `dashboard/templates/pdf/doc_pdf.html:172` or `dashboard/templates/research_detail.html:131`). It does not affect S01 correctness — S01 is not responsible for Class B. S03 should be told to expect 17, not 16.

## What was done, in detail

### Class A — `subprocess-shell-true` (12 sites)

Twelve `shell=True,` lines now carry **both** `# nosec B602` **and** a same-line `# nosemgrep: python.lang.security.audit.subprocess-shell-true.subprocess-shell-true — <site-specific rationale>`. The eight sites that were already showing up in baseline got fresh `# nosemgrep` markers appended after the existing `# nosec`. The four sites in `orch/test_runner.py` had a malformed multi-line `# nosemgrep:` (rule on a continuation line — semantically invalid but accidentally suppressed everything on the line) that I replaced with the canonical single-line form, also adding `# nosec B602` to make those four sites consistent with the other eight Class A sites in the codebase.

Sites:

- `dashboard/routers/staleness.py:178`
- `orch/archive/batch_archiver.py:325`
- `orch/daemon/batch_manager.py:875` and `:1302`
- `orch/daemon/browser_env.py:421` and `:650`
- `orch/daemon/doc_job_poller.py:248`
- `orch/daemon/fix_cycle.py:1258`
- `orch/test_runner.py:115`, `:339`, `:399`, `:649` (post-edit line numbers; the malformed multi-line form was removed so line numbers shifted up by ~3 each)

### Class D — Jinja autoescape (n/a)

The prompt referenced `orch/daemon/worktree_compose.py:219` with `autoescape=False`. The current code is `autoescape=jinja2.select_autoescape()` (the unsafe pattern was already replaced upstream — likely in CR-00050 or a prior CR). The Semgrep rule does not fire on this line, so no suppression is needed. The Makefile previously excluded `incorrect-autoescape-disabled` project-wide; that exclude has been removed because there is nothing to silence.

### Class E — `python-logger-credential-disclosure` (2 sites)

Both `logger.warning(...)` calls in `orch/rag/chat_repo.py:53` and `:63` had `# noqa: B701` already; both now also carry `# nosemgrep: ... — false positive: only a tiktoken model identifier is logged, never a credential` on the same line. `make format` did not reformat these — `ruff` is happy with the trailing comment on the `logger.warning(` line.

### Makefile — project-wide excludes (Class C/F/G/H)

`Makefile`'s `security-sast:` target previously had **eight** `--exclude-rule` flags (the four template-noise rules plus the four Python rules that should be silenced per-line). The four Python excludes were removed, leaving only:

- `generic.html-templates.security.unquoted-attribute-var.unquoted-attribute-var` (Class C — 26 sites at `write_button_attrs` callsites)
- `generic.html-templates.security.var-in-href.var-in-href` (Class F — 31 sites)
- `generic.html-templates.security.var-in-script-tag.var-in-script-tag` (Class G — 5 sites)
- `html.security.plaintext-http-link.plaintext-http-link` (Class H — 1 site)

A rationale comment block was added immediately above the `security-sast:` target enumerating each excluded rule, the finding count, and why per-line annotation is not the right tool. The block names the invariant test that locks the macro's constant-output contract (`tests/unit/test_db_guard_macro.py`, to be added by S05).

### Documentation

`docs/IW_AI_Core_Testing_Strategy.md` — appended a new H2 section "11. Semgrep finding triage (CR-00051)" after the existing "10. Quick reference" section. It documents:

- Bandit `# nosec` does NOT silence Semgrep — the marker is `# nosemgrep: <rule-id>`.
- In-macro `{# nosemgrep #}` does NOT propagate to call-site analyses (empirically verified during CR-00051).
- Canonical comment syntax for Python, Jinja2, and Makefile-level suppressions.
- Four reasons to suppress rather than fix: confirmed FP, trusted-source rendering, deliberate-but-audited pattern, project-wide structural FP.
- Every per-line suppression carries a same-line rationale after an em-dash; every Makefile `--exclude-rule` carries a rationale comment block above the target.

The section is ~38 lines. The Quick reference section above it is untouched.

## Files changed (11)

- `dashboard/routers/staleness.py` — 1 line: same-line `# nosemgrep`
- `orch/archive/batch_archiver.py` — 1 line
- `orch/daemon/batch_manager.py` — 2 lines
- `orch/daemon/browser_env.py` — 2 lines
- `orch/daemon/doc_job_poller.py` — 1 line
- `orch/daemon/fix_cycle.py` — 1 line
- `orch/test_runner.py` — 4 sites cleaned up (each site was previously a 4-line malformed multi-line `# nosemgrep:`; now each is the canonical single-line form, total net -8 lines)
- `orch/rag/chat_repo.py` — 2 lines: same-line `# nosemgrep` appended after `# noqa: B701`
- `orch/daemon/worktree_compose.py` — **not modified** (autoescape line was already `select_autoescape()`; rule doesn't fire)
- `Makefile` — `security-sast:` target: 8 `--exclude-rule` flags reduced to 4 (Class C/F/G/H only); rationale comment block added immediately above the target
- `docs/IW_AI_Core_Testing_Strategy.md` — appended H2 section "11. Semgrep finding triage (CR-00051)"

## Quality gates

| Gate | Result |
|---|---|
| `make format` | 682 files already formatted — no changes |
| `make lint` | ruff + check_templates.py + lint-js — all checks passed |
| `make typecheck` | mypy on `orch/` + `dashboard/` — 241 files, no issues |
| `make security-sast` | 17 blocking findings remain (all Class B, deferred to S03); 0 Class A/D/E/F/G/H — gate exits non-zero as expected (it's the very gate this CR exists to drive green; the final pass happens at S11 after S03 silences Class B) |

Targeted smoke tests on touched files (`tests/unit/test_archive.py`, `test_batch_archiver.py`, `test_test_runner.py`, `tests/unit/staleness/`, `tests/unit/daemon/test_worktree_compose.py`, `tests/unit/rag/test_chat_repo_enqueue.py`): **212 passed** in 1.71s.

## Observations / notes for S02 (CodeReview) and S03 (Frontend)

1. **Test-runner divergence**: `orch/test_runner.py` originally lacked `# nosec B602` on its four `shell=True,` lines. The prompt assumed all 12 Class A sites carried `# nosec B602`; in reality only 8 did. I added `# nosec B602` to the four `test_runner.py` sites to make all 12 Class A sites consistent. This is a no-behavior change (the marker is a Bandit suppression comment) but reviewer should confirm this minor extension is acceptable. The alternative — leaving the four sites without `# nosec B602` — would have created an asymmetry where the "both markers" pattern documented in the new triage doc section did not hold for one file.
2. **Class D doesn't exist anymore**: `worktree_compose.py:219` no longer matches the unsafe `autoescape=False` pattern (it's `select_autoescape()`). The Makefile previously excluded the rule project-wide; removing that exclude is safe because the rule does not fire on the codebase. If a future change re-introduces `autoescape=False`, Semgrep will catch it.
3. **Class B count is 17, not 16**: S03's prompt may state the count as 16. The actual raw count is 17. S03 should not be alarmed.
4. **No `--exclude-rule template-unescaped-with-safe`**: I removed that exclude from the Makefile in anticipation of S03 silencing the rule per-line in templates. If S03 cannot silence all 17, the gate will stay red — by design.

## Subagent result contract

```json
{
  "step": "S01",
  "agent": "Backend",
  "work_item": "CR-00051",
  "completion_status": "complete",
  "files_changed": [
    "dashboard/routers/staleness.py",
    "orch/archive/batch_archiver.py",
    "orch/daemon/batch_manager.py",
    "orch/daemon/browser_env.py",
    "orch/daemon/doc_job_poller.py",
    "orch/daemon/fix_cycle.py",
    "orch/test_runner.py",
    "orch/rag/chat_repo.py",
    "Makefile",
    "docs/IW_AI_Core_Testing_Strategy.md"
  ],
  "preflight": {
    "format": "ok",
    "typecheck": "ok",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "make security-sast: 17 blocking findings remain, all Class B (template-unescaped-with-safe), to be silenced by S03; Classes A/D/E/F/G/H all report 0 findings. 212 targeted unit tests on touched modules passed.",
  "tdd_red_evidence": "n/a — comments, Makefile flags, and doc-only edits, no production logic",
  "blockers": [],
  "notes": "Raw baseline pre-S01 had 90 Semgrep findings (8 firing Class A + 4 already silenced by malformed multi-line nosemgrep in test_runner.py = 12 Class A total; 0 Class D — rule no longer fires because worktree_compose.py:219 was already changed upstream to select_autoescape(); 2 Class E; 26 Class C; 31 Class F; 5 Class G; 1 Class H; 17 Class B). After S01: 17 Class B only. The design doc said 16 Class B — the actual baseline is 17; S03 should expect 17."
}
```
