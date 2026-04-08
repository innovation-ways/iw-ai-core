# Architecture Document Structure Reference

## Purpose

Detailed section breakdown for architecture documents. The `iw-tech-doc-writer` skill references this file when generating architecture documentation.

---

## Document Structure

```
1. Document Header
   - Title: "{System} — System Architecture"
   - Version, Date, Status
   - Audience: Architects, Senior Developers, DevOps
   - Document purpose (2-3 sentences)

2. Table of Contents
   - All H2 sections listed

3. System Overview (400-600 words)
   - What the system does (1-2 paragraphs)
   - C4 Context diagram (system + users + external systems)
   - Key components summary table (Component | Technology | Purpose)
   - Key metrics (users, throughput, data volume)

4. Architecture Principles (200-400 words)
   - 3-5 design principles with rationale
   - Use numbered list with bold principle name + explanation
   - Example: "1. Simplicity First — Monolithic over microservices..."

5. Technology Stack (300-500 words)
   - Backend, Frontend, Infrastructure sections
   - Use YAML-style code blocks for version listing
   - Rationale for key choices (2-3 sentences per major choice)
   - Technology decision table (Decision | Choice | Rationale)

6. System Components (800-1,500 words)
   - C4 Container diagram (all major containers)
   - One subsection per major component (H3)
   - Each component: responsibilities, key modules, performance targets
   - Component diagram for the most complex container
   - Directory structure (code block) where relevant

7. Data Flow Diagrams (600-1,000 words)
   - 2-3 sequence diagrams for critical flows
   - Each flow: participants, steps, what happens at each step
   - Text explanation after each diagram
   - Cover: main user flow, background processing flow, external integration flow

8. Security Architecture (400-600 words)
   - Authentication flow (JWT, OAuth, etc.)
   - Authorization model (RBAC, permissions)
   - Input validation approach
   - Data protection (encryption, hashing)
   - Audit logging

9. Scalability & Performance (400-600 words)
   - Current capacity and targets
   - Horizontal scaling strategy (phases)
   - Database optimization (indexes, pooling)
   - Caching strategy
   - CDN / static asset delivery

10. Development Architecture (300-500 words, optional)
    - Local development setup
    - Testing pyramid
    - CI/CD pipeline
    - Deployment process

11. Technology Decision Log (200-400 words, optional)
    - Key decisions as H3 entries
    - Each: Pros, Cons, Decision, Rationale
```

## Required Diagrams

| # | Diagram | Type | Complexity |
|---|---------|------|------------|
| 1 | System Context | C4 Context or flowchart | 5-8 elements |
| 2 | Container / Deployment | Flowchart with subgraphs | 8-12 elements |
| 3 | Component (most complex container) | Flowchart | 8-12 elements |
| 4 | Primary user flow | Sequence diagram | 3-5 participants |
| 5 | Background processing flow | Sequence diagram | 3-5 participants |
| 6 | Deployment topology (if hybrid/complex) | Flowchart with subgraphs | 8-15 elements |

Minimum: 5 diagrams. Target: 6-8.

## Tables to Include

- Technology stack (component | technology | version | purpose)
- Key components summary
- Performance targets
- Environment comparison (dev vs staging vs prod)
- Security measures

## Callout Boxes

- **Info**: Architecture principles, design rationale
- **Warning**: Known limitations, planned but not implemented features
- **Tip**: Configuration advice, optimization suggestions

## Audience Expectations

Architecture documents are read by:
- **Architects**: Want to understand system boundaries, integration points, and scaling strategy
- **Senior developers**: Want to understand component responsibilities and data flows
- **DevOps**: Want deployment topology, infrastructure requirements, and monitoring

Write for all three. Start at the highest abstraction level and drill down.
