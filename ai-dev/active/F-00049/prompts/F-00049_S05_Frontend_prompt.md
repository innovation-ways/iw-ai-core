# F-00049_S05_Frontend_prompt

**Work Item**: F-00049 — Code Understanding: Q&A Panel (SSE Streaming)
**Step**: S05
**Agent**: frontend-impl

---

## Input Files

- `ai-dev/active/F-00049/F-00049_Feature_Design.md` — Full design document (read this first)
- `ai-dev/work/F-00049/reports/F-00049_S01_Backend_report.md` — QAEngine interface (read to understand token format)
- `ai-dev/work/F-00049/reports/F-00049_S03_API_report.md` — Endpoint URL and SSE format (read before writing JS)
- `dashboard/templates/base.html` — Base layout (study existing head includes, script includes)
- `dashboard/templates/project_code.html` — Code tab template (you will modify this to include the panel)
- `dashboard/templates/fragments/code_job_status.html` — Existing vanilla JS EventSource pattern (study this)
- `dashboard/templates/fragments/nav_projects.html` — Existing fragment (reference only)
- `dashboard/CLAUDE.md` — Dashboard conventions (NON-NEGOTIABLE)
- `CLAUDE.md` — Project-level conventions (NON-NEGOTIABLE)

## Output Files

- `dashboard/templates/fragments/code_qa_panel.html` — New Q&A panel fragment
- `dashboard/templates/project_code.html` — Modified to include panel and `data-context-level` attrs
- `ai-dev/work/F-00049/reports/F-00049_S05_Frontend_report.md` — Step report

---

## Context

You are implementing the frontend for **F-00049: Code Understanding Q&A Panel**. This is a Jinja2 HTML fragment with embedded JavaScript. There is no TypeScript, no build step, and no external JS files. Tailwind CSS classes are loaded from CDN.

Before writing any code:
1. Read `dashboard/CLAUDE.md` — especially the gotchas section
2. Read `dashboard/templates/fragments/code_job_status.html` — to understand the existing vanilla JS + SSE pattern
3. Read `dashboard/templates/project_code.html` — to understand where to insert the panel and the `data-context-level` attribute

---

## Requirements

### 1. Fragment: dashboard/templates/fragments/code_qa_panel.html

**Critical rules**:
- This file MUST NOT contain `{% extends "base.html" %}` — it is a partial fragment
- All JS must be inline in the template — no external `.js` files
- No dynamic Tailwind class construction (e.g., no `"bg-" + color`) — only static class strings
- The `project_id` variable is available from the Jinja2 context (passed from `project_code.html`)

#### Panel HTML Structure

```html
{# Q&A Panel — included in project_code.html via {% include %} #}
<div id="qa-panel" class="border border-border rounded-lg bg-card mt-4">

  {# Header #}
  <div id="qa-panel-header"
       class="flex items-center justify-between px-4 py-3 cursor-pointer select-none"
       onclick="qaTogglePanel()">
    <div class="flex items-center gap-2">
      <span id="qa-toggle-icon" class="text-muted-foreground text-xs">▼</span>
      <span class="text-sm font-medium">Ask about this codebase</span>
    </div>
    <span id="qa-collapse-label" class="text-xs text-muted-foreground">collapse</span>
  </div>

  {# Body #}
  <div id="qa-panel-body" class="px-4 pb-4 border-t border-border">

    {# Conversation area #}
    <div id="qa-conversation"
         class="space-y-3 max-h-72 overflow-y-auto py-3 mb-3 min-h-[2rem]">
    </div>

    {# Context indicator #}
    <div class="text-xs text-muted-foreground mb-2">
      Context: <span id="qa-context-label" class="font-medium">Architecture</span>
    </div>

    {# Input row #}
    <div class="flex gap-2">
      <input id="qa-input"
             type="text"
             placeholder="Ask a question about the codebase..."
             class="flex-1 border border-border rounded-md px-3 py-1.5 text-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring"
             maxlength="1000" />
      <button id="qa-submit-btn"
              onclick="qaSubmit()"
              class="px-4 py-1.5 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:opacity-90 disabled:opacity-50">
        Ask →
      </button>
    </div>

  </div>
</div>
```

#### JavaScript (place in `<script>` tag at the end of the fragment, before closing `</div>`)

The script block must be a self-contained IIFE or use unique function names prefixed with `qa` to avoid collisions with other page scripts.

