---
description: User story acceptance testing. Validates that implemented features meet the acceptance criteria defined in the design document.
---

# User Story Acceptance Testing

Validate that an implemented work item meets its acceptance criteria.

## Usage

Provide the work item ID to test.

## Workflow

1. **Read the design document** at `ai-dev/design/work/{ID}/design.md` to extract acceptance criteria.

2. **Read CLAUDE.md** to understand the project's architecture and how to interact with the system.

3. **For each acceptance criterion**:
   a. **Understand the criterion** — what exactly needs to be true?
   b. **Determine how to test it**:
      - Can it be verified by running existing tests?
      - Does it require manual verification (reading code, checking output)?
      - Does it require running the application?
   c. **Execute the test**:
      - Run relevant test suites
      - Check code for correct implementation
      - Verify behavior matches the criterion
   d. **Record result**: PASS or FAIL with evidence

4. **Run the full test suite** to check for regressions:
   ```bash
   make test-unit
   make test-integration
   ```

5. **Report to user**:

   For each acceptance criterion:
   - Criterion description
   - Test method used
   - Result: PASS or FAIL
   - Evidence (test output, code reference, etc.)

   Summary:
   - Total criteria: X
   - Passed: Y
   - Failed: Z
   - Overall verdict: ACCEPTED or REJECTED
   - Notes on any failures

## Safety

- Do NOT modify code during acceptance testing
- Do NOT mark criteria as passed without evidence
- Report ALL failures, even minor ones
