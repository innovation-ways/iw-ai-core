# CR-00012 S01 Frontend Report

## What was done

Fixed the **stale/status badge overlap** issue in `docs_card.html`.

### Problem
The stale badge was positioned absolutely at `top-2 right-2` of the card, while the status badge was the last item in a flex container. When both were shown, they visually overlapped.

### Solution
Moved the stale badge **inside the flex container**, after the status badge. Now the order is:

```
Type → Tier → [flex-1 spacer] → Last Failed → Status → Stale
```

Both badges flow naturally and cannot overlap. Also removed the unnecessary `border border-yellow-300` on the stale badge (inconsistent with other badges).

### Files Changed
- `dashboard/templates/fragments/docs_card.html`

### Test Results
- Lint: 1 pre-existing warning (ARG002 in `orch/rag/qa.py`) — not related to this change
- No JS syntax errors in dashboard static files

### Issues/Observations
- The card still has `relative` positioning for the select checkbox at `top-3 left-3` (which is correct — checkbox is conditionally shown)
- No functional tests exist for docs card rendering