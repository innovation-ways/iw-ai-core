(function () {
  var panel = document.getElementById('chat-panel');
  var resizeHandle = document.getElementById('chat-resize-handle');
  var collapseBtn = document.getElementById('chat-collapse-btn');
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
      if (collapseBtn) collapseBtn.setAttribute('aria-label', 'Expand chat panel (Cmd+\\)');
    } else {
      document.documentElement.style.setProperty('--chat-width', chatWidth + 'px');
      panel.style.width = '';
      if (collapseBtn) collapseBtn.setAttribute('aria-label', 'Collapse chat panel (Cmd+\\)');
    }
  }

  function togglePanel() {
    var isCollapsed = panel && panel.dataset.collapsed === 'true';
    applyCollapsedState(!isCollapsed);
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

  applyCollapsedState(false);

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
