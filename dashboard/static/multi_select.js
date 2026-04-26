document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('[data-multi-select]').forEach(function (wrapper) {
    var name = wrapper.getAttribute('data-multi-select');
    var btn = wrapper.querySelector('[data-multi-select-btn="' + name + '"]');
    var panel = wrapper.querySelector('[data-multi-select-panel="' + name + '"]');

    function updateLabel() {
      var checked = wrapper.querySelectorAll('input[type="checkbox"]:checked');
      var count = checked.length;
      btn.textContent = btn.textContent.replace(/ \(\d+ selected\)/, '') +
        (count > 0 ? ' (' + count + ' selected)' : '');
    }

    function open() {
      panel.removeAttribute('hidden');
      btn.setAttribute('aria-expanded', 'true');
    }

    function close() {
      panel.setAttribute('hidden', '');
      btn.setAttribute('aria-expanded', 'false');
    }

    btn.addEventListener('click', function () {
      var isHidden = panel.hasAttribute('hidden');
      if (isHidden) { open(); } else { close(); }
    });

    wrapper.querySelectorAll('input[type="checkbox"]').forEach(function (cb) {
      cb.addEventListener('change', updateLabel);
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !panel.hasAttribute('hidden')) {
        close();
        btn.focus();
      }
    });

    document.addEventListener('click', function (e) {
      if (!wrapper.contains(e.target)) {
        close();
      }
    });

    updateLabel();
  });
});
