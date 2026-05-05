(function () {
  'use strict';

  function getMessageSource(msgEl) {
    var bodyEl = msgEl.querySelector('.chat-message-body');
    if (!bodyEl) return '';
    var clone = bodyEl.cloneNode(true);
    var chips = clone.querySelectorAll('.citation-chip, [data-cite]');
    chips.forEach(function (c) { c.remove(); });
    return clone.textContent || '';
  }

  function stashFeedback(msgId, rating, categories, reason) {
    var key = 'iw_chat_feedback.' + msgId;
    var payload = {
      rating: rating,
      ts: Date.now(),
      reason: reason || null,
      categories: categories || [],
    };
    try {
      localStorage.setItem(key, JSON.stringify(payload));
    } catch (e) {}
    return payload;
  }

  function attachActions(messageEl) {
    var actionsEl = messageEl.querySelector('.chat-message-actions');
    if (!actionsEl) return;
    var msgId = messageEl.getAttribute('data-msg-id') || '';

    actionsEl.querySelectorAll('button[data-action]').forEach(function (btn) {
      if (btn._iwBound) return;
      btn._iwBound = true;
      var action = btn.getAttribute('data-action');

      if (action === 'copy') {
        btn.addEventListener('click', function () {
          var source = getMessageSource(messageEl);
          window.iwClipboard.copy(source, null).then(function () {
            var span = btn.querySelector('span');
            var orig = span ? span.textContent : btn.textContent.trim();
            if (span) span.textContent = 'Copied!';
            else btn.textContent = 'Copied!';
            setTimeout(function () {
              if (span) span.textContent = orig;
              else btn.textContent = orig;
            }, 2000);
          }).catch(function () {});
        });
      }

      if (action === 'thumbs-up') {
        btn.addEventListener('click', function () {
          stashFeedback(msgId, 'up', [], null);
          btn.setAttribute('aria-pressed', 'true');
          btn.classList.add('opacity-60');
          var downBtn = actionsEl.querySelector('[data-action="thumbs-down"]');
          if (downBtn) {
            downBtn.removeAttribute('aria-pressed');
            downBtn.classList.remove('opacity-60');
          }
        });
      }

      if (action === 'thumbs-down') {
        btn.addEventListener('click', function () {
          var form = actionsEl.querySelector('.thumbs-down-form');
          if (!form) return;
          var isHidden = form.classList.contains('hidden');
          if (isHidden) {
            form.classList.remove('hidden');
            var firstCb = form.querySelector('input[type="checkbox"]');
            if (firstCb) firstCb.focus();
          } else {
            form.classList.add('hidden');
          }
        });
      }

      if (action === 'feedback-submit') {
        btn.addEventListener('click', function () {
          var form = actionsEl.querySelector('.thumbs-down-form');
          if (!form) return;
          var categories = [];
          form.querySelectorAll('input[type="checkbox"]:checked').forEach(function (cb) {
            categories.push(cb.name);
          });
          var reason = form.querySelector('textarea')?.value || '';
          stashFeedback(msgId, 'down', categories, reason);
          form.classList.add('hidden');
          actionsEl.querySelector('[data-action="thumbs-down"]').setAttribute('aria-pressed', 'true');
          actionsEl.querySelector('[data-action="thumbs-down"]').classList.add('opacity-60');
          var upBtn = actionsEl.querySelector('[data-action="thumbs-up"]');
          if (upBtn) {
            upBtn.removeAttribute('aria-pressed');
            upBtn.classList.remove('opacity-60');
          }
        });
      }

      if (action === 'feedback-cancel') {
        btn.addEventListener('click', function () {
          var form = actionsEl.querySelector('.thumbs-down-form');
          if (form) form.classList.add('hidden');
        });
      }

      if (action === 'regenerate') {
        btn.addEventListener('click', function () {
          var panel = messageEl.closest('#chat-panel');
          if (!panel) return;
          var composer = panel.querySelector('#chat-composer');
          if (!composer) return;
          var lastUserMsg = panel.querySelector('[data-role="user"]:last-child');
          if (!lastUserMsg) return;
          var lastAssistant = panel.querySelector('[data-role="assistant"]:last-child');
          if (lastAssistant !== messageEl) return;
          btn.disabled = true;
          btn.classList.add('opacity-50', 'cursor-not-allowed');
          if (composer._iwRegenerate) {
            composer._iwRegenerate();
          }
        });
      }
    });
  }

  function makeActionsGlobal() {
    document.addEventListener('click', function (e) {
      var msgEl = e.target.closest('[data-msg-id]');
      if (!msgEl) return;
      var actionsEl = msgEl.querySelector('.chat-message-actions');
      if (!actionsEl) return;
      if (e.target.closest('.action-btn, .thumbs-down-form')) {
        attachActions(msgEl);
      }
    });
    document.querySelectorAll('[data-role="assistant"]').forEach(function (msgEl) {
      attachActions(msgEl);
    });
  }

  window.iwChat = window.iwChat || {};
  window.iwChat.attachActions = attachActions;
  window.iwChat.getMessageSource = getMessageSource;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', makeActionsGlobal);
  } else {
    makeActionsGlobal();
  }
})();
