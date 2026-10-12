(() => {
  "use strict";

  const SECTOR_ORDER = ["Technology", "Digital & Media", "Private Equity", "Financial Services",
    "Healthcare & Life Sciences", "Industrials", "Energy & Resources", "Consumer & Retail",
    "Telecom", "Real Estate", "Other"];
  const PAGE = 60;
  const $ = (s) => document.querySelector(s);

  let deals = [];
  let shown = PAGE;
  const state = { q: "", sector: [], type: [], status: [], region: [], days: 7, min: 0, kind: "", sort: "date", parties: false };
  const DEFAULTS = JSON.stringify(state);

  // ------------------------------------------------------------ URL state
  function readHash() {
    try {
      const h = new URLSearchParams(location.hash.slice(1));
      for (const k of Object.keys(state)) {
        if (!h.has(k)) continue;
        const v = h.get(k);
        if (Array.isArray(state[k])) state[k] = v ? v.split("|") : [];
        else if (typeof state[k] === "number") state[k] = Number(v) || 0;
        else if (typeof state[k] === "boolean") state[k] = v === "1";
        else state[k] = v;
      }
    } catch (_) { /* ignore malformed hash */ }
  }
  function writeHash() {
    const d = JSON.parse(DEFAULTS);
    const h = new URLSearchParams();
    for (const [k, v] of Object.entries(state)) {
      if (JSON.stringify(v) === JSON.stringify(d[k])) continue;
      h.set(k, Array.isArray(v) ? v.join("|") : typeof v === "boolean" ? (v ? "1" : "0") : v);
    }
    const s = h.toString();
    history.replaceState(null, "", s ? "#" + s : location.pathname + location.search);
  }

  // ------------------------------------------------------------ helpers
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  function fmtValue(m) {
    if (m == null) return "";
    if (m >= 1000) return "$" + (m / 1000).toFixed(m >= 10000 ? 0 : 1) + "B";
    if (m >= 1) return "$" + Math.round(m) + "M";
    return "$" + (m * 1000).toFixed(0) + "K";
  }
  function fmtAgo(iso) {
    const ms = Date.now() - new Date(iso).getTime();
    const h = Math.round(ms / 36e5);
    if (h < 1) return "just now";
    if (h < 24) return h + "h ago";
    const d = Math.round(h / 24);
    return d === 1 ? "1 day ago" : d + " days ago";
  }
  const statusClass = (s) => "s-" + String(s).split(/[ /]/)[0];
  const hay = (d) => (d._hay ??= [d.title, d.summary, d.acquirer, d.target, d.publisher, d.pe_firm,
    d.deal_type, d.status, ...(d.sectors || []), ...(d.regions || [])].join(" ").toLowerCase());

  // ------------------------------------------------------------ filtering
  function matches(d, skip) {
    if (state.q) {
      const terms = state.q.toLowerCase().split(/\s+/).filter(Boolean);
      if (!terms.every((t) => hay(d).includes(t))) return false;
    }
    if (skip !== "sector" && state.sector.length && !d.sectors.some((s) => state.sector.includes(s))) return false;
    if (skip !== "type" && state.type.length && !state.type.includes(d.deal_type)) return false;
    if (skip !== "status" && state.status.length && !state.status.includes(d.status)) return false;
    if (skip !== "region" && state.region.length && !d.regions.some((r) => state.region.includes(r))) return false;
    if (state.days && Date.now() - new Date(d.published).getTime() > state.days * 864e5) return false;
    if (state.min === -1 && d.value_usd_m == null) return false;
    if (state.min > 0 && !(d.value_usd_m >= state.min)) return false;
    if (state.kind && d.source_kind !== state.kind) return false;
    if (state.parties && !(d.acquirer && d.target)) return false;
    return true;
  }
  function sorted(list) {
    const by = {
      date: (a, b) => b.published.localeCompare(a.published),
      value: (a, b) => (b.value_usd_m ?? -1) - (a.value_usd_m ?? -1) || b.published.localeCompare(a.published),
      sources: (a, b) => (b.links?.length || 1) - (a.links?.length || 1) || b.published.localeCompare(a.published),
    }[state.sort] || ((a, b) => b.published.localeCompare(a.published));
    return list.slice().sort(by);
  }

  // ------------------------------------------------------------ rendering
  function buildChecks(el, key, values, field) {
    const counts = {};
    for (const d of deals) {
      if (!matches(d, key)) continue;
      const v = d[field];
      for (const x of Array.isArray(v) ? v : [v]) counts[x] = (counts[x] || 0) + 1;
    }
    el.innerHTML = values.map((v) =>
      `<label><input type="checkbox" value="${esc(v)}" ${state[key].includes(v) ? "checked" : ""}> ${esc(v)} <span class="n">${counts[v] || 0}</span></label>`
    ).join("");
    el.onchange = () => {
      state[key] = [...el.querySelectorAll("input:checked")].map((i) => i.value);
      shown = PAGE;
      render();
    };
  }
  function uniq(field) {
    const s = new Set();
    for (const d of deals) for (const x of [].concat(d[field] || [])) s.add(x);
    return [...s];
  }

  function card(d) {
    const parties = d.acquirer || d.target
      ? `<div class="parties"><b>${esc(d.acquirer || "?")}</b><span class="arrow">→</span><b>${esc(d.target || "?")}</b>${d.pe_firm && d.pe_firm !== d.acquirer ? ` <span class="muted">(${esc(d.pe_firm)})</span>` : ""}</div>`
      : "";
    const tags = [
      d.value_usd_m != null ? `<span class="tag value" title="${esc(d.value_text)}">${fmtValue(d.value_usd_m)}${d.value_currency && d.value_currency !== "USD" ? " ≈" : ""}</span>` : "",
      `<span class="tag ${statusClass(d.status)}">${esc(d.status)}</span>`,
      `<span class="tag">${esc(d.deal_type)}</span>`,
      ...d.sectors.map((s) => `<span class="tag">${esc(s)}</span>`),
      ...d.regions.filter((r) => r !== "Unknown").map((r) => `<span class="tag">${esc(r)}</span>`),
    ].join("");
    const links = d.links || [{ url: d.url, publisher: d.publisher }];
    const more = links.length > 1
      ? ` · also: ${links.slice(1, 5).map((l) => `<a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.publisher || "link")}</a>`).join(", ")}${links.length > 5 ? ` +${links.length - 5}` : ""}`
      : "";
    return `<article class="card">
      <h2><a href="${esc(d.url)}" target="_blank" rel="noopener">${esc(d.title)}</a></h2>
      ${parties}
      ${d.summary ? `<p class="sum">${esc(d.summary.slice(0, 220))}${d.summary.length > 220 ? "…" : ""}</p>` : ""}
      <div class="meta">${tags}</div>
      <div class="src">${esc(d.publisher)} · ${fmtAgo(d.published)}${more}</div>
    </article>`;
  }

  function render() {
    writeHash();
    const sectors = SECTOR_ORDER.filter((s) => uniq("sectors").includes(s));
    buildChecks($("#f-sector"), "sector", sectors, "sectors");
    buildChecks($("#f-type"), "type", uniq("deal_type").sort(), "deal_type");
    buildChecks($("#f-status"), "status", ["Announced", "Completed", "Rumored / In talks", "Terminated / Blocked"].filter((s) => uniq("status").includes(s)), "status");
    buildChecks($("#f-region"), "region", uniq("regions").sort(), "regions");
    for (const b of document.querySelectorAll("[data-quick]")) {
      const q = b.dataset.quick;
      b.classList.toggle("on", q === "all" ? state.sector.length === 0 : state.sector.length === 1 && state.sector[0] === q);
    }

    const list = sorted(deals.filter((d) => matches(d)));
    const total = list.reduce((s, d) => s + (d.value_usd_m || 0), 0);
    const disclosed = list.filter((d) => d.value_usd_m != null).length;
    const pe = list.filter((d) => d.private_equity).length;
    $("#stats").innerHTML = `<span><b>${list.length}</b> deals</span><span><b>${fmtValue(total) || "$0"}</b> disclosed value (${disclosed} with value)</span><span><b>${pe}</b> private equity</span>`;
    $("#list").innerHTML = list.length ? list.slice(0, shown).map(card).join("") : `<div class="empty">No deals match these filters.</div>`;
    $("#more").hidden = list.length <= shown;
    $("#more").textContent = `Show more (${list.length - shown} remaining)`;
    current = list;
  }
  let current = [];

  // ------------------------------------------------------------ CSV
  function exportCsv() {
    const cols = ["published", "acquirer", "target", "value_usd_m", "value_text", "deal_type", "status", "sectors", "regions", "private_equity", "pe_firm", "title", "publisher", "url"];
    const cell = (v) => {
      const s = Array.isArray(v) ? v.join("; ") : v == null ? "" : String(v);
      return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
    };
    const csv = [cols.join(",")].concat(current.map((d) => cols.map((c) => cell(d[c])).join(","))).join("\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    a.download = `acquisitions-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }

  // ------------------------------------------------------------ data
  async function load() {
    const r = await fetch("data/deals.json?t=" + Date.now(), { cache: "no-store" });
    if (!r.ok) throw new Error("HTTP " + r.status);
    const data = await r.json();
    deals = data.deals || [];
    const okFeeds = (data.sources || []).filter((s) => s.ok).length;
    $("#updated").textContent = data.generated_at
      ? `Updated ${fmtAgo(data.generated_at)} (${new Date(data.generated_at).toLocaleString()}) · ${deals.length} deals stored · ${okFeeds}/${(data.sources || []).length} feeds OK`
      : "No data yet. The first scheduled update has not run.";
  }

  // ------------------------------------------------------------ wiring
  function syncControls() {
    $("#q").value = state.q;
    $("#f-days").value = String(state.days);
    $("#f-min").value = String(state.min);
    $("#f-kind").value = state.kind;
    $("#f-sort").value = state.sort;
    $("#f-parties").checked = state.parties;
  }
  function bind() {
    let t;
    $("#q").addEventListener("input", (e) => { clearTimeout(t); t = setTimeout(() => { state.q = e.target.value.trim(); shown = PAGE; render(); }, 150); });
    for (const [id, key, num] of [["#f-days", "days", 1], ["#f-min", "min", 1], ["#f-kind", "kind", 0], ["#f-sort", "sort", 0]]) {
      $(id).addEventListener("change", (e) => { state[key] = num ? Number(e.target.value) : e.target.value; shown = PAGE; render(); });
    }
    $("#f-parties").addEventListener("change", (e) => { state.parties = e.target.checked; render(); });
    $("#toggle-filters").addEventListener("click", () => {
      const f = $("#filters");
      f.hidden = !f.hidden;
      $("#toggle-filters").setAttribute("aria-expanded", String(!f.hidden));
    });
    $("#quick").addEventListener("click", (e) => {
      const q = e.target.dataset?.quick;
      if (!q) return;
      state.sector = q === "all" ? [] : [q];
      shown = PAGE;
      render();
    });
    $("#reset").addEventListener("click", () => { Object.assign(state, JSON.parse(DEFAULTS)); syncControls(); render(); });
    $("#more").addEventListener("click", () => { shown += PAGE; render(); });
    $("#export").addEventListener("click", exportCsv);

    // "Refresh now" only works with the local server (python -m acqtracker serve).
    if (["localhost", "127.0.0.1"].includes(location.hostname) || location.hostname.endsWith(".local")) {
      const b = $("#refresh");
      b.hidden = false;
      b.addEventListener("click", async () => {
        b.disabled = true; b.textContent = "Fetching…";
        try {
          const r = await fetch("api/refresh", { method: "POST" });
          if (!r.ok) throw new Error("HTTP " + r.status);
          await load(); render();
        } catch (err) { alert("Refresh failed: " + err.message); }
        b.disabled = false; b.textContent = "Refresh now";
      });
    }
  }

  readHash();
  syncControls();
  bind();
  load().then(render).catch((e) => {
    $("#updated").textContent = "Could not load data: " + e.message;
    $("#list").innerHTML = `<div class="empty">No data available.</div>`;
  });
})();
