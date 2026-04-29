# F-00067 S03 Template Report

## Step Summary

Updated skill templates to incorporate the new visual design standards from the Feature Design doc.

## Files Changed

1. `skills/iw-doc-generator/references/module-doc-template.md` — Added "## Why Read This", "## Key Diagrams" sections, and callout usage rules comment
2. `skills/iw-doc-generator/references/diagram-guidelines.md` — Created new file with semantic color palette, diagram type selection, and abstraction rules
3. `skills/iw-tech-doc-writer/references/diagram-guidelines.md` — Added "## Canonical Color Palette" and "## Why Paragraph Rule" sections

## Skills Sync

Ran `uv run iw sync-skills`:
- **iw-ai-core**: 22 skipped (project override) — current project uses local skill overrides
- **innoforge**: 16 skipped (project override), 6 up to date — doc-generator and tech-doc-writer have project overrides

Non-blocking: Some skills show "project override (skipped)" meaning those projects have local versions that take precedence. The updated canonical content is available in the platform skills directory.

## Preflight

- **Lint**: 2 pre-existing ARG001 errors in `dashboard/routers/code_qa.py` (unused function arguments `dsl` in `render_mermaid` and `render_d2`). Unrelated to this step's changes.
- **Typecheck**: Skipped (markdown-only skill files)
- **Format**: Skipped (markdown-only skill files)

## Test Summary

N/A — markdown skill files