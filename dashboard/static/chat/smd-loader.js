(function () {
  'use strict';

  import('/static/vendor/streaming-markdown/smd.min.js')
    .then(function (smd) {
      window.__iwSMD = smd;
      if (window.__iwChatOnSMDReady) {
        window.__iwChatOnSMDReady(smd);
      }
      var event = new CustomEvent('iw-smd-ready', { detail: smd });
      document.dispatchEvent(event);
    })
    .catch(function (err) {
      console.error('[iwChat] Failed to load streaming-markdown:', err);
    });
})();
