---
version: "1.0.0"
name: iw-blog-writer
description: >
  Generates branded technical blog posts with embedded diagrams, code examples,
  and SEO metadata. Use when asked to write a blog post, article, or thought
  piece for Innovation Ways. Triggers on "blog", "blog post", "article",
  "thought leadership", "tutorial post", "case study", "how we built",
  "/iw-blog", or when creating content for the Innovation Ways blog.
---

# Innovation Ways Blog Writer

## Purpose

Generate publication-ready technical blog posts that follow Innovation Ways brand identity, tone of voice, and proven content structure patterns. Output includes Markdown source, branded HTML, and PDF.

## Prerequisites

Before writing, load these dependencies:

1. **Brand configuration**: Read `templates/brand/brand.json` for colors, fonts, and diagram theme
2. **Tone of voice**: Read `templates/brand/tone-of-voice.md` — use the "Blog Post Voice" section
3. **Blog structure reference**: Read `skills/iw-blog-writer/references/blog-structure.md` for the selected blog style
4. **Research guide**: For detailed best practices, consult `poc/guide-blog-writing.md`

## Instructions

### 1. Determine Blog Style

Select one of five styles based on the topic and intent:

| Style | When to Use | Length |
|-------|-------------|--------|
| **Thought Leadership** | Opinionated analysis of trends, architecture decisions, industry shifts | 2,000-3,000 words |
| **Tutorial** | Step-by-step implementation guides with working code | 1,500-2,500 words |
| **Case Study** | "How we built X" with narrative arc, challenges, and results | 1,200-2,000 words |
| **Comparison** | Evaluating technologies, tools, or approaches side-by-side | 1,500-2,500 words |
| **How-To** | Focused task completion — solve one specific problem | 800-1,500 words |

If the user specifies `--style`, use that. Otherwise, infer from the topic.

### 1b. Select Voice

Choose based on the `--voice` flag (default: `company`):

| Voice | Pronoun | Author | Tone | CTA Style |
|-------|---------|--------|------|-----------|
| `company` | "we", "our team", "let's" | Innovation Ways | Professional firm, collective expertise | "Contact Innovation Ways" / "Get in Touch" |
| `personal` | "I", "my", "me" | Sérgio Gaspar | Individual practitioner, relatable, candid | "Follow me on Medium" / "DM me on LinkedIn" / "Let me know in the comments" |

**Personal voice rules** (when `--voice personal`):

- Use "I built", "I decided", "in my experience" — own every decision
- Share personal motivations and learning moments ("I hit a wall when...", "That's when I realized...")
- More opinion, more vulnerability — readers connect with the person behind the code
- Still technically rigorous — personal doesn't mean sloppy
- Avoid corporate phrasing ("our team leveraged", "we delivered value")
- "We" is allowed only when referring to a specific team you worked with ("the team and I decided...")
- Read `templates/brand/tone-of-voice.md` — "Personal Blog Voice" section

### 1c. Select Brand

Choose based on the `--brand` flag (default: `iw`):

| Brand | Styling | Footer | HTML Template |
|-------|---------|--------|---------------|
| `iw` | IW colors, fonts | "Innovation Ways" / innovationways.com | `templates/blog/blog-template.html` |
| `none` | Same clean styling, no company references | Author name only | `templates/blog/blog-template-neutral.html` |

### 2. Plan Content Structure

Before writing, create an outline with:

- **Title** (50-70 characters, includes primary keyword, front-loaded)
- **Meta description** (150-160 characters, includes keyword + value proposition)
- **URL slug** (3-5 words, kebab-case, includes primary keyword)
- **Target audience** (who specifically benefits from this post)
- **Key takeaways** (3-5 bullets the reader should walk away with)
- **Diagram plan** (at least one diagram per 1,000 words; minimum one per post)
- **Section outline** with estimated word counts

Load the detailed structure from `skills/iw-blog-writer/references/blog-structure.md` for the selected style.

### 3. Write the Hook (First 150 Words)

The opening must immediately establish relevance. Use one of these patterns:

- **Problem-Solution**: State a pain point the reader recognizes, preview the solution
- **Surprising Statistic**: Lead with a specific, verifiable number
- **Before/After**: Contrast the current state with the achievable outcome
- **Question**: Ask a question that challenges assumptions (use sparingly)

**Anti-patterns to avoid**:
- "In today's fast-paced world of technology..."
- "As developers, we all know..."
- "In this blog post, we will discuss..."
- Generic AI-style openings with no specificity

### 4. Write in Conversational Technical Tone

Follow these rules strictly:

- **Apply pronouns from the selected voice** — "we/you/let's" for company, "I/you" for personal (see section 1b)
- **Active voice** for 80-90% of sentences
- **Short sentences**: Average 15-20 words, vary between 10-30
- **Short paragraphs**: 2-4 sentences (40-80 words)
- **Technical precision**: Use correct terminology, never oversimplify to inaccuracy
- **Contractions**: "we'll", "you're", "it's" — natural, not forced
- **No filler**: Cut "basically", "essentially", "in order to", "it should be noted that"
- **No exclamation marks** in technical content
- **Oxford comma** always
- **Numbers**: Spell out one through nine, digits for 10+. Always digits for technical values.
- **Concrete over abstract**: "reduced from 800ms to 120ms" not "significantly improved"
- **H2 headings every 300-500 words** for scanability
- **Descriptive headings** that work as standalone TOC entries

