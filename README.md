# IW AI Core

**An AI-assisted development platform that schedules LLM agents in isolated git worktrees, runs automated fix cycles, and squash-merges to main — so developers review outcomes, not process.**

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/innovation-ways/iw-ai-core/badge)](https://securityscorecards.dev/viewer/?uri=github.com/innovation-ways/iw-ai-core)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

![IW AI Core — project dashboard showing active batches, recent activity, and git status](assets/screenshot-dashboard.png)

---

IW AI Core is the orchestration layer between your backlog and your main branch. You design a feature or bug fix, approve it, and the platform handles the rest: it picks up work items, spins up a sandboxed git worktree with its own Docker stack, launches a claude-code or opencode agent, runs your test and quality gates, iterates through fix cycles, and squash-merges on success. A FastAPI dashboard gives you live visibility into every agent, job, and document the system produces.

**Who it's for**: engineering teams that want AI-assisted development without sacrificing code review standards or losing traceability.

---

## Table of Contents

- [Quick Start](#quick-start)
- [Features](#features)
- [Architecture](#architecture)
- [Why IW AI Core?](#why-iw-ai-core)
- [Dashboard](#dashboard)
- [Research](#research)
- [Documentation Catalogue](#documentation-catalogue)
- [Docs Reference](#docs-reference)
- [Contributing](#contributing)
- [License](#license)

---

## Quick Start

**Prerequisites**: Docker, Python 3.11+, [uv](https://docs.astral.sh/uv/)

```bash
git clone https://github.com/innovation-ways/iw-ai-core.git
cd iw-ai-core
./ai-core.sh install      # sync deps, start DB, run migrations
./ai-core.sh start        # start daemon + dashboard
```

Open **http://localhost:9900** — the dashboard is live.

> For manual setup, cloud deployments, or non-Docker environments see [DB Setup](docs/IW_AI_Core_DB_Setup.md).

---

## Features

| Feature | Description |
|---------|-------------|
| Agent Scheduler | Polls approved work items, launches claude-code or opencode agents in isolated git worktrees |
| Worktree Isolation | Each work item gets a fresh git worktree with its own Docker compose stack and PostgreSQL |
| Automated Fix Cycles | Agents retry failing test/quality gates up to N times before escalating for review |
| Web Dashboard | FastAPI + htmx UI: queue, history, batches, docs, code understanding, jobs, worktrees |
| Code Understanding | LanceDB-backed RAG with streaming Q&A, symbol explainer, and citation links |
| Doc Generation | AI-generated versioned docs with diff tracking, HTML/PDF export, and stale detection |
| Test & Quality Runner | Launch and monitor pytest suites and lint gates from the UI with live output |
| Multi-Project | Manage multiple repositories from one platform via `projects.toml` |
| DB Backups | Daily scheduled logical backups with configurable retention and a guided restore runbook |
| `iw` CLI | Agent-to-DB bridge: `iw step-done`, `iw next-id`, `iw register`, and more |

---

## Architecture

```mermaid
flowchart TD
    Dev["Developer"] -->|"design + approve"| DB[("PostgreSQL\nport 5433")]
    DB -->|"poll every 60s"| Daemon["Daemon"]
    Daemon -->|"git worktree add"| WT["Isolated Worktree\n+ Docker Stack"]
    WT -->|"launch agent"| Agent["LLM Agent\nclaude-code / opencode"]
    Agent -->|"iw step-done"| DB
    Agent -->|"tests / gates fail"| Fix["Fix Cycle\nup to N retries"]
    Fix -->|"gates pass"| Merge["Squash merge → main"]
    Fix -->|"exhausted"| Queue["Back to queue\nneeds review"]
    DB -->|"live data"| Dashboard["FastAPI Dashboard\nport 9900"]
    Dashboard -->|"RAG + Q&A"| RAG["LanceDB\nCode Index"]
```

All operational state lives in PostgreSQL — no files, no race conditions. The daemon also drives background jobs for doc generation (`DocGenerationJob`) and code indexing (`CodeIndexJob`).

---

## Why IW AI Core?

Modern AI coding tools answer questions or write patches — they don't own the full development lifecycle. IW AI Core is built around the insight that **the hard part isn't generating code, it's integrating it**: running the right tests, iterating on failures, respecting branch policies, and producing a reviewable diff.

|  | IW AI Core | LangChain | AutoGen | Temporal |
|--|:--:|:--:|:--:|:--:|
| LLM agent scheduling on backlog items | ✅ | ❌ | ❌ | ❌ |
| Git worktree isolation per work item | ✅ | ❌ | ❌ | ❌ |
| Automated test/gate fix cycles | ✅ | ❌ | Partial | ❌ |
| Web dashboard with live agent visibility | ✅ | ❌ | Partial | ✅ |
| RAG-backed code understanding | ✅ | Partial | ❌ | ❌ |
| Multi-project management | ✅ | ❌ | ❌ | Partial |
| Versioned AI-generated documentation | ✅ | ❌ | ❌ | ❌ |

---

## Dashboard

The dashboard is the human interface to the platform — a FastAPI + htmx web app with per-project pages for every stage of the development lifecycle.

<table>
  <tr>
    <td align="center">
      <img src="assets/screenshot-queue.png" width="420"/><br/>
      <sub><b>Work Item History</b> — filterable log of every feature, incident, and change request</sub>
    </td>
    <td align="center">
      <img src="assets/screenshot-code-qa.png" width="420"/><br/>
      <sub><b>Code Understanding</b> — architecture map with inline RAG-backed Q&A chat panel</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <img src="assets/screenshot-research.png" width="420"/><br/>
      <sub><b>Research Catalogue</b> — filed research documents with mode tags and full-text search</sub>
    </td>
    <td align="center">
      <img src="assets/screenshot-docs.png" width="420"/><br/>
      <sub><b>Documentation Catalogue</b> — AI-generated docs with version tracking and export</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <img src="assets/screenshot-tests.png" width="420"/><br/>
      <sub><b>Test Runner</b> — launch E2E, performance, and unit suites with one click</sub>
    </td>
    <td align="center">
      <img src="assets/screenshot-quality.png" width="420"/><br/>
      <sub><b>Quality Gates</b> — lint, format, type-check, dead code, and dependency hygiene</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <img src="assets/screenshot-item-detail.png" width="420"/><br/>
      <sub><b>Item Detail</b> — step pipeline with agent assignments, fix cycles, and execution metrics for a completed incident</sub>
    </td>
    <td align="center">
      <img src="assets/screenshot-item-test-restart.png" width="420"/><br/>
      <sub><b>Implementation with Test Verification</b> — 15-step pipeline over 761m with 6 fix cycles including test-suite restart steps</sub>
    </td>
  </tr>
</table>

---

## Research

![Research catalogue showing filed documents with mode tags](assets/screenshot-research.png)

The Research page is a structured knowledge base built alongside the codebase. Every time a decision requires investigation — evaluating a library, understanding a failure mode, mapping a design space — the `/iw-research` skill files a research document with a unique ID (`R-NNNNN`), registers it in the database, and makes it searchable from the dashboard.

**What it offers:**

- **Filed research documents** tied to work items — so the reasoning behind a design decision is never lost in Slack or a browser tab
- **Mode tagging** (Technical, Functional, Marketing, Compliance, Release) for filtering by audience
- **Full-text search** across all research titles
- **Direct linking** from design documents to the research that informed them
- **Version-controlled** — every document lives in `docs/research/` in the repository, visible in git history

Research documents are first-class project artifacts. When an agent designs a feature, it can read prior research to avoid reinvestigating solved problems.

---

## Documentation Catalogue

![Documentation catalogue with versioned cards and export options](assets/screenshot-docs.png)

The Docs page manages AI-generated technical documentation for each project. Rather than hand-maintaining docs that drift from the code, IW AI Core regenerates them on demand and tracks what has changed.

**What it offers:**

- **AI-generated documents** covering architecture, modules, components, diagrams, and guides — produced by the `iw-doc-generator` skill against the current codebase
- **Stale detection** — the platform monitors source files and flags documents whose underlying code has changed since last generation, with a one-click "Regenerate All Stale" action
- **Version history** — every generation is a new version; diffs show exactly what changed between `v1` and `v2`
- **Export** — each document can be exported as HTML or PDF for sharing outside the platform
- **Audience targeting** — documents carry audience metadata (`architects`, `senior-developers`, `contributors`) so agents can serve the right level of detail
- **Editorial categories** — Technical, Functional, Marketing, Compliance, and Release, with per-project catalogues and a global `/docs` view spanning all projects

Documents are stored in `docs/` in the repository. The platform is the generation and versioning layer — the content itself remains in git.

---

## Docs Reference

| Document | Contents |
|----------|----------|
| [Architecture](docs/IW_AI_Core_Architecture.md) | System layout and end-to-end flow |
| [DB Setup](docs/IW_AI_Core_DB_Setup.md) | Production and bootstrap setup |
| [CLI Spec](docs/IW_AI_Core_CLI_Spec.md) | Every `iw` command: inputs, outputs, DB ops |
| [Daemon Design](docs/IW_AI_Core_Daemon_Design.md) | Daemon loop, state transitions, monitoring |
| [Dashboard Design](docs/IW_AI_Core_Dashboard_Design.md) | Dashboard pages, htmx patterns, SSE |
| [Testing Strategy](docs/IW_AI_Core_Testing_Strategy.md) | Test layers, infrastructure, conventions |
| [DB Backup & Restore](docs/IW_AI_Core_DB_Backup_Restore.md) | Backup configuration and restore runbook |
| [Worktree Isolation](docs/IW_AI_Core_Worktree_Isolation.md) | Per-worktree Docker compose design |

---

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for how to open issues and pull requests.

All commits must be signed-off per the [Developer Certificate of Origin](https://developercertificate.org/):

```bash
git commit -s -m "your message"
```

Please do not file public issues for security vulnerabilities — see [SECURITY.md](SECURITY.md) for the responsible disclosure process.

This project follows the [Contributor Covenant v3](CODE_OF_CONDUCT.md). Report conduct concerns to info@innovation-ways.com.

---

## License

Licensed under the [Apache-2.0](LICENSE) license.  
Copyright © 2026 Innovation Ways.

"Innovation Ways" is a trademark of Innovation Ways. See [TRADEMARK.md](TRADEMARK.md) for permitted uses.

---

Maintained by [Innovation Ways](https://innovation-ways.com).
