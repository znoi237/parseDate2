async function fetchJson(url, opts) {
  const res = await fetch(url, opts);
  const txt = await res.text();
  if (!res.ok) throw new Error(txt || res.statusText);
  return JSON.parse(txt);
}

function getFormValues() {
  const symbol = document.getElementById("an_symbol").value.trim() || (window.__AN_SYMBOL__ || "BTC/USDT");
  const tf = document.getElementById("an_tf").value || (window.__AN_TF__ || "15m");
  const limit = Number(document.getElementById("an_limit").value || window.__AN_LIMIT__ || 500);
  return { symbol, timeframe: tf, limit };
}

async function loadAnalysisAndRender(rootId = "chart-root") {
  try {
    const { symbol, timeframe, limit } = getFormValues();
    // ВАЖНО: вызываем /api/analysis
    const js = await fetchJson(`/api/analysis?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}&limit=${encodeURIComponent(limit)}`);
    const data = js.data || {};
    const ctx = { symbol, timeframe };
    if (typeof window.setAnalysisContext === "function") {
      window.setAnalysisContext(symbol, timeframe);
    }
    if (typeof window.renderIndicatorPanelsFromAnalysis === "function") {
      const wrap = document.getElementById("indicator-panels");
      if (wrap) wrap.remove();
      const exp = document.getElementById("explain-panel");
      if (exp) exp.remove();
      window.renderIndicatorPanelsFromAnalysis(data, ctx, rootId);
    }
  } catch (e) {
    console.error("analysis load failed", e);
    alert("Ошибка загрузки анализа: " + e.message);
  }
}

window.addEventListener("load", () => {
  if (document.getElementById("an_symbol")) {
    if (window.__AN_SYMBOL__) document.getElementById("an_symbol").value = window.__AN_SYMBOL__;
  }
  if (document.getElementById("an_tf")) {
    if (window.__AN_TF__) document.getElementById("an_tf").value = window.__AN_TF__;
  }
  if (document.getElementById("an_limit")) {
    if (window.__AN_LIMIT__) document.getElementById("an_limit").value = String(window.__AN_LIMIT__);
  }
  loadAnalysisAndRender("chart-root");
  const form = document.getElementById("analysis-form");
  if (form) {
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      loadAnalysisAndRender("chart-root");
    });
  }
});