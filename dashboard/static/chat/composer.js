(function () {
  var VALID_MIME = ['image/png', 'image/jpeg', 'image/gif', 'image/webp'];
  var MAX_SIZE = 10 * 1024 * 1024;

  function showToast(opts) {
    if (typeof showToast === 'function') {
      showToast(opts);
    } else {
      alert(opts.message);
    }
  }

  function validateImage(file) {
    if (!VALID_MIME.includes(file.type)) {
      showToast({ type: 'error', message: 'Only PNG, JPEG, GIF, and WEBP images are supported.' });
      return false;
    }
    if (file.size > MAX_SIZE) {
      showToast({ type: 'error', message: 'Image too large (max 10MB).' });
      return false;
    }
    return true;
  }

  function createImageChip(file, container) {
    var chip = document.createElement('div');
    chip.className = 'relative inline-flex items-center gap-1 bg-muted rounded px-2 py-1 text-xs';
    var img = document.createElement('img');
    img.src = URL.createObjectURL(file);
    img.className = 'w-8 h-8 object-cover rounded';
    img.alt = 'Attached image';
    var removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.className = 'absolute -top-1 -right-1 bg-destructive text-destructive-foreground rounded-full w-4 h-4 text-xs';
    removeBtn.textContent = '×';
    removeBtn.setAttribute('aria-label', 'Remove image');
    removeBtn.addEventListener('click', function () {
      URL.revokeObjectURL(img.src);
      chip.remove();
    });
    chip.appendChild(img);
    chip.appendChild(removeBtn);
    container.appendChild(chip);
    return chip;
  }

  function handleImages(files, container) {
    Array.from(files).forEach(function (file) {
      if (validateImage(file)) {
        createImageChip(file, container);
      }
    });
  }

  function getImageFiles(dataTransfer) {
    var items = dataTransfer ? dataTransfer.items : [];
    var files = [];
    Array.from(items).forEach(function (item) {
      if (item.kind === 'file' && VALID_MIME.includes(item.type)) {
        files.push(item.getAsFile());
      }
    });
    return files;
  }

  function initComposer() {
    var composer = document.getElementById('chat-composer');
    var input = document.getElementById('chat-input');
    var slashMenu = document.getElementById('chat-slash-menu');
    var imageChips = document.getElementById('chat-image-chips');
    var imagePicker = document.getElementById('chat-image-picker');
    var sendBtn = document.getElementById('chat-send');
    var contextChips = document.getElementById('chat-context-chips');

    if (!composer || !input) return;

    var slashCommands = [
      { label: '/explain', name: 'explain', description: 'Explain this module' },
      { label: '/findusages', name: 'findusages', description: 'Find usages of a symbol' },
      { label: '/diagram', name: 'diagram', description: 'Generate a diagram' },
      { label: '/why', name: 'why', description: 'Explain with work item context' },
      { label: '/history', name: 'history', description: 'Explain with history context' },
    ];
    var selectedSlashIndex = -1;
    var slashMenuOpen = false;
    var currentFiltered = [];

    function syncContextChip() {
      var root = document.getElementById('code-content-root');
      if (!root || !contextChips) return;
      var modulePath = root.dataset.modulePath || '';
      var existing = contextChips.querySelector('[data-chip-type="module"]');
      if (modulePath && !existing) {
        var chip = document.createElement('span');
        chip.className = 'inline-flex items-center gap-1 bg-secondary text-secondary-foreground rounded px-2 py-0.5 text-xs';
        chip.dataset.chipType = 'module';
        chip.dataset.chipValue = modulePath;
        chip.textContent = 'module:' + modulePath;
        var removeBtn = document.createElement('button');
        removeBtn.type = 'button';
        removeBtn.className = 'hover:text-destructive';
        removeBtn.setAttribute('aria-label', 'Remove module context');
        removeBtn.textContent = '×';
        removeBtn.addEventListener('click', function () { chip.remove(); });
        chip.appendChild(removeBtn);
        contextChips.appendChild(chip);
      }
    }

    syncContextChip();
    document.body.addEventListener('htmx:afterSwap', function (e) {
      if (e.detail.target && e.detail.target.id === 'code-content-root') {
        syncContextChip();
      }
    });
    document.body.addEventListener('iw:code-context-changed', syncContextChip);

    if (imagePicker) {
      imagePicker.addEventListener('change', function () {
        if (imagePicker.files) {
          handleImages(imagePicker.files, imageChips);
          imagePicker.value = '';
        }
      });
    }

    var panel = document.getElementById('chat-panel');
    if (panel) {
      panel.addEventListener('dragover', function (e) {
        e.preventDefault();
        e.stopPropagation();
      });
      panel.addEventListener('drop', function (e) {
        e.preventDefault();
        e.stopPropagation();
        var files = getImageFiles(e.dataTransfer);
        if (files.length > 0) {
          handleImages({ length: files.length, forEach: function (fn) { files.forEach(fn); } }, imageChips);
        }
      });
    }

    if (input) {
      input.addEventListener('paste', function (e) {
        var clipboardData = e.clipboardData || window.clipboardData;
        var files = getImageFiles(clipboardData);
        if (files.length > 0) {
          e.preventDefault();
          handleImages({ length: files.length, forEach: function (fn) { files.forEach(fn); } }, imageChips);
        }
      });

      input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey && !e.isComposing && !slashMenuOpen) {
          e.preventDefault();
          sendBtn && sendBtn.click();
          return;
        }
        if (slashMenuOpen && e.key === 'ArrowDown') {
          e.preventDefault();
          selectedSlashIndex = Math.min(selectedSlashIndex + 1, currentFiltered.length - 1);
          updateSlashMenuSelection();
          return;
        }
        if (slashMenuOpen && e.key === 'ArrowUp') {
          e.preventDefault();
          selectedSlashIndex = Math.max(selectedSlashIndex - 1, 0);
          updateSlashMenuSelection();
          return;
        }
        if (slashMenuOpen && e.key === 'Enter' && selectedSlashIndex >= 0) {
          e.preventDefault();
          acceptSlashCommand(selectedSlashIndex);
          return;
        }
        if (slashMenuOpen && e.key === 'Escape') {
          e.preventDefault();
          closeSlashMenu();
          return;
        }
      });

      input.addEventListener('input', function () {
        var value = input.value;
        var lastWord = value.split(/\s/).pop();
        if (lastWord.startsWith('/')) {
          openSlashMenu(lastWord.slice(1));
        } else {
          closeSlashMenu();
        }
      });
    }

    function openSlashMenu(prefix) {
      currentFiltered = slashCommands.filter(function (cmd) {
        return cmd.label.toLowerCase().startsWith('/' + prefix.toLowerCase());
      });
      if (currentFiltered.length === 0) {
        closeSlashMenu();
        return;
      }
      slashMenu.innerHTML = '';
      currentFiltered.forEach(function (cmd, i) {
        var item = document.createElement('div');
        item.className = 'px-3 py-1.5 text-sm cursor-pointer';
        item.dataset.index = i;
        item.textContent = cmd.label + ' — ' + cmd.description;
        item.addEventListener('click', function () { acceptSlashCommand(i); });
        slashMenu.appendChild(item);
      });
      slashMenu.classList.remove('hidden');
      slashMenuOpen = true;
      selectedSlashIndex = 0;
      updateSlashMenuSelection();
    }

    function closeSlashMenu() {
      slashMenu.classList.add('hidden');
      slashMenuOpen = false;
      selectedSlashIndex = -1;
      currentFiltered = [];
    }

    function updateSlashMenuSelection() {
      var items = slashMenu.querySelectorAll('[data-index]');
      items.forEach(function (item) {
        var idx = parseInt(item.dataset.index, 10);
        if (idx === selectedSlashIndex) {
          item.classList.add('bg-primary', 'text-primary-foreground');
        } else {
          item.classList.remove('bg-primary', 'text-primary-foreground');
        }
      });
    }

    function acceptSlashCommand(index) {
      var cmd = currentFiltered[index];
      if (!cmd) return;
      var value = input.value;
      var lastWordStart = value.lastIndexOf('/');
      if (lastWordStart >= 0) {
        input.value = value.substring(0, lastWordStart);
      }
      var chip = document.createElement('span');
      chip.className = 'inline-flex items-center gap-1 bg-secondary text-secondary-foreground rounded px-2 py-0.5 text-xs';
      chip.dataset.chipType = 'cmd';
      chip.dataset.chipValue = cmd.name;
      chip.textContent = 'cmd:' + cmd.name;
      var removeBtn = document.createElement('button');
      removeBtn.type = 'button';
      removeBtn.className = 'hover:text-destructive';
      removeBtn.setAttribute('aria-label', 'Remove command');
      removeBtn.textContent = '×';
      removeBtn.addEventListener('click', function () { chip.remove(); });
      chip.appendChild(removeBtn);
      contextChips.appendChild(chip);
      closeSlashMenu();
    }

    if (sendBtn) {
      sendBtn.addEventListener('click', function () {
        var question = input.value.trim();
        if (!question) return;

        var root = document.getElementById('code-content-root');
        var contextLevel = (root && root.dataset.contextLevel) || 'architecture';
        var contextDocId = (root && root.dataset.contextDocId) || null;
        var modulePath = (root && root.dataset.modulePath) || null;
        var moduleName = (root && root.dataset.moduleName) || null;
        var projectId = root && root.dataset.projectId;

        var images = Array.from((imageChips && imageChips.querySelectorAll('img')) || [])
          .map(function (img) { return img.src; })
          .filter(Boolean);

        if (images.length > 0) {
          showToast({ type: 'info', message: 'Image attachments coming soon' });
          return;
        }

        var conversationHistory = [];

        appendUserBubble(question);
        input.value = '';
        closeSlashMenu();

        var assistantBubble = appendAssistantBubble();

        var contextChips_data = Array.from((contextChips && contextChips.querySelectorAll('[data-chip-value]')) || [])
          .map(function (chip) { return chip.dataset.chipValue; })
          .filter(Boolean);

        var body = {
          question: question,
          context_level: contextLevel,
          context_doc_id: contextDocId,
          module_path: modulePath,
          module_name: moduleName,
          conversation_history: conversationHistory,
          context_chips: contextChips_data,
        };

        if (window.iwChat && window.iwChat.streamAnswer) {
          var renderer = null;
          if (window.iwChat.createAssistantRenderer) {
            var assistantArticle = assistantBubble.parentElement;
            renderer = window.iwChat.createAssistantRenderer(assistantArticle);
          }
          var renderId = null;
          var lastPhaseName = null;
          window.iwChat.streamAnswer({
            projectId: projectId || (window.location.pathname.split('/')[2]),
            body: body,
            onToken: renderer ? renderer.onToken : function (text) {
              assistantBubble.textContent += text;
            },
            onCitation: renderer ? renderer.onCitation : function () {},
            onWorkItemCitation: renderer ? renderer.onWorkItemCitation : function () {},
            onPhase: function (data) {
              lastPhaseName = data.name;
              if (data.name === 'composing' && data.detail && data.detail.render_id) {
                renderId = data.detail.render_id;
              }
              if (renderer && renderer.onPhase) {
                renderer.onPhase(data);
              }
            },
            onDone: function (result) {
              if (renderer && renderer.onDone) {
                renderer.onDone(result);
              }
              if (renderId && window.iwChat && window.iwChat.injectToneSwitchChip) {
                var assistantArticle = assistantBubble.parentElement;
                var tone = lastPhaseName === 'composing' ? 'technical' : 'functional';
                window.iwChat.injectToneSwitchChip(assistantArticle, renderId, tone);
              }
            },
            onImage: renderer ? renderer.onImage : function () {},
            onError: renderer ? renderer.onError : function (err) {
              if (assistantBubble) assistantBubble.textContent = 'Error: ' + err.message;
            },
          });
        }
      });
    }

    function hideEmptyState() {
      var empty = document.getElementById('chat-empty-state');
      if (empty) empty.remove();
    }

    function appendUserBubble(text) {
      var messages = document.getElementById('chat-messages');
      if (!messages) return;
      hideEmptyState();
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
      return article;
    }

    function appendAssistantBubble() {
      var messages = document.getElementById('chat-messages');
      if (!messages) return;
      hideEmptyState();
      var article = document.createElement('article');
      article.className = 'chat-message bg-background border border-border rounded-lg px-3 py-2 text-sm mr-8';
      article.dataset.role = 'assistant';
      var label = document.createElement('header');
      label.className = 'font-medium text-xs text-muted-foreground block mb-1';
      label.textContent = 'Assistant';
      var content = document.createElement('div');
      content.className = 'chat-message-body text-sm leading-relaxed';
      content.id = 'chat-current-response';
      article.appendChild(label);
      article.appendChild(content);
      messages.appendChild(article);
      return content;
    }

    function scrollToBottom() {
      var anchor = document.getElementById('chat-scroll-anchor');
      if (anchor) {
        anchor.scrollIntoView({ behavior: 'instant', block: 'end' });
      }
    }

    var scrollBtn = document.getElementById('chat-scroll-to-bottom');
    if (scrollBtn) {
      scrollBtn.addEventListener('click', function () {
        var anchor = document.getElementById('chat-scroll-anchor');
        if (anchor) anchor.scrollIntoView({ behavior: 'smooth', block: 'end' });
      });
    }

    var observer = new IntersectionObserver(function (entries) {
      var btn = document.getElementById('chat-scroll-to-bottom');
      if (btn) {
        btn.classList.toggle('hidden', entries[0].isIntersecting);
      }
    }, { threshold: 0.1 });
    var anchor = document.getElementById('chat-scroll-anchor');
    if (anchor) observer.observe(anchor);
  }

  initComposer();
})();
