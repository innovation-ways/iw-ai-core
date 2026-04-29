# F-00068: AI Chat Visual Improvements

**Type**: Feature
**Priority**: High
**Created**: 2026-04-29
**Status**: Draft

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that changes Docker container/volume/network state. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ No live DB migrations

No schema changes required for this feature.

---

## Description

The AI code chat panel currently renders responses as unstyled markdown — headings, blockquotes, and body text are visually indistinguishable, and the LLM produces prose walls instead of structured, scannable answers. This feature improves both layers: the `RENDERING_CAPABILITIES_BLOCK` in `orch/rag/qa.py` is updated to instruct the LLM to use callout syntax, structured headers, and concise bullets; the chat frontend (`chat.css` + `render.js`) is updated to render those callouts as colored admonition blocks and apply a prose hierarchy to `chat-message-body` content. The result is a chat experience that matches the visual quality of the doc system.

## Project Context

Read `CLAUDE.md` and `dashboard/CLAUDE.md`. Dashboard is FastAPI + Jinja2/htmx; chat frontend is vanilla JS in `dashboard/static/chat/`; RAG engine is in `orch/rag/qa.py`.

---

## Scope

### In Scope

- **`RENDERING_CAPABILITIES_BLOCK` update** (`orch/rag/qa.py`): add callout syntax guidance (`> [!NOTE]`, `> [!WARNING]`, `> [!DANGER]`, `> [!TIP]`), structured response instructions (use H2/H3 for multi-topic answers, bullets for lists ≥3 items), and anti-prose-wall rule
- **`chat-message-body` prose styles** (`dashboard/static/chat.css`): H1/H2/H3 hierarchy (weight + color + size), code blocks, inline code, blockquotes, bullet/numbered lists, paragraph spacing — compact for chat panel width
- **Callout CSS in chat** (`dashboard/static/chat.css`): same 5-type semantic palette as F-00067 canonical spec (note/tip/warning/danger/important), scoped to `.chat-message-body`
- **Callout JS parser in chat** (`dashboard/static/chat/render.js`): `iwProcessChatCallouts(container)` function called after markdown is rendered into `.chat-message-body`, detects `> [!TYPE]` blockquotes and converts to styled callout divs
- **DOMPurify allowlist update** (`dashboard/static/chat/render.js`): ensure `callout`, `callout-header`, `callout-body`, `callout-icon`, `callout-label` CSS classes are allowed (DOMPurify currently strips unknown classes)

### Out of Scope

- Changing the Ollama model or RAG retrieval logic
- Chat history persistence or conversation threading
- Shared callout CSS file (each page has its own scoped styles — no shared file created in this feature)
- Docs page callout rendering (handled in F-00067)
- Mobile/responsive chat layout changes

---

## Canonical Callout Spec (from F-00067 — must match exactly)

```css
/* Callout types and colors — identical to F-00067 */
note:      border #3B82F6, bg #EFF6FF,  label #1D4ED8, icon ℹ️
tip:       border #10B981, bg #ECFDF5,  label #065F46, icon 💡
warning:   border #F59E0B, bg #FFFBEB,  label #92400E, icon ⚠️
danger:    border #EF4444, bg #FEF2F2,  label #991B1B, icon 🚨
important: border #8B5CF6, bg #F5F3FF,  label #4C1D95, icon 📌
```

---

## Response Style Instructions (canonical — for `RENDERING_CAPABILITIES_BLOCK`)

Add to the existing `RENDERING_CAPABILITIES_BLOCK` in `qa.py`:

```
- Callouts — use GitHub-style blockquote callouts for special content:
  > [!NOTE] supplementary context that doesn't interrupt flow
  > [!TIP] best practice or shortcut worth highlighting
  > [!WARNING] behavior the reader must not miss
  > [!DANGER] destructive or breaking behavior — use sparingly
  The chat UI renders these as colored admonition blocks. Use [!WARNING] when
  describing a footgun or a non-obvious constraint. Never use [!DANGER] for
  normal informational notes.
- Structure — for answers covering multiple topics, use H2 or H3 headings to
  separate sections. Use bullet lists for any enumeration of 3+ items. Avoid
  dense paragraphs when a list would be clearer. Do not start every answer with
  a heading — only use them when the response has ≥2 distinct sections.
```

