# CR-00003 S01 — Frontend Implementation

## Input Files

- `dashboard/static/favicon.svg` — source SVG to convert
- `dashboard/templates/base.html` — template to update (line ~95)

## Output Files

- `dashboard/static/logo.png` — new static asset (generated)
- `dashboard/templates/base.html` — modified (sidebar logo element)

## Context

You are implementing a cosmetic change to the IW AI Core dashboard. Read `CLAUDE.md` for project conventions.

**Work item**: CR-00003  
**Step**: S01  
**Agent**: frontend-impl

## Objective

Replace the "IW" text badge in the sidebar with a PNG version of the favicon SVG. Two changes are required:

1. Generate `dashboard/static/logo.png` from the existing `dashboard/static/favicon.svg`
2. Update `dashboard/templates/base.html` to use the PNG instead of the text badge

## Task 1: Generate logo.png

Run the following command from the repo root:

```bash
convert -background transparent -size 56x56 dashboard/static/favicon.svg dashboard/static/logo.png
```

Verify the output:
```bash
identify dashboard/static/logo.png
```

Expected: `PNG 56x56 56x56+0+0 8-bit sRGBA` (or TrueColorAlpha). If the command fails, check that ImageMagick is available at `/usr/bin/convert`.

## Task 2: Update base.html

File: `dashboard/templates/base.html`

**Find** (line ~95):
```html
<div class="w-7 h-7 rounded bg-primary flex items-center justify-center text-primary-foreground font-bold text-sm">IW</div>
```

**Replace with**:
```html
<img src="/static/logo.png" alt="IW AI Core" class="w-7 h-7">
```

The surrounding `<a>` tag and `<span>IW AI Core</span>` must remain **unchanged**.

## Verification

After making both changes:

1. Confirm `dashboard/static/logo.png` exists and is a valid PNG
2. Confirm `base.html` no longer contains `bg-primary` or the text `>IW<` in the logo area
3. Confirm the `<a>` wrapper and `<span>IW AI Core</span>` are intact

## Signal completion

```bash
iw step-done CR-00003 S01 --summary "Generated logo.png from favicon.svg; updated base.html sidebar logo from IW text badge to img tag"
```

If anything goes wrong:
```bash
iw step-fail CR-00003 S01 --reason "<what failed>"
```
