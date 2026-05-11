---
version: "1.0.0"
name: iw-doc-system
description: >
  Unified documentation generation system for InnoForge deliverable documents.
  Generates markdown content with diagrams, then renders to branded HTML + PDF.
  Reads brand config, editorial guidelines, and catalog manifest for consistent output.
  Triggers on "generate document", "generate doc", "doc system", "iw doc",
  "/iw-doc-system", or when creating deliverable documentation for clients.
  Supersedes iw-tech-doc-writer and iw-doc-generator for deliverable documents.
---

# Innovation Ways Document System

## Purpose

Generate publication-ready deliverable documents for InnoForge. Each document follows
centralized branding, editorial guidelines, and structured templates. Output includes
Markdown (committed to git), HTML, and PDF (generated on demand via Playwright).

This skill handles the **content generation** step. The rendering pipeline
(`doc-system/scripts/`) handles HTML templating and PDF conversion separately.

## Prerequisites

Before generating ANY document, you MUST read these files in order:

1. **System instructions**: `doc-system/CLAUDE.md` (if it exists)
2. **Brand configuration**: `doc-system/brand/brand.json`
3. **Global editorial guidelines**: `doc-system/editorial/_default.md`
4. **Category editorial guidelines**: `doc-system/editorial/{category}.md` — if this file does not exist, `_default.md` already covers the required guidelines; proceed without it
5. **Document catalog**: `doc-system/catalog/index.json` — find the target document entry (skip if the doc is not listed; use `doc_title` and `editorial_category` from the job context instead)
6. **Generation manifest**: `doc-system/catalog/generation-manifest.json` — find source files for this document (skip if not listed; read `CLAUDE.md` and relevant `docs/` files instead)
7. **Source files**: Read ALL files listed in the manifest's `sources` array for this document

The editorial guidelines contain critical instructions that affect content, tone, and structure.
Do NOT skip steps 2–4. Steps 1, 5, 6, 7 may be skipped if the files don't exist or the document isn't listed.

## Workflow

### Step 1: Identify the Document

