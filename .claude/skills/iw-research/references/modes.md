# Research Modes — Detailed Tool Chain Instructions

This file supplements `skills/iw-research/SKILL.md` with per-mode execution guidance.

---

## Mode: tech

**Use when**: Evaluating libraries, frameworks, SDKs, or technical tools.
**Topic examples**: "redis vs rabbitmq for queues", "evaluate FastAPI vs Flask", "which ORM for PostgreSQL?"

### Tool Chain

1. **Resolve library IDs** (context7):
   ```
   mcp__context7__resolve-library-id <library-name-1>
   mcp__context7__resolve-library-id <library-name-2>
   ```
   Get stable IDs for all candidate libraries before querying docs.

2. **Query official docs** (context7):
   ```
   mcp__context7__query-docs <library-id> <specific question>
   ```
   Ask 3-5 targeted questions: performance characteristics, concurrency model, use cases, known limitations.

3. **WebSearch for real-world usage** (5-8 queries):
   - "{library} benchmarks 2024"
   - "{library} known issues github"
   - "{library} vs {alternative} production experience"
   - "{library} developer experience survey"
   - "{library} adoption major companies"
   - "{library} community size StackOverflow GitHub stars"
   - "{library} roadmap future plans"
   - "{library} breaking changes migration"

4. **WebFetch** (3-5 pages):
   - Official documentation pages for key features being compared
   - GitHub README of candidate libraries (check for recent updates)
   - Any benchmark posts cited in search results

5. **Codebase investigation** (optional but recommended):
   - Grep/Read existing code that uses any of the candidates
   - Check `package.json`, `requirements.txt`, `pyproject.toml`, `Cargo.toml` for current dependencies
   - Identify migration effort if replacing an existing solution

### Source Credibility Hierarchy
1. Official documentation (primary)
2. Conference talks by library authors
3. Blog posts by recognized contributors
4. Benchmark articles (check methodology)
5. Community discussions (StackOverflow, Reddit)

### Confidence Level Rules
- **HIGH**: Official docs AND 2+ independent benchmarks agree
- **MEDIUM**: One good source (e.g., official docs) or mixed signals from secondary sources
- **LOW**: Extrapolation from old data, community speculation

### Key Findings to Capture
- Performance characteristics (throughput, latency, memory)
- Developer experience (API design, documentation quality, tooling)
- Operational characteristics (clustering, monitoring, operational overhead)
- Ecosystem (community size, third-party integrations, longevity)
- Migration costs (if replacing existing solution)

---

## Mode: market

**Use when**: Investigating competitors, products, pricing, market landscape.
**Topic examples**: "vercel vs netlify vs cloudflare pages", "who are the main PostgreSQL GUI tools", "competitive landscape for AI code assistants"

### Tool Chain

1. **WebSearch for landscape overview** (6-10 queries):
   - "{product category} market overview 2024"
   - "{product} pricing plans"
   - "{competitor 1} vs {competitor 2} comparison"
   - "{product} case studies customers"
   - "{product} features roadmap"
   - "{category} industry report"
   - "{product} developer reviews"
   - "{category} emerging players 2024"
   - "{product} integrations ecosystem"
   - "{product} SLA uptime guarantees"

2. **WebFetch for detailed information** (4-8 pages):
   - Pricing pages for each major competitor
   - Feature comparison pages
   - Case studies or customer stories
   - G2, Capterra, or TrustRadius reviews
   - Company blog/press release for recent developments

3. **WebSearch for specific claims**:
   - Verify specific statistics cited in marketing materials
   - Find independent reviews or benchmarks
   - Check for recent news about acquisitions, funding, leadership changes

### Source Credibility Hierarchy
1. Official pricing/features pages (primary)
2. Independent analyst reports (Gartner, Forrester)
3. Verified user reviews (G2, Capterra — aggregate, not single reviews)
4. News articles from established tech publications
5. Company blog posts and press releases

### Confidence Level Rules
- **HIGH**: Official pricing page AND 2+ independent sources confirm
- **MEDIUM**: One verified source or official claim without independent confirmation
- **LOW**: Marketing claims not independently verified, aged data

### Key Findings to Capture
- Pricing tiers and model (per-seat, usage-based, enterprise)
- Key differentiating features
- Target customer segment
- Market positioning
- Customer testimonials / notable users
- Gaps or weaknesses commonly mentioned

---

## Mode: deep

**Use when**: Comprehensive multi-angle investigation requiring all available tools.
**Topic examples**: "comprehensive analysis of LLM hallucination mitigation techniques", "deep dive into WebAssembly for frontend developers"

### Tool Chain

1. **Landscape framing** (WebSearch — 3-5 queries):
   - Broad overview searches to understand the full scope
   - Identify all major sub-topics and stakeholders
   - Find canonical definitions and frameworks

