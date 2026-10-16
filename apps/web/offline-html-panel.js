(() => {
  "use strict";

  const section = document.createElement("section");
  section.className = "panel";
  section.setAttribute("aria-labelledby", "offline-html-heading");
  section.innerHTML = `
    <div class="panel-heading"><div>
      <p class="eyebrow">Offline / user-supplied source</p>
      <h2 id="offline-html-heading">Analyze your own HTML</h2>
    </div><span class="pill fixture">NO NETWORK SCAN</span></div>
    <p>This checks missing image alternative text in supplied HTML only. It does not visit a URL, run JavaScript, or certify WCAG compliance.</p>
    <form id="offline-html-form">
      <label>HTML file (optional, UTF-8, max 1 MiB)
        <input id="offline-html-file" type="file" accept=".html,.htm,text/html">
      </label>
      <label>HTML source
        <textarea id="offline-html-source" rows="5" placeholder="Paste HTML source or choose a file"></textarea>
      </label>
      <button type="submit" class="primary" id="offline-html-submit">Analyze supplied HTML</button>
    </form>
    <p id="offline-html-status" role="status" aria-live="polite">No HTML analyzed.</p>
    <pre class="output" id="offline-html-results" aria-live="polite">Waiting for HTML input.</pre>`;
  const main = document.querySelector("main");
  const footer = main.querySelector("footer");
  main.insertBefore(section, footer);

  const el = (id) => document.getElementById(id);
  const maxBytes = 1_048_576;

  el("offline-html-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = el("offline-html-submit");
    button.disabled = true;
    el("offline-html-status").textContent = "Validating HTML source...";
    el("offline-html-results").textContent = "";
    try {
      const file = el("offline-html-file").files[0];
      let html = el("offline-html-source").value;
      if (file) {
        if (file.size < 1 || file.size > maxBytes) throw new Error("HTML file must be between 1 byte and 1 MiB.");
        html = new TextDecoder("utf-8", { fatal: true }).decode(await file.arrayBuffer());
      }
      if (!html || new TextEncoder().encode(html).byteLength > maxBytes) {
        throw new Error("Supply nonempty UTF-8 HTML within the 1 MiB limit.");
      }
      const token = el("bearer-token").value.trim();
      if (!token) throw new Error("A scoped scan:start bearer token is required.");
      const configured = el("api-base").value.trim();
      const base = new URL(configured || location.origin);
      if (!["http:", "https:"].includes(base.protocol) ||
          (base.origin !== location.origin && !["localhost", "127.0.0.1"].includes(base.hostname))) {
        throw new Error("API must be same-origin or an explicitly configured local development host.");
      }
      const response = await fetch(new URL("/v1/offline/html-findings", base), {
        method: "POST",
        headers: {
          "Authorization": token.startsWith("Bearer ") ? token : "Bearer " + token,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ source_html: html }),
        cache: "no-store",
        credentials: "omit"
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || "Offline analysis failed (" + response.status + ").");
      if (payload.source_kind !== "USER_SUPPLIED_HTML" || !Array.isArray(payload.findings)) {
        throw new Error("The API did not return verified offline analysis metadata.");
      }
      el("offline-html-results").textContent = JSON.stringify(payload, null, 2);
      el("offline-html-status").textContent = payload.finding_count + " image-alt finding(s). No remote website was contacted.";
    } catch (error) {
      el("offline-html-status").textContent = "Analysis stopped: " + (error instanceof Error ? error.message : String(error));
    } finally {
      button.disabled = false;
    }
  });
})();
