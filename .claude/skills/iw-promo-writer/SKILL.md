---
version: "1.0.0"
name: iw-promo-writer
description: >
  Generates branded marketing one-pagers as HTML + PDF. Use when asked to create
  a one-pager, promo, marketing material, brochure, or solution brief. Triggers
  on "one-pager", "promo", "marketing", "brochure", "solution brief",
  "/iw-promo", or when creating promotional material for Innovation Ways.
---

# Innovation Ways Promo Writer

## Purpose

Generate publication-ready marketing one-pagers that fit on a single A4 page. Output includes branded HTML and PDF. One-pagers are concise, visual, and action-oriented — they distill a product, solution, or case study into a format a decision-maker can absorb in 60 seconds.

## Prerequisites

Before writing, load these dependencies:

1. **Brand configuration**: Read `templates/brand/brand.json` for colors, fonts, company info
2. **Tone of voice**: Read `templates/brand/tone-of-voice.md` — use "Client Communication Voice" section
3. **One-pager structure**: Read `skills/iw-promo-writer/references/one-pager-structure.md` for section breakdowns, word limits, and visual composition rules
4. **HTML template**: Read `templates/promo/one-pager-template.html` — the output template
5. **CSS**: Read `templates/promo/promo-style.css` — the styling rules

## Instructions

### 1. Determine One-Pager Type

Select based on the `--type` flag or infer from the request:

| Type | When to Use | Primary Audience | Key Message |
|------|-------------|-----------------|-------------|
| **solution** | Selling a solution to a specific problem | Decision-makers, CTOs | "Here's how we solve your problem" |
| **case-study** | Showcasing results from a real project | Prospects, stakeholders | "Here's what we achieved" |
| **product** | Introducing a product or platform | Potential buyers, partners | "Here's what our product does" |

### 2. Select Voice

Choose based on the `--voice` flag (default: `company`):

| Voice | Pronouns | Author | Tone |
|-------|----------|--------|------|
| `company` | "we", "our" | Innovation Ways | Professional firm, solution-focused |
| `personal` | "I", "my" | Sérgio Gaspar | Individual expert, portfolio showcase |

### 3. Select Brand

Choose based on the `--brand` flag (default: `iw`):

| Brand | Header | Footer | CTA |
|-------|--------|--------|-----|
| `iw` | IW logo area, company name | Innovation Ways / innovationways.com | "Contact Innovation Ways" |
| `none` | Author name only | Author name only | "Get in Touch" / personal URL |

### 4. Plan Content

Before writing, create a section plan:

| Section | Word Budget | Purpose |
|---------|:----------:|---------|
| Hero header | 15-20 words | Headline + one-line value proposition |
| Problem statement | 40-60 words | Pain point the reader recognizes |
| Solution | 50-80 words | How the product/service addresses the problem |
| Key benefits | 60-80 words | 3-4 benefits with short descriptions |
| Proof point | 20-40 words | Metric, quote, or result that builds credibility |
| CTA | 15-25 words | Clear next step with contact info |

**Total word budget: 200-305 words** (must fit single A4 page with visual elements)

### 5. Write Content

Follow these rules:

- **A4 single-page constraint** — everything must fit on one printed page
- **Scannable** — use short sentences, bullet points, bold key phrases
- **Quantify value** — "reduces cost by 90%" not "significantly reduces cost"
- **Active voice** — "Our platform processes 10,000 articles daily" not "10,000 articles are processed"
- **No filler** — every word must earn its place on the page
- **Headline formula**: [Action Verb] + [Specific Outcome] + [For Whom]
  - Example: "Automate Podcast Production at 97% Lower Cost"
- **Benefits over features** — "Save 40 hours per month" not "Has a batch processing engine"

### 6. Generate Output

Use the one-pager HTML template and CSS:

1. Replace all `{{placeholders}}` in `templates/promo/one-pager-template.html`
2. Apply brand colors and fonts from `brand.json`
3. Save HTML to `poc/output/{topic-slug}-one-pager.html`
4. Convert to PDF via Puppeteer:
   ```bash
   NODE_PATH=$(npm root -g) node tools/scripts/html-to-pdf.js poc/output/{file}.html poc/output/{file}.pdf
   ```
5. Verify PDF is exactly one page

### 7. Verify Single-Page Constraint

If the PDF extends to a second page:
1. Reduce word count in the longest section
2. Reduce font sizes slightly (min: title 24pt, body 11pt)
3. Tighten spacing
4. Re-generate and verify again

## Quality Checklist

Before delivering, verify:

- [ ] Fits on a single A4 page (PDF is one page)
- [ ] Hero headline is compelling (action + outcome + audience)
- [ ] Problem statement is specific and relatable
- [ ] Solution section clearly links to the problem
- [ ] 3-4 key benefits with quantified value where possible
- [ ] Proof point (metric, quote, or result)
- [ ] Clear CTA with contact info
- [ ] Brand colors applied (primary for headings, accent for CTA)
- [ ] No filler words or vague claims
- [ ] Total word count under 305 words
- [ ] Active voice 90%+

## Anti-Patterns

Do NOT:
- Write more than 305 words (will overflow the page)
- Use generic headlines ("Innovative Solutions for Modern Businesses")
- List features without benefits
- Include more than 4 key benefits (dilutes impact)
- Skip the proof point (credibility matters)
- Use decorative diagrams (one-pagers are too compact for complex visuals)
- Make the CTA vague ("Learn More" — instead: "Schedule a 15-Minute Call")

## Files Referenced

- `templates/brand/brand.json` — Visual identity
- `templates/brand/tone-of-voice.md` — Client Communication Voice section
- `skills/iw-promo-writer/references/one-pager-structure.md` — Section details and visual composition
- `templates/promo/one-pager-template.html` — HTML template
- `templates/promo/promo-style.css` — Print-optimized CSS
- `tools/scripts/html-to-pdf.js` — Puppeteer PDF converter
