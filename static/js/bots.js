async function fetchJson(url, opts) {
  const res = await fetch(url, opts);
  const txt = await res.text();
  if (!res.ok) throw new Error(txt);
  return JSON.parse(txt);
}

async function loadSymbols() {
  try {
    const js = await fetchJson("/api/symbols");
    const sel = document.getElementById("bot_symbol");
    sel.innerHTML = '<option value="" selected disabled>Выберите пару...</option>';
    (js.data || []).forEach(sym => {
      const opt = document.createElement("option");
      opt.value = sym;
      opt.textContent = sym;
      sel.appendChild(opt);
    });
    if (js.data && js.data.length > 0) sel.value = js.data[0];
  } catch (e) {
    console.error("loadSymbols error", e);
  }
}

async function startBot() {
  const symbol = document.getElementById("bot_symbol").value;
  if (!symbol) { alert("Выберите пару"); return; }
  const tfs = Array.from(document.getElementById("bot_tfs").selectedOptions).map(o=>o.value);
  const interval_sec = Number(document.getElementById("bot_interval").value);
  const js = await fetchJson("/api/bots/start", {
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body: JSON.stringify({symbol, timeframes:tfs, interval_sec})
  });
  alert(js.message || "OK");
  loadBots();
}

async function stopBot(symbol, btnEl) {
  try {
    if (btnEl) {
      btnEl.disabled = true;
      btnEl.innerText = "Стоп...";
    }
    const js = await fetchJson("/api/bots/stop", {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body: JSON.stringify({symbol})
    });
    const closed = js.closed_trades ?? 0;
    const price = typeof js.exit_price === "number" ? js.exit_price.toFixed(8) : js.exit_price;
    alert(`${js.message}\nЗакрыто позиций: ${closed}\nЦена закрытия: ${price}`);
  } catch (e) {
    console.error(e);
    alert("Ошибка остановки бота");
  } finally {
    loadBots();
  }
}

function renderStopButtonCell(symbol, status) {
  const td = document.createElement("td");
  if (status === "active") {
    const btn = document.createElement("button");
    btn.className = "btn btn-sm btn-outline-danger";
    btn.textContent = "Стоп";
    btn.onclick = () => stopBot(symbol, btn);
    td.appendChild(btn);
  } else {
    const btn = document.createElement("button");
    btn.className = "btn btn-sm btn-outline-secondary";
    btn.textContent = "Стоп";
    btn.disabled = true;
    td.appendChild(btn);
  }
  return td;
}

async function loadBots() {
  const js = await fetchJson("/api/bots");
  const tb = document.querySelector("#bots_table tbody");
  tb.innerHTML = "";
  (js.data || []).forEach(b => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${b.symbol}</td>
      <td>${b.status}</td>
      <td>${(() => { try { return JSON.stringify(b.stats||{}); } catch { return "{}"; } })()}</td>
      <td>${b.started_at||""}</td>
    `;
    tr.appendChild(renderStopButtonCell(b.symbol, b.status));
    tb.appendChild(tr);
  });
}

window.addEventListener("load", () => {
  loadSymbols();
  loadBots();
});