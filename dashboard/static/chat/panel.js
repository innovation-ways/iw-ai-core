(function () {
  var panel = document.getElementById('chat-panel');
  var resizeHandle = document.getElementById('chat-resize-handle');
  var collapseBtn = document.getElementById('chat-collapse-btn');
  var drawerOpen = document.getElementById('chat-drawer-open');
  var drawer = document.getElementById('chat-drawer');
  var drawerClose = document.getElementById('chat-drawer-close');
  var drawerBackdrop = document.getElementById('chat-drawer-backdrop');
  var drawerMessages = document.getElementById('chat-drawer-messages');

  var chatWidth = parseInt(localStorage.getItem('iw_chat_width') || '400', 10);
  chatWidth = Math.max(320, Math.min(480, chatWidth));
  document.documentElement.style.setProperty('--chat-width', chatWidth + 'px');

  function applyCollapsedState(collapsed) {
    if (!panel) return;
    panel.dataset.collapsed = collapsed;
    if (collapsed) {
      panel.style.width = '48px';
      if (collapseBtn) collapseBtn.setAttribute('aria-label', 'Expand chat panel (Cmd+\)');
    } else {
      panel.style.width = '';
      if (collapseBtn) collapseBtn.setAttribute('aria-label', 'Collapse chat panel (Cmd+\)');
    }
  }

  function togglePanel() {
    var isCollapsed = panel && panel.dataset.collapsed === 'true';
    applyCollapsedState(!isCollapsed);
  }

  if (collapseBtn) {
    collapseBtn.addEventListener('click', togglePanel);
  }

  document.addEventListener('keydown', function (e) {
    if ((e.metaKey || e.ctrlKey) && e.key === '\\') {
      e.preventDefault();
      togglePanel();
    }
    if (e.key === '/' && e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
      e.preventDefault();
      var input = document.getElementById('chat-input');
      if (input) input.focus();
    }
    if (e.key === 'Escape') {
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
    var delta = e.clientX - startX;
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

  function openDrawer() {
    if (!drawer || !drawerBackdrop) return;
    drawer.classList.remove('translate-x-full');
    drawerBackdrop.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
  }

  function closeDrawer() {
    if (!drawer || !drawerBackdrop) return;
    drawer.classList.add('translate-x-full');
    drawerBackdrop.classList.add('hidden');
    document.body.style.overflow = '';
  }

  if (drawerOpen) drawerOpen.addEventListener('click', openDrawer);
  if (drawerClose) drawerClose.addEventListener('click', closeDrawer);
  if (drawerBackdrop) drawerBackdrop.addEventListener('click', closeDrawer);

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && !drawer.classList.contains('translate-x-full')) {
      closeDrawer();
    }
  });

  applyCollapsedState(false);
})();
