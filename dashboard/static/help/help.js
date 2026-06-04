// dashboard/static/help/help.js
// Popover + Driver.js tour glue code.
// Plain ES module-free script — no bundler, no imports.
//
// Global API surface:
//   window.IW_TOURS  — tour step definitions (loaded from tours.js)
//
// Driver.js is lazy-loaded on first tour start; the IIFE exposes its API as
//   window.driver.js  (the driver factory function).
// Calling the factory gives a driver instance with .drive() / .setSteps() etc.

(function () {
  "use strict";

  // ── helpers ─────────────────────────────────────────────────────────────────

  function qs(sel, ctx) {
    return (ctx || document).querySelector(sel);
  }

  function qsa(sel, ctx) {
    return Array.from((ctx || document).querySelectorAll(sel));
  }

  function storageGet(key) {
    try {
      return localStorage.getItem(key);
    } catch (_) {
      return null;
    }
  }

  function storageSet(key, val) {
    try {
      localStorage.setItem(key, val);
    } catch (_) {
      // private mode / quota exceeded — silently ignore
    }
  }

  // ── driver.js lazy-load (once) ───────────────────────────────────────────────

  var _driverCSSLoaded = false;
  var _driverScriptLoaded = false;
  var _driverScriptPromise = null;

  function loadDriverCSS() {
    if (_driverCSSLoaded) return;
    _driverCSSLoaded = true;
    var link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "/static/vendor/driver/driver.css";
    document.head.appendChild(link);
  }

  function loadDriverScript() {
    if (_driverScriptPromise) return _driverScriptPromise;
    _driverScriptPromise = new Promise(function (resolve, reject) {
      var s = document.createElement("script");
      s.src = "/static/vendor/driver/driver.js.iife.js";
      s.onload = function () {
        _driverScriptLoaded = true;
        resolve();
      };
      s.onerror = function () {
        reject(new Error("failed to load driver.js"));
      };
      document.head.appendChild(s);
    });
    return _driverScriptPromise;
  }

  // ── open / close helpers ─────────────────────────────────────────────────────

  var _openSlug = null; // slug of currently-open popover
  var _originButton = null; // the '?' button that opened the current popover

  function closeOpenPopover() {
    if (!_openSlug) return;
    var btn = qs('[data-help-slug="' + _openSlug + '"]');
    var popover = btn ? qs("[data-help-popover]", btn.parentElement) : null;
    if (popover) {
      popover.hidden = true;
      popover.innerHTML = "";
    }
    if (btn) {
      btn.setAttribute("aria-expanded", "false");
    }
    _openSlug = null;
    _originButton = null;
  }

  function openPopover(slug, button) {
    // Close any previously-open popover first
    closeOpenPopover();

    var popover = qs("[data-help-popover]", button.parentElement);
    if (!popover) return;

    _openSlug = slug;
    _originButton = button;

    // Fetch fragment HTML and mount it
    fetch("/_help/" + slug)
      .then(function (r) {
        if (!r.ok) throw new Error(r.status);
        return r.text();
      })
      .then(function (html) {
        popover.innerHTML = html;
        popover.hidden = false;
        button.setAttribute("aria-expanded", "true");

        // Move focus to close button inside the loaded fragment
        var closeBtn = qs("[data-help-close]", popover);
        if (closeBtn) closeBtn.focus();
      })
      .catch(function (err) {
        popover.innerHTML =
          '<p class="help-popover__error">Help content unavailable.</p>';
        popover.hidden = false;
      });
  }

  // ── tourseen marker (called on DOMContentLoaded and after tour destroy) ───────

  function markTourSeen(slug) {
    storageSet("iw.tour." + slug + ".completedAt", new Date().toISOString());
    var btn = qs('[data-help-slug="' + slug + '"]');
    if (btn) btn.setAttribute("data-tour-seen", "true");
  }

  function restoreTourSeenMarkers() {
    qsa("[data-help-slug]").forEach(function (btn) {
      var slug = btn.getAttribute("data-help-slug");
      if (!slug) return;
      var completed = storageGet("iw.tour." + slug + ".completedAt");
      if (completed) btn.setAttribute("data-tour-seen", "true");
    });
  }

  // ── ESCAPE closes popover ───────────────────────────────────────────────────────

  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape" && e.key !== "Esc") return;
    if (_openSlug) {
      e.preventDefault();
      if (_originButton) _originButton.focus();
      closeOpenPopover();
    }
  });

  // ── background click closes popover ──────────────────────────────────────────

  document.addEventListener("mousedown", function (e) {
    if (!_openSlug) return;
    var popover = qs("[data-help-popover]");
    if (!popover || popover.hidden) return;
    // Click was on the popover itself or inside it → let it propagate
    if (popover.contains(e.target)) return;
    // Click was outside → close
    if (_originButton) _originButton.focus();
    closeOpenPopover();
  });

  // ── event delegation: [data-help-slug] buttons ───────────────────────────────

  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-help-slug]");
    if (!btn) return;
    e.preventDefault();
    var slug = btn.getAttribute("data-help-slug");
    if (_openSlug === slug) {
      // Toggle: close if already open
      if (_originButton) _originButton.focus();
      closeOpenPopover();
    } else {
      openPopover(slug, btn);
    }
  });

  // ── event delegation: [data-help-close] inside popover ─────────────────────

  document.addEventListener("click", function (e) {
    var closeBtn = e.target.closest("[data-help-close]");
    if (!closeBtn) return;
    if (_originButton) _originButton.focus();
    closeOpenPopover();
  });

  // ── event delegation: [data-tour-start] inside popover ─────────────────────

  document.addEventListener("click", function (e) {
    var tourBtn = e.target.closest("[data-tour-start]");
    if (!tourBtn) return;
    e.preventDefault();

    var popover = tourBtn.closest("[data-help-popover]");
    var slug = popover
      ? popover.previousElementSibling.getAttribute("data-help-slug")
      : null;
    if (!slug) return;

    var steps = window.IW_TOURS && window.IW_TOURS[slug];
    if (!steps || steps.length === 0) {
      tourBtn.hidden = true;
      return;
    }

    // Close the help popover BEFORE mounting Driver.js. If we leave it open,
    // _openSlug stays set and our global Escape handler intercepts the Escape
    // key with preventDefault, stopping Driver.js's own Escape-to-dismiss
    // path — which is also where onDestroyStarted/onDestroyed fire and where
    // markTourSeen() runs. (F-00080 V5.)
    closeOpenPopover();

    // Load driver.js + driver.css, then drive
    tourBtn.setAttribute("aria-disabled", "true");
    tourBtn.disabled = true;
    tourBtn.textContent = "Loading tour…";

    loadDriverCSS();

    loadDriverScript()
      .then(function () {
        // The IIFE structure: this.driver.js = function(F){...}({});
        // F.driver = the factory Ae; window.driver.js === F === {}
        // The actual driver constructor lives at window.driver.js.driver
        var driver;
        try {
          driver = new window.driver.js.driver();
        } catch (_) {
          driver = window.driver.js.driver();
        }

        driver.setConfig({
          allowKeyboardControl: true,
          showProgress: true,
          showButtons: ["next", "previous", "close"],
          onDestroyStarted: function () {
            // Mark seen when tour is ending (before final cleanup)
            markTourSeen(slug);
          },
          onDestroyed: function () {
            markTourSeen(slug);
          },
        });

        driver.setSteps(steps);
        driver.drive(0);
      })
      .catch(function (err) {
        tourBtn.setAttribute("aria-disabled", "true");
        tourBtn.disabled = true;
        tourBtn.title = "Tour unavailable";
        tourBtn.textContent = "Tour unavailable";
      });
  });

  // ── restore tour-seen markers on every page load ───────────────────────────────

  document.addEventListener("DOMContentLoaded", restoreTourSeenMarkers);

  // ── expose restore helper so base.html can call it on ajaxy pages ─────────────
  window.iwHelpRestoreSeen = restoreTourSeenMarkers;
})();
