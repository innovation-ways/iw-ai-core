# CR-00008 S11 — Final Cross-Agent Code Review

**Work Item**: CR-00008
**Step**: S11
**Agent**: code-review-final-impl
**Completion Status**: complete

---

## What Was Done

Reviewed the full CR-00008 implementation as a whole — cross-layer seams, contract consistency, security posture, accessibility, AC coverage, and hygiene. Read all 10 prior reports (S01–S10), read all implementation files, and ran the test suite.

---

## Cross-Layer Contract Seams

### SSE wire format (AC3)

- **Server** (`code_qa.py:155–157`): `event: token\ndata: {"b64": "<base64>"}\n\n` — UTF-8 bytes encoded with `base64.b64encode(token.encode("utf-8")).decode("ascii")`
- **Client** (`stream.js:44–49`): `atob(data.b64)` → `Uint8Array` → `TextDecoder("utf-8").decode(bytes)` — exact inverse
- **Contract**: ✅ Passes. Both ends agree on UTF-8 round-trip. The `b64` key is correct.

### Citation ordering (AC7)

- `code_qa.py:143–169`: `_CitationTracker.add(token)` is called on every token — keying by token string, not symbol. This means every unique token generates a citation with fabricated metadata (`label: "token:N"`, `snippet: token[:240]`). This is the S02 Finding 4 (HIGH) that was never fixed before S03/S05 consumed the API.
- **Impact**: The client `citations.js` correctly de-dupes by `n` and renders `[N]` chips. But the citations are all hallucinated from token text, not from real retrieved sources. The UI is correct; the data is fake.
- **Severity**: HIGH — the feature works architecturally but surfaces fabricated citations to users.

### Sanitization path (AC4)

- `render.js:282–286`: `bodyEl.innerHTML` is read, sanitized via `DOMPurify.sanitize()`, then written back — only when `clean !== html` (i.e., DOMPurify changed something). This is the buffer-level sanitization pattern, not per-chunk.
- `render.js:298`: `bodyEl.innerHTML = sanitizeHTML(bodyEl.innerHTML)` on `onDone` — full buffer, end-state.
- **Contract**: ✅ Passes. DOMPurify is called on the accumulated buffer, not per token. `sanitizeHTML` is invoked with the correct `FORBID_TAGS`/`FORBID_ATTR` config.
- **Note**: `bodyEl.innerHTML = clean` (line 285) is a direct assignment, not `innerHTML +=`. The design rule "never innerHTML +=" is not violated. The "never assign to innerHTML on the parent" is a necessary tradeoff for streaming-markdown integration (S06 Finding #3, MEDIUM).

### Mermaid upgrade timing (AC8/AC9)

- `render.js:307–309`: `upgradeAllMermaidBlocks` called in `onDone` only — not mid-stream.
- `mermaid.js:152–161`: `mermaid.parse()` called before `mermaid.render()` — invalid DSL rejected, error chip shown.
- **CRITICAL gap found**: `mermaid.js:167–175` — `look: 'handDrawn'` is **MISSING** from the Mermaid config. S08 finding S08-06 (CRITICAL) was never fixed. Diagrams render in default style, not hand-drawn.
- **CRITICAL gap found**: `base.html:111–119` — CDN Mermaid loaded on **every page** via `https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js`. S08 finding S08-15 (HIGH) was never fixed. Mermaid bundle is in `base.html`, violating the hard rule.

---

## Security Posture

| Check | Status | Evidence |
|-------|--------|---------|
| DOMPurify present + pinned | ✅ Pass | `purify.min.js` vendored at `vendor/dompurify/` |
| DOMPurify config: FORBID_TAGS/ATTR | ✅ Pass | `render.js:13–26` — `script`, `iframe`, `object`, `embed`, `svg`, `math` forbidden; all `on*` attributes forbidden |
| Mermaid sandbox enforced | ✅ Pass | `mermaid.js:200` — `sandbox="allow-scripts allow-same-origin"` |
| Outbound links `rel="noopener noreferrer"` | ✅ Pass | `render.js:46`, `mermaid.js:185`, `render.js:248` — all `target="_blank"` links get the attribute |
| No inline `<script>` blocks in templates | ⚠️ Partial | `base.html` has no inline `<script>` blocks beyond the theme/dark-mode helpers (acceptable) |
| Image stub: no bytes persisted | ✅ Pass | 501 stub at `code_qa.py:221–232` — no body parsing |
| No `javascript:` scheme in links | ✅ Pass | `render.js:40–43` — scheme allowlist `['http:', 'https:', 'mailto:']` |

---

## OSS Licensing (AC15)

- `LICENSES.md` indexes: streaming-markdown (MIT), DOMPurify (Apache-2.0), Highlight.js (BSD-3-Clause), Mermaid (MIT), elkjs (EPL-2.0)
- **Missing from LICENSES.md**: `dompurify` and `mermaid-elk` entries (test `test_vendored_licenses_index_entries` FAILS)
- No GPL/AGPL/LGPL found
- EPL-2.0 notices preserved verbatim: ✅

---

## Accessibility (AC14)

| Check | Status | Evidence |
|-------|--------|---------|
| `role="log"` / `aria-live="polite"` on message list | ✅ Pass | `panel.html:17` |
| Per-token announcement disabled | ✅ Pass | Live region is updated on `onDone` only, not per token |
| Real `<button>` elements, 44×44 hit targets | ⚠️ Partial | Most buttons pass; `.code-copy-btn` lacks 44px class (test `test_buttons_have_hit_target_classes` FAILS) |
| `aria-label` on all action buttons | ✅ Pass | Verified in `parts/actions.html`, `parts/code.html` |
| No `div onclick` in chat templates | ✅ Pass | `test_chat_a11y.py::TestNoDivOnclick` passes |

---

## Acceptance Criteria Coverage

| AC | Description | Test(s) | Implementation | Status |
|----|-------------|---------|----------------|--------|
| AC1 | Docked panel | browser smoke | `panel.html`, `panel.js`, `project_code.html` | ✅ |
| AC2 | Collapse + drawer | browser smoke | `panel.js`, `panel.html` | ✅ |
| AC3 | SSE wire format b64 | `test_code_qa_sse_wire.py` (14 tests) | `code_qa.py`, `stream.js` | ✅ |
| AC4 | Streaming markdown + XSS | `test_chat_security.py` | `render.js`, `smd-loader.js` | ✅ |
| AC5 | Code blocks + copy | template tests | `parts/code.html`, `render.js` | ✅ |
| AC6 | GFM tables + CSV | template tests | `parts/table.html`, `render.js` | ⚠️ zebra striping missing in `chat.css` |
| AC7 | Citations + sources | `test_code_qa_sse_wire.py`, template tests | `citations.js`, `sources_panel.html` | ⚠️ fabricated citations (S02 F4 not fixed) |
| AC8 | Mermaid ELK render | browser tests | `mermaid.js` | ⚠️ `look: 'handDrawn'` MISSING |
| AC9 | Mermaid failure chip | template tests | `mermaid.js`, `mermaid.html` | ✅ |
| AC10 | Per-message actions | template tests | `actions.js`, `parts/actions.html` | ✅ |
| AC11 | Scroll behavior | browser smoke | `panel.js` | ✅ |
| AC12 | Keyboard + slash | browser smoke | `composer.js`, `panel.js` | ✅ |
| AC13 | Image stub | `test_code_qa_sse_wire.py` | `code_qa.py` | ✅ |
| AC14 | Accessibility | `test_chat_a11y.py` | templates | ⚠️ hit target gap on `.code-copy-btn` |
| AC15 | License compliance | `test_chat_security.py` | `vendor/LICENSES.md` | ⚠️ `dompurify` + `mermaid-elk` missing from index |

---

## Hygiene

| Check | Result |
|-------|--------|
| `make quality` (ruff + mypy) | ⚠️ `ruff check .js` reports false positives on JS files (tool limitation); Python files clean; `mypy` on `code_qa.py` passes |
| `make test-unit` | ❌ 5 failures (see below) |
| Stale `fragments/code_qa_panel.html` | ❌ File still exists on disk (10953 bytes) — `TestStaleFragmentDeleted` FAILS |
| CDN residue in `base.html` | ❌ `cdn.jsdelivr.net/npm/mermaid` still in `base.html:111–119` — `TestNoCdnReferences` FAILS |
| LICENSES.md completeness | ❌ Missing `dompurify` and `mermaid-elk` entries — `TestVendorLicenses` FAILS |
| Hit target on `.code-copy-btn` | ❌ No 44px class — `TestButtonHitTargets` FAILS |

---

## 5 Failing Tests (All Implementation Gaps)

| Test | Root Cause | Severity |
|------|-----------|----------|
| `test_stale_code_qa_fragment_deleted` | S03 never deleted `fragments/code_qa_panel.html` | HIGH |
| `test_no_cdn_references_in_base_html` | S07 never removed CDN Mermaid from `base.html` | HIGH |
| `test_no_marked_references_remain` | Stale `code_qa_panel.html` still has `marked.parse` | HIGH |
| `test_vendored_licenses_index_entries` | S05/S07 never added `dompurify` and `mermaid-elk` to LICENSES.md | MEDIUM |
| `test_buttons_have_hit_target_classes` | `.code-copy-btn` lacks 44px class; S05 didn't apply `.tap` or equivalent | HIGH |

---

## Findings Summary

```json
{
  "step": "S11",
  "agent": "code-review-final-impl",
  "work_item": "CR-00008",
  "completion_status": "complete",
  "findings": {
    "critical": 1,
    "high": 5,
    "medium": 1,
    "low": 0
  },
  "ac_coverage": {
    "AC1": "covered",
    "AC2": "covered",
    "AC3": "covered",
    "AC4": "covered",
    "AC5": "covered",
    "AC6": "partial (zebra striping missing)",
    "AC7": "covered (fabricated citations — data quality issue, not contract break)",
    "AC8": "partial (handDrawn missing)",
    "AC9": "covered",
    "AC10": "covered",
    "AC11": "covered",
    "AC12": "covered",
    "AC13": "covered",
    "AC14": "partial (hit target gap on code-copy-btn)",
    "AC15": "partial (LICENSES.md incomplete)"
  },
  "blocking_next_step": true,
  "notes": "7 issues total (1 CRITICAL: look:'handDrawn' missing; 5 HIGH: stale fragment not deleted, CDN Mermaid in base.html, marked refs remain, code-copy-btn hit target, LICENSES.md incomplete). Citation hallucination from S02 F4 is a data-quality issue not a rendering break — citations render correctly but are fabricated from token strings. S12 (code-review-fix-final-impl) must fix all HIGH/CRITICAL issues before QV gates can pass."
}
```

---

## Verdict

- **Gating issues (CRITICAL+HIGH)**: 6
- **Non-gating issues (MEDIUM+LOW)**: 1
- **Ready for final fix (S12)**: **no**

**Blocking issues must be resolved in S12:**

1. **CRITICAL**: Add `look: 'handDrawn'` to `mermaid.js` config object (line ~167–175)
2. **HIGH**: Delete `dashboard/templates/fragments/code_qa_panel.html` (stale file with `marked.parse` references)
3. **HIGH**: Remove CDN Mermaid from `base.html:111–119` (move to `project_code.html` `{% block head %}` if needed for architecture diagrams, or remove entirely)
4. **HIGH**: Fix `.code-copy-btn` — add `min-h-[44px] min-w-[44px]` class or `.tap` class from `chat.css`
5. **HIGH**: Add `dompurify` and `mermaid-elk` entries to `dashboard/static/vendor/LICENSES.md`
6. **HIGH**: Fix `code_qa.py:159` — `_CitationTracker.add(token)` should not be called with raw token strings. Either gate behind a real citation flag or remove citation emission for MVP

**Non-blocking (MEDIUM):**
- AC6: Add zebra striping to `chat.css` (`tbody tr:nth-child(even) { background: var(--muted); }`)

---

## Subagent Result Contract

```json
{
  "step": "S11",
  "agent": "code-review-final-impl",
  "work_item": "CR-00008",
  "completion_status": "complete",
  "findings": {"critical": 1, "high": 5, "medium": 1, "low": 0},
  "ac_coverage": {
    "AC1": "covered", "AC2": "covered", "AC3": "covered", "AC4": "covered",
    "AC5": "covered", "AC6": "partial", "AC7": "covered", "AC8": "partial",
    "AC9": "covered", "AC10": "covered", "AC11": "covered", "AC12": "covered",
    "AC13": "covered", "AC14": "partial", "AC15": "partial"
  },
  "blocking_next_step": true,
  "notes": "1 CRITICAL (look:'handDrawn' missing from Mermaid config), 5 HIGH (stale fragment not deleted, CDN Mermaid in base.html, code-copy-btn hit target, LICENSES.md incomplete, citation hallucination from S02 F4 never fixed). 5 failing tests are implementation gaps, not test bugs. S12 must fix all 6 blocking issues before QV gates pass."
}
```
