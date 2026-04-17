# CR-00008 S11 — Final Cross-Agent Code Review

**Work Item**: CR-00008
**Step**: S11
**Agent**: code-review-final-impl

---

## Input Files

- `ai-dev/active/CR-00008/CR-00008_CR_Design.md`
- All reports: `ai-dev/active/CR-00008/reports/CR-00008_S0{1..10}_*_report.md`
- Full diff of:
  - `dashboard/routers/code_qa.py`
  - `dashboard/templates/project_code.html`
  - `dashboard/templates/base.html`
  - `dashboard/templates/chat/**`
  - `dashboard/static/chat/**`
  - `dashboard/static/chat.css`
  - `dashboard/static/vendor/**` (sampling; confirm LICENSES.md and folder structure)
  - `tests/dashboard/**`

## Output Files

- `ai-dev/active/CR-00008/reports/CR-00008_S11_CodeReviewFinal_report.md`

## Context

You review the implementation **as a whole** — the layer-specific reviews (S02/S04/S06/S08/S10) already inspected each slice. Your job is the cross-layer seams: does the API's wire format match the client's parser? Does the sanitizer actually reach every rendering path? Do the tests actually exercise the shipped contract? Are the acceptance criteria end-to-end satisfied, not just per-layer?

## Cross-agent review focus areas

### Contract seams

- [ ] API (S01) emits `event: token` / `event: citation` / `event: done` / `event: error` with the exact payload shapes the client (S03/S05) parses.
- [ ] Base64 encoding / decoding: server encodes with UTF-8 bytes; client decodes via `atob` + `TextDecoder("utf-8")`. Emoji / CJK cases are exercised by tests.
- [ ] Citation `n` ordering is preserved end-to-end: server emits monotonically increasing; client de-dupes by `n`; rendered `[N]` inline markers match.

### Rendering safety

- [ ] Every accumulation path in `render.js` sanitizes the **full buffer**, never a chunk.
- [ ] Every render call goes through DOMPurify **before** it hits the DOM.
- [ ] Mermaid upgrade (S07) is only invoked on `onDone` — never mid-stream.
- [ ] No `<script>` / `on*` attribute / `javascript:` link survives either pipeline.

### Security posture

- [ ] DOMPurify is present and pinned.
- [ ] Mermaid sandbox enforced.
- [ ] All outbound links `rel="noopener noreferrer"`.
- [ ] CSP-aligned: no inline `<script>` blocks in templates beyond what's already in `base.html`.
- [ ] Image stub: no bytes persisted.

### Licensing (OSS-only contract)

- [ ] `dashboard/static/vendor/LICENSES.md` lists every vendored library with SPDX ID + source URL + version.
- [ ] No GPL / AGPL / LGPL code.
- [ ] EPL-2.0 (ELK loader) notices preserved verbatim.

### Accessibility end-to-end

- [ ] `role="log"` / `aria-live="polite"` / `aria-relevant="additions"` on the message list.
- [ ] Per-token announcement disabled (announce on complete).
- [ ] Every action button is a real `<button>`, 44×44 hit target, visible focus.
- [ ] Keyboard coverage: Cmd+\, `/`, Esc, Cmd+Enter, Shift+Enter all behave as designed.

### Acceptance-criteria coverage

Walk AC1…AC15; for each, cite the exact test(s) and implementation file(s) that satisfy it. Any AC not fully covered is a **CRITICAL** finding.

### Hygiene

- [ ] `make quality` passes (ruff + mypy).
- [ ] `make test-unit` passes.
- [ ] `make test-integration` passes.
- [ ] No stale files: `dashboard/templates/fragments/code_qa_panel.html` is deleted; `base.html` has no `marked` / CDN residue.
- [ ] No dead code or TODO markers from S03 placeholders (every TODO(S05) / TODO(S07) must be resolved).

## Severity

- **CRITICAL** — any cross-layer contract break, XSS-surface, missing AC coverage, GPL residue.
- **HIGH** — layer-level fix needed that slipped through S02/S04/S06/S08/S10.
- **MEDIUM/LOW** — polish.

## Verdict block

```
## Verdict
- Gating issues (CRITICAL+HIGH): N
- Non-gating issues (MEDIUM+LOW): N
- Ready for final fix (S12): yes|no
```

## Subagent Result Contract

```json
{
  "step": "S11",
  "agent": "code-review-final-impl",
  "work_item": "CR-00008",
  "completion_status": "complete",
  "findings": {"critical": 0, "high": 0, "medium": 0, "low": 0},
  "ac_coverage": {"AC1": "covered", "AC2": "covered", "...": "..."},
  "blocking_next_step": false,
  "notes": ""
}
```
