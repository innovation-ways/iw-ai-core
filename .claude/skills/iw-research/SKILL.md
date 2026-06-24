---
name: iw-research
version: "1.0.0"
description: >
  Conducts online research and produces a filed research document registered in
  the IW AI Core database. Supports four modes: tech (library/framework evaluation),
  market (competitive landscape), deep (multi-angle investigation), general (default).
  Use when asked to "research X", "investigate Y", "evaluate Z options",
  "/iw-research", or when research output should be saved as a project document.
  Requires: iw next-id --type research (F-00020 must be deployed).
allowed-tools: WebSearch, WebFetch, mcp__context7__resolve-library-id, mcp__context7__query-docs, Read, Grep, Glob, Bash, Write, Edit
argument-hint: <topic or research question>
---

# IW Research

Produces a filed research document registered in the IW AI Core database.

**Research topic**: $ARGUMENTS

---

## Prerequisites

- F-00020 must be deployed: `iw next-id --type research` must work
- OpenCode users: set `OPENCODE_ENABLE_EXA=1` for WebSearch support
- context7 tools are optional but recommended when investigating libraries/frameworks

## Step 1: Reserve Research ID (IMMEDIATE)

Reserve the next available Research ID **immediately** — before any other work:

```bash
iw next-id --type research
```

This atomically allocates a fresh ID (e.g., `R-00001`). Store it verbatim. The database is the sole source of truth.

**CRITICAL**: This call MUST happen before ANY other action.

---

## Step 2: Scope & Mode Selection (MANDATORY INTERACTION)

Discuss with the user to determine:

### 2a. Primary Question
What is the single main question this research answers? (1-2 sentences)

### 2b. Secondary Questions
List 2-5 specific sub-questions or angles to investigate.

### 2c. Depth Level
| Level | When to Use |
|-------|-------------|
| quick | Single specific fact or narrow comparison |
| standard | Multi-angle overview with key trade-offs |
| deep | Comprehensive investigation with multiple sources per claim |

### 2d. Mode Selection
Auto-detect from topic, then confirm with user:

| Mode | Trigger Keywords | Description |
|------|-----------------|-------------|
| **tech** | library, framework, SDK, tool comparison, evaluate X vs Y | Evaluate technical options; uses context7 for official docs |
| **market** | competitor, pricing, market share, landscape, company X vs Y | Competitive landscape; no codebase access needed |
| **deep** | investigate, comprehensive, multi-angle, deep dive | All tools, broadest coverage, 10+ queries minimum |
| **general** | default | WebSearch + WebFetch; unclassified topics |

**Mode → tool mapping**:

| Mode | WebSearch | WebFetch | context7 | Codebase |
|------|-----------|----------|----------|----------|
| tech | yes | yes | yes | yes |
| market | yes | yes | no | no |
| deep | yes | yes | yes | no |
| general | yes | yes | no | optional |

**WAIT for user confirmation on mode and questions before proceeding.**

---

## Step 3: GO/NO-GO Checkpoint (MANDATORY — no web calls before this)

Present the research plan:

```markdown
### Research Plan: {ID}

**Topic**: {research topic}
**Mode**: {tech|market|deep|general}
**Depth**: {quick|standard|deep}

**Primary Question**: {main question}
**Secondary Questions**:
1. {sub-question 1}
2. {sub-question 2}

**Tool Plan**:
- Queries: ~{N} WebSearch calls
- Pages to fetch: ~{N} WebFetch calls
- context7: {yes|no} (library/framework docs)
- Codebase: {yes|no|optional}

**Expected Sources**: {official docs, blog posts, community forums, etc.}

---

**Ready to proceed? Confirm GO or provide changes.**
```

Only proceed on explicit GO. If user declines, abort cleanly — no files written, no web calls made.

---

## Step 4: Execute Research

Execute the tool chain for the selected mode. See `references/modes.md` for full per-mode instructions.

**General rules for all modes**:
- Use **official documentation** as primary source whenever available
- Prefer **conference talks and blog posts from primary authors** over community summaries
- **Log every source URL** as you go — you need these for the citation table
- For each finding, assess: 2+ authoritative sources agree → **HIGH**, 1 good source → **MEDIUM**, inference/extrapolation → **LOW**
- If context7 is available, resolve library IDs before querying:
  ```
  mcp__context7__resolve-library-id <library-name>
  mcp__context7__query-docs <library-id> <query>
  ```
- If context7 is unavailable, skip gracefully and use WebSearch + WebFetch only

**Quick mode** (tech/market/general):
- 3-5 WebSearch queries
- 2-3 WebFetch calls
- Write document immediately after

**Standard mode** (tech/market/general):
- 5-8 WebSearch queries
- 4-6 WebFetch calls
- Optional: outline checkpoint for complex topics