**State variables** (module-level via closure or `window` prefix):
```javascript
var qaHistory = [];          // Conversation history array: [{role, content}, ...]
var qaIsPanelCollapsed = false;
var qaBubbleCounter = 0;     // Unique ID counter for assistant bubbles
var QA_PROJECT_ID = "{{ current_project.id }}";
var QA_MAX_HISTORY = 10;     // MAX_HISTORY_TURNS * 2 = 10 messages
```

**Function: `qaTogglePanel()`**
```javascript
function qaTogglePanel() {
  qaIsPanelCollapsed = !qaIsPanelCollapsed;
  var body = document.getElementById('qa-panel-body');
  var icon = document.getElementById('qa-toggle-icon');
  var label = document.getElementById('qa-collapse-label');
  if (qaIsPanelCollapsed) {
    body.classList.add('hidden');
    icon.textContent = '▶';
    label.textContent = 'expand';
  } else {
    body.classList.remove('hidden');
    icon.textContent = '▼';
    label.textContent = 'collapse';
  }
}
```

**Function: `qaUpdateContextLabel()`** — reads the `data-context-level` from the page and updates the label.
```javascript
function qaUpdateContextLabel() {
  var root = document.getElementById('code-content-root');
  if (!root) return;
  var level = root.dataset.contextLevel || 'architecture';
  var modulePath = root.dataset.modulePath || '';
  var label = document.getElementById('qa-context-label');
  if (!label) return;
  if (level === 'module' && modulePath) {
    label.textContent = modulePath + ' module';
  } else {
    label.textContent = 'Architecture';
  }
}
```

Call `qaUpdateContextLabel()` on load and also listen for `htmx:afterSwap` to re-run it after navigation.

**Function: `qaAppendUserBubble(question)`** — appends a user message bubble to `#qa-conversation`.

**Function: `qaAppendAssistantBubble()`** — appends an empty assistant bubble and returns its text span element. Increment `qaBubbleCounter`.

**Function: `qaAppendErrorBubble(message)`** — appends an error bubble.

**Function: `qaSetLoading(isLoading)`** — disables/enables input and button; toggles button text between "Ask →" and "...".

**Function: `qaScrollBottom()`** — sets `document.getElementById('qa-conversation').scrollTop` to `scrollHeight`.

**Function: `qaSubmit()`** — the main submit handler:

```javascript
function qaSubmit() {
  var input = document.getElementById('qa-input');
  var question = input.value.trim();
  if (!question) return;

  // Read context from page
  var root = document.getElementById('code-content-root');
  var contextLevel = (root && root.dataset.contextLevel) || 'architecture';
  var contextDocId = (root && root.dataset.contextDocId) || null;
  var modulePath = (root && root.dataset.modulePath) || null;

  // Show user bubble
  qaAppendUserBubble(question);
  var responseSpan = qaAppendAssistantBubble();
  qaScrollBottom();
  qaSetLoading(true);
  input.value = '';

  // Build POST body
  var body = JSON.stringify({
    question: question,
    context_level: contextLevel,
    context_doc_id: contextDocId || null,
    module_path: modulePath || null,
    conversation_history: qaHistory
  });

  // POST with fetch, consume ReadableStream for SSE
  var fullResponse = '';
  fetch('/api/projects/' + QA_PROJECT_ID + '/code/qa', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: body
  }).then(function(response) {
    if (!response.ok) {
      responseSpan.textContent = 'Error: ' + response.status + ' ' + response.statusText;
      qaSetLoading(false);
      return;
    }
    var reader = response.body.getReader();
    var decoder = new TextDecoder();
    var buffer = '';

    function readChunk() {
      reader.read().then(function(result) {
        if (result.done) {
          qaSetLoading(false);
          return;
        }
        buffer += decoder.decode(result.value, {stream: true});
        // Parse SSE lines: split on \n, process "data: ..." lines
        var lines = buffer.split('\n');
        buffer = lines.pop(); // Keep incomplete last line in buffer
        lines.forEach(function(line) {
          if (!line.startsWith('data: ')) return;
          var jsonStr = line.slice(6);
          try {
            var data = JSON.parse(jsonStr);
            if (data.token !== undefined) {
              fullResponse += data.token;
              responseSpan.textContent += data.token;
              qaScrollBottom();
            } else if (data.event === 'done') {
              // Push to history
              qaHistory.push({role: 'user', content: question});
              qaHistory.push({role: 'assistant', content: data.full_response || fullResponse});
              // Trim history to QA_MAX_HISTORY
              if (qaHistory.length > QA_MAX_HISTORY) {
                qaHistory = qaHistory.slice(qaHistory.length - QA_MAX_HISTORY);
              }
              qaSetLoading(false);
            } else if (data.event === 'error') {
              responseSpan.parentElement.outerHTML = qaErrorBubbleHtml(data.message || 'Local AI unavailable. Check that Ollama is running.');
              qaSetLoading(false);
            }
          } catch (e) {
            // Ignore JSON parse errors for incomplete lines
          }
        });
        readChunk();
      }).catch(function(err) {
        responseSpan.textContent = 'Connection error.';
        qaSetLoading(false);
      });
    }
    readChunk();
  }).catch(function(err) {
    responseSpan.textContent = 'Failed to connect to server.';
    qaSetLoading(false);
  });
}
```

