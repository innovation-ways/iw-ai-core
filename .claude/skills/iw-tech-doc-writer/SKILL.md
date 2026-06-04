---
version: "1.0.0"
name: iw-tech-doc-writer
description: >
  Generates comprehensive technical documents with embedded diagrams, code
  examples, and branded PDF output. Use when asked to write architecture docs,
  API docs, infrastructure docs, user guides, or functional specs. Triggers on
  "documentation", "tech doc", "architecture document", "API doc", "user guide",
  "functional spec", "infrastructure doc", "/iw-doc", or when generating
  project documentation.
---

# Innovation Ways Technical Document Writer

## Purpose

Generate publication-ready technical documents with embedded Mermaid diagrams, code examples, tables, and callout boxes. Output includes branded HTML and PDF. Documents follow the C4 model for architecture diagrams and use progressive detail levels.

## Prerequisites

Before writing, load these dependencies:

1. **Brand configuration**: Read `templates/brand/brand.json` for colors, fonts, and diagram theme
2. **Tone of voice**: Read `templates/brand/tone-of-voice.md` — use the "Documentation Voice" section
3. **Document structure reference**: Read `skills/iw-tech-doc-writer/references/doc-structure-{type}.md` for the selected document type
4. **Diagram guidelines**: Read `skills/iw-tech-doc-writer/references/diagram-guidelines.md` for diagram requirements per document type
5. **Research guide**: For detailed best practices, consult `poc/guide-technical-documentation.md`

## Instructions

### 1. Determine Document Type

Select based on the `--type` flag or infer from the request:

| Type | When to Use | Typical Length | Min Diagrams |
|------|-------------|----------------|--------------|
| **architecture** | System design, component relationships, data flows | 3,000-8,000 words | 5-8 |
| **infrastructure** | Deployment topology, networking, environments, ops procedures | 2,000-5,000 words | 3-5 |
| **api** | Endpoint reference, authentication, error handling, examples | 2,000-6,000 words | 2-4 |
| **user-guide** | End-user instructions, workflows, troubleshooting | 1,500-4,000 words | 2-4 |
| **functional** | Requirements, business logic, acceptance criteria, user flows | 2,000-5,000 words | 3-5 |

Load the detailed structure from `skills/iw-tech-doc-writer/references/doc-structure-{type}.md`.

### 2. Select Voice

Choose based on the `--voice` flag (default: `company`):

| Voice | Pronoun | Author | Tone |
|-------|---------|--------|------|
| `company` | "we", "our" | Innovation Ways | Professional firm, collective expertise |
| `personal` | "I", "my" | Sérgio Gaspar | Individual practitioner, portfolio showcase |

For personal voice, read the "Personal Blog Voice" section in `templates/brand/tone-of-voice.md` and adapt for documentation (keep precision, add personal context for decisions).

### 3. Select Brand

Choose based on the `--brand` flag (default: `iw`):

| Brand | Header | Footer | Template CSS |
|-------|--------|--------|-------------|
| `iw` | "Innovation Ways" + company subtitle | "Innovation Ways" / innovationways.com | `templates/docs/tech-doc-style.css` |
| `none` | Author name only | Author name only | `templates/docs/tech-doc-style.css` (same styling, neutral labels) |

### 4. Plan the Document

Before writing, create an outline with:

- **Title** (system name + document type, e.g., "PodForger — System Architecture")
- **Version** and **Date**
- **Audience** (who specifically reads this document)
- **Table of Contents** with all H2 sections
- **Diagram plan**: List each diagram with:
  - Type (C4 context, container, component, sequence, ER, deployment, flowchart, state)
  - What it conveys
  - Estimated complexity (nodes/participants)
- **Section outline** with estimated word counts

### 5. Generate Diagrams

For each planned diagram:

1. Write Mermaid source to `poc/diagrams/{system}-{diagram-name}.mmd`
   - Include the brand theme init string from `brand.json` `diagrams.mermaidInit`
   - Follow the `iw-diagram-generator` skill guidelines for complexity and naming
   - Use C4 diagram syntax for context/container/component diagrams
2. Render to SVG: `mmdc -i {file}.mmd -o {file}.svg -b white`
3. Verify the SVG was created and is non-empty

**Diagram requirements by document type**:

| Document Type | Required Diagrams |
|---------------|-------------------|
| architecture | C4 context, C4 container, 1+ component, 1+ sequence, deployment overview |
| infrastructure | Deployment topology, network diagram, environment comparison |
| api | Request flow sequence, authentication flow, error handling flowchart |
| user-guide | User workflow flowchart, system interaction sequence |
| functional | Business process flow, user journey, data model (ER) |

