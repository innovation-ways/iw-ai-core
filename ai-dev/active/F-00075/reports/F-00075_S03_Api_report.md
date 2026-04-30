# F-00075 S03 API Report

## What was done

Extended the `llm_usage_fragment` template context in `dashboard/routers/usage.py` to forward three new MiniMax fields from `_minimax_usage()` into the frontend, mirroring the existing Claude pattern:

| Key | Source | Notes |
|-----|--------|-------|
| `minimax_reset` | `minimax.get("block_reset")` | Reset timestamp; `None` on failure |
| `minimax_5h_used` | `minimax.get("used")` | Requests used in window; `None` if call failed |
| `minimax_5h_total` | `minimax.get("total")` | Window limit; `None` if call failed |

All three use `.get()` so they default cleanly to `None` when the MiniMax dict contains only `block_pct` / `block_reset` (i.e., when the remote call fails).

## Files changed

- `dashboard/routers/usage.py` — added 3 keys to template context dict (lines 39–41)

## Preflight results

| Check | Result |
|-------|--------|
| `make format` | ok |
| `make typecheck` | ok |
| `make lint` | ok |

## Test results

```
===== 2224 passed, 2 skipped, 5 xfailed, 1 xpassed, 48 warnings in 46.32s =====
```

All unit tests pass. No existing test for `llm_usage_fragment` to extend — coverage deferred to S07 as noted in the prompt.

## Notes

- The router prefix, path, and response type are unchanged.
- `_bar_color()` is unchanged.
- No new imports required.