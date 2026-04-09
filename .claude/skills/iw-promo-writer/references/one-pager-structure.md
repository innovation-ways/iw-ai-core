# One-Pager Structure Reference

Detailed section breakdown, visual composition rules, and typography guidelines for marketing one-pagers.

---

## Section Breakdown by Type

### Solution Overview

Target audience: CTOs, VP Engineering, Technical Decision-Makers

| Section | % of Page | Word Limit | Content |
|---------|:---------:|:----------:|---------|
| **Hero header** | 25% | 15-20 | Bold headline + one-line value proposition |
| **Problem statement** | 15% | 40-60 | 2-3 sentences describing the pain point |
| **Solution** | 20% | 50-80 | How the product/service addresses the problem |
| **Key benefits** | 25% | 60-80 | 3-4 benefits as icon-label-description cards |
| **Proof point** | 5% | 20-30 | Single metric or testimonial quote |
| **CTA** | 10% | 15-25 | Action + contact information |

**Hero headline patterns**:
- "[Verb] [Outcome] for [Audience]"
- "[Metric] [Improvement] with [Solution]"
- "From [Pain] to [Gain] in [Timeframe]"

**Example**: "Automate Podcast Production at 97% Lower Cost"

### Case Study

Target audience: Prospects evaluating similar solutions

| Section | % of Page | Word Limit | Content |
|---------|:---------:|:----------:|---------|
| **Hero header** | 20% | 15-20 | Client name + headline result |
| **Challenge** | 15% | 40-60 | What problem the client faced |
| **Solution** | 20% | 50-70 | What was built/delivered |
| **Results** | 25% | 60-80 | 3-4 quantified outcomes |
| **Quote** | 10% | 20-40 | Client testimonial |
| **CTA** | 10% | 15-25 | "See how we can help you" + contact |

**Hero headline patterns**:
- "[Client] Achieved [Result] with [Solution]"
- "How [Client] [Verb]ed [Metric] in [Timeframe]"

**Example**: "PodForger Reduced Episode Production Cost by 97%"

### Product Overview

Target audience: Potential buyers, partners, evaluators

| Section | % of Page | Word Limit | Content |
|---------|:---------:|:----------:|---------|
| **Hero header** | 25% | 15-20 | Product name + tagline |
| **What it does** | 15% | 40-60 | One-paragraph product description |
| **Key features** | 25% | 60-80 | 3-4 features with benefit-focused descriptions |
| **How it works** | 15% | 30-50 | 3-step simplified workflow |
| **Proof point** | 10% | 20-30 | Metric or early adopter quote |
| **CTA** | 10% | 15-25 | "Try it" or "Request a Demo" + contact |

**Hero headline patterns**:
- "[Product]: [Benefit in 5 Words]"
- "The [Category] Platform That [Differentiator]"

**Example**: "PodForger: AI-Powered Podcast Generation Platform"

---

## Visual Composition Rules

### Page Layout (A4: 210mm × 297mm)

```
┌─────────────────────────────────┐
│         HERO HEADER (25%)        │ ← Bold headline, accent background
│  Headline + Value Proposition    │
├─────────────────────────────────┤
│     PROBLEM / CHALLENGE (15%)    │ ← White background, body text
│                                  │
├─────────────────────────────────┤
│       SOLUTION (20%)             │ ← Light background (bg-alt)
│                                  │
├─────────────┬───────────────────┤
│  Benefit 1  │  Benefit 2        │ ← 2×2 grid or 4-column strip
├─────────────┼───────────────────┤ ← KEY BENEFITS (25%)
│  Benefit 3  │  Benefit 4        │
├─────────────┴───────────────────┤
│      PROOF POINT (5%)           │ ← Single metric or quote
├─────────────────────────────────┤
│          CTA (10%)              │ ← Accent background, contact info
└─────────────────────────────────┘
```

### Spacing Rules

| Element | Margin/Padding |
|---------|---------------|
| Page margins | 15mm top/bottom, 20mm left/right |
| Section gaps | 8-12px between sections |
| Hero padding | 24px top, 20px bottom |
| Benefit cards | 12px internal padding, 8px gap between cards |
| CTA padding | 16px all sides |

### Color Usage

