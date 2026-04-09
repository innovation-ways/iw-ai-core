# Workflow Definition

## Steps
1. Implementation (agent: per step_type)
2. Code Review (agent: code-review-impl)
3. Code Review Fix (agent: code-review-fix-impl, conditional: review finds issues)
4. Code Review Final (agent: code-review-final-impl)
5. Code Review Fix Final (agent: code-review-fix-final-impl, conditional)
6. Quality Validation: lint (script)
7. Quality Validation: format (script)
8. Quality Validation: typecheck (script)
9. Quality Validation: tests (script)
10. Browser Verification (agent: quality-validation-impl, conditional: browser_verification=true)

## Timeouts
(use platform defaults)

## Fix Cycles
max_fix_cycles: 5
