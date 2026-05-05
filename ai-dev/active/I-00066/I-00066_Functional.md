# I-00066 — Functional Design

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This item adds no migration — pure presentation change.)

## Why

A reviewer of the OSS Compliance page noticed two visual issues with the
detail popup that opens from the row-level "…" button. The popup is too
narrow on a desktop window — about half of the screen — which makes the
already long explanatory text feel cramped. The popup's footer contains
three actions (re-run the check, mark accepted, close) but they look
like plain text labels rather than buttons, so a first-time viewer hesitates
about whether they can click them. The goal is to make the popup feel
appropriately sized for the content it shows and to make the bottom
actions read unambiguously as buttons, while keeping the look elegant
and free of flashy or brand-coloured backgrounds.

## What Changed (for the User)

- The OSS finding popup now occupies roughly eighty percent of the
  window width on a desktop, instead of about half. The popup is more
  comfortable to read; long explanations and long file lists fit
  without forcing horizontal scrolling.
- The three footer actions render with a visible border, consistent
  padding, consistent height, and a clear hover effect. They look
  unmistakably like buttons.
- The bottom-right close action looks like a peer of the other two
  footer buttons, instead of inheriting the tiny header close icon
  style.

## How It Behaves

When a reviewer is on the OSS Compliance page and clicks the "…"
button on any row, the popup that appears now sizes itself relative
to the window: on wide screens it spans most of the visible area;
on narrower screens (small laptops, tablets) it shrinks to fit
without overflowing. The popup still has a maximum height so it
never runs off the screen — content beyond that limit scrolls
inside the popup as before.

The footer always shows the same three actions on a typical row
(re-run check, mark accepted, close). They look like buttons at
rest and respond visibly to a hover. Clicking the close button
in the footer dismisses the popup, exactly as before; clicking
the small close icon in the popup's top-right corner also still
works — the icon style for that header close is intentionally
unchanged. The other actions (preview / apply / accept-form
confirm) keep their existing wiring.

## Out of Scope

- The popup's header close icon (the small "×" in the top-right
  corner) is left untouched. Changing it would alter look-and-feel
  beyond the bug report.
- No content, copy, ordering, or behaviour of the popup sections
  (What this test checks / How it tests / Risk / Findings / How
  to fix / References) changes — only the popup width and the
  footer button styling.
