---
description: Fast inline research using web search and fetch — answers directly in the conversation without saving a document or allocating an ID. Use when asked a quick research question, "what is X", "is Y still maintained", "compare A vs B briefly", or "/iw-research-quick". For research that should be filed as a project document, use /iw-research instead.
---

# IW Research Quick

Fast inline research — no file, no ID, no workflow overhead.

**Topic**: $ARGS

---

## Workflow

1. **Get topic** — Extract from $ARGS or ask user a single clarifying question
2. **context7 (optional)** — If topic is a library/framework, try `mcp__context7__resolve-library-id` first for current official docs
3. **WebSearch** — Run 2–3 targeted queries to identify best sources
4. **WebFetch** — Fetch up to 4 pages maximum; extract targeted answers only
5. **Respond inline** — Direct answer (2–3 paragraphs) with:
   - `[HIGH/MEDIUM/LOW]` confidence marker
   - Inline source citations per factual claim
   - `Sources` section at the end
6. **Upgrade nudge** — If topic warrants deeper investigation, suggest `/iw-research {topic}`

---

## When to Use context7

**Use context7 when** the topic is a **library or framework** and you want current official documentation:

```
mcp__context7__resolve-library-id <library-name>
mcp__context7__query-docs <library-id> <query>
```

**Do NOT use context7** for general topics (companies, concepts, market research, opinions, etc.).

If context7 is unavailable or returns no results, fall back to WebSearch + WebFetch only.

---

## Max 4 WebFetch Calls

**Hard limit: 4 WebFetch calls per invocation.**

Prioritize:
1. Official documentation (docs page, API reference)
2. Primary source (author blog, official announcement)
3. Credible secondary (well-known blog, reputable publication)

Skip: forums, Reddit threads, low-quality summaries.

If 4 fetches are not enough to answer confidently, the topic likely warrants `/iw-research` instead.

---

## Output Format

```markdown
## Quick Research: {topic}

{direct answer paragraph 1 with [source](url) inline}

{direct answer paragraph 2 with [source](url) inline if needed}

**Confidence**: [HIGH/MEDIUM/LOW]

**Sources**
- [Page Title](url) — credibility note
- [Page Title](url) — credibility note
```

**Rules**:
- Every factual claim must have an inline `[source](url)` citation
- `**Confidence**` line is mandatory
- `**Sources**` section is mandatory — list all URLs fetched
- No file is created; answer is fully inline

---

## Upgrade Suggestion Triggers

Suggest `/iw-research {topic}` when ANY of:

| Trigger | Example |
|---------|---------|
| Topic has >3 main questions | "research all queue systems for 4M/month volume" |
| User asks for depth/comparison | "evaluate all options comprehensively" |
| Findings contradict each other | Sources disagree on key facts |
| Topic warrants synthesis | "advantages and disadvantages of each approach" |

**Suggested phrasing**:
> This looks like a topic worth filing as a proper document. Run `/iw-research {topic}` for a full investigation.

---

## Confidence Levels

| Level | When to Use |
|-------|-------------|
| **HIGH** | 2+ authoritative sources agree on the fact |
| **MEDIUM** | 1 authoritative source, or multiple lower-quality sources agree |
| **LOW** | Inference, extrapolation, or sources conflict |

---

## Constraints

- **NO** `iw next-id` — this command never allocates IDs
- **NO** `iw register`, `iw doc-update`, or any platform registration
- **NO** file creation — answer is fully inline in conversation
- Max **4 WebFetch** calls per invocation
- Every factual claim requires an inline source URL
- Confidence marker (`[HIGH/MEDIUM/LOW]`) is mandatory on every answer
- Answer is inline — never say "see attached" or reference external files
