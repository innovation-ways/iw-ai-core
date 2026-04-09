# Blog Post Structure Reference

## Purpose

Detailed section breakdowns for each blog post style. The `iw-blog-writer` skill references this file when planning post structure.

---

## Style: Thought Leadership

**Goal**: Share an opinionated, evidence-backed perspective on a technology trend, architecture decision, or industry shift.

**Length**: 2,000-3,000 words

**Structure**:

```
1. Hook: Provocative Statement or Contrarian View (100-150 words)
   - Challenge conventional wisdom or state a surprising position
   - Example: "Most teams adopt event-driven architecture for the wrong reasons."
   - Establish credibility with a specific observation

2. Context: Why This Matters Now (200-300 words)
   - Current industry trend or pattern
   - What triggered this analysis
   - Who should care and why

3. The Argument (800-1,200 words)
   - Present your thesis with supporting evidence
   - Use 2-3 sub-sections (H3) for different facets
   - Include at least one architecture/concept diagram
   - Reference real examples (open-source projects, published case studies)
   - Acknowledge counter-arguments honestly

4. Practical Implications (400-600 words)
   - What this means for engineering teams
   - Concrete decision criteria or evaluation frameworks
   - When to apply vs. when to avoid
   - Include a comparison table or decision flowchart

5. Looking Forward (200-300 words)
   - Where this trend is heading
   - What to watch for
   - How to prepare

6. Conclusion + CTA (100-150 words)
   - 3-5 key takeaways as bullets
   - Engagement prompt (question to the community)
```

**Diagram types**: Architecture overview, comparison flowchart, decision matrix, evolution timeline

**Code examples**: Minimal (10-15% of content). Use short snippets to illustrate concepts, not full implementations.

**Example titles**:
- "Why Event-Driven Architecture Fails Most Teams (and When It Works)"
- "The Hidden Cost of Microservices: When Monoliths Win"
- "Database-Backed Task Queues vs. Message Brokers: A Pragmatic Guide"

---

## Style: Tutorial

**Goal**: Teach the reader how to implement something specific, step by step, with working code.

**Length**: 1,500-2,500 words

**Structure**:

```
1. Hook: Problem Statement + Outcome Preview (100-150 words)
   - What the reader will build/achieve
   - Why this approach matters
   - Example: "By the end of this tutorial, you'll have a FastAPI endpoint
     that handles 10,000 requests/second using async SQLAlchemy."

2. Prerequisites (50-100 words)
   - Required knowledge level
   - Tools and versions needed
   - Repository link (if applicable)

3. Architecture Overview (150-200 words)
   - High-level diagram of what we're building
   - Component relationships
   - Data flow summary

4. Step-by-Step Implementation (800-1,500 words)
   - 3-7 numbered steps
   - Each step: explanation (2-3 sentences) → code block → verification
   - Progressive complexity: simple → add features → add error handling
   - Use comments in code to explain the "why"
   - Include expected output for verification steps

5. Testing (200-300 words)
   - How to verify the implementation works
   - Common errors and fixes
   - Edge cases to consider

6. Going Further (100-200 words)
   - Enhancements the reader can make
   - Related topics or next tutorials
   - Production considerations

7. Conclusion + CTA (100-150 words)
   - Key takeaways as bullets
   - Link to complete source code
   - Invitation to share results
```

**Diagram types**: Architecture overview (before implementation), sequence diagram (request flow), component diagram

**Code examples**: Heavy (30-40% of content). Complete, runnable examples with imports.

**Example titles**:
- "How to Build an Async Task Queue with FastAPI and PostgreSQL"
- "Implementing JWT Authentication in FastAPI: A Complete Guide"
- "Building Real-Time Updates with Server-Sent Events in Next.js"

---

## Style: Case Study

**Goal**: Tell the story of a real project — what we built, why, what went wrong, and what we learned.

**Length**: 1,200-2,000 words

**Structure**:

```
1. Hook: The Challenge (100-150 words)
   - State the problem in concrete terms with numbers
   - Example: "Our client's deployment pipeline took 45 minutes and failed
     30% of the time. They needed it under 10 minutes with 99% success."

2. Context: The Starting Point (200-300 words)
   - What the system looked like before
   - Key constraints (budget, timeline, team size, existing tech)
   - Architecture diagram of the "before" state

3. What We Tried First (200-300 words)
   - Initial approaches and why they fell short
   - Honest discussion of false starts
   - This builds credibility — readers trust authors who share failures

4. The Breakthrough (300-500 words)
   - Key insight that changed the approach
   - The solution we implemented
   - Architecture diagram of the "after" state
   - Code snippets for critical components

5. Results (200-300 words)
   - Concrete metrics: before vs. after
   - Use a comparison table or metrics callout
   - Business impact (cost savings, time saved, reliability)

6. Lessons Learned (200-300 words)
   - 3-5 principles that apply beyond this specific project
   - What we'd do differently next time
   - Advice for teams facing similar challenges

7. Conclusion + CTA (100-150 words)
   - Summary of the transformation
   - Offer to discuss similar challenges
```