---

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | `backend-impl` | Update `RENDERING_CAPABILITIES_BLOCK` in `orch/rag/qa.py` | S02 |
| S02 | `frontend-impl` | `chat.css`: prose styles + callout CSS; `render.js`: callout JS parser + DOMPurify allowlist | S01 |
| S03 | `code-review-impl` | Review S01 | — |
| S04 | `code-review-impl` | Review S02 | S03 |
| S05 | `tests-impl` | Unit tests: system prompt content; dashboard tests: callout CSS in rendered HTML | — |
| S06 | `code-review-impl` | Review S05 | — |
| S07 | `code-review-final-impl` | Global cross-layer review | — |
| S08 | `qv-gate` | lint | — |
| S09 | `qv-gate` | format | — |
| S10 | `qv-gate` | typecheck | — |
| S11 | `qv-gate` | unit-tests | — |
| S12 | `qv-gate` | integration-tests | — |
| S13 | `qv-browser` | Browser verification | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None

### API Changes

- **New endpoints**: None
- **Modified endpoints**: None

### Frontend Changes

- **Modified files**:
  - `dashboard/static/chat.css` — prose + callout styles for `.chat-message-body`
  - `dashboard/static/chat/render.js` — `iwProcessChatCallouts()` + DOMPurify allowlist update

---

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `ai-dev/active/F-00068/F-00068_Feature_Design.md` | Design | This document |
| `ai-dev/active/F-00068/workflow-manifest.json` | Manifest | Step definitions |
| `ai-dev/active/F-00068/prompts/F-00068_S01_Backend_prompt.md` | Prompt | System prompt update |
| `ai-dev/active/F-00068/prompts/F-00068_S02_Frontend_prompt.md` | Prompt | Chat CSS + JS callout parser |
| `ai-dev/active/F-00068/prompts/F-00068_S03_CodeReview_Backend_prompt.md` | Prompt | Review S01 |
| `ai-dev/active/F-00068/prompts/F-00068_S04_CodeReview_Frontend_prompt.md` | Prompt | Review S02 |
| `ai-dev/active/F-00068/prompts/F-00068_S05_Tests_prompt.md` | Prompt | Tests |
| `ai-dev/active/F-00068/prompts/F-00068_S06_CodeReview_Tests_prompt.md` | Prompt | Review S05 |
| `ai-dev/active/F-00068/prompts/F-00068_S07_CodeReview_Final_prompt.md` | Prompt | Global review |
| `ai-dev/active/F-00068/prompts/F-00068_S13_BrowserVerification_prompt.md` | Prompt | Browser verification |
| `orch/rag/qa.py` | Modified | `RENDERING_CAPABILITIES_BLOCK` update |
| `dashboard/static/chat.css` | Modified | Prose + callout styles |
| `dashboard/static/chat/render.js` | Modified | Callout parser + DOMPurify |

---

## Acceptance Criteria

### AC1: LLM uses callouts in responses

```
Given the system prompt includes callout syntax instructions
When the LLM produces a response mentioning a non-obvious constraint or warning
Then the response includes a > [!WARNING] or > [!DANGER] callout block (not inline text)
```

*Note: AC1 is not mechanically verifiable — validate by manual inspection during browser verification.*

### AC2: Callout blocks render correctly in chat

```
Given a chat response containing "> [!WARNING] some warning text"
When the response is rendered in the chat panel
Then the blockquote is converted to a div.callout.callout-warning with amber border and ⚠️ icon
And plain blockquotes (without [!TYPE]) continue to render as styled blockquotes, not as callouts
```