**Deep mode**:
- 10+ WebSearch queries across multiple angles
- 8+ WebFetch calls to primary sources
- context7 for any library/framework components
- Optional: outline checkpoint before full research

---

## Step 5: Write Document

Create the research document using the template in `references/output_format.md`.

Output path:
```
docs/research/{ID}-{slug}.md
```

Where `slug` is a 3-5 word kebab-case descriptor of the topic.

**Document requirements** (mandatory for all modes):
- Title, ID, date, mode, primary question
- Executive Summary (3-5 sentences)
- Findings with `[HIGH/MEDIUM/LOW]` confidence markers in section headers
- Every factual claim has inline source citation: `[source text](url)`
- Recommendations section
- Limitations section
- Sources table with #, title, credibility, URL

### Visualizations (apply per finding while writing)

A research document is not text-only. Where a finding has a **shape** — a flow,
hierarchy, relationship, trend, distribution, or positioning — embed a figure;
where it is a single number or a few exact values, use **bold text or a table**
instead. Diagrams render natively in the dashboard and PDF (fenced ` ```mermaid `
and ` ```d2 ` blocks → SVG; brand theme applied automatically).

Run this decision for each finding:

1. **Visualize the shape, tabulate/narrate the values.** One number → bold inline.
   A handful of exact values in one unit → markdown table. A trend, flow,
   hierarchy, relationship, distribution, or positioning → a figure.
2. **Pick the chart by the data relationship** (FT Visual Vocabulary): comparison →
   bar (≤15 categories); change over time → line/area (ordered x-axis only);
   part-to-whole → stacked bar/treemap (pie only for 2-3 slices); relationship →
   scatter/bubble; distribution → histogram/boxplot; flow/process → flowchart or
   Sankey; positioning of options → 2×2 quadrant matrix.
3. **Make each figure self-contained**: a **declarative title that states the
   takeaway** (not "X vs Y"), a one-line "why this figure" framing blockquote
   *before* it, and the interpretation in prose *after* it. Caption carries units
   and the data **source**.
4. **Accessibility & restraint**: never encode by color alone (use labels/shapes/
   line styles too); keep figures decluttered (no chartjunk, no 3D/dual-axis);
   budget roughly one orienting figure plus one per shaped finding — not a figure
   per section by rote.

For quantitative data (benchmarks, market sizes, shares), prefer a chart over a
prose dump: Mermaid `xychart-beta` covers bar/line; otherwise present the numbers
as a table. See `references/output_format.md` → "Visualizations" for the full
chart-selection table, syntax examples, and the accessibility checklist, and
[R-00051](../../docs/research/R-00051-beautiful-diagram-tools.md) /
[R-00153](../../docs/research/R-00153-research-visualization-best-practices.md)
for the underlying tool and editorial guidance.

---

## Step 6: Register in Platform

Register the research document in the IW AI Core database:

```bash
iw register {ID} "{Title}" --type research
```

Update the document record with metadata:

```bash
iw doc-update {ID} \
  --doc-type research \
  --editorial-category {technical|marketing|functional} \
  --title "{Title}" \
  --status draft \
  --content-file docs/research/{ID}-{slug}.md
```

**Editorial category mapping**:

| Mode | `--editorial-category` |
|------|------------------------|
| tech | technical |
| market | marketing |
| deep | functional |
| general | functional |

---

## Step 7: Report

Present a summary to the user:

```markdown
## Research Complete: {ID}

**Title**: {title}
**Mode**: {mode}
**Date**: {YYYY-MM-DD}

### Key Findings
- **{Finding 1}** [HIGH] — 1-sentence summary
- **{Finding 2}** [MEDIUM] — 1-sentence summary
- **{Finding 3}** [LOW] — 1-sentence summary

### Document
`docs/research/{ID}-{slug}.md`

### Next Steps
- Review the document and provide feedback
- To update status: `iw doc-update {ID} --status published`
- Dashboard: http://localhost:9900
```

---

## Constraints

- **MUST** call `iw next-id --type research` as Step 1 (before any other work)
- **MUST** interact with user in Step 2 to confirm scope and mode
- **MUST** present GO/NO-GO checkpoint before any web tool calls
- **MUST** write the research document only after explicit GO
- **MUST** include confidence markers `[HIGH/MEDIUM/LOW]` on every finding
- **MUST** cite every factual claim with an inline source URL
- **MUST** call `iw register` and `iw doc-update` at the end
- **MUST** consider a visualization for every finding that has a shape (flow,
  hierarchy, relationship, trend, distribution, positioning) — embed a brand-themed
  ` ```mermaid `/` ```d2 ` figure with a declarative title, framing, and source;
  use a table or bold text for exact values. See Step 5 → "Visualizations".
- **NEVER** implement code — this is a documentation/research skill
- **NEVER** make web calls before GO checkpoint
- **NEVER** skip the Sources table — it is required for all modes