### 6. Write the Document

Follow the structure from the reference file for the selected type. Apply these rules:

**Writing standards**:
- **Active voice** for 80%+ of sentences
- **Version header** at top of every document (version, date, status, audience)
- **Audience tag** — state who this document is for
- **Diagrams first** — lead with the visual, then explain in text
- **Every diagram gets a caption** (`Figure N: Description`)
- **Every diagram gets a text explanation** — never rely on diagram alone
- **Code examples** have language specified and are under 80 chars wide
- **Tables** for structured comparisons (technology stacks, config options, environment variables)
- **Callout boxes** for warnings, tips, and important notes
- **Cross-references** between sections ("See Section 4 for data flow details")
- **No filler** — cut "basically", "essentially", "in order to"
- **Technical precision** — use correct terminology
- **H2 for major sections**, H3 for subsections, never skip levels

**Document-specific rules**:
- **Architecture docs**: Start with system context (highest abstraction), drill down to component level
- **Infrastructure docs**: Start with deployment topology, then detail each environment
- **API docs**: Start with authentication, then group endpoints by resource
- **User guides**: Start with prerequisites, then step-by-step workflows
- **Functional docs**: Start with business objectives, then detail requirements

### 7. Generate HTML Output

Build the HTML file manually (no template file — construct from scratch using `templates/docs/tech-doc-style.css`):

1. Use the same HTML structure as `poc/output/podforger-architecture.html` (from Phase 1) as reference
2. Include: doc-header with title/version/audience, table of contents, all sections with embedded SVGs
3. Reference `templates/docs/tech-doc-style.css` for styling
4. Use CSS classes: `.doc-header`, `.toc`, `.diagram-container`, `.caption`, `.callout`, `.two-col`, `.kv-grid`
5. For `--brand none`: replace "Innovation Ways" with author name in header and footer

Save to: `poc/output/{system}-{type}.html`

### 8. Generate PDF Output

Convert HTML to PDF using Puppeteer:

```bash
NODE_PATH=$(npm root -g) node tools/scripts/html-to-pdf.js poc/output/{file}.html poc/output/{file}.pdf
```

Verify the PDF was created and is non-empty.

### 9. Summary

Report what was generated:

- **HTML**: path and file size
- **PDF**: path and file size
- **Diagrams**: list of `.mmd` and `.svg` files
- **Sections**: count and list of H2 headings
- **Word count**: approximate
- **Voice/Brand**: which settings were used
- **Quality check**: diagram count, section count, audience tag present, version header present

## Quality Checklist

Before finalizing, verify:

- [ ] Version header with date, status, and audience tag
- [ ] Table of contents with all H2 sections
- [ ] Minimum diagram count met for the document type
- [ ] Every diagram has a caption and text explanation
- [ ] All code examples have language specified
- [ ] Active voice used 80%+ of the time
- [ ] No filler words
- [ ] Cross-references between related sections
- [ ] Tables used for structured data (not prose)
- [ ] Callout boxes for warnings and important notes
- [ ] HTML renders correctly with tech-doc-style.css
- [ ] PDF is multi-page A4, diagrams are legible

## Anti-Patterns

Do NOT:
- Generate a document without reading the source material first
- Use decorative diagrams that don't convey information
- Write walls of text without headings, tables, or diagrams
- Skip the table of contents
- Omit the version header or audience tag
- Include every detail — focus on what the audience needs
- Mix abstraction levels in a single diagram (keep C4 levels separate)

## Files Referenced

- `templates/brand/brand.json` — Visual identity and diagram theme
- `templates/brand/tone-of-voice.md` — Writing style (Documentation Voice section)
- `templates/docs/tech-doc-style.css` — Document CSS
- `skills/iw-tech-doc-writer/references/doc-structure-architecture.md` — Architecture doc structure
- `skills/iw-tech-doc-writer/references/doc-structure-api.md` — API doc structure
- `skills/iw-tech-doc-writer/references/doc-structure-user-guide.md` — User guide structure
- `skills/iw-tech-doc-writer/references/diagram-guidelines.md` — Diagram requirements per doc type
- `skills/iw-diagram-generator/SKILL.md` — Diagram generation rules
- `tools/scripts/html-to-pdf.js` — Puppeteer PDF converter
- `poc/guide-technical-documentation.md` — Full research reference
- `poc/guide-functional-documentation.md` — Functional doc research reference