**Diagram types**: Before/after architecture diagrams, metrics comparison, timeline of key milestones

**Code examples**: Moderate (15-25% of content). Show critical implementation details, not everything.

**Narrative style**: First person plural ("we"). Storytelling structure with tension and resolution.

**Example titles**:
- "How We Reduced API Latency 73% with Connection Pooling"
- "Migrating 2M Records from MongoDB to PostgreSQL Without Downtime"
- "Building a Hybrid Cloud Architecture for AI Podcast Generation"

---

## Style: Comparison

**Goal**: Help the reader make an informed technology decision by evaluating options objectively.

**Length**: 1,500-2,500 words

**Structure**:

```
1. Hook: The Decision Context (100-150 words)
   - What decision the reader faces
   - Why it matters (consequences of choosing wrong)
   - Example: "Choosing between REST, GraphQL, and gRPC affects your team's
     productivity, API performance, and long-term maintenance for years."

2. Evaluation Criteria (200-300 words)
   - Define 4-6 criteria for comparison
   - Explain why each criterion matters
   - Weight criteria by importance for the target audience

3. Option Analysis (600-1,000 words — divided per option)
   - For each option (2-4 options):
     - What it is (1-2 sentences)
     - Strengths (with evidence)
     - Weaknesses (honest assessment)
     - Best suited for (specific scenarios)
     - Code example showing the option in action

4. Comparison Table (standalone section)
   - Feature matrix with all options side by side
   - Use clear indicators (check marks, ratings, or descriptors)
   - Include a "verdict" row

5. Decision Framework (200-400 words)
   - Flowchart or decision tree: "If X, choose Y"
   - Scenario-based recommendations
   - Example: "Choose REST if your team is small, your API is CRUD-focused,
     and you value simplicity over flexibility."

6. Our Recommendation (100-200 words)
   - State Innovation Ways' position with rationale
   - Acknowledge that context matters
   - When we use each option in our projects

7. Conclusion + CTA (100-150 words)
   - Summary of key differentiators
   - Encourage readers to evaluate based on their context
```

**Diagram types**: Decision flowchart, architecture comparison diagrams, feature matrix visualization

**Code examples**: Moderate (20-30% of content). Show the same operation in each technology for direct comparison.

**Tone**: Objective and balanced. State your recommendation but don't dismiss alternatives.

**Example titles**:
- "REST vs GraphQL vs gRPC: Choosing APIs for Microservices"
- "SQLAlchemy vs Tortoise ORM vs Raw asyncpg: Python Async Database Access"
- "Celery vs Dramatiq vs Database Queues: Task Processing in 2026"

---

## Style: How-To

**Goal**: Solve one specific problem quickly. No narrative, minimal context, maximum utility.

**Length**: 800-1,500 words

**Structure**:

```
1. Problem Statement (50-100 words)
   - What specific problem this solves
   - Expected outcome after reading

2. Prerequisites (30-50 words)
   - Required tools/versions
   - Assumed knowledge

3. Solution (500-1,000 words)
   - 3-5 clear steps
   - Code-first: show the solution, then explain
   - Each step: code block → brief explanation
   - Include verification/testing for each step

4. Troubleshooting (100-200 words)
   - Common errors and fixes
   - Edge cases

5. Summary (50-100 words)
   - What was accomplished
   - Link to related how-tos
```

**Diagram types**: Usually one simple flowchart or sequence diagram. Keep it minimal.

**Code examples**: Heavy (40-50% of content). Runnable, complete, copy-paste ready.

**Tone**: Direct and efficient. No storytelling. Get to the solution fast.

**Example titles**:
- "Fix: SQLAlchemy Async Session Not Committing in FastAPI"
- "How to Set Up Alembic Migrations with Async SQLAlchemy"
- "Configure PostgreSQL Connection Pooling for FastAPI in 5 Minutes"

---

## Cross-Style Guidelines

### Heading Frequency

- H2 every 300-500 words (creates scanable structure)
- H3 for sub-topics within an H2 section
- Never skip heading levels (H2 → H4 is invalid; use H2 → H3)

### Visual Cadence

Target one visual element every 300-500 words:
- Diagram (Mermaid-rendered SVG)
- Code block (15+ lines)
- Table (3+ rows)
- Callout box (info, warning, or tip)

### Link Strategy

- **Internal links**: 3-5 per post to related IW content
- **External links**: 2-4 to authoritative sources (official docs, research)
- **Anchor text**: Descriptive, never "click here"

### Front Matter Tags

Use consistent tag taxonomy:

| Category | Example Tags |
|----------|-------------|
| Language | `python`, `typescript`, `sql` |
| Framework | `fastapi`, `nextjs`, `react`, `sqlalchemy` |
| Topic | `performance`, `security`, `architecture`, `testing` |
| Pattern | `async`, `microservices`, `event-driven`, `repository-pattern` |
| Database | `postgresql`, `redis`, `migrations` |
| DevOps | `docker`, `ci-cd`, `github-actions`, `deployment` |
