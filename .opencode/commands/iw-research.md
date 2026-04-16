---
description: Conducts online research and produces a filed research document registered in the IW AI Core database. Supports four modes: tech (library/framework evaluation), market (competitive landscape), deep (multi-angle investigation), general (default). Use when asked to "research X", "investigate Y", "evaluate Z options", or "/iw-research". Requires iw next-id --type research.
---

# IW Research

Produces a filed research document registered in the IW AI Core database.

**Research topic**: $ARGS

---

## Prerequisites

- F-00020 must be deployed: `iw next-id --type research` must work
- OpenCode: set `OPENCODE_ENABLE_EXA=1` for WebSearch support
- context7 tools are optional; if unavailable, use WebSearch + WebFetch only

---

## Step 1: Reserve Research ID (IMMEDIATE)

Reserve the next available Research ID **before any other work**:

```bash
iw next-id --type research
```

This atomically allocates a fresh ID (e.g., `R-00001`). Store it verbatim — the database is the sole source of truth.

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

Execute the tool chain for the selected mode. See per-mode instructions below.

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

**Standard mode** (tech/market/general):
- 5-8 WebSearch queries
- 4-6 WebFetch calls

**Deep mode**:
- 10+ WebSearch queries across multiple angles
- 8+ WebFetch calls to primary sources
- context7 for any library/framework components
- Optional: outline checkpoint before full research

---

### Mode: tech

**Use when**: Evaluating libraries, frameworks, SDKs, or technical tools.

#### Tool Chain

1. **Resolve library IDs** (context7, if available):
   ```
   mcp__context7__resolve-library-id <library-name>
   ```
   Get stable IDs for all candidate libraries before querying docs.

2. **Query official docs** (context7):
   ```
   mcp__context7__query-docs <library-id> <specific question>
   ```
   Ask 3-5 targeted questions: performance, concurrency model, use cases, known limitations.

3. **WebSearch for real-world usage** (5-8 queries):
   - "{library} benchmarks 2024"
   - "{library} known issues github"
   - "{library} vs {alternative} production experience"
   - "{library} developer experience survey"
   - "{library} adoption major companies"
   - "{library} community size StackOverflow GitHub stars"
   - "{library} roadmap future plans"
   - "{library} breaking changes migration"

4. **WebFetch** (3-5 pages): official docs, GitHub READMEs, benchmark posts.

5. **Codebase investigation** (optional): grep existing code using the candidates; check `pyproject.toml`, `package.json`, `requirements.txt`.

#### Confidence Levels
- **HIGH**: Official docs AND 2+ independent benchmarks agree
- **MEDIUM**: One good source or mixed signals from secondary sources
- **LOW**: Extrapolation from old data, community speculation

#### Key Findings to Capture
- Performance (throughput, latency, memory)
- Developer experience (API design, documentation quality, tooling)
- Operational characteristics (clustering, monitoring, overhead)
- Ecosystem (community size, integrations, longevity)
- Migration costs (if replacing an existing solution)

---

### Mode: market

**Use when**: Investigating competitors, products, pricing, market landscape.

#### Tool Chain

1. **WebSearch for landscape overview** (6-10 queries):
   - "{product category} market overview 2024"
   - "{product} pricing plans"
   - "{competitor 1} vs {competitor 2} comparison"
   - "{product} case studies customers"
   - "{category} industry report"
   - "{product} developer reviews"
   - "{category} emerging players 2024"
   - "{product} integrations ecosystem"
   - "{product} SLA uptime guarantees"

2. **WebFetch** (4-8 pages): pricing pages, feature comparison pages, G2/Capterra reviews, company blog for recent developments.

3. **Verify specific claims**: find independent reviews, check for recent acquisitions/funding.

#### Confidence Levels
- **HIGH**: Official pricing page AND 2+ independent sources confirm
- **MEDIUM**: One verified source or official claim without independent confirmation
- **LOW**: Marketing claims not independently verified, aged data

#### Key Findings to Capture
- Pricing tiers and model (per-seat, usage-based, enterprise)
- Key differentiating features
- Target customer segment
- Market positioning
- Customer testimonials / notable users
- Gaps or weaknesses commonly mentioned

---

### Mode: deep

**Use when**: Comprehensive multi-angle investigation requiring all available tools.

#### Tool Chain

1. **Landscape framing** (WebSearch — 3-5 queries): broad overview, identify major sub-topics, canonical definitions.

2. **context7** (if available): resolve and query docs for any library/framework components mentioned.

3. **WebSearch across multiple angles** (10+ queries):
   - Academic: "{topic} research paper survey"
   - Industry: "{topic} enterprise adoption"
   - Developer: "{topic} developer experience"
   - Future: "{topic} future trends predictions"
   - Problems: "{topic} challenges limitations"
   - Solutions: "{topic} best practices guide"
   - Tools: "{topic} tools libraries frameworks"
   - Community: "{topic} community discussions"
   - History: "{topic} evolution history"
   - Regulations: "{topic} legal ethical considerations"

4. **WebFetch** (8+ pages): academic papers, official documentation, conference talk transcripts, case studies with real numbers.

5. **Optional outline checkpoint** (for complex topics):
   ```
   ### Proposed Research Outline: {ID}

   **Primary Question**: {question}

   **Sections**:
   1. {Section A} — covering X, Y
   2. {Section B} — covering W, Z

   **Key Sources Identified**:
   - {Source 1} (confirmed accessible)
   - {Source 2} (suspected relevant)

   **Proceed with this outline? Confirm GO to continue.**
   ```

#### Confidence Levels
- **HIGH**: 2+ authoritative sources (academic, official, expert) agree; primary sources verified
- **MEDIUM**: One authoritative source OR multiple secondary sources in partial agreement
- **LOW**: Inference, extrapolation, or sources of unknown credibility

#### Key Findings to Capture
- Comprehensive coverage of all angles
- Contradicting viewpoints with evidence on both sides
- Historical context and evolution
- Current state and future trajectory
- Open questions and research gaps
- Practical recommendations grounded in evidence

---

### Mode: general

**Use when**: Default mode for unclassified topics.

#### Tool Chain

1. **WebSearch** (4-6 queries): "{topic} explained", "{topic} how it works technical", "{topic} use cases", "{topic} advantages disadvantages"

2. **WebFetch** (2-4 pages): most authoritative result, practical tutorial, architectural overview.

#### Confidence Levels
- **HIGH**: Multiple independent sources confirm core facts
- **MEDIUM**: One reliable source; no contradictions found
- **LOW**: Limited sources, inferred details, or conflicting information

---

### Cross-Mode Rules

- Start broad to frame the topic, then narrow to specific questions
- Always search for "{topic} limitations problems pitfalls" — surfaces important nuance
- For every WebSearch result and WebFetch page, record: title, URL, credibility (HIGH/MEDIUM/LOW), key info extracted
- If WebSearch returns no useful results: try alternative terms, broaden the query, report LOW confidence with a note in Limitations — do not fabricate information
- If context7 is unavailable: skip entirely, use WebSearch + WebFetch, note it in the document

---

## Step 5: Write Document

Create the `docs/research/` directory if needed:
```bash
mkdir -p docs/research/
```

Output path: `docs/research/{ID}-{slug}.md`  
Where `slug` is a 3-5 word kebab-case descriptor (e.g., `R-00001-redis-queue-comparison.md`).

**Document template**:

```markdown
# {Title}

**Research ID**: {ID}
**Date**: {YYYY-MM-DD}
**Mode**: {tech|market|deep|general}
**Depth**: {quick|standard|deep}
**Primary Question**: {main research question}

---

## Executive Summary

{3-5 sentences covering: the topic, key findings, and primary recommendation.
This section should stand alone as a summary for busy readers.}

## Background

{2-3 sentences on why this research was conducted and what prompted it.}

## Findings

### {Finding Title} [HIGH confidence]

{Finding text with inline citations: [source text](url)}

### {Finding Title} [MEDIUM confidence]

{Finding text with inline citations: [source text](url)}

### {Finding Title} [LOW confidence]

{Finding text — be explicit about uncertainty:
"This finding is based on [single source](url) and requires additional validation."}

---

## Recommendations

1. **Primary**: {main recommendation with rationale tied to specific findings}
2. **Alternative**: {alternative approach if primary is not viable}
3. **Avoid**: {what NOT to do and why, with evidence}

---

## Limitations

- {What this research does not cover}
- {Known gaps — be honest}
- {Time constraints or source availability issues}
- {Questions that remain unanswered}

---

## Sources

| # | Source | Credibility | URL |
|---|--------|-------------|-----|
| 1 | {title} | HIGH | {url} |
| 2 | {title} | MEDIUM | {url} |
| 3 | {title} | LOW | {url} |

---

## Appendix: Research Log

**Date range**: {start} to {end}
**Queries run**: {N} WebSearch, {N} WebFetch, {N} context7
**Mode used**: {mode}
**Depth level**: {depth}
```

**Mandatory elements** (ALL must be present):
- Frontmatter lines: Research ID, Date, Mode, Depth, Primary Question
- Executive Summary (3-5 sentences; must stand alone)
- Background (2-3 sentences)
- Findings with `[HIGH/MEDIUM/LOW]` in every section header
- Inline citations on every factual claim: `[text](url)`
- Recommendations: Primary, Alternative, Avoid
- Limitations (be honest)
- Sources table with #, title, credibility, URL

**Writing rules**:
- Write Executive Summary **last** — after all findings are complete
- Place `[HIGH/MEDIUM/LOW]` in the **section heading**, not just the body
- Every factual claim must have an inline citation `[text](url)`
- Do NOT cite a source you did not actually read

---

## Step 6: Register in Platform

```bash
iw register {ID} "{Title}" --type research
```

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
- **NEVER** implement code — this is a documentation/research command
- **NEVER** make web calls before GO checkpoint
- **NEVER** skip the Sources table — it is required for all modes
