# Slide Selection Guide

Reference for choosing slide layouts, planning slide sequences, and maintaining visual variety in presentations.

---

## Layout Decision Tree

Use this decision tree to select the right layout for each slide:

```
What is the slide's primary purpose?
│
├─ Opening the presentation
│  └─ → title-slide
│
├─ Transitioning between major sections
│  └─ → section-break-slide
│
├─ Presenting key metrics or KPIs
│  └─ How many data points?
│     ├─ 2-4 numbers → stats-slide
│     └─ 5+ or complex data → content-slide (with table)
│
├─ Showing a diagram or architecture
│  └─ Does it need text explanation alongside?
│     ├─ Yes, significant text → two-column-slide
│     └─ No, diagram speaks for itself → architecture-slide
│
├─ Displaying a quote or testimonial
│  └─ → quote-slide
│
├─ Listing bullet points or features
│  └─ Is there an accompanying visual?
│     ├─ Yes → two-column-slide
│     └─ No → content-slide
│
├─ Closing the presentation
│  └─ → closing-slide
│
└─ None of the above
   └─ → content-slide (most versatile)
```

---

## Slide Count by Presentation Type

| Type | Target Slides | Duration | Notes |
|------|:------------:|:--------:|-------|
| **Pitch** | 10-15 | 15-20 min | Focus on problem, solution, value, proof |
| **Product Overview** | 15-20 | 20-30 min | Feature walkthrough with demos/screenshots |
| **Technical Deep-Dive** | 15-25 | 30-45 min | Architecture, data flows, implementation details |
| **Project Update** | 8-12 | 10-15 min | Status, metrics, risks, next steps |

### Recommended Layout Distribution by Type

**Pitch (12 slides)**:
1. title-slide
2. content-slide (problem)
3. stats-slide (market/pain metrics)
4. content-slide (solution)
5. architecture-slide (how it works)
6. two-column-slide (feature + visual)
7. stats-slide (results/savings)
8. quote-slide (testimonial)
9. content-slide (roadmap)
10. section-break-slide (pricing/next steps)
11. content-slide (pricing/plan)
12. closing-slide

**Product Overview (16 slides)**:
1. title-slide
2. content-slide (agenda)
3. section-break-slide (problem space)
4. content-slide (problem details)
5. stats-slide (impact metrics)
6. section-break-slide (our solution)
7. architecture-slide (system overview)
8. two-column-slide (feature 1)
9. two-column-slide (feature 2)
10. two-column-slide (feature 3)
11. section-break-slide (results)
12. stats-slide (performance metrics)
13. quote-slide (customer feedback)
14. content-slide (roadmap)
15. content-slide (getting started)
16. closing-slide

**Technical Deep-Dive (20 slides)**:
1. title-slide
2. content-slide (agenda)
3. section-break-slide (architecture)
4. architecture-slide (C4 context)
5. architecture-slide (C4 container)
6. content-slide (technology stack)
7. section-break-slide (data flows)
8. architecture-slide (sequence diagram)
9. two-column-slide (async patterns)
10. stats-slide (performance benchmarks)
11. section-break-slide (infrastructure)
12. architecture-slide (deployment)
13. two-column-slide (scaling strategy)
14. content-slide (monitoring)
15. section-break-slide (security)
16. content-slide (auth + access control)
17. content-slide (data protection)
18. section-break-slide (operations)
19. content-slide (runbooks)
20. closing-slide

**Project Update (10 slides)**:
1. title-slide
2. stats-slide (key metrics)
3. content-slide (accomplishments)
4. architecture-slide (current state diagram)
5. content-slide (challenges/risks)
6. two-column-slide (before/after)
7. content-slide (next sprint goals)
8. stats-slide (timeline/budget)
9. content-slide (blockers/asks)
10. closing-slide

---

## Variety Rules

These rules prevent monotonous presentations:

### Hard Rules (must follow)

1. **No 3+ consecutive same-layout slides** — If you have two content-slides in a row, the third must be different
2. **content-slide must not exceed 25% of total** — In a 12-slide deck, max 3 content-slides
3. **Visual layouts must be at least 50% of non-structural slides** — stats-slide, architecture-slide, two-column-slide, and quote-slide count as visual. title-slide, section-break-slide, and closing-slide are structural
4. **Every presentation must have title-slide + closing-slide** — Non-negotiable bookends

### Soft Rules (follow when possible)

5. **Alternate text-heavy and visual slides** — After a content-slide, prefer a visual layout next
6. **Place stats-slide after context** — Show the problem or solution first, then the numbers
7. **Use section-break-slide before new topics** — Gives the audience a mental reset
8. **Place quote-slide near the end** — Testimonials land best after you've built the case
9. **Limit section-break-slides to one per 5 slides** — Too many transitions break flow