### AC3: Chat-message-body headings are visually distinct

```
Given a chat response containing H2 and H3 headings
When the response is rendered in chat-message-body
Then H2 has font-weight 600 and is visually larger than H3
And H3 has a muted color, visually distinct from H2
And all headings are compact enough to fit the chat panel width
```

### AC4: Inline code and code blocks are styled

```
Given a chat response containing inline `code` and a fenced code block
When rendered in chat-message-body
Then inline code has a tinted background and monospace font
And fenced code blocks have a distinct background, border, and syntax highlighting (if hljs is loaded)
```

### AC5: DOMPurify allows callout class names

```
Given a callout div with class="callout callout-warning" is produced by the parser
When sanitizeHTML() is called on the HTML
Then the div and its classes survive sanitization (not stripped)
```

---

## Boundary Behavior

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| Unknown callout type `> [!CUSTOM]` | Non-standard type | Falls back to styled blockquote — no blank div, no crash |
| Multi-line callout body | `> [!NOTE]\n> line1\n> line2` | Both lines appear in callout-body |
| Nested blockquote `> > text` | Standard Markdown nesting | Renders as nested blockquote — no false callout detection |
| Response with only H1 | LLM uses H1 for title | H1 styled correctly, no layout break in narrow panel |
| Empty callout body `> [!TIP]` | No text after the type | Renders empty callout-body div — no crash |
| DOMPurify strips custom classes | Existing sanitizer behavior | `sanitizeHTML()` allowlist updated to pass callout classes |

---

## Invariants

1. Plain blockquotes (no `[!TYPE]`) are never converted to callouts — the parser requires the exact `[!TYPE]` prefix on the first `<p>` inside the blockquote.
2. `iwProcessChatCallouts()` is called only after the markdown has been fully rendered into the DOM (not during streaming).
3. The `sanitizeHTML()` allowlist in `render.js` explicitly permits `callout`, `callout-header`, `callout-body`, `callout-icon`, `callout-label` class names.
4. The callout hex color values in `chat.css` exactly match the F-00067 canonical palette.
5. Prose styles in `chat.css` are scoped to `.chat-message-body` — no global style leakage.

---

## Dependencies

- **Depends on**: F-00067 (canonical callout spec and color palette — F-00068 must use identical colors)
- **Blocks**: None

---

## TDD Approach

- **Unit tests** (`tests/unit/test_qa_system_prompt.py`):
  - Assert `RENDERING_CAPABILITIES_BLOCK` contains `[!NOTE]` and `[!WARNING]` strings
  - Assert it contains "bullet lists" or "H2" or "headings" instruction
  - Assert `_build_system_prompt()` includes the capabilities block in its return value
- **Dashboard tests** (`tests/dashboard/test_chat_callouts.py`):
  - Render a mock chat message with `> [!WARNING] text` via the message template
  - Assert resulting HTML contains `class="callout callout-warning"`
  - Assert plain `> blockquote` does NOT gain callout class (parser is in JS, so this test may be limited to template structure only)
- **Edge cases**: unknown type, multi-line body, empty body, DOMPurify class passthrough

---

## Notes

- The `iwProcessChatCallouts()` function in `render.js` is intentionally separate from `iwProcessCallouts()` in `docs_detail.html` (added by F-00067). They are identical in logic but scoped separately. A future refactor could extract to a shared `dashboard/static/callouts.js` utility — but that is out of scope here.
- The callout JS parser must run AFTER `iwRenderMermaid()` to avoid interfering with diagram blocks.
- Chat panel has a fixed width (~400px) — heading font sizes must be smaller than doc page. H2 → 1rem (not 1.2rem), H3 → 0.9rem (not 1rem).
- The `RENDERING_CAPABILITIES_BLOCK` is a Python class attribute on `QAEngine`. The update is additive — do not remove existing Mermaid/D2/table/code instructions, only append the new callout + structure sections.