**If `$ARGUMENTS` starts with `doc-job`** (e.g. `doc-job 4914211f-...`): skip directly to the **[Job lifecycle](#job-lifecycle-when-invoked-via-iw-doc-system-doc-job-job-id)** section at the bottom of this skill. Do not execute Steps 2–6.

The user specifies a document by ID (e.g., `TECH-001`) or by description.

If by ID:
- Look up the document in `doc-system/catalog/index.json`
- Read its entry for title, audience, description, template, source dependencies

If by description:
- Search the catalog for a matching planned document
- If none exists, propose a new document ID following the naming convention:
  `{CATEGORY_PREFIX}-{NNN}` where prefixes are TECH, FUNC, GUIDE, COMP, MKT, REL

### Step 2: Read All Context

Read the prerequisite files listed above. Pay special attention to:
- The editorial guidelines for the document's category
- The source files that contain the raw information to synthesize

### Step 3: Generate Diagrams

For each diagram the document needs:

1. **Use draw.io** (preferred) via the `iw-draw-io` skill:
   - Generate the `.drawio` XML file
   - Export to `.png`
   - Store both in `documentation/{category}/{DOC_ID}-{slug}/_diagrams/`

2. **Fallback to Mermaid** only for simple flowcharts or sequence diagrams:
   - Write `.mmd` source file
   - Render via `mmdc` to `.png`
   - Store both in the `_diagrams/` subfolder

Diagram rules:
- Every diagram MUST have a descriptive title
- Every diagram MUST use brand colors from `brand.json`
- Every node/box MUST be labeled clearly
- Export both source (`.drawio` or `.mmd`) and rendered (`.png`)
- Reference diagrams in markdown as: `![Title](_diagrams/filename.png)`

### Step 4: Write the Markdown Document

Create the markdown file at:
```
documentation/{category}/{DOC_ID}-{slug}/{slug}.md
```

The markdown MUST include YAML frontmatter:
```yaml
---
id: TECH-001
title: Platform Architecture Overview
version: "1.0"
date: 2026-03-24
author: Innovation Ways
audience:
  - architects
  - senior-developers
  - ctos
status: draft
template: technical.html
---
```

Content structure depends on the document category and template. Follow the
structure defined in the editorial guidelines for that category.

General rules:
- Start with a one-paragraph executive summary (ALWAYS)
- Use heading hierarchy: H1 for title only, H2 for sections, H3 for subsections
- Diagrams before prose — show the picture, then explain it
- Tables for comparisons, not bullet lists
- Code blocks with language identifiers
- Concrete numbers over vague claims
- Active voice, present tense
- Reference the editorial guidelines for category-specific structure

### Step 5: Update Catalog

After generating the document:
- Update the document's `status` from `planned` to `draft` in `doc-system/catalog/index.json`
- Update `last_generated` to the current ISO date
- Update `version` if this is a regeneration

### Step 6: Inform the User

Tell the user:
1. What was generated (file paths)
2. How to render HTML + PDF: `make docs-generate-single ID={DOC_ID}`
3. How to review and provide feedback (edit `doc-system/editorial/{category}.md`)
4. Any source files that were missing or incomplete

## Document Categories and Prefixes

| Prefix | Category | Template | Typical Length |
|--------|----------|----------|---------------|
| TECH | technical | technical.html | 10-30 pages |
| FUNC | functional | functional.html | 5-15 pages |
| GUIDE | guides | guide.html | 5-20 pages |
| COMP | compliance | compliance.html | 10-25 pages |
| MKT | marketing | promotional.html | 1-3 pages |
| REL | releases | technical.html | 2-5 pages |

## Output Structure

```
documentation/{category}/{DOC_ID}-{slug}/
├── {slug}.md                    # Markdown source (committed)
├── {slug}.html                  # Rendered HTML (gitignored)
├── {slug}.pdf                   # Rendered PDF (gitignored)
└── _diagrams/                   # Diagrams
    ├── diagram-name.drawio      # Editable source (committed)
    └── diagram-name.png         # Rendered export (committed)
```

## Critical Rules

- **NEVER** modify `doc-system/brand/brand.json` or any template files
- **NEVER** modify `doc-system/catalog/` files except to update status/timestamp of the document you just generated
- **ALWAYS** read editorial guidelines before writing — they contain accumulated human feedback
- **ALWAYS** read ALL source files from the generation manifest before writing
- **ALWAYS** include YAML frontmatter in every markdown document
- **ALWAYS** export diagrams as both source (.drawio/.mmd) and rendered (.png)
- **ALWAYS** use brand colors in diagrams
- **NEVER** invent features, capabilities, or metrics not backed by source files
- **NEVER** use placeholder text ("Lorem ipsum", "TBD", "TODO") — if information is unavailable, state what exists and note what's missing
- **NEVER** copy-paste large sections from source files — synthesize and restructure for the target audience
- Accuracy over completeness — only document what's verifiable in source files
- Every claim must be traceable to a source file

## Job lifecycle (when invoked via `/iw-doc-system doc-job <job-id>`)

When this skill is invoked by the platform's `DocJobPoller` (i.e. the slash command `/iw-doc-system doc-job <job-id>` is issued), you are running inside a queued documentation generation job. Your responsibilities:

1. **Read the job context.** Run `uv run iw doc-job-status <job-id> --json`. The JSON output gives you `editorial_category`, `doc_id`, `project_id`, `doc_title`, `section_guides_snapshot`, and `guide_snapshot` — everything you need to produce the right content. If this command exits non-zero, do NOT proceed — close the job immediately with `iw doc-job-done <job-id> --error 'job context not found'`.

   **Note on null editorial snapshots:** `section_guides_snapshot` and/or `guide_snapshot` being `null` (or empty) is **normal and expected** — many docs have no per-section or per-type editorial guide. It is **not** a reason to abort. When the editorial snapshot is null/empty, proceed using the static editorial guidance bundled with this skill (`references/diagram-guidelines.md` for diagram docs, and the other `references/…-guidelines.md` / the rest of this SKILL.md for prose docs). Only close the job with `--error` when `iw doc-job-status <job-id> --json` itself exits non-zero (job not found / DB error), or when generation genuinely cannot proceed for a concrete reason — never merely because the editorial snapshot was empty.

2. **Generate the document content** following the editorial guide rules described in the rest of this skill.

3. **Persist content via `iw doc-update`:**
   ```
   uv run iw doc-update <doc-id> \
     --content-file - \
     --generated-by skill:<this-skill-name> \
     --trigger-reason job:<job-id>
   ```
   `<doc-id>` is the inner `ProjectDoc.doc_id` slug (e.g. `code-index`) returned by `iw doc-job-status`, NOT the UUID. Project is auto-resolved from the worktree's `.iw-orch.json` — do not pass project as a positional arg (the CLI accepts only `<doc-id>` and will reject extra positionals). Pipe markdown via stdin. Run this exactly once for the job's target doc. Do NOT call `iw doc-update` for any unrelated doc.

4. **Close the job** by calling EXACTLY ONE of:
   - `uv run iw doc-job-done <job-id>` — on success
   - `uv run iw doc-job-done <job-id> --error '<one-line message>'` — on failure

   Failing to close the job leaves it in `running` until the daemon's PID-liveness probe (within ~60s if your process exits) or the 15-minute wall-clock stall guard kicks in. Always close.

5. **Do NOT call `iw item-status`, `iw step-start`, `iw step-done`, or any work-item-oriented CLI commands.** Doc jobs are not work items. Mistakenly calling these will succeed-but-do-nothing for the job's outcome.
