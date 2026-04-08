// dashboard/static/duration.js
// Updates all [data-started-at] elements every second with live elapsed time.

setInterval(() => {
  document.querySelectorAll('[data-started-at]').forEach(el => {
    const started = new Date(el.dataset.startedAt);
    const elapsed = Math.floor((Date.now() - started) / 1000);
    const min = Math.floor(elapsed / 60);
    const sec = elapsed % 60;
    el.textContent = `${min}m${sec.toString().padStart(2, '0')}s`;
  });
}, 1000);
