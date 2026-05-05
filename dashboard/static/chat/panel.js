(function () {
  // ── localStorage helpers (iwChatState namespace) ──────────────────────────
  var TTL_MS = 4 * 60 * 60 * 1000; // 4 hours

  function chatStateKey(projectId, modulePath) {
    return 'iw_chat_conv_' + projectId + '_' + (modulePath || 'arch');
  }

  function getCachedConversation(projectId, modulePath) {
    try {
      var raw = localStorage.getItem(chatStateKey(projectId, modulePath));
      if (!raw) return null;
      var parsed = JSON.parse(raw);
      if (!parsed.conversation_id || !parsed.last_active_at) return null;
      if (Date.now() - parsed.last_active_at > TTL_MS) return null; // stale
      return parsed.conversation_id;
    } catch (e) {
      return null; // localStorage blocked / quota / corrupt
    }
  }

  function setCachedConversation(projectId, modulePath, conversationId) {
    try {
      localStorage.setItem(
        chatStateKey(projectId, modulePath),
        JSON.stringify({ conversation_id: conversationId, last_active_at: Date.now() })
      );
    } catch (e) { /* graceful no-op */ }
  }

  function clearCachedConversation(projectId, modulePath) {
    try { localStorage.removeItem(chatStateKey(projectId, modulePath)); } catch (e) {}
  }

  // Expose on window for use by composer.js
  window.iwChatState = {
    getCachedConversation: getCachedConversation,
    setCachedConversation: setCachedConversation,
    clearCachedConversation: clearCachedConversation,
  };

  // ── DOM references ──────────────────────────────────────────────────────
  var panel = document.getElementById('chat-panel');
  var panelSlot = document.getElementById('chat-panel-slot');
  var resizeHandle = document.getElementById('chat-resize-handle');
  var collapseBtn = document.getElementById('chat-collapse-btn');
  var expandRail = document.getElementById('chat-expand-rail');
  var closeBtn = document.getElementById('chat-close-btn');
  var drawerOpen = document.getElementById('chat-drawer-open');
  var drawerBackdrop = document.getElementById('chat-drawer-backdrop');

  var chatWidth = parseInt(localStorage.getItem('iw_chat_width') || '400', 10);
  chatWidth = Math.max(320, Math.min(480, chatWidth));
  document.documentElement.style.setProperty('--chat-width', chatWidth + 'px');

  function isDesktop() {
    return window.matchMedia('(min-width: 1024px)').matches;
  }

  function applyCollapsedState(collapsed) {
    if (!panel) return;
    panel.dataset.collapsed = collapsed;
    if (collapsed) {
      document.documentElement.style.setProperty('--chat-width', '48px');
      panel.style.width = '48px';
    } else {
      document.documentElement.style.setProperty('--chat-width', chatWidth + 'px');
      panel.style.width = '';
    }
  }

  function togglePanel() {
    var isCollapsed = panel && panel.dataset.collapsed === 'true';
    var next = !isCollapsed;
    applyCollapsedState(next);
    try {
      localStorage.setItem('iw_chat_collapsed', String(next));
    } catch (_) { /* localStorage unavailable, ignore */ }
  }

  function openDrawer() {
    if (!panel || !drawerBackdrop) return;
    panel.classList.remove('translate-x-full');
    drawerBackdrop.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
  }

  function closeDrawer() {
    if (!panel || !drawerBackdrop) return;
    panel.classList.add('translate-x-full');
    drawerBackdrop.classList.add('hidden');
    document.body.style.overflow = '';
  }

  function isDrawerOpen() {
    return panel && !panel.classList.contains('translate-x-full');
  }

  if (collapseBtn) collapseBtn.addEventListener('click', togglePanel);
  if (expandRail) expandRail.addEventListener('click', togglePanel);
  if (closeBtn) closeBtn.addEventListener('click', closeDrawer);
  if (drawerOpen) drawerOpen.addEventListener('click', openDrawer);
  if (drawerBackdrop) drawerBackdrop.addEventListener('click', closeDrawer);

  document.addEventListener('keydown', function (e) {
    if ((e.metaKey || e.ctrlKey) && e.key === '\\') {
      e.preventDefault();
      if (isDesktop()) togglePanel();
      return;
    }
    if (e.key === '/' && e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
      e.preventDefault();
      var input = document.getElementById('chat-input');
      if (input) input.focus();
      return;
    }
    if (e.key === 'Escape') {
      if (!isDesktop() && isDrawerOpen()) {
        closeDrawer();
        return;
      }
      if (typeof window.__iwChatCancel === 'function') {
        window.__iwChatCancel();
      }
    }
  });

  var isDragging = false;
  var startX = 0;
  var startWidth = 0;

  if (resizeHandle) {
    resizeHandle.addEventListener('mousedown', function (e) {
      isDragging = true;
      startX = e.clientX;
      startWidth = panel ? panel.offsetWidth : chatWidth;
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
      e.preventDefault();
    });
  }

  document.addEventListener('mousemove', function (e) {
    if (!isDragging) return;
    var delta = startX - e.clientX;
    var newWidth = Math.max(320, Math.min(480, startWidth + delta));
    document.documentElement.style.setProperty('--chat-width', newWidth + 'px');
    chatWidth = newWidth;
  });

  document.addEventListener('mouseup', function () {
    if (isDragging) {
      isDragging = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      localStorage.setItem('iw_chat_width', String(chatWidth));
    }
  });

  var storedCollapsed = localStorage.getItem('iw_chat_collapsed');
  var initialCollapsed = storedCollapsed === null ? true : storedCollapsed === 'true';
  applyCollapsedState(initialCollapsed);

  // ── Project / module context helpers ──────────────────────────────────
  function getProjectModuleContext() {
    var root = document.getElementById('code-content-root');
    if (!root) return { projectId: null, modulePath: null };
    return {
      projectId: root.dataset.projectId || null,
      modulePath: root.dataset.modulePath || null,
    };
  }

  // ── Empty state management ──────────────────────────────────────────────
  function showEmptyState() {
    var messages = document.getElementById('chat-messages');
    if (!messages) return;
    // Remove any pre-existing empty-state block so clicking "+ New"
    // multiple times never stacks duplicate greetings.
    var existingEmpty = document.getElementById('chat-empty-state');
    if (existingEmpty) existingEmpty.remove();
    // Remove all article bubbles but keep the scroll anchor
    var articles = messages.querySelectorAll('article');
    articles.forEach(function (a) { a.remove(); });
    var anchor = document.getElementById('chat-scroll-anchor');
    var empty = document.createElement('div');
    empty.id = 'chat-empty-state';
    empty.className = 'text-sm text-muted-foreground py-8 px-2 text-center space-y-2';
    empty.innerHTML = '<p class="font-medium text-foreground">Ask about this module</p>'
      + '<p>Try: <span class="font-mono">What does this component do?</span></p>'
      + '<p class="text-xs">Type <kbd class="px-1 py-0.5 rounded border border-border bg-muted">/</kbd> for commands</p>';
    messages.insertBefore(empty, anchor);
  }

  // ── "New chat" button handler ───────────────────────────────────────────
  var newChatBtn = document.getElementById('chat-new-btn');
  if (newChatBtn) {
    newChatBtn.addEventListener('click', function () {
      var ctx = getProjectModuleContext();
      if (window.iwChatState && window.iwChatState.clearCachedConversation) {
        window.iwChatState.clearCachedConversation(ctx.projectId, ctx.modulePath);
      }
      showEmptyState();
      // Announce to screen readers
      var messages = document.getElementById('chat-messages');
      if (messages) {
        messages.setAttribute('aria-live', 'polite');
      }
    });
  }

  // ── Replay conversation from localStorage cache ─────────────────────────
  function replayConversation(conversationId) {
    var ctx = getProjectModuleContext();
    if (!conversationId || !ctx.projectId) return;

    var messages = document.getElementById('chat-messages');
    if (!messages) return;

    // Defensive: skip replay if there's only one user message and no assistant
    // reply yet (first turn in progress — race with streaming)
    var existingUser = messages.querySelectorAll('article[data-role="user"]');
    var existingAssistant = messages.querySelectorAll('article[data-role="assistant"]');
    if (existingUser.length === 1 && existingAssistant.length === 0) return;

    var url = '/api/projects/' + ctx.projectId + '/conversations/' + conversationId + '/messages';
    fetch(url, { credentials: 'same-origin' })
      .then(function (response) {
        if (!response.ok) {
          if (response.status === 404) {
            // Conversation gone — clear localStorage and show empty state
            if (window.iwChatState && window.iwChatState.clearCachedConversation) {
              window.iwChatState.clearCachedConversation(ctx.projectId, ctx.modulePath);
            }
            showEmptyState();
          }
          return;
        }
        return response.json();
      })
      .then(function (payload) {
        if (!payload || !payload.messages) return;
        // Clear DOM except empty-state and anchor
        var articles = messages.querySelectorAll('article');
        articles.forEach(function (a) { a.remove(); });
        // Hide the empty state
        var emptyState = document.getElementById('chat-empty-state');
        if (emptyState) emptyState.remove();
        // Render each message
        payload.messages.forEach(function (msg) {
          if (msg.role === 'user') {
            appendUserBubbleStatic(msg.content);
          } else if (msg.role === 'assistant') {
            appendAssistantBubbleStatic(msg.content, msg.metadata && msg.metadata.render_id);
          }
        });
        scrollToBottom();
      })
      .catch(function () {
        // Network / parse error — degrade gracefully
      });
  }

  function appendUserBubbleStatic(text) {
    var messages = document.getElementById('chat-messages');
    if (!messages) return;
    var article = document.createElement('article');
    article.className = 'chat-message bg-muted rounded-lg px-3 py-2 text-sm ml-8';
    article.dataset.role = 'user';
    var label = document.createElement('header');
    label.className = 'font-medium text-xs text-muted-foreground block mb-1';
    label.textContent = 'You';
    var content = document.createElement('div');
    content.className = 'chat-message-body';
    content.textContent = text;
    article.appendChild(label);
    article.appendChild(content);
    messages.appendChild(article);
  }

  function appendAssistantBubbleStatic(text, renderId) {
    var messages = document.getElementById('chat-messages');
    if (!messages) return;
    var article = document.createElement('article');
    article.className = 'chat-message bg-background border border-border rounded-lg px-3 py-2 text-sm mr-8';
    article.dataset.role = 'assistant';
    var label = document.createElement('header');
    label.className = 'font-medium text-xs text-muted-foreground block mb-1';
    label.textContent = 'Assistant';
    var content = document.createElement('div');
    content.className = 'chat-message-body text-sm leading-relaxed';
    article.appendChild(label);
    article.appendChild(content);
    messages.appendChild(article);
    if (window.iwChat && window.iwChat.renderMarkdownStatic) {
      content.appendChild(window.iwChat.renderMarkdownStatic(text));
    } else {
      content.textContent = text;
    }
  }

  function scrollToBottom() {
    var messages = document.getElementById('chat-messages');
    if (messages) {
      messages.scrollTop = messages.scrollHeight;
    }
  }

  // ── Panel expand handler (replay on open) ─────────────────────────────
  var originalTogglePanel = togglePanel;
  function handlePanelExpand() {
    var ctx = getProjectModuleContext();
    var cachedConvId = null;
    if (window.iwChatState && window.iwChatState.getCachedConversation) {
      cachedConvId = window.iwChatState.getCachedConversation(ctx.projectId, ctx.modulePath);
    }
    if (cachedConvId) {
      replayConversation(cachedConvId);
    }
  }

  // Override toggle to fire replay when transitioning to expanded
  function togglePanelWithReplay() {
    var isCollapsed = panel && panel.dataset.collapsed === 'true';
    if (isCollapsed) {
      // Was collapsed, toggling to expanded — trigger replay
      togglePanel(); // apply state first
      handlePanelExpand();
    } else {
      togglePanel();
    }
  }

  if (collapseBtn) {
    collapseBtn.removeEventListener('click', togglePanel);
    collapseBtn.addEventListener('click', togglePanelWithReplay);
  }
  if (expandRail) {
    expandRail.removeEventListener('click', togglePanel);
    expandRail.addEventListener('click', togglePanelWithReplay);
  }

  // ── Page-load auto-expand: if panel was already expanded ───────────────
  if (!initialCollapsed) {
    handlePanelExpand();
  }

  function syncChatHeader() {
    var root = document.getElementById('code-content-root');
    var label = document.getElementById('chat-context-label');
    if (!root || !label) return;
    var path = (root.dataset.modulePath || '').trim();
    var name = (root.dataset.moduleName || '').trim();
    var text;
    if (path) {
      text = name ? 'Chat — ' + path + ' (' + name + ')' : 'Chat — ' + path;
    } else {
      text = 'Chat — Architecture';
    }
    label.textContent = text;
    label.setAttribute('title', text);
  }

  syncChatHeader();
  document.body.addEventListener('iw:code-context-changed', syncChatHeader);
  document.body.addEventListener('htmx:afterSwap', function (e) {
    if (e.detail && e.detail.target && e.detail.target.id === 'code-content-root') {
      syncChatHeader();
    }
  });
  document.body.addEventListener('htmx:afterSwap', function (e) {
    var target = e.detail && e.detail.target;
    if (!target) return;
    var isComponentsSwap = target.id === 'code-components-section';
    var isDetailPanelSwap = target.id === 'code-detail-panel';
    if (isComponentsSwap || (isDetailPanelSwap && !target.querySelector('#code-module-detail'))) {
      var root = document.getElementById('code-content-root');
      if (root) {
        root.dataset.modulePath = '';
        root.dataset.moduleName = '';
        root.dataset.contextLevel = 'architecture';
        root.dataset.contextDocId = root.dataset.archContextDocId || '';
        document.body.dispatchEvent(new CustomEvent('iw:code-context-changed', {
          detail: { source: 'architecture-reset' }
        }));
      }
    }
  });
})();
