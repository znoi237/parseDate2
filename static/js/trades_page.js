async function fetchJson(url, opts) {
  const res = await fetch(url, opts);
  const txt = await res.text();
  if (!res.ok) throw new Error(txt || res.statusText);
  return JSON.parse(txt);
}

async function loadTrades() {
  const network = document.getElementById("t_network").value || "testnet";
  const symbol = document.getElementById("t_symbol").value.trim();
  const status = document.getElementById("t_status").value;
  const q = new URLSearchParams();
  q.append("network", network);
  if (symbol) q.append("symbol", symbol);
  if (status) q.append("status", status);
  const js = await fetchJson(`/api/trades?${q.toString()}`);
  const rows = js.data || [];
  const tb = document.getElementById("trades_tbody");
  tb.innerHTML = "";
  rows.forEach(r => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${r.network || ''}</td>
      <td>${r.symbol || ''}</td>
      <td>${(r.side || '').toUpperCase()}</td>
      <td>${Number(r.entry_price || 0).toFixed(4)}</td>
      <td>${Number(r.exit_price || 0).toFixed(4)}</td>
      <td>${Number(r.pnl_percent || 0).toFixed(2)}</td>
      <td>${r.status || ''}</td>
      <td>${r.entry_time ? new Date(r.entry_time).toLocaleString() : ''}</td>
      <td>${r.exit_time ? new Date(r.exit_time).toLocaleString() : ''}</td>
    `;
    tb.appendChild(tr);
  });
}

window.addEventListener("load", () => {
  document.getElementById("trades-form").addEventListener("submit", (e)=>{ e.preventDefault(); loadTrades(); });
  loadTrades();
});