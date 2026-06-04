// dashboard/static/help/tours.js
// Tour definitions — one entry per slug that has a meaningful guided tour.
// S05 is responsible for adding the corresponding data-tour="..." attributes
// to actual page templates.
//
// Slugs with tours: queue, batches, jobs, item_detail, code, docs, worktrees, status
// Slugs with popover-only (no tour): projects, history, batch_detail, job_detail,
//   research, tests, quality, search, containers, all_active, config,
//   keep_alive, coverage, running
window.IW_TOURS = {
  queue: [
    {
      element: "[data-tour='queue-table']",
      popover: {
        title: "The queue table",
        description:
          "Approved items appear here. Select one or more and click Create Batch to group them for the next daemon run.",
      },
    },
    {
      element: "[data-tour='queue-create']",
      popover: {
        title: "Create Batch",
        description:
          "Select items using the checkboxes, then click here to create a batch. Batches are how the daemon schedules work.",
      },
    },
    {
      element: "[data-tour='queue-drafts']",
      popover: {
        title: "Draft items",
        description:
          "Draft items are awaiting review. Click Approve to move an item into the ready queue.",
      },
    },
  ],

  batches: [
    {
      element: "[data-tour='batches-table']",
      popover: {
        title: "Batches list",
        description:
          "Every batch for this project — running, held, completed, or archived. Updated live via SSE.",
      },
    },
    {
      element: "[data-tour='batch-create']",
      popover: {
        title: "Create a new batch",
        description:
          "Open this to build a new batch from items in the queue. Give it a name and launch it.",
      },
    },
  ],

  jobs: [
    {
      element: "[data-tour='jobs-table']",
      popover: {
        title: "Unified job table",
        description:
          "Every background job — code index builds, doc generation, research drafts, batch runs — in one view.",
      },
    },
    {
      element: "[data-tour='job-cancel']",
      popover: {
        title: "Cancel a job",
        description:
          "Click the cancel button next to any running or pending job to interrupt it.",
      },
    },
  ],

  item_detail: [
    {
      element: "[data-tour='item-header']",
      popover: {
        title: "Item header",
        description:
          "This shows the item ID, type, status, and title. Click any tab below to explore.",
      },
    },
    {
      element: "[data-tour='item-tabs']",
      popover: {
        title: "Item tabs",
        description:
          "Overview, design doc, reports, artefacts, logs, fix cycles — each tab shows a different facet of this item.",
      },
    },
    {
      element: "[data-tour='item-fix-cycles']",
      popover: {
        title: "Fix cycles",
        description:
          "If any step failed, fix cycles appear here — each shows the error, the correction attempt, and the outcome.",
      },
    },
  ],

  code: [
    {
      element: "[data-tour='code-index']",
      popover: {
        title: "Code index",
        description:
          "Build or rebuild the semantic index for this codebase. The index powers the Q&A and symbol-explainer features.",
      },
    },
    {
      element: "[data-tour='code-modules']",
      popover: {
        title: "Module browser",
        description:
          "Browse all indexed modules. Click any module to explore its symbols and documentation.",
      },
    },
    {
      element: "[data-tour='code-qa']",
      popover: {
        title: "Ask about the code",
        description:
          "Type any question and the RAG system returns an answer with precise source citations.",
      },
    },
    {
      element: "[data-tour='code-arch']",
      popover: {
        title: "Architecture diagram",
        description:
          "The auto-generated architecture diagram visualises module relationships and dependencies.",
      },
    },
  ],

  docs: [
    {
      element: "[data-tour='docs-catalogue']",
      popover: {
        title: "Document catalogue",
        description:
          "Every document for this project — versioned, searchable, and rendered to HTML or PDF on demand.",
      },
    },
    {
      element: "[data-tour='docs-regen']",
      popover: {
        title: "Regenerate stale docs",
        description:
          "Documents flagged as stale can be regenerated with a single click. Progress streams live.",
      },
    },
    {
      element: "[data-tour='docs-diff']",
      popover: {
        title: "Compare versions",
        description:
          "Pick any two versions of a document and view a side-by-side diff with per-section breakdown.",
      },
    },
  ],

  worktrees: [
    {
      element: "[data-tour='worktrees-table']",
      popover: {
        title: "Worktrees table",
        description:
          "Every active git worktree created by the daemon. Shows branch, last-commit status, and which batch it belongs to.",
      },
    },
    {
      element: "[data-tour='worktree-prune']",
      popover: {
        title: "Prune worktrees",
        description:
          "Stale or merged worktrees can be pruned from this panel. The daemon will reclaim the git worktree automatically.",
      },
    },
  ],

  status: [
    {
      element: "[data-tour='status-daemon']",
      popover: {
        title: "Daemon health",
        description:
          "Shows daemon uptime, last poll timestamp, and current polling interval. Green means healthy.",
      },
    },
    {
      element: "[data-tour='status-db']",
      popover: {
        title: "Database status",
        description:
          "Verifies DB connectivity and confirms schema version matches head. Mismatches block write actions.",
      },
    },
    {
      element: "[data-tour='status-identity']",
      popover: {
        title: "Instance identity",
        description:
          "CR-00014: confirms this UI is connected to the expected DB instance. A mismatch triggers a 503 and refuses to boot.",
      },
    },
  ],
};