**Function: `qaErrorBubbleHtml(message)`** — returns an HTML string for an error bubble (used when replacing the assistant bubble on error).

**Enter key support**: Add a `keydown` event listener on `#qa-input` to call `qaSubmit()` when Enter is pressed and input is not disabled.

**On load**: Call `qaUpdateContextLabel()`. Listen for `htmx:afterSwap` events on `document.body` to re-call `qaUpdateContextLabel()` (in case Level 2 navigation swaps the `code-content-root` attributes).

#### Bubble HTML (generated by JS)

User bubble:
```html
<div class="bg-muted rounded-lg px-3 py-2 text-sm text-right ml-8">
  <span class="font-medium text-xs text-muted-foreground block mb-1">You</span>
  {question text — set via textContent, not innerHTML}
</div>
```

Assistant bubble:
```html
<div class="bg-background border border-border rounded-lg px-3 py-2 text-sm mr-8">
  <span class="font-medium text-xs text-muted-foreground block mb-1">Assistant</span>
  <span class="qa-response-text" id="qa-bubble-{N}"></span>
</div>
```

Error bubble:
```html
<div class="rounded-lg px-3 py-2 text-sm mr-8 bg-destructive/10 border border-destructive/20 text-destructive">
  ⚠ {message}
</div>
```

**Security note**: Always set user question text via `.textContent` (not `.innerHTML`) to prevent XSS. Token text also uses `.textContent +=` (appending to text node).

---

### 2. Modify: dashboard/templates/project_code.html

**Goal**: Add `data-context-level` attributes to a stable container element and include the Q&A panel.

Find the main content container in `project_code.html` (the div wrapping the architecture panel and job panel) and add:

```html
<div id="code-content-root"
     data-context-level="architecture"
     data-context-doc-id="{{ index_status.level1_doc_id | default('') }}"
     data-module-path="">
  {# ... existing content ... #}

  {# Q&A Panel at the bottom #}
  {% include "fragments/code_qa_panel.html" %}
</div>
```

If `project_code.html` already has a suitable root div, add the `id`, `data-context-level`, `data-context-doc-id`, and `data-module-path` attributes to it. Do not restructure the template layout.

---

## Browser Verification (Required)

After implementation, use `playwright-cli` to verify:

```bash
playwright-cli kill-all
playwright-cli open http://localhost:9900
# Navigate to a project's Code tab
playwright-cli snapshot
# Verify: "Ask about this codebase" panel is visible at the bottom
playwright-cli click "#qa-panel-header"
# Verify: panel collapses (body hidden)
playwright-cli click "#qa-panel-header"
# Verify: panel expands again
playwright-cli snapshot
# Verify: context label shows "Architecture"
```

---

## Project Conventions

- No `{% extends "base.html" %}` in fragment files
- No external JS files — all JS inline in the template
- No dynamic Tailwind class construction
- Use `textContent` (not `innerHTML`) for user-supplied text
- Tailwind utility classes only — no custom CSS
- Follow the existing pattern from `code_job_status.html` for vanilla JS + streaming

## Test Verification

After implementation, run all existing tests to ensure nothing is broken:

```bash
uv run pytest tests/unit/ -v
uv run pytest tests/integration/ -v --alluredir=allure-results
uv run ruff check dashboard/templates/  # If ruff template linting is configured
```

The template itself does not have unit tests (no JS test framework in this project). Verify correctness via browser verification above.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "frontend-impl",
  "work_item": "F-00049",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/fragments/code_qa_panel.html",
    "dashboard/templates/project_code.html"
  ],
  "tests_passed": true,
  "test_summary": "All existing tests pass; browser verification confirms panel renders and toggles",
  "blockers": [],
  "notes": ""
}
```
