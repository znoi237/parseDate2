let chart, candleSeries, sma20Series, ema50Series, bbUpperSeries, bbLowerSeries;

async function fetchJson(url, opts) {
  const res = await fetch(url, opts);
  const txt = await res.text();
  if (!res.ok) throw new Error(txt || res.statusText);
  return JSON.parse(txt);
}

async function loadSymbolsForAnalysis() {
  try {
    const js = await fetchJson("/api/symbols");
    const sel = document.getElementById("an_symbol");
    sel.innerHTML = "";
    (js.data || []).forEach(sym => {
      const opt = document.createElement("option");
      opt.value = sym;
      opt.textContent = sym;
      sel.appendChild(opt);
    });
    if (js.data && js.data.length > 0) sel.value = js.data[0];
  } catch (e) {
    console.error("loadSymbolsForAnalysis", e);
  }
}

function ensureChart() {
  const el = document.getElementById("an_chart");
  if (!chart) {
    chart = LightweightCharts.createChart(el, { height: 420, layout: { background: { color: '#ffffff' }, textColor: '#333' }, grid: { horzLines: { color: '#eee' }, vertLines: { color: '#eee' }}, crosshair: { mode: LightweightCharts.CrosshairMode.Normal } });
    candleSeries = chart.addCandlestickSeries();
    sma20Series = chart.addLineSeries({ color: '#2962FF', lineWidth: 1 });
    ema50Series = chart.addLineSeries({ color: '#FF6D00', lineWidth: 1 });
    bbUpperSeries = chart.addLineSeries({ color: '#9CCC65', lineWidth: 1 });
    bbLowerSeries = chart.addLineSeries({ color: '#EF5350', lineWidth: 1 });
  }
  return chart;
}

function setMsg(msg) {
  const box = document.getElementById("an_msg");
  if (msg) {
    box.style.display = "block";
    box.textContent = msg;
  } else {
    box.style.display = "none";
    box.textContent = "";
  }
}

function toTsSec(iso) { return Math.floor(new Date(iso).getTime() / 1000); }

function applyMarkersFromApi(markers, botMarkers) {
  const shapes = {
    buy:      { position: 'belowBar', color: '#2e7d32', shape: 'arrowUp' },
    sell:     { position: 'aboveBar', color: '#c62828', shape: 'arrowDown' },
    tp:       { position: 'belowBar', color: '#1b5e20', shape: 'circle' },
    sl:       { position: 'aboveBar', color: '#b71c1c', shape: 'circle' },
    timeout:  { position: 'aboveBar', color: '#6d4c41', shape: 'square' },
    bot_entry_buy:  { position: 'belowBar', color: '#00BCD4', shape: 'arrowUp' },
    bot_entry_sell: { position: 'aboveBar', color: '#00BCD4', shape: 'arrowDown' },
    bot_exit:       { position: 'aboveBar', color: '#546E7A', shape: 'circle' },
  };
  const all = [...(markers || []), ...(botMarkers || [])];
  const items = all.map(m => {
    const t = shapes[m.type] || { position: 'aboveBar', color: m.color || '#555', shape: 'circle' };
    return {
      time: toTsSec(m.time),
      position: t.position,
      color: t.color,
      shape: t.shape,
      text: m.note || m.type
    };
  });
  candleSeries.setMarkers(items.slice(-400));
}

function setList(id, items) {
  const ul = document.getElementById(id);
  ul.innerHTML = "";
  (items || []).slice(-20).reverse().forEach(p => {
    const li = document.createElement("li");
    const dt = new Date(p.time).toLocaleString();
    li.textContent = `${dt}: ${p.note || p.type}`;
    ul.appendChild(li);
  });
}

async function loadAnalysis() {
  try {
    const symbol = document.getElementById("an_symbol").value;
    const tf = document.getElementById("an_tf").value;
    if (!symbol) { setMsg("Выберите пару"); return; }
    const js = await fetchJson(`/api/analysis?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(tf)}&limit=500&network=testnet`);
    const d = js.data || {};
    if (!d.trained) {
      setMsg("Модель не обучена на этой паре. График скрыт.");
      const el = document.getElementById("an_chart");
      el.innerHTML = "";
      chart = null; candleSeries = null;
      document.getElementById("an_summary").textContent = "—";
      setList("an_patterns", []);
      setList("an_opps", []);
      return;
    }
    setMsg("");
    ensureChart();

    const candles = (d.candles||[]).map(k => ({ time: toTsSec(k.time), open: k.open, high: k.high, low: k.low, close: k.close }));
    candleSeries.setData(candles);

    const inds = d.indicators || {};
    const mapLine = (arr) => (arr||[]).map((v,i) => ({ time: candles[i]?.time, value: (typeof v === "number" && isFinite(v)) ? v : null })).filter(p => p.time && p.value !== null);
    sma20Series.setData(mapLine(inds.sma20));
    ema50Series.setData(mapLine(inds.ema50));
    bbUpperSeries.setData(mapLine(inds.bb_upper));
    bbLowerSeries.setData(mapLine(inds.bb_lower));

    applyMarkersFromApi(d.markers, d.bot_markers);
    document.getElementById("an_summary").textContent = d.summary || "—";
    setList("an_patterns", d.patterns);
    setList("an_opps", d.opportunities);

    chart.timeScale().fitContent();
  } catch (e) {
    console.error("loadAnalysis", e);
    setMsg("Ошибка загрузки анализа");
  }
}

window.addEventListener("load", async () => {
  await loadSymbolsForAnalysis();
  await loadAnalysis();
});