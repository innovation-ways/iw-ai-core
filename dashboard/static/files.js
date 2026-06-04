/**
 * files.js — Files tab client-side logic
 *
 * Responsibilities:
 * - Initial diff fetch + Diff2HtmlUI render on tab load
 * - Step dropdown change → re-fetch + re-render
 * - Live filter (path substring) across tree rows and diff cards
 * - Tree node click → scroll + expand diff card
 * - Per-file large-file collapse toggle (client-side only)
 * - Dark-mode sync with Diff2HtmlUI colorScheme
 * - Untracked sub-panel expand → fetch /files/untracked JSON → populate list
 *
 * No build step — vanilla JS, ES2020.
 */

(function () {
  "use strict";

  // ─── State ────────────────────────────────────────────────────────────────

  let _ctx = null;
  let _currentStep = "all";
  let _diff2htmlUi = null;
  let _filterText = "";
  let _allFilePaths = [];   // used for keyboard nav j/k

  // ─── Init ────────────────────────────────────────────────────────────────

  document.addEventListener("DOMContentLoaded", function () {
    _ctx = window.__IW_FILES_CTX || {};
    if (!_ctx.projectId || !_ctx.itemId) return;

    _currentStep = _ctx.stepOptions ? "all" : "all";

    // Populate step dropdown
    _populateStepSelect();

    // Wire filter input
    var filterInput = document.getElementById("diff-filter-input");
    if (filterInput) {
      filterInput.addEventListener("input", _onFilterInput);
    }

    // Wire untracked panel expand
    var untrackedDetails = document.getElementById("untracked-panel");
    if (untrackedDetails) {
      untrackedDetails.addEventListener("toggle", _onUntrackedPanelToggle);
    }

    // Dark-mode observer
    _observeDarkMode();

    // Initial diff render
    _renderDiff(_currentStep);
  });

  // Re-initialize after htmx swaps any content into #tab-content
  document.body.addEventListener("htmx:afterSwap", function (evt) {
    // Check if the swap targeted or contained #tab-content
    var target = evt.detail.target;
    var swappedEl = evt.detail.element;
    if (target && target.id === "tab-content") {
      _reInitFilesTab();
    } else if (swappedEl && swappedEl.querySelector && swappedEl.querySelector("#diff-render-root")) {
      _reInitFilesTab();
    }
  });

  function _reInitFilesTab() {
    _ctx = window.__IW_FILES_CTX || {};
    if (!_ctx.projectId || !_ctx.itemId) return;
    _currentStep = _ctx.stepOptions ? "all" : "all";
    _populateStepSelect();
    var filterInput = document.getElementById("diff-filter-input");
    if (filterInput) {
      filterInput.removeEventListener("input", _onFilterInput);
      filterInput.addEventListener("input", _onFilterInput);
    }
    var untrackedDetails = document.getElementById("untracked-panel");
    if (untrackedDetails) {
      untrackedDetails.removeEventListener("toggle", _onUntrackedPanelToggle);
      untrackedDetails.addEventListener("toggle", _onUntrackedPanelToggle);
    }
    _renderDiff(_currentStep);
  }

  // ─── Step select ─────────────────────────────────────────────────────────

  function _populateStepSelect() {
    var select = document.getElementById("step-select");
    if (!select || !_ctx.stepOptions) return;

    var allOption = document.createElement("option");
    allOption.value = "all";
    allOption.textContent = "All steps (aggregate)";
    select.appendChild(allOption);

    (_ctx.stepOptions || []).forEach(function (opt) {
      var optEl = document.createElement("option");
      optEl.value = opt.step_id;
      optEl.textContent = opt.step_name;
      select.appendChild(optEl);
    });

    select.addEventListener("change", function () {
      var step = select.value;
      _currentStep = step;
      _renderDiff(step);
    });
  }

  // ─── Diff rendering ───────────────────────────────────────────────────────

  function _renderDiff(step) {
    step = step || "all";
    var root = document.getElementById("diff-render-root");
    if (!root) return;

    root.innerHTML = '<p class="text-muted-foreground text-sm animate-pulse">Loading diff\u2026</p>';

    var url =
      "/project/" +
      _ctx.projectId +
      "/item/" +
      _ctx.itemId +
      "/files/diff?step=" +
      encodeURIComponent(step);

    fetch(url)
      .then(function (r) {
        if (r.headers.get("X-Diff-Empty") === "1") {
          root.innerHTML =
            '<div class="bg-card border border-border rounded-lg p-8 text-center">' +
            '<p class="text-muted-foreground text-sm">No changes captured for this step.</p>' +
            "</div>";
          _diff2htmlUi = null;
          _allFilePaths = [];
          return null;
        }
        return r.text();
      })
      .then(function (diffText) {
        if (!diffText) return;
        return _drawDiff2Html(diffText, root);
      })
      .catch(function (err) {
        root.innerHTML =
          '<div class="bg-card border border-border rounded-lg p-4 text-destructive text-sm">' +
          "Failed to load diff: " +
          (err && err.message ? err.message : String(err)) +
          "</div>";
      });
  }

  function _drawDiff2Html(diffText, root) {
    // Destroy previous instance if any
    if (_diff2htmlUi) {
      _diff2htmlUi = null;
    }

    root.innerHTML = ""; // clear loading state

    try {
      // diff2html@3.4.x: only use options from defaultConfig
      _diff2htmlUi = new Diff2HtmlUI(root, diffText, {
        colorScheme: _isDarkMode() ? "dark" : "light",
        drawFileList: true,
        fileContentToggle: false,
        highlight: true,
        synchronisedScroll: true,
        fileListToggle: true,
        fileListStartVisible: true,
        stickyFileHeaders: false,
      });

      // draw() injects diffHtml into targetElement.innerHTML
      _diff2htmlUi.draw();

      // After draw, attach file-collapse handlers and build _allFilePaths
      _afterDiffDraw();

      // Apply current filter
      if (_filterText) {
        _applyFilter(_filterText);
      }
    } catch (e) {
      root.innerHTML =
        '<div class="bg-card border border-border rounded-lg p-4 text-destructive text-sm">' +
        "Diff render error: " +
        (e && e.message ? e.message : String(e)) +
        "</div>";
    }
  }

  function _afterDiffDraw() {
    // Build _allFilePaths from rendered diff2html file wrappers (the file
    // path lives as text inside `.d2h-file-name`; the wrappers carry no
    // data-file attribute in diff2html-ui-slim v3.x).
    var wrappers = document.querySelectorAll(
      "#diff-render-root .d2h-file-wrapper"
    );
    _allFilePaths = [];
    wrappers.forEach(function (w, i) {
      var nameEl = w.querySelector(".d2h-file-header .d2h-file-name");
      var path = nameEl ? nameEl.textContent.trim() : "";
      _allFilePaths.push(path);
      // Show only the first file by default. Clicking another file in the
      // top-list switches which one is visible (see below). This keeps the
      // page short instead of stacking 38 files of highlighted code.
      w.style.display = i === 0 ? "" : "none";
    });

    // Wire click handlers on the top file-list anchors so a click swaps
    // which file's diff is shown below — not jumps to its anchor inside
    // a giant scrollable wall of all files.
    _attachFileListSelection();

    // Attach collapse toggle to large diff cards
    _attachLargeFileToggles();

    // Make diff cards scroll-into-view when tree rows clicked (no-op for
    // diff2html-ui-slim, which doesn't render `.d2h-file-tree-list-item`).
    _attachTreeRowHandlers();
  }

  // ─── File list selection (one-file-at-a-time view) ──────────────────────

  function _attachFileListSelection() {
    var links = document.querySelectorAll(
      "#diff-render-root .d2h-file-list-line a.d2h-file-name"
    );
    links.forEach(function (a, idx) {
      a.addEventListener("click", function (e) {
        e.preventDefault();
        var href = a.getAttribute("href") || "";
        if (href.charAt(0) !== "#") return;
        _showOnlyFile(href.slice(1));
      });
    });
    // Mark the first file as active in the list.
    var firstLine = document.querySelector(
      "#diff-render-root .d2h-file-list-line"
    );
    if (firstLine) firstLine.classList.add("iw-file-active");
  }

  function _showOnlyFile(wrapperId) {
    var root = document.getElementById("diff-render-root");
    if (!root) return;
    var wrappers = root.querySelectorAll(".d2h-file-wrapper");
    var shown = null;
    wrappers.forEach(function (w) {
      if (w.id === wrapperId) {
        w.style.display = "";
        shown = w;
      } else {
        w.style.display = "none";
      }
    });
    // Highlight active row in the list at top.
    root.querySelectorAll(".d2h-file-list-line").forEach(function (li) {
      var a = li.querySelector("a.d2h-file-name");
      var matches = a && a.getAttribute("href") === "#" + wrapperId;
      li.classList.toggle("iw-file-active", !!matches);
    });
    // Reset scroll so the file list stays at the top and the newly-shown
    // file's diff appears right below it (instead of scrolling past the
    // list). All hidden wrappers take 0 height, so the visible one is
    // always positioned just below the file-list wrapper.
    var fileList = root.querySelector(".d2h-file-list-wrapper");
    if (fileList) {
      fileList.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  // ─── Large-file collapse toggle ─────────────────────────────────────────

  function _attachLargeFileToggles() {
    var cards = document.querySelectorAll(
      "#diff-render-root .d2h-file-wrapper"
    );
    cards.forEach(function (wrapper) {
      var header = wrapper.querySelector(".d2h-file-header");
      var fileName = header ? header.getAttribute("data-file") || "" : "";
      var numAdded = parseInt(wrapper.getAttribute("data-num-added") || "0", 10);
      var numRemoved = parseInt(wrapper.getAttribute("data-num-removed") || "0", 10);
      var totalLines = numAdded + numRemoved;

      // Collapse threshold: ≥500 lines
      if (totalLines < 500) return;

      // Find the stats bar or create one
      var statsEl = wrapper.querySelector(".d2h-file-stats");
      if (!statsEl) return;

      // Add "Show/Hide diff" toggle button
      var toggleBtn = document.createElement("button");
      toggleBtn.className = "iw-diff-toggle text-xs ml-2 px-1.5 py-0.5 border border-border rounded hover:bg-muted transition-colors";
      toggleBtn.textContent = "Hide diff";

      var isCollapsed = false;
      toggleBtn.addEventListener("click", function () {
        isCollapsed = !isCollapsed;
        toggleBtn.textContent = isCollapsed ? "Show diff" : "Hide diff";
        var codeEl = wrapper.querySelector(".d2h-code-linenums");
        if (codeEl) {
          codeEl.style.display = isCollapsed ? "none" : "";
        }
        var diffLinesEl = wrapper.querySelector(".d2h-diff-lines");
        if (diffLinesEl) {
          diffLinesEl.style.display = isCollapsed ? "none" : "";
        }
      });

      statsEl.appendChild(toggleBtn);
    });
  }

  // ─── Tree row click → scroll to diff card ────────────────────────────────

  function _attachTreeRowHandlers() {
    // diff2html renders file tree as .d2h-files-chart with .d2h-file-tree-list
    var treeRows = document.querySelectorAll(
      "#diff-render-root .d2h-file-tree-list-item"
    );
    treeRows.forEach(function (row) {
      var fileName = row.getAttribute("data-file-name") || "";
      // Make entire row clickable
      var link = row.querySelector(".d2h-file-name");
      if (!link) return;

      row.style.cursor = "pointer";
      row.addEventListener("click", function () {
        var target = document.querySelector(
          "#diff-render-root .d2h-file-wrapper[data-file='" + _cssEscape(fileName) + "']"
        );
        if (target) {
          target.scrollIntoView({ behavior: "smooth", block: "start" });
          // Expand if collapsed
          var codeEl = target.querySelector(".d2h-code-linenums");
          if (codeEl && codeEl.style.display === "none") {
            var toggleBtn = target.querySelector(".iw-diff-toggle");
            if (toggleBtn) toggleBtn.click();
          }
        }
      });
    });
  }

  // ─── Filter ───────────────────────────────────────────────────────────────

  function _onFilterInput(e) {
    var text = (e.target.value || "").trim();
    _filterText = text;
    _applyFilter(text);
  }

  function _applyFilter(text) {
    var root = document.getElementById("diff-render-root");
    if (!root) return;

    // Filter narrows the file list at the top only; the diff area below
    // shows whichever single file the user has selected. Wrapper visibility
    // is managed by _showOnlyFile, not by the filter.
    var listLines = root.querySelectorAll(".d2h-file-list-line");
    var totalCount = listLines.length;

    if (!text) {
      listLines.forEach(function (line) { line.style.display = ""; });
      _updateFilterCounts(null);
      return;
    }

    var lcText = text.toLowerCase();
    var visibleCount = 0;
    listLines.forEach(function (line) {
      var fn = (line.textContent || "").trim().toLowerCase();
      var matches = fn.indexOf(lcText) !== -1;
      line.style.display = matches ? "" : "none";
      if (matches) visibleCount++;
    });

    _updateFilterCounts({ visible: visibleCount, total: totalCount });
  }

  function _updateFilterCounts(obj) {
    var countEl = document.querySelector(
      "#diff-render-root .iw-filter-count"
    );
    if (!obj) {
      if (countEl) countEl.textContent = "";
      return;
    }
    if (!countEl) {
      countEl = document.createElement("span");
      countEl.className = "iw-filter-count text-xs text-muted-foreground ml-3";
      var toolbar = document.querySelector(
        "#diff-render-root .d2h-files"
      );
      if (toolbar) toolbar.parentNode.insertBefore(countEl, toolbar.nextSibling);
    }
    countEl.textContent =
      obj.visible + " of " + obj.total + " files shown";
  }

  function _updateAggregateFiltered(text) {
    // Recompute added/removed from visible diff cards only
    var root = document.getElementById("diff-render-root");
    if (!root) return;

    var visibleWrappers = root.querySelectorAll(
      ".d2h-file-wrapper[style=''], .d2h-file-wrapper:not([style])"
    );
    var totalAdded = 0;
    var totalRemoved = 0;
    visibleWrappers.forEach(function (w) {
      totalAdded += parseInt(w.getAttribute("data-num-added") || "0", 10);
      totalRemoved += parseInt(w.getAttribute("data-num-removed") || "0", 10);
    });

    // Update toolbar aggregate counts
    var countSpans = document
      .querySelector(".flex.flex-wrap.items-center.gap-3.mb-4")
      .querySelectorAll("span");
    // First green span, second red span
    if (countSpans[0])
      countSpans[0].textContent = "+" + totalAdded;
    if (countSpans[1])
      countSpans[1].textContent = "−" + totalRemoved;
  }

  // ─── Untracked panel ──────────────────────────────────────────────────────

  function _onUntrackedPanelToggle(e) {
    if (!e.target.closest("details")) return;
    var detailsEl = e.target.closest("details");
    if (!detailsEl.open) return;

    var content = document.getElementById("untracked-content");
    if (!content) return;

    // Already populated?
    if (content.querySelector(".bg-card")) return;

    var url =
      "/project/" +
      _ctx.projectId +
      "/item/" +
      _ctx.itemId +
      "/files/untracked";

    fetch(url)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var files = (data && data.files) || [];
        _renderUntrackedList(content, files);
        var countEl = document.getElementById("untracked-count");
        if (countEl) countEl.textContent = "(" + files.length + ")";
      })
      .catch(function () {
        content.innerHTML =
          '<p class="text-xs text-destructive">Failed to load untracked files.</p>';
      });
  }

  function _renderUntrackedList(container, files) {
    if (!files.length) {
      container.innerHTML =
        '<p class="text-xs text-muted-foreground">No other files in this worktree.</p>';
      return;
    }

    // Render the untracked files inline. A `/tab/untracked` fragment route
    // was referenced in an earlier draft but never implemented; the file
    // list endpoint at `/files/untracked` already returns everything we
    // need, so we render directly from `files` instead of refetching.
    var rows = files
      .map(function (f) {
        var icon = f.file_type === "image" ? "🖼" : "📄";
        var leaf = f.path.split("/").pop() || f.path;
        return (
          '<div class="untracked-file-row flex items-center gap-2 px-3 py-1.5 cursor-pointer hover:bg-muted/30 transition-colors rounded-sm mx-1 my-0.5"' +
          ' data-path="' + _escHtml(f.path) + '"' +
          ' data-file-type="' + _escHtml(f.file_type || "text") + '">' +
          '<span class="text-xs text-muted-foreground w-4 text-center">' + icon + '</span>' +
          '<span class="font-mono text-xs text-foreground flex-1 truncate" title="' + _escHtml(f.path) + '">' +
            _escHtml(leaf) +
          '</span>' +
          '</div>'
        );
      })
      .join("");

    container.innerHTML =
      '<div id="untracked-file-list" class="bg-card border border-border rounded-md py-1">' +
      rows +
      '</div>';

    // Wire click → preview via /artifact-raw (preserved endpoint).
    container.querySelectorAll(".untracked-file-row").forEach(function (row) {
      row.addEventListener("click", function () {
        var path = row.getAttribute("data-path");
        var fileType = row.getAttribute("data-file-type") || "text";
        if (typeof window.loadUntrackedFile === "function") {
          window.loadUntrackedFile(path, fileType);
        } else {
          // Minimal default: open the raw artifact in a new tab.
          var url =
            "/project/" + _ctx.projectId +
            "/item/" + _ctx.itemId +
            "/artifact-raw?path=" + encodeURIComponent(path);
          window.open(url, "_blank");
        }
      });
    });
  }

  // ─── Dark mode ────────────────────────────────────────────────────────────

  function _isDarkMode() {
    return document.documentElement.classList.contains("dark");
  }

  function _observeDarkMode() {
    // Use MutationObserver on documentElement to detect theme changes
    var observer = new MutationObserver(function (records) {
      records.forEach(function (rec) {
        if (rec.attributeName === "class") {
          _onDarkModeChange();
        }
      });
    });
    observer.observe(document.documentElement, { attributes: true });
  }

  function _onDarkModeChange() {
    // diff2html-ui-slim v3.4.x has no setColorScheme(); the colorScheme is
    // baked into the rendered HTML at construction time. Re-render the
    // current step's diff so the new theme takes effect.
    if (!_ctx || !_ctx.projectId || !_ctx.itemId) return;
    if (!document.getElementById("diff-render-root")) return;
    _renderDiff(_currentStep);
  }

  // ─── Keyboard shortcuts ────────────────────────────────────────────────────

  document.addEventListener("keydown", function (e) {
    // Ignore when typing in inputs
    var tag = e.target.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

    if (e.key === "t") {
      var fi = document.getElementById("diff-filter-input");
      if (fi) { fi.focus(); fi.select(); }
    } else if (e.key === "j" || e.key === "k") {
      // Navigate through visible (filter-respecting) file list and select.
      var root = document.getElementById("diff-render-root");
      if (!root) return;
      var visibleLines = Array.from(
        root.querySelectorAll(".d2h-file-list-line")
      ).filter(function (li) { return li.style.display !== "none"; });
      if (!visibleLines.length) return;
      var activeIdx = visibleLines.findIndex(function (li) {
        return li.classList.contains("iw-file-active");
      });
      if (activeIdx < 0) activeIdx = 0;
      var nextIdx = e.key === "j" ? activeIdx + 1 : activeIdx - 1;
      nextIdx = Math.max(0, Math.min(nextIdx, visibleLines.length - 1));
      var nextLink = visibleLines[nextIdx].querySelector("a.d2h-file-name");
      if (!nextLink) return;
      var href = nextLink.getAttribute("href") || "";
      if (href.charAt(0) === "#") _showOnlyFile(href.slice(1));
    } else if (e.key === "o" && e.target === document.body) {
      // Toggle large-file collapse on the currently shown file.
      var current = document.querySelector(
        "#diff-render-root .d2h-file-wrapper:not([style*='display: none'])"
      );
      if (current) {
        var toggle = current.querySelector(".iw-diff-toggle");
        if (toggle) toggle.click();
      }
    }
  });

  // ─── Utilities ─────────────────────────────────────────────────────────────

  function _cssEscape(s) {
    return s.replace(/['\"\\]/g, function (c) { return "\\" + c; });
  }

  function _escHtml(s) {
    if (!s) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function _escJs(s) {
    if (!s) return '""';
    return JSON.stringify(String(s));
  }

  // ─── Auto-init when loaded via htmx swap ──────────────────────────────────
  //
  // files.js is loaded inside the Files-tab fragment, so by the time the
  // browser parses this script the htmx swap event has already fired and
  // DOMContentLoaded fired during the original page load. Neither listener
  // registered above will run for THIS swap. Trigger the init explicitly
  // here whenever the surrounding fragment has populated __IW_FILES_CTX
  // and #diff-render-root — that's the contract of fragments/item_files.html.
  if (
    typeof window !== "undefined" &&
    window.__IW_FILES_CTX &&
    document.getElementById("diff-render-root")
  ) {
    if (!window.__IW_FILES_DARK_OBSERVED) {
      _observeDarkMode();
      window.__IW_FILES_DARK_OBSERVED = true;
    }
    _reInitFilesTab();
  }

})();