### 5. Embed Diagrams

Every blog post MUST include at least one diagram. Use the `iw-diagram-generator` skill guidelines:

- **Architecture overview**: Use Mermaid flowchart with subgraphs
- **Data/request flows**: Use Mermaid sequence diagrams
- **Decision logic**: Use Mermaid flowcharts
- **Data models**: Use Mermaid erDiagram
- **Process flows**: Use Mermaid flowcharts (LR direction)

**Diagram rules**:
- Maximum 10-12 nodes per diagram (blog readers scan, not study)
- Apply brand theme from `templates/brand/brand.json` `diagrams.mermaidInit`
- Save `.mmd` source files alongside output
- Render to SVG using `mmdc -i diagram.mmd -o diagram.svg -b white`
- Always include a text explanation after the diagram — never rely on diagram alone
- Caption every diagram with `Figure N: Description`

**Diagram frequency guideline**: One visual element (diagram, code block, or table) every 300-500 words.

### 6. Format Code Examples

When including code:

- **Always specify language** for syntax highlighting
- **Keep lines under 80 characters** to prevent horizontal scrolling
- **Include imports** — examples should be runnable when possible
- **Comment the "why"**, not the "what"
- **Use progressive complexity**: Start simple, build up
- **Before/After pattern** for optimizations and refactoring
- **Code-to-prose ratio**: 20-40% code for tutorials, 10-20% for thought leadership

### 7. Write the Conclusion

Every post ends with:

1. **Recap** (2-3 sentences summarizing the journey)
2. **Key Takeaways** (3-5 actionable bullet points)
3. **Next Steps** (what the reader should do or explore next)
4. **Call-to-Action** (engagement prompt — comment, share, contact)

### 8. Add SEO Metadata

Generate these elements for the HTML output. Adjust author and canonical URL based on voice/brand:

**Company voice + IW brand** (default):
```html
<title>{Title} | Innovation Ways Blog</title>
<meta name="author" content="Innovation Ways">
<link rel="canonical" href="https://innovationways.com/blog/{slug}">
```

**Personal voice + no brand**:
```html
<title>{Title} | Sérgio Gaspar</title>
<meta name="author" content="Sérgio Gaspar">
<!-- canonical URL omitted or set to Medium/personal site URL -->
```

**Common to both**:
```html
<meta name="description" content="{150-160 char meta description}">
<meta name="keywords" content="{5-8 relevant keywords, comma-separated}">
<meta property="og:title" content="{Title}">
<meta property="og:description" content="{Meta description}">
<meta property="og:type" content="article">
<meta property="og:image" content="{hero image path if available}">
```

### 9. Generate Output Files

Produce three output files:

1. **Markdown** (`{slug}.md`): Clean Markdown with front matter (title, date, author, tags, description, slug)
2. **HTML** (`{slug}.html`): Branded HTML using `templates/blog/blog-style.css`, with embedded SVG diagrams and SEO metadata
3. **PDF** (`{slug}.pdf`): Generated from HTML using Puppeteer via `tools/scripts/html-to-pdf.js`

**Markdown front matter format**:
```yaml
---
title: "Post Title Here"
date: "YYYY-MM-DD"
author: "Innovation Ways"        # or "Sérgio Gaspar" for personal voice
voice: "company"                 # or "personal"
tags: ["fastapi", "postgresql", "performance"]
description: "150-160 character description"
slug: "post-slug-here"
style: "thought-leadership"
---
```

**HTML generation**: Select the template based on `--brand`:
- `--brand iw` (default): Use `templates/blog/blog-template.html`
- `--brand none`: Use `templates/blog/blog-template-neutral.html`

Both use `templates/blog/blog-style.css` for styling.

**PDF generation**:
```bash
NODE_PATH=$(npm root -g) node tools/scripts/html-to-pdf.js {slug}.html {slug}.pdf
```

## Quality Checklist

Before finalizing, verify:

- [ ] Title is 50-70 characters with primary keyword
- [ ] Meta description is 150-160 characters
- [ ] Hook grabs attention in first 2-3 sentences (no generic openings)
- [ ] At least one diagram embedded with caption and text explanation
- [ ] All code examples have language specified and are under 80 chars wide
- [ ] Active voice used 80%+ of the time
- [ ] No filler words (basically, essentially, in order to)
- [ ] H2 headings every 300-500 words
- [ ] Conclusion has takeaways + CTA
- [ ] Brand colors applied to HTML and diagrams
- [ ] All three output files generated (MD, HTML, PDF)

## Anti-Patterns

Do NOT:
- Write generic introductions ("In today's world...")
- Use decorative diagrams that don't convey information
- Pad content to hit word count targets
- Include code blocks without explanation
- Skip the conclusion or CTA
- Use informal tone inappropriate for the audience ("awesome!", "super cool!")
- Generate walls of text without headings or visual breaks
- Include more than one CTA (focus drives action)

## Files Referenced

- `templates/brand/brand.json` — Visual identity
- `templates/brand/tone-of-voice.md` — Writing style (Blog Post Voice section)
- `skills/iw-blog-writer/references/blog-structure.md` — Detailed structure per blog style
- `templates/blog/blog-template.html` — HTML template
- `templates/blog/blog-style.css` — Blog CSS
- `tools/scripts/html-to-pdf.js` — Puppeteer PDF converter
- `poc/guide-blog-writing.md` — Full research reference (consult for edge cases)