| Element | Color | Source |
|---------|-------|--------|
| Hero background | `primary` (#1B2A4A) | brand.json |
| Hero headline text | `textOnPrimary` (#FFFFFF) | brand.json |
| Section headings | `primary` (#1B2A4A) | brand.json |
| Body text | `text` (#1A1A2E) | brand.json |
| Benefit icons/numbers | `accent` (#F18F01) | brand.json |
| CTA background | `accent` (#F18F01) | brand.json |
| CTA text | `textOnPrimary` (#FFFFFF) | brand.json |
| Proof point highlight | `secondary` (#2E86AB) | brand.json |
| Alternate section bg | `backgroundAlt` (#F5F7FA) | brand.json |
| Borders/dividers | `border` (#E5E7EB) | brand.json |

---

## Typography Hierarchy

| Element | Font | Size | Weight | Line Height |
|---------|------|:----:|:------:|:-----------:|
| Hero headline | Inter | 28pt | 800 (Extra Bold) | 1.2 |
| Hero subtitle | Inter | 14pt | 400 | 1.4 |
| Section heading | Inter | 16pt | 700 | 1.3 |
| Body text | Inter | 12pt | 400 | 1.5 |
| Benefit title | Inter | 13pt | 600 | 1.3 |
| Benefit description | Inter | 11pt | 400 | 1.4 |
| Proof metric | Inter | 24pt | 700 | 1.2 |
| CTA headline | Inter | 16pt | 700 | 1.3 |
| CTA body | Inter | 12pt | 400 | 1.4 |
| Footer | Inter | 9pt | 400 | 1.2 |

**Font fallback**: `-apple-system, BlinkMacSystemFont, sans-serif`

---

## Benefit Card Patterns

### Icon + Title + Description (recommended)

```
┌──────────────────┐
│  ◆  Benefit Title │
│  Short description │
│  with one metric   │
└──────────────────┘
```

Each card: 3-4 words for title, 10-15 words for description.

### Number + Title + Description

```
┌──────────────────┐
│  97%  Cost        │
│  Reduction        │
│  vs. cloud-only   │
└──────────────────┘
```

Use when you have concrete metrics for each benefit.

### Best Practices

- **3-4 benefits maximum** — more dilutes impact
- **Lead with the number** when you have one
- **Benefit, not feature** — "Save 40 hours/month" not "Has batch processing"
- **Consistent structure** — all cards should follow the same pattern
- **Equal visual weight** — cards should be the same size

---

## Proof Point Patterns

### Single Metric

```
"97% cost reduction in production infrastructure"
```

Best when you have a standout number.

### Mini Quote

```
"The system paid for itself in the first month."
— CTO, Client Company
```

Best when you have a compelling client statement.

### Before/After

```
Before: $2.40/episode  →  After: $0.08/episode
```

Best when the contrast is dramatic.

---

## CTA Patterns

### Primary CTA (always include)

| Type | CTA Text | Subtext |
|------|----------|---------|
| solution | "Schedule a 15-Minute Call" | email + website |
| case-study | "See How We Can Help You" | email + website |
| product | "Request a Demo" or "Try It Free" | email + website |

### Contact Info Format

```
info@innovationways.com  |  innovationways.com
```

Keep to one line. Include only email and website (no phone, no physical address).

---

## Writing Guidelines Specific to One-Pagers

### Word Economy

Every word must earn its place. Apply these cuts:

| Instead of | Write |
|-----------|-------|
| "We are able to provide" | "We provide" |
| "In order to achieve" | "To achieve" |
| "A significant improvement in" | "90% faster" |
| "Our innovative solution" | "PodForger" (use the name) |
| "State-of-the-art technology" | "[Specific technology]" |

### Headline Formula

```
[Strong Verb] + [Specific Outcome] + [For Whom/Context]
```

Good: "Automate Podcast Production at 97% Lower Cost"
Bad: "Innovative AI Solution for Content Creation"

Good: "Cut Episode Production from 6 Hours to 12 Minutes"
Bad: "Significantly Improve Your Production Pipeline"

### Scanning Optimization

Decision-makers scan one-pagers in a Z-pattern:
1. **Top-left** → Hero headline (must hook immediately)
2. **Top-right** → Value proposition or key metric
3. **Diagonal** → Benefits section (eyes drawn to bold/colored elements)
4. **Bottom-right** → CTA (must be visually distinct)

Design the layout to support this scanning pattern.

---

## Single-Page Constraint Enforcement

If content overflows to a second page in the PDF:

1. **First**: Cut word count in the longest section
2. **Second**: Reduce body font to 11pt (minimum)
3. **Third**: Reduce section gaps from 12px to 8px
4. **Fourth**: Remove one benefit card (keep best 3)
5. **Last resort**: Reduce hero section height

Never compromise on:
- Hero headline visibility
- CTA section presence
- At least 3 benefit cards
- Proof point
