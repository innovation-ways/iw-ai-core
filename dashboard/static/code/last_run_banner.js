(function () {
  var banner = document.getElementById('code-last-run-banner');
  var dismissBtn = banner && banner.querySelector('[data-dismiss-job-id]');
  if (!banner || !dismissBtn) return;
  var projectId = dismissBtn.dataset.projectId;
  var jobId = dismissBtn.dataset.dismissJobId;
  var storageKey = 'iw_code_lastrun_dismissed:' + projectId;
  function applyDismissal() {
    if (localStorage.getItem(storageKey) === jobId) {
      banner.style.display = 'none';
    }
  }
  applyDismissal();
  document.body.addEventListener('htmx:afterSettle', function (e) {
    var target = e.detail && e.detail.target;
    if (target && (target.id === 'code-status-panel' || target.closest('#code-status-panel'))) {
      applyDismissal();
    }
  });
  dismissBtn.addEventListener('click', function () {
    localStorage.setItem(storageKey, jobId);
    banner.style.display = 'none';
  });
})();