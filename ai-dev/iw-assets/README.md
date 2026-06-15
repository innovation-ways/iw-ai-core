# Innovation Ways — brand assets

The canonical, ready-to-use logo, icon, and social assets for Innovation Ways. Everything
here is generated from a single source of truth — **`scripts/build-brand-assets.mjs`** — so
the mark, colours, and wordmark stay identical across every file and match the live website.

> Regenerate after any change to the mark, colours, or taglines:
> ```bash
> node scripts/build-brand-assets.mjs
> ```

## Brand basics

| Token | Value | Use |
|-------|-------|-----|
| Accent (teal) | `#0D9488` | The "I" of the mark, links, accents |
| Accent strong | `#115E59` | Hover/active teal |
| Ink | `#1A1D23` | The "W" of the mark, primary text |
| Paper | `#FFFFFF` | Light background (brand default) |
| Dark paper | `#1B1F27` | Dark-mode / dark banner background |
| Muted | `#71757E` | Secondary text |

- **Mark:** "IW" monogram — teal **I** + ink **W** (single round-cap strokes). On the
  rounded-square tile, both letters are white on teal.
- **Wordmark:** "Innovation Ways" in **Space Grotesk, weight 600**, tracking `-0.02em`.
- **Clear space:** keep at least the height of the **I** clear around any lockup.
- The light/clean treatment is the default. Use the white/dark variants only on dark or
  photographic backgrounds.

## `svg/` — vector sources (scale to any size)

| File | What |
|------|------|
| `iw-mark.svg` | **Primary mark** — teal I + ink W, transparent (light backgrounds) |
| `iw-mark-white.svg` | Teal I + white W — for dark / photo backgrounds |
| `iw-mark-mono-ink.svg` | Single-colour ink (one-colour print, stamps) |
| `iw-mark-mono-white.svg` | Single-colour white (knockout on solid colour) |
| `iw-tile.svg` | Rounded teal tile + white monogram — app icon / avatar |
| `iw-tile-maskable.svg` | Full-bleed teal tile, mark in the inner safe zone — PWA maskable |
| `iw-logo-horizontal.svg` | Mark + wordmark, ink — **default logo** |
| `iw-logo-horizontal-white.svg` | Mark + wordmark, white — dark backgrounds |
| `iw-logo-stacked.svg` | Mark above wordmark — square-ish placements |
| `iw-wordmark.svg` | Wordmark only |

The mark/tile SVGs are pure paths — fully portable. The lockup/wordmark SVGs use live
`<text>` in Space Grotesk; they render correctly anywhere the font is installed. **For print
or hand-off to a design tool, outline the text to paths first.**

## `png/` — web & app rasters

| File | Size | Use |
|------|------|-----|
| `iw-mark-512.png` / `iw-mark-1024.png` | 512 / 1024² | Transparent mark |
| `iw-mark-white-1024.png` | 1024² | Transparent mark for dark backgrounds |
| `iw-tile-512.png` / `iw-tile-1024.png` | 512 / 1024² | App icon / avatar tile |
| `apple-touch-icon-180.png` | 180² | iOS home-screen icon |
| `android-chrome-192.png` / `-512.png` | 192 / 512² | PWA manifest icons |
| `maskable-512.png` | 512² | PWA maskable icon |
| `favicon-16/32/48.png` | 16/32/48² | Favicons |
| `iw-logo-horizontal-2400.png` | ~3500w | Default logo, transparent, tight-cropped |
| `iw-logo-horizontal-white-2400.png` | ~3500w | Logo for dark backgrounds |
| `iw-logo-stacked-1600.png` | ~1900w | Stacked logo, transparent |
| `iw-wordmark-1600.png` | ~1900w | Wordmark only, transparent |
| `og-image-1200x630.png` (+ `.svg`) | 1200×630 | Open Graph / social share card |

## `social/` — social media

| File | Size | Where |
|------|------|-------|
| `linkedin-company-cover-1128x191.png` | 1128×191 | LinkedIn **company page** banner |
| `linkedin-personal-banner-1584x396.png` | 1584×396 | LinkedIn **personal profile** background |
| `linkedin-personal-banner-dark-1584x396.png` | 1584×396 | Dark variant of the above |
| `linkedin-personal-banner-avatar-safe-1584x396.png` | 1584×396 | **Recommended for personal profile** — logo top-left, text right-aligned clear of the profile-photo overlay |
| `linkedin-personal-banner-avatar-safe-dark-1584x396.png` | 1584×396 | Dark variant of the avatar-safe banner |
| `x-header-1500x500.png` | 1500×500 | X / Twitter header |
| `linkedin-avatar-400.png` | 400² | LinkedIn profile/company logo |
| `github-org-avatar-512.png` | 512² | GitHub org avatar |

Each banner also has an editable `.svg` source alongside its PNG.

> **Safe-zone note:** LinkedIn overlays the profile/company logo on the **lower-left** of the
> banner, and crops a little on small screens. The IW lockup and tagline sit upper-/mid-left
> by design; the URL line is near the bottom-left and may be partially covered by the avatar
> on a personal profile. If that bothers you, use the company cover (no avatar overlap on the
> text) or ask for a centred/right-biased variant.

## Note on `../logo-candidates/`

That folder holds earlier exploration (chevron "Converging Ways" concepts A/B and comparison
sheets). **Superseded** — the shipped identity is the IW monogram generated here and used by
`src/components/Logo.astro` and the favicon set. Kept for history only.
