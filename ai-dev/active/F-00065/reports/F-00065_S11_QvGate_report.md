# F-00065 S11 QvGate Report

## Gate: unit-tests | Command: `make test-unit`

## Result: FAIL

**Summary:** 3 unit tests failed; 1932 passed, 2 skipped.

## Failing Tests

| Test | File |
|------|------|
| `test_mermaid_blocks_converted_to_div` | `tests/unit/test_code_ui_routes.py:50` |
| `test_multiple_mermaid_blocks_converted` | `tests/unit/test_code_ui_routes.py:59` |
| `test_mermaid_blocks_with_whitespace_converted` | `tests/unit/test_code_ui_routes.py:74` |

## Issue

The `_preprocess_mermaid` function in `dashboard/routers/code_ui.py` is returning `<pre data-lang="mermaid"><code>...</code></pre>` instead of `<div class="mermaid">...</div>` for mermaid code blocks. The tests assert that the function should convert mermaid blocks to div elements with the `mermaid` CSS class.

**Observed output:**
```
'<pre data-lang="mermaid"><code>graph TD\n  A-->B</code></pre>'
```

**Expected output (per tests):**
```
'<div class="mermaid">graph TD\n  A-->B</div>'
```

## Recommendation

The `_preprocess_mermaid` function in `dashboard/routers/code_ui.py` needs to be fixed to properly convert mermaid fenced code blocks into `<div class="mermaid">...</div>` elements instead of leaving them as `<pre>` blocks.
