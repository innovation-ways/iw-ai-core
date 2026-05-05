// dashboard/static/clipboard.js
// Shared clipboard helper — tries navigator.clipboard.writeText in secure contexts
// and falls back to a textarea + document.execCommand('copy') otherwise.
// Exposes window.iwClipboard.copy(text, button) which:
//   - Resolves on success, rejects on failure (never swallows errors)
//   - Sets button label to "Copied" / "Copy failed" for ~1.5s then restores original
(function () {
  function copyViaTextarea(text) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.left = '-9999px';
    ta.style.top = '0';
    document.body.appendChild(ta);
    ta.select();
    try {
      var ok = document.execCommand('copy');
      return ok;
    } finally {
      document.body.removeChild(ta);
    }
  }

  function applyButtonFeedback(button, label, durationMs) {
    if (!button || typeof button.textContent !== 'string') return;
    var original = button.dataset.iwClipboardOriginal;
    if (typeof original !== 'string') {
      original = button.textContent;
      button.dataset.iwClipboardOriginal = original;
    }
    button.textContent = label;
    setTimeout(function () {
      // Only restore if no other call has changed the label since
      if (button.textContent === label) {
        button.textContent = original;
      }
    }, durationMs || 1500);
  }

  function copy(text, button) {
    var hasModern =
      typeof navigator !== 'undefined' &&
      !!navigator.clipboard &&
      typeof navigator.clipboard.writeText === 'function' &&
      typeof window !== 'undefined' &&
      window.isSecureContext === true;
    var p;
    if (hasModern) {
      p = navigator.clipboard.writeText(text);
    } else {
      p = new Promise(function (resolve, reject) {
        try {
          var ok = copyViaTextarea(text);
          if (ok) resolve();
          else reject(new Error('execCommand("copy") returned false'));
        } catch (err) {
          reject(err);
        }
      });
    }
    return p.then(
      function () {
        applyButtonFeedback(button, 'Copied');
      },
      function (err) {
        applyButtonFeedback(button, 'Copy failed');
        throw err;
      }
    );
  }

  window.iwClipboard = { copy: copy };
})();