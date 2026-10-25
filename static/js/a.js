/*
 * falcondatabase analytics — add to your website:
 *   <script defer data-project="PROJECT_REF" src="https://your-server/a.js"></script>
 * Sends one page view per page load and per client-side navigation.
 * No cookies, no local storage, ~1 KB.
 */
(function () {
  var script = document.currentScript;
  if (!script || !script.getAttribute("data-project")) return;
  var endpoint = new URL(script.src).origin + "/api/v1/" + script.getAttribute("data-project") + "/collect";
  var lastUrl = null;

  function send() {
    var url = location.href;
    if (url === lastUrl) return;
    lastUrl = url;
    var tz = "";
    try { tz = Intl.DateTimeFormat().resolvedOptions().timeZone || ""; } catch (e) {}
    var body = JSON.stringify({ u: url, r: document.referrer || "", tz: tz });
    if (navigator.sendBeacon && navigator.sendBeacon(endpoint, new Blob([body], { type: "text/plain" }))) return;
    fetch(endpoint, { method: "POST", body: body, keepalive: true, mode: "no-cors", headers: { "Content-Type": "text/plain" } });
  }

  // Single-page apps: count client-side navigations too.
  var pushState = history.pushState;
  history.pushState = function () { pushState.apply(this, arguments); send(); };
  window.addEventListener("popstate", send);
  send();
})();