---

## Diagram Embedding Workflow

Presentations use PNG format for diagrams (PPTX does not support SVG embedding).

### Step 1: Create Mermaid Source

Write the `.mmd` file with the brand theme init string from `brand.json`:

```bash
# Include the mermaidInit string at the top of the .mmd file
```

### Step 2: Render to PNG

```bash
mmdc -i diagram.mmd -o diagram.png -b white -w 1920
```

Parameters:
- `-b white` — White background (matches slide backgrounds)
- `-w 1920` — Width in pixels (16:9 slide ratio, high resolution)

### Step 3: Embed in Slide

```python
from pptx.util import Inches

# Full-width (architecture-slide)
slide.shapes.add_picture(
    "diagram.png",
    Inches(0.8), Inches(1.6),
    Inches(11.733), Inches(5.4)
)

# Right column (two-column-slide)
slide.shapes.add_picture(
    "diagram.png",
    Inches(7.2), Inches(2.0),
    Inches(5.2), Inches(4.8)
)
```

### Step 4: Verify

- Open the generated `.pptx` in PowerPoint/Google Slides
- Check that diagrams are sharp (no pixelation at presentation zoom)
- Verify text in diagrams is readable from the back of a room (min effective 18pt)

---

## Speaker Notes Best Practices

Every slide should have speaker notes. Follow these guidelines:

### Structure

```
[Opening line — what to say when this slide appears]

Key points:
- Point 1: [detail to mention]
- Point 2: [detail to mention]
- Point 3: [detail to mention]

[Transition — how to bridge to the next slide]
```

### Rules

1. **Write in natural speech** — Notes are prompts for speaking, not a script
2. **Include timing hints** — "Spend 2 minutes here" or "Quick — 30 seconds"
3. **Add audience interaction cues** — "Ask: Has anyone experienced this?"
4. **Reference diagram elements** — "Point to the Worker Pool box on the left"
5. **Include backup data** — Numbers or details that might come up in Q&A
6. **Keep under 150 words** — If you need more, the slide is trying to do too much

### Notes by Layout Type

| Layout | Notes Should Cover |
|--------|-------------------|
| title-slide | Introduce yourself, set context, state the presentation goal |
| content-slide | Expand on each bullet with an example or anecdote |
| stats-slide | Explain what each number means and why it matters |
| two-column-slide | Walk through the text, then reference the visual |
| architecture-slide | Trace through the diagram component by component |
| quote-slide | Add context about who said it and when |
| section-break-slide | Preview what's coming, check in with audience |
| closing-slide | Summarize key message, invite questions, point to contact info |

---

## Batch Generation Strategy

python-pptx is most reliable when generating slides in batches.

### Rules

1. **Max 5 slides per batch** — Generate 5 slides, save, verify, then continue
2. **Combine batches** — After all batches are generated, combine into a single `.pptx`:

```python
from pptx import Presentation
import copy

final = Presentation()
final.slide_width = Inches(13.333)
final.slide_height = Inches(7.5)

for batch_file in batch_files:
    batch = Presentation(batch_file)
    for slide in batch.slides:
        # Copy slide layout and content
        new_slide_layout = final.slide_layouts[6]
        new_slide = final.slides.add_slide(new_slide_layout)
        for shape in slide.shapes:
            # Clone each shape to the new slide
            el = copy.deepcopy(shape._element)
            new_slide.shapes._spTree.append(el)
        # Copy background
        bg_elem = copy.deepcopy(
            slide.background._element
        )
        new_slide.background._element.getparent().replace(
            new_slide.background._element, bg_elem
        )

final.save("combined-deck.pptx")
```

3. **Verify after combine** — Open the combined file and check:
   - All slides present (correct count)
   - No white backgrounds from combine bug
   - Speaker notes preserved
   - Diagrams embedded correctly

---

## Common Pitfalls

| Problem | Cause | Fix |
|---------|-------|-----|
| White slide background | Missing explicit fill on background | Always set `slide.background.fill.solid()` |
| Tiny or missing text | Font not installed on system | Use system fonts (Arial, Calibri) as fallback |
| Diagram pixelated | Low render resolution | Use `-w 1920` or higher with `mmdc` |
| Slides out of order | Batch combination error | Verify slide order matches the plan |
| Speaker notes missing | Not copied during combine | Copy notes elements explicitly |
| Text overflow | Too many words on slide | Max 6 bullets, 15 words each |
