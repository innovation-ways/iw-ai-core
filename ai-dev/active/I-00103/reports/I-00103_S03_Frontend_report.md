# I-00103 S03 Frontend Report

## Summary

Added a "Per-file errors" section to `auto_merge_event_detail.html` that renders the new `per_file_errors` field from `merge_auto_resolution_failed` event metadata as a labelled, readable block above the raw JSON dump. The section is hidden when the field is absent or empty (backward compatibility for historical events).

## What Was Done

Modified `dashboard/templates/fragments/auto_merge_event_detail.html` to add a new `<section>` after the "Message" paragraph and before the "Metadata" `<details>` block. The section:

- Guards on `event.metadata.get('per_file_errors')` — only renders when the key is present **and** non-empty.
- Iterates the list, rendering one card per entry with `file`, `runtime` (cli_tool/model), and `error` fields.
- Wraps the error string in `<pre>` to preserve multi-line / free-form text (timeouts, exit codes, JSON exceptions).
- Uses existing Tailwind utility classes already used in the fragment (`text-xs`, `text-muted-foreground`, `uppercase`, `tracking-wide`, `font-mono`, `grid`, `gap-1`), so no new CSS is needed.

No existing behaviour is modified — the top-of-modal DL, the Message paragraph, the Metadata block, the Verdict section, the Diffs section, and the verdict form all render exactly as before.

## Files Changed

- `dashboard/templates/fragments/auto_merge_event_detail.html` — added "Per-file errors" section above the "Metadata" block

## Preflight Results

| Gate | Result |
|------|--------|
| `make format` | ok — no drift |
| `make typecheck` | ok — 0 errors in 274 source files |
| `make lint` | ok — All checks passed (including `scripts/check_templates.py`) |

## Test Verification

```
uv run pytest tests/dashboard/test_auto_merge_routes.py -v 2>&1 | tail -5
```

**57 passed, 0 failed** in 50.00 s. Coverage warning is pre-existing and unrelated to this change.

**TDD note**: template/markdown edits only, no production logic. Behavioural tests (render-with-field, render-without-field, render-with-empty-list) are owned by S05 (tests-impl) per the design doc's TDD Approach.

## Acceptance Criteria Coverage

- **AC3** (renders when present): The new `<section>` uses the same `text-xs` / `text-muted-foreground` / `uppercase` heading pattern as the existing "Message" and "Metadata" sections. `entry.file_path`, `entry.cli_tool/entry.model`, and `entry.error` all render via Jinja2 expression (autoescape on, no `| safe`).
- **AC4** (hides when absent or empty): Jinja2 guard `{% if per_file_errors %}` ensures the section is absent from the HTML when the key is missing or the list is empty.

## Blockers

None.