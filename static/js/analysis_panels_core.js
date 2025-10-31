// Базовые утилиты, контейнеры и глобальный контекст для панелей анализа (светлая тема).
(function () {
  var AP = window.AnalysisPanels || (window.AnalysisPanels = {});

  var ANALYSIS_CTX = { symbol: null, timeframe: null };
  function setAnalysisContext(symbol, timeframe) {
    ANALYSIS_CTX.symbol = symbol;
    ANALYSIS_CTX.timeframe = timeframe;
  }
  AP.CTX = ANALYSIS_CTX;
  AP.setAnalysisContext = setAnalysisContext;

  async function fetchJson(url, opts) {
    const r = await fetch(url, opts);
    const t = await r.text();
    if (!r.ok) throw new Error(t || r.statusText);
    return JSON.parse(t);
  }
  function hasLC() { return typeof LightweightCharts !== 'undefined'; }

  function makeChart(container, height = 120, timeScaleOpt = {}) {
    if (!hasLC()) return null;
    return LightweightCharts.createChart(container, {
      height,
      layout: { background: { type: 'Solid', color: '#ffffff' }, textColor: '#222' },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false, rightOffset: 2, ...timeScaleOpt },
      grid: { horzLines: { color: '#e9ecef' }, vertLines: { color: '#e9ecef' } },
      crosshair: { mode: 0 }
    });
  }
  function setSeries(series, data) {
    try { series.setData(data || []); } catch (e) {}
  }

  function ensureContainer(rootId = 'chart-root') {
    const root = document.getElementById(rootId) || document.body;
    let wrap = document.getElementById('indicator-panels');
    if (!wrap) {
      wrap = document.createElement('div');
      wrap.id = 'indicator-panels';
      wrap.style.marginTop = '8px';
      wrap.style.display = 'grid';
      wrap.style.gridTemplateColumns = '1fr';
      wrap.style.rowGap = '8px';
      root.appendChild(wrap);
    }
    return wrap;
  }

  function ensureExplainPanel(rootId = 'chart-root') {
    const root = document.getElementById(rootId) || document.body;
    let card = document.getElementById('explain-panel');
    if (!card) {
      card = document.createElement('div');
      card.className = 'card';
      card.id = 'explain-panel';
      const header = document.createElement('div');
      header.className = 'card-header';
      header.textContent = 'Объяснение сигнала';
      const body = document.createElement('div');
      body.className = 'card-body';
      body.id = 'explain-panel-body';
      body.style.whiteSpace = 'pre-wrap';
      body.style.fontFamily = 'monospace';
      body.style.fontSize = '12px';
      body.textContent = 'Нажмите на точку/столбик на панели AI Signal, чтобы увидеть объяснение.';
      card.appendChild(header); card.appendChild(body);
      root.appendChild(card);
    }
    return card;
  }
  function updateExplainPanelText(text, rootId = 'chart-root') {
    ensureExplainPanel(rootId);
    const body = document.getElementById('explain-panel-body');
    if (body) body.textContent = text || '—';
  }

  function addPanel(wrap, title) {
    const card = document.createElement('div');
    card.className = 'card';
    const header = document.createElement('div');
    header.className = 'card-header';
    header.textContent = title;
    const body = document.createElement('div');
    body.className = 'card-body';
    const div = document.createElement('div');
    div.style.height = '120px';
    body.appendChild(div);
    card.appendChild(header); card.appendChild(body);
    wrap.appendChild(card);
    return { card, body, div, header };
  }
  function addListPanel(wrap, title) {
    const card = document.createElement('div');
    card.className = 'card';
    const header = document.createElement('div');
    header.className = 'card-header';
    header.textContent = title;
    const body = document.createElement('div');
    body.className = 'card-body';
    body.style.maxHeight = '220px';
    body.style.overflowY = 'auto';
    const ul = document.createElement('ul');
    ul.className = 'list-group list-group-flush';
    ul.id = 'news-list';
    body.appendChild(ul);
    card.appendChild(header); card.appendChild(body);
    wrap.appendChild(card);
    return { card, body, ul };
  }

  function createPriceLine(series, price, color = '#adb5bd', style) {
    try {
      var st = style || (window.LightweightCharts ? LightweightCharts.LineStyle.Dashed : 0);
      series.createPriceLine({ price, color, lineStyle: st, lineWidth: 1, axisLabelVisible: true, title: '' });
    } catch (e) {}
  }

  function nearestTimeIso(seriesData, clickTime) {
    if (!seriesData || !seriesData.length || !clickTime) return null;
    let clickMs;
    if (typeof clickTime === 'number') clickMs = clickTime * 1000;
    else if (typeof clickTime === 'object' && clickTime.year) clickMs = Date.UTC(clickTime.year, (clickTime.month || 1) - 1, clickTime.day || 1);
    else return null;
    let best = null, bestDiff = Infinity;
    for (const p of seriesData) {
      const ms = Date.parse(p.time); const d = Math.abs(ms - clickMs);
      if (d < bestDiff) { bestDiff = d; best = p.time; }
    }
    return best;
  }

  // Экспорт в namespace
  AP.fetchJson = fetchJson;
  AP.hasLC = hasLC;
  AP.makeChart = makeChart;
  AP.setSeries = setSeries;
  AP.ensureContainer = ensureContainer;
  AP.ensureExplainPanel = ensureExplainPanel;
  AP.updateExplainPanelText = updateExplainPanelText;
  AP.addPanel = addPanel;
  AP.addListPanel = addListPanel;
  AP.createPriceLine = createPriceLine;
  AP.nearestTimeIso = nearestTimeIso;
})();