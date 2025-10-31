async function fetchJson(url, opts) {
  const res = await fetch(url, opts);
  const txt = await res.text();
  if (!res.ok) throw new Error(txt || res.statusText);
  return JSON.parse(txt);
}

function setBadge(el, ok, textOk="connected", textFail="—") {
  if (!el) return;
  if (ok) { el.className = "badge bg-success"; el.textContent = textOk; }
  else { el.className = "badge bg-secondary"; el.textContent = textFail; }
}

// -------- System status --------
async function loadAccount(network, prefix) {
  try {
    const js = await fetchJson(`/api/account?network=${encodeURIComponent(network)}`);
    const d = js.data || {};
    setBadge(document.getElementById(`${prefix}_badge`), !!d.connected, d.connected ? "connected" : "—");
    document.getElementById(`${prefix}_balance`).textContent = (d.balance_usdt ?? "—");
    document.getElementById(`${prefix}_open`).textContent = (d.open_positions ?? 0);
    document.getElementById(`${prefix}_closed`).textContent = (d.closed_trades ?? 0);
    const pnl = (d.total_pnl_percent ?? 0).toFixed ? d.total_pnl_percent.toFixed(2)+"%" : String(d.total_pnl_percent);
    document.getElementById(`${prefix}_pnl`).textContent = pnl;
  } catch (e) {
    setBadge(document.getElementById(`${prefix}_badge`), false, "—");
  }
}

async function loadTrainingStatusSmall() {
  try {
    const js = await fetchJson("/api/training/active");
    const job = js.data;
    const badge = document.getElementById("train_job_status");
    const progressText = document.getElementById("train_job_progress");
    if (!badge || !progressText) return;
    if (job) {
      const pct = Math.round((job.progress ?? 0) * 1000) / 10;
      badge.className = "badge bg-warning text-dark";
      badge.textContent = job.status === "queued" ? "в очереди" : `идёт: ${pct}%`;
      progressText.textContent = `${pct}%`;
    } else {
      badge.className = "badge bg-secondary";
      badge.textContent = "нет задачи";
      progressText.textContent = "0%";
    }
  } catch (e) {
    // ignore
  }
}

async function loadWsStatus() {
  // Прямого эндпойнта нет: считаем, что если API отвечает на /api/ping — сервис жив.
  try {
    await fetchJson("/api/ping");
    setBadge(document.getElementById("ws_badge"), true, "активен");
    const txt = document.getElementById("ws_status_text");
    if (txt) txt.textContent = "активен";
  } catch (e) {
    setBadge(document.getElementById("ws_badge"), false, "—");
    const txt = document.getElementById("ws_status_text");
    if (txt) txt.textContent = "недоступен";
  }
}

// -------- Analysis block --------
async function loadAnalysis() {
  const symbol = document.getElementById("an_symbol").value || "BTC/USDT";
  const tf = document.getElementById("an_tf").value || "15m";
  const limit = 500;
  const err = document.getElementById("analysis_error");
  try {
    const js = await fetchJson(`/api/analysis?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(tf)}&limit=${limit}`);
    const data = js.data || {};
    // summary
    document.getElementById("ai_summary").textContent = data.summary || "—";
    // patterns
    const pat = (data.patterns || []).slice(-10);
    const pl = document.getElementById("patterns_list"); pl.innerHTML = "";
    pat.forEach(p => {
      const li = document.createElement("li");
      li.textContent = `${p.name || "pattern"} @ ${p.time || ""}`;
      pl.appendChild(li);
    });
    // opportunities
    const opps = (data.opportunities || []).slice(-10);
    const ol = document.getElementById("opps_list"); ol.innerHTML = "";
    opps.forEach(o => {
      const li = document.createElement("li");
      li.textContent = `${o.type || "opportunity"} @ ${o.time || ""}`;
      ol.appendChild(li);
    });
    // indicator panels under chart
    if (typeof window.renderIndicatorPanelsFromAnalysis === "function") {
      const wrap = document.getElementById("indicator-panels");
      if (wrap) wrap.remove();
      const exp = document.getElementById("explain-panel");
      if (exp) exp.remove();
      window.renderIndicatorPanelsFromAnalysis(data, { symbol, timeframe: tf }, "chart-root");
    }
    if (err) err.style.display = "none";
  } catch (e) {
    if (err) err.style.display = "";
  }
}

// -------- Pairs status --------
async function loadPairsStatus() {
  try {
    const js = await fetchJson("/api/pairs_status");
    const rows = js.data || [];
    const tb = document.getElementById("pairs_tbody");
    tb.innerHTML = "";
    rows.forEach(r => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${r.symbol || r.pair || ""}</td>
        <td>${r.trained ? "да" : "нет"}</td>
        <td>${r.last_full_train || "—"}</td>
        <td>${r.last_incremental || "—"}</td>
        <td>${(r.accuracy ?? "—")}</td>
      `;
      tb.appendChild(tr);
    });
  } catch (e) {
    // silent
  }
}

// -------- Trades --------
async function loadTrades(limit = 30, network = "testnet") {
  try {
    const js = await fetchJson(`/api/trades?limit=${encodeURIComponent(limit)}&network=${encodeURIComponent(network)}`);
    const rows = js.data || [];
    const tb = document.getElementById("trades_tbody");
    tb.innerHTML = "";
    rows.forEach(r => {
      const tr = document.createElement("tr");
      const ts = r.entry_time ? new Date(r.entry_time).toLocaleString() : "";
      tr.innerHTML = `
        <td>${ts}</td>
        <td>${r.symbol || ""}</td>
        <td>${(r.side || "").toUpperCase()}</td>
        <td>${Number(r.pnl_percent || 0).toFixed(2)}</td>
      `;
      tb.appendChild(tr);
    });
  } catch (e) {
    // ignore
  }
}

// -------- News --------
async function loadNews(hours = 24) {
  try {
    const js = await fetchJson(`/api/news?hours=${encodeURIComponent(hours)}`);
    const rows = js.data || [];
    const tb = document.getElementById("news_tbody");
    tb.innerHTML = "";
    rows.forEach(n => {
      const tr = document.createElement("tr");
      const when = n.published_at ? new Date(n.published_at).toLocaleString() : "";
      const sent = (n.sentiment !== null && n.sentiment !== undefined) ? Number(n.sentiment).toFixed(2) : "";
      tr.innerHTML = `
        <td>${when}</td>
        <td>${n.provider || ""}</td>
        <td>${n.title || ""}</td>
        <td>${sent}</td>
      `;
      tb.appendChild(tr);
    });
  } catch (e) {
    // ignore
  }
}

function wireEvents() {
  document.getElementById("an_btn")?.addEventListener("click", (e)=>{ e.preventDefault(); loadAnalysis(); });
  document.getElementById("pairs_refresh")?.addEventListener("click", (e)=>{ e.preventDefault(); loadPairsStatus(); });
  document.getElementById("trades_refresh")?.addEventListener("click", (e)=>{ e.preventDefault(); loadTrades(); });
  document.getElementById("news_refresh")?.addEventListener("click", (e)=>{ e.preventDefault(); loadNews(); });
}

async function initialLoad() {
  wireEvents();
  await Promise.all([
    loadAccount("mainnet", "mainnet"),
    loadAccount("testnet", "testnet"),
    loadWsStatus(),
    loadTrainingStatusSmall(),
    loadAnalysis(),
    loadPairsStatus(),
    loadTrades(),
    loadNews()
  ]);
  // периодические обновления
  setInterval(loadTrainingStatusSmall, 8000);
  setInterval(()=>loadAccount("mainnet","mainnet"), 20000);
  setInterval(()=>loadAccount("testnet","testnet"), 20000);
  setInterval(loadWsStatus, 20000);
  setInterval(loadPairsStatus, 30000);
  setInterval(loadTrades, 30000);
  setInterval(loadNews, 60000);
}

window.addEventListener("load", initialLoad);