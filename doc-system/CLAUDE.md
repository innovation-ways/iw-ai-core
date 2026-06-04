# doc-system — Documentation System Instructions

This directory contains the configuration and editorial guidelines for the IW AI Core
documentation system. It is read by the `iw-doc-system` and `iw-doc-generator` skills
before generating any document.

## Directory Layout

| Path | Purpose |
|------|---------|
| `brand/brand.json` | Innovation Ways brand colors, fonts, and logo metadata |
| `editorial/_default.md` | Global editorial guidelines — apply to all documents |
| `editorial/{category}.md` | Category-specific overrides (marketing, technical, …) |
| `catalog/index.json` | Registered document catalog — ID, title, category, status |
| `catalog/generation-manifest.json` | Per-document source files and diagram specs |

## How to Use

1. Read `brand/brand.json` for brand colors (use in diagrams).
2. Read `editorial/_default.md` for universal writing rules.
3. Read `editorial/{category}.md` if it exists for category-specific structure rules.
4. Look up the target document in `catalog/index.json` by its ID or `doc_id` slug.
5. Look up source files in `catalog/generation-manifest.json` for that document ID.
6. If the document is not in the catalog or manifest, use the project's `CLAUDE.md` and
   relevant `docs/` files as source material, guided by the editorial guidelines.

## Categories

| Category | Prefix | Audience |
|----------|--------|----------|
| technical | TECH | engineers, architects |
| functional | FUNC | product, engineering |
| guide | GUIDE | operators, developers |
| compliance | COMP | legal, auditors |
| marketing | MKT | executives, stakeholders |
| release | REL | all |

## Critical Rules

- Documents managed by the platform (`doc_type` stored in DB) are persisted via
  `iw doc-update`, not written to files. Only deliverable documents go to `documentation/`.
- Never modify `brand/brand.json` or template files.
- Never add documents to the catalog that haven't been approved by the project owner.