2. **context7 for library/framework components**:
   - If the topic touches any technical components, resolve IDs and query official docs
   - This applies to any library, framework, SDK, or tool mentioned

3. **WebSearch across multiple angles** (10+ queries):
   Cover each angle with 2-3 queries:
   - Academic/research perspective: "{topic} research paper survey"
   - Industry perspective: "{topic} enterprise adoption"
   - Developer perspective: "{topic} developer experience"
   - Future outlook: "{topic} future trends predictions"
   - Problems/gaps: "{topic} challenges limitations"
   - Solutions: "{topic} best practices guide"
   - Tools: "{topic} tools libraries frameworks"
   - Community: "{topic} community discussions"
   - History: "{topic} evolution history"
   - Regulations: "{topic} legal ethical considerations"

4. **WebFetch for primary sources** (8+ pages):
   - Academic papers or technical specifications
   - Official documentation for any technical components
   - In-depth articles from authoritative sources
   - Conference talk transcripts or slides
   - Case studies with actual numbers

5. **Optional outline checkpoint**:
   Before full research, present an outline for complex topics:
   ```
   ### Proposed Research Outline: {ID}

   **Primary Question**: {question}

   **Sections**:
   1. {Section A} — covering X, Y
   2. {Section B} — covering W, Z
   3. {Section C} — covering ...

   **Key Sources Identified**:
   - {Source 1} (confirmed accessible)
   - {Source 2} (suspected relevant)
   - {Source 3} (needs verification)

   **Proceed with this outline? Confirm GO to continue.**
   ```

### Source Credibility Hierarchy
1. Academic papers and formal specifications
2. Official documentation
3. Conference talks by recognized experts
4. Technical blog posts with rigorous methodology
5. Industry reports from established analysts
6. Community discussions (lower weight)

### Confidence Level Rules
- **HIGH**: 2+ authoritative sources (academic, official, expert) agree; primary sources verified
- **MEDIUM**: One authoritative source OR multiple secondary sources in partial agreement
- **LOW**: Inference, extrapolation from indirect evidence, or sources of unknown credibility

### Key Findings to Capture
- Comprehensive coverage of all angles
- Contradicting viewpoints with evidence on both sides
- Historical context and evolution
- Current state and future trajectory
- Open questions and research gaps
- Practical recommendations grounded in evidence

---

## Mode: general

**Use when**: Default mode for unclassified topics; quick research on general questions.
**Topic examples**: "how does content-addressable storage work", "what is vector database approximate nearest neighbor"

### Tool Chain

1. **WebSearch** (4-6 queries):
   - "{topic} explained"
   - "{topic} overview introduction"
   - "{topic} how it works technical"
   - "{topic} use cases applications"
   - "{topic} advantages disadvantages"
   - "{topic} getting started tutorial"

2. **WebFetch** (2-4 pages):
   - The most authoritative result from WebSearch
   - A practical tutorial or getting-started guide
   - An architectural overview or deep-dive article

### Source Credibility Hierarchy
1. Official documentation or established reference (Wikipedia for general concepts)
2. Technical tutorials from recognized publications
3. Well-known developer blogs (Medium, Dev.to, Hashnode)
4. Community wikis and documentation

### Confidence Level Rules
- **HIGH**: Multiple independent sources confirm the core facts
- **MEDIUM**: One reliable source; no contradictions found
- **LOW**: Limited sources, inferred details, or conflicting information

### Key Findings to Capture
- Clear definition and explanation
- Primary use cases
- Key advantages and trade-offs
- Getting started guidance
- Common pitfalls or misconceptions

---

## Cross-Mode Rules

### Query Strategy
- Start broad to frame the topic, then narrow to specific questions
- Always search for "{topic} limitations problems pitfalls" — this surfaces important nuance
- For comparisons, search each option separately AND the comparison

### Source Logging
For every WebSearch result and WebFetch page, record:
- Title
- URL
- Credibility assessment (HIGH/MEDIUM/LOW)
- Key information extracted

You will need these for the Sources table in the output document.

### Handling Zero Results
If a WebSearch returns no useful results:
- Try alternative search terms
- Broaden the query
- Report the finding as LOW confidence with a note in Limitations
- Do not fabricate information

### Handling context7 Unavailability
context7 tools are optional. If `mcp__context7__resolve-library-id` returns an error or "tool not found":
- Skip context7 entirely
- Use WebSearch + WebFetch as the primary tool chain
- Note in the research document that official docs were accessed via web search
- Continue without interruption

### OpenCode Environments
OpenCode supports `WebSearch` and `WebFetch` when `OPENCODE_ENABLE_EXA=1` is set.
context7 tools may or may not be available depending on the host configuration.
Always check tool availability before relying on context7.
