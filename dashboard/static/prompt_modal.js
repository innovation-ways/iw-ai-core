// dashboard/static/prompt_modal.js
// CR-00056: Prompt modal init — focus trap, Escape, backdrop dismiss, copy-to-clipboard.
// Shares the .activity-modal* CSS classes (already styled in styles.css).
// Called via the inline <script> block in prompt_text_modal.html after each htmx swap.
(function () {
  var currentTrigger = null;

  function getFocusable(root) {
    return Array.prototype.slice.call(root.querySelectorAll(
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    ));
  }

  function trapFocus(root) {
    var focusable = getFocusable(root);
    if (!focusable.length) return;
    var first = focusable[0];
    var last = focusable[focusable.length - 1];

    // Move focus to first element immediately
    first.focus();

    function handleKeydown(e) {
      if (e.key === 'Tab' || e.key === 'Shift+Tab') {
        // Shift+Tab on first → wrap to last
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        }
        // Tab on last → wrap to first
        else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    }
    root.addEventListener('keydown', handleKeydown);
    return function () { root.removeEventListener('keydown', handleKeydown); };
  }

  function closeModal() {
    var overlay = document.getElementById('prompt-modal-overlay');
    var modal = document.getElementById('prompt-modal');
    var mount = document.getElementById('prompt-modal-mount');
    if (!modal) return;

    // Release focus trap
    if (modal._releaseTrap) { modal._releaseTrap(); modal._releaseTrap = null; }

    // Restore body scroll
    document.body.style.overflow = '';

    // Clear mount
    if (mount) { mount.innerHTML = ''; }

    // Restore focus to the trigger button that opened the modal
    if (currentTrigger) {
      currentTrigger.focus();
      currentTrigger = null;
    }
  }

  function handleCopyClick(button) {
    var sectionIndex = button.getAttribute('data-prompt-copy-section');
    if (sectionIndex === null) return;
    var pre = document.querySelector('[data-prompt-section-body="' + sectionIndex + '"]');
    if (!pre) return;
    var text = pre.textContent || '';
    window.iwClipboard.copy(text, button);
  }

  function initPromptModal() {
    var overlay = document.getElementById('prompt-modal-overlay');
    var modal = document.getElementById('prompt-modal');
    var mount = document.getElementById('prompt-modal-mount');
    if (!overlay || !modal || !mount) return;

    // Only proceed if the modal has been swapped in (not already set up)
    if (modal._promptModalBound) return;
    modal._promptModalBound = true;

    // Save the currently focused element as the trigger (the View button)
    currentTrigger = document.activeElement;

    // Apply focus trap
    var releaseTrap = trapFocus(modal);
    modal._releaseTrap = releaseTrap;

    // Disable body scroll
    document.body.style.overflow = 'hidden';

    // Close button
    var closeBtn = modal.querySelector('.modal-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        closeModal();
      });
    }

    // Backdrop click
    overlay.addEventListener('click', function () {
      closeModal();
    });

    // Modal outer click (not inner content)
    modal.addEventListener('click', function (e) {
      if (e.target === modal) {
        closeModal();
      }
    });

    // Escape key
    document.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape' && modal.getAttribute('aria-hidden') !== 'true') {
        closeModal();
      }
    });

    // Copy buttons
    modal.querySelectorAll('.prompt-modal-copy').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        handleCopyClick(btn);
      });
    });
  }

  // Expose singleton init — safe to call multiple times (guards via _promptModalBound)
  window.__promptModalInit = initPromptModal;

  // Also support htmx afterSwap event on the mount point
  // (the inline <script> in the fragment also calls this directly, but this is a fallback)
  document.addEventListener('htmx:afterSwap', function (evt) {
    if (evt.target && evt.target.id === 'prompt-modal-mount') {
      initPromptModal();
    }
  });
})();
