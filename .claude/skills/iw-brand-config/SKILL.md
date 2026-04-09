---
version: "1.0.0"
name: iw-brand-config
description: >
  Innovation Ways brand configuration and style guidelines. Use when generating
  any branded content, presentations, documents, blog posts, diagrams, or
  promotional material. Triggers on keywords like "IW brand", "Innovation Ways
  style", "branded", "company colors", "brand voice", or when any other IW
  content generation skill is active. Also activates when generating Mermaid
  diagrams, HTML documents, PDFs, or PowerPoint files that should follow
  Innovation Ways visual identity.
---

# Innovation Ways Brand Configuration

## Purpose

Provide consistent brand identity across all generated content. This skill is the foundation — every other IW content generation skill depends on it.

## Instructions

### 1. Load Brand Configuration

Read `templates/brand/brand.json` for visual identity:
- **Colors**: Use hex values from `colors` object. Never use color names — always hex.
- **Fonts**: Use font names from `fonts` object. Primary: Inter (heading + body), JetBrains Mono (code).
- **Logo**: Reference paths from `logo` object. Use `primary` for light backgrounds, `darkBackground` for dark.
- **Spacing**: Apply `spacing` values for consistent layout.
- **PDF settings**: Use `pdf` object for page format, margins, headers.

### 2. Load Tone of Voice

Read `templates/brand/tone-of-voice.md` for writing style:
- Match the voice attributes and style rules to the document type being generated.
- Use the appropriate voice section (Blog, Client, Documentation) based on context.

### 3. Apply Brand Colors to Mermaid Diagrams

Every Mermaid diagram MUST start with the theme initialization block from `brand.json`:

```
%%{init: {'theme': 'base', 'themeVariables': { ... }}}%%
```

Use the pre-built init string from `diagrams.mermaidInit` in brand.json. This ensures all diagrams use IW brand colors instead of Mermaid defaults.

### 4. Apply Brand to HTML Output

When generating HTML documents:
- Import Inter font from Google Fonts: `https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap`
- Import JetBrains Mono: `https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap`
- Use colors from brand.json for all styling
- Include IW logo in header
- Include page numbers and "Innovation Ways" text in footer for PDFs

### 5. Apply Brand to PowerPoint

When generating PPTX files:
- Use brand colors for slide backgrounds, text, and accents
- Use Inter font family (or closest available system font)
- Include IW logo on title slide and optionally in footer of other slides

### 6. Never Deviate

Do not deviate from brand guidelines unless the user explicitly overrides with a specific request (e.g., "use red instead of blue"). If no brand override is specified, always apply the full brand configuration.

## Output Format

This skill does not produce output directly. It provides configuration that other skills consume.

## Files Referenced

- `templates/brand/brand.json` — Visual identity (colors, fonts, logo, spacing, diagram theme)
- `templates/brand/tone-of-voice.md` — Writing style guidelines
- `templates/brand/assets/` — Logo files (SVG, ICO)
