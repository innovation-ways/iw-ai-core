---
version: "1.0.0"
name: iw-pitch-deck
description: >
  Generates branded PowerPoint presentations using python-pptx with cookbook
  slide layouts. Use when asked to create a deck, presentation, pitch, slides,
  or PowerPoint. Triggers on "deck", "presentation", "pitch", "slides",
  "powerpoint", "pptx", "/iw-deck", or when creating presentation materials.
---

# Innovation Ways Pitch Deck Generator

## Purpose

Generate branded PowerPoint presentations (.pptx) using python-pptx cookbook scripts as layout references. Each slide is composed programmatically with consistent brand colors, fonts, and spacing. Output is a single .pptx file with speaker notes on every slide.

## Prerequisites

Before generating, load these dependencies:

1. **Brand configuration**: Read `templates/brand/brand.json` for colors, fonts, company info
2. **Tone of voice**: Read `templates/brand/tone-of-voice.md` — use "Client Communication Voice" for pitch/product, "Documentation Voice" for technical
3. **Cookbook scripts**: Read the relevant scripts from `skills/iw-pitch-deck/cookbook/` as reference patterns for each layout type
4. **Slide selection guide**: Read `skills/iw-pitch-deck/references/slide-selection-guide.md` for layout decisions, variety rules, and diagram embedding workflow

## Instructions

### 1. Determine Presentation Type

Select based on the `--type` flag or infer from the topic:

| Type | When to Use | Target Slides | Key Focus |
|------|-------------|:------------:|-----------|
| **pitch** | Selling a product/service, investor deck, client proposal | 10-15 | Problem → solution → value → proof |
| **product** | Feature walkthrough, product demo companion, launch deck | 15-20 | Features, architecture, demo flow |
| **technical** | Architecture review, tech deep-dive, engineering showcase | 15-25 | Systems, data flows, infrastructure |
| **update** | Sprint review, project status, stakeholder update | 8-12 | Metrics, progress, risks, next steps |

### 2. Select Voice

Choose based on the `--voice` flag (default: `company`):

| Voice | Pronouns | Presenter | Tone |
|-------|----------|-----------|------|
| `company` | "we", "our" | Innovation Ways | Professional firm, collective expertise |
| `personal` | "I", "my" | Sérgio Gaspar | Individual expert, personal portfolio |

### 3. Select Brand

Choose based on the `--brand` flag (default: `iw`):

| Brand | Title Slide | Closing Slide | Colors |
|-------|-------------|---------------|--------|
| `iw` | "Innovation Ways" company name, tagline | IW contact info, social links | brand.json colors |
| `none` | Presenter name only | Personal contact info | brand.json colors (same styling, no company name) |

### 4. Plan the Slide Sequence

Before generating, create a slide plan table:

| # | Layout | Title | Content Summary | Speaker Notes Summary |
|---|--------|-------|-----------------|----------------------|
| 1 | title-slide | Deck Title | Subtitle, date | Intro, context |
| 2 | content-slide | The Problem | 3-4 bullet points | Expand with examples |
| ... | ... | ... | ... | ... |

**Planning rules**:
- Follow the recommended layout distribution from `slide-selection-guide.md` for the chosen type
- Apply variety rules: no 3+ consecutive same-layout, content-slide ≤25%, visual layouts ≥50%
- Plan diagram slides: identify which concepts need architecture or data flow diagrams
- Every slide must have a speaker notes summary in the plan

### 5. Generate Diagrams

For slides that need embedded diagrams:

1. Write Mermaid source to `poc/diagrams/{topic}-{name}.mmd`
   - Include brand theme init string from `brand.json` `diagrams.mermaidInit`
2. Render to **PNG** (not SVG — PPTX needs raster images):
   ```bash
   mmdc -i poc/diagrams/{file}.mmd -o poc/diagrams/{file}.png -b white -w 1920
   ```
3. Verify the PNG was created and is non-empty

### 6. Generate Slides in Batches

Generate slides in batches of max 5 slides per script execution.

