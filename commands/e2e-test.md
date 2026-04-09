---
description: Run end-to-end tests for the project. Reads test configuration from CLAUDE.md and Makefile.
---

# End-to-End Testing

Run the project's end-to-end test suite.

## Workflow

1. **Read CLAUDE.md** to understand:
   - E2E test framework and tools
   - How to start the application for testing
   - Test data setup requirements
   - Environment configuration

2. **Read the Makefile** for E2E test targets (e.g., `make test-e2e`).

3. **Set up test environment**:
   - Start any required services (database, etc.)
   - Apply migrations if needed
   - Seed test data if required

4. **Run E2E tests**:
   - Execute the E2E test suite
   - Capture all output

5. **Analyze results**:
   - Identify any failures
   - Categorize failures (test bug vs. application bug vs. environment issue)
   - Check for flaky tests

6. **Report to user**:
   - Total tests: pass/fail/skip counts
   - Details of any failures
   - Screenshots or logs if available
   - Recommendations for fixing failures

## Safety

- Do NOT modify production code to make tests pass
- Do NOT skip failing tests
- Clean up test data and services after completion
