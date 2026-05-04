# CR-00030 — Functional Design

## Why

The dashboard footer shows a small Claude usage indicator with two numbers: a label on the left of each progress bar and a percentage on the right. For the short five-hour budget, the label currently shows the wall-clock time at which the slot resets, for example "15:00". A user looking at this has to glance at their own clock and subtract to know how long they actually have left. The MiniMax indicator beside it already shows time remaining (for example "4h 32m"), so the two indicators are inconsistent and the Claude one is the harder of the two to read at a glance. This change brings the Claude five-hour label in line with the MiniMax one.

## What Changed (for the User)

- The Claude five-hour label in the footer now reads as time remaining, in the form "Xh Ym" (for example "4h 32m") when at least one hour is left, or "Xm" (for example "25m") when less than an hour is left.
- If less than a minute is left but the slot has not yet reset, the label reads "0m".
- When the slot has already reset or no usage has been recorded yet, the label falls back to the existing placeholder "5h", exactly as it does today.
- The Claude seven-day label is intentionally untouched — it continues to show the wall-clock day and time of reset (for example "Tue 09:00"), because users typically want to know what day, not how many hours.
- The percentage on the right of each bar (for example "8%") is unchanged in every case.

## How It Behaves

The label is refreshed by the same background poll that already updates the footer once per minute. When the page is idle for a long time, the label can be slightly stale — up to one polling cycle — which is the same behaviour as before.

If the underlying rate-limit cache is missing, unreadable, or older than its reset deadline, the indicator behaves exactly as it does today: the percentage shows zero and the label falls back to the static "5h" placeholder. No new error states, modal dialogs, or notifications are introduced.

If the slot resets while the page is open, the next refresh shows the new "Xh Ym" label counting down from the new deadline, and the percentage resets to whatever the next reading reports.

## Out of Scope

- The seven-day Claude label and the MiniMax five-hour label are not touched.
- No change to how usage is measured, fetched, or cached. This is purely a label-formatting change in the dashboard footer.