For each slide:
1. Read the corresponding cookbook script from `skills/iw-pitch-deck/cookbook/` as a reference pattern
2. Write a custom Python script that creates the slide with actual content
3. Replace all `BRAND_*` placeholder values with real values from `brand.json`
4. Set explicit background fill on every slide (prevents white-slide bug)
5. Add speaker notes to every slide
6. For diagram slides: use `slide.shapes.add_picture()` to embed the rendered PNG

**Key python-pptx patterns** (from cookbook scripts):
- Slide dimensions: `Inches(13.333) × Inches(7.5)` (16:9)
- Always use blank layout: `prs.slide_layouts[6]`
- Background fill: `slide.background.fill.solid()` + set `fore_color.rgb`
- Shape type 1 = rectangle (for accent bars, dividers)
- `hex_to_rgb()` helper to convert hex colors to `RGBColor`

### 7. Combine into Single Presentation

After all batches are generated, combine into a single `.pptx` file.

Combination approach:
1. Create a master `Presentation()` with correct slide dimensions
2. For each batch file, copy slides (shapes + backgrounds + notes)
3. Save to final output path
4. Verify slide count matches the plan

### 8. Verify Output

Check the generated presentation:

- [ ] Correct slide count (matches plan)
- [ ] No white backgrounds (explicit fill on every slide)
- [ ] Brand colors applied consistently (primary, secondary, accent)
- [ ] Speaker notes present on every slide
- [ ] Diagrams embedded and readable
- [ ] Variety rules met (no 3+ consecutive same-layout)
- [ ] Title slide has company/presenter name and date
- [ ] Closing slide has contact information
- [ ] Text is readable (min 18pt for body, 28pt+ for titles)

## Quality Checklist

Before delivering, verify:

- [ ] All slides follow a cookbook layout pattern
- [ ] Brand colors from `brand.json` applied (no default PowerPoint colors)
- [ ] Explicit background fill on every slide
- [ ] Speaker notes on every slide (min 2-3 sentences each)
- [ ] Diagrams rendered as PNG and embedded (no SVG, no broken images)
- [ ] Variety rules: content-slide ≤25%, visual layouts ≥50%, no 3+ consecutive same
- [ ] Title slide includes date and company/presenter name
- [ ] Closing slide includes contact info and CTA
- [ ] Font sizes: titles ≥28pt, body ≥18pt, captions ≥11pt
- [ ] Max 6 bullets per content-slide, max 15 words per bullet

## Anti-Patterns

Do NOT:
- Generate slides without reading cookbook scripts first (they contain essential patterns)
- Use SVG format for diagrams (PPTX does not embed SVG reliably)
- Skip background fill on any slide (causes white-slide bug when combining)
- Put more than 6 bullets on a single content-slide
- Create 3+ consecutive slides with the same layout
- Skip speaker notes on any slide
- Use python-pptx's built-in slide layouts (they vary by template) — always use blank layout (index 6)
- Generate more than 5 slides in a single script execution

## Files Referenced

- `templates/brand/brand.json` — Colors, fonts, company info, diagram theme
- `templates/brand/tone-of-voice.md` — Voice and tone guidelines
- `skills/iw-pitch-deck/cookbook/title-slide.py` — Title slide pattern
- `skills/iw-pitch-deck/cookbook/content-slide.py` — Bullet point slide pattern
- `skills/iw-pitch-deck/cookbook/stats-slide.py` — KPI/metrics slide pattern
- `skills/iw-pitch-deck/cookbook/two-column-slide.py` — Text + image pattern
- `skills/iw-pitch-deck/cookbook/architecture-slide.py` — Full-width diagram pattern
- `skills/iw-pitch-deck/cookbook/quote-slide.py` — Testimonial/quote pattern
- `skills/iw-pitch-deck/cookbook/section-break-slide.py` — Chapter divider pattern
- `skills/iw-pitch-deck/cookbook/closing-slide.py` — CTA + contacts pattern
- `skills/iw-pitch-deck/references/slide-selection-guide.md` — Layout selection, variety rules, batch strategy
- `skills/iw-diagram-generator/SKILL.md` — Diagram generation rules
- `tools/scripts/html-to-pdf.js` — Not used (PPTX pipeline, not HTML)
