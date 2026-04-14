# F-00041 S07 QVGate Report: Type Checking

## What was done

Fixed mypy type checking errors in `dashboard/routers/docs.py`:

1. **Line 169**: Added `# type: ignore` to `from weasyprint import HTML` — weasyprint is installed but ships without type stubs, causing `import-not-found` error
2. **Line 217**: Removed unused `# type: ignore` from same import — mypy reported it as unused since it had suppressed the duplicate error

## Files changed

- `dashboard/routers/docs.py` (2 line edits)

## Test results

- `mypy dashboard/routers/docs.py` → **Success: no issues found in 1 source file**

## Issues/observations

- The weasyprint imports at lines 169 and 217 are pre-existing (from F-00014 era), not introduced by F-00041
- weasyprint v68.1 is installed but provides no type stubs
- mypy appeared to only report the import error on the first occurrence (line 169) and treat the second (line 217) as already handled, making the `# type: ignore` there appear "unused"
