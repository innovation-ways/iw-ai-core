# User Guide Structure Reference

## Purpose

Detailed section breakdown for user guides. The `iw-tech-doc-writer` skill references this file when generating end-user documentation.

---

## Document Structure

```
1. Document Header
   - Title: "{System} — User Guide"
   - Version, Date, Status
   - Audience: End Users, Administrators, Support Staff
   - Document purpose (what the reader will learn)

2. Table of Contents

3. Introduction (150-300 words)
   - What the system does (plain language, no jargon)
   - Who this guide is for
   - What you'll learn
   - How to use this guide (read sequentially vs. reference)

4. Getting Started (300-500 words)
   - Prerequisites (accounts, access, software)
   - First-time setup steps (numbered, with screenshots/diagrams)
   - Verification: how to confirm setup worked
   - Workflow overview diagram

5. Core Workflows (600-1,500 words)
   - One H3 section per major workflow
   - Each workflow:
     - Goal: what the user accomplishes
     - Steps: numbered, specific, actionable
     - Visual: screenshot, diagram, or annotated UI reference
     - Expected result: what success looks like
     - Common variations or options
   - Prioritize by frequency of use (most common first)

6. Advanced Features (300-600 words)
   - Features that aren't needed daily
   - Configuration options
   - Customization
   - Integration with other tools

7. Administration (300-500 words, if applicable)
   - Admin-only features
   - User management
   - System configuration
   - Monitoring and health checks

8. Troubleshooting (300-500 words)
   - Common issues table (Symptom | Cause | Fix)
   - Error messages and their meaning
   - How to get support
   - Diagnostic steps

9. FAQ (200-300 words)
   - 5-10 most asked questions
   - Direct, concise answers

10. Glossary (100-200 words, if needed)
    - Domain-specific terms
    - Acronyms
```

## Required Diagrams

| # | Diagram | Type | Complexity |
|---|---------|------|------------|
| 1 | System workflow overview | Flowchart | 6-10 nodes |
| 2 | Primary user journey | Flowchart or sequence | 5-8 steps |
| 3 | Setup/onboarding flow | Flowchart | 4-6 nodes |

Minimum: 2 diagrams. Target: 3-4.

## Writing Style

User guides differ from architecture docs:

- **Plain language** — avoid jargon, define terms on first use
- **Imperative mood** for instructions — "Click the Create button" not "The user should click..."
- **Numbered steps** for procedures — every action is a step
- **Expected results** after each major step — "You should see a confirmation message..."
- **Callout boxes** for warnings and tips
- **Visual aids** — diagrams, tables, annotated screenshots

## Tables to Include

- Feature comparison (Free vs. Pro)
- Configuration options (Setting | Default | Description)
- Troubleshooting (Symptom | Cause | Fix)
- Keyboard shortcuts (if applicable)

## Audience Expectations

- **End users**: Want step-by-step instructions, plain language, visual aids
- **Administrators**: Want configuration, user management, monitoring
- **Support staff**: Want troubleshooting guide, error reference, FAQ
