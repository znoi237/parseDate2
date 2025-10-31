// Рендер-утилиты для отдельных индикаторных панелей.
(function () {
  var AP = window.AnalysisPanels || (window.AnalysisPanels = {});
  if (!AP.makeChart) return;

  function addRsiPanel(wrap, panels) {
    if (!panels?.rsi || !AP.hasLC()) return;
    const { div } = AP.addPanel(wrap, 'RSI');
    const chart = AP.makeChart(div, 120);
    const line = chart.addLineSeries({ color: '#0d6efd', lineWidth: 2 });
    AP.setSeries(line, panels.rsi);
    try {
      line.createPriceLine({ price: 30, color: '#adb5bd', lineStyle: LightweightCharts.LineStyle.Dashed, axisLabelVisible: true });
      line.createPriceLine({ price: 70, color: '#adb5bd', lineStyle: LightweightCharts.LineStyle.Dashed, axisLabelVisible: true });
    } catch (e) {}
    const markers = [];
    for (const p of panels.rsi) {
      if (p.value >= 70) markers.push({ time: p.time, position: 'aboveBar', color: '#dc3545', shape: 'arrowDown', text: 'OB' });
      else if (p.value <= 30) markers.push({ time: p.time, position: 'belowBar', color: '#198754', shape: 'arrowUp', text: 'OS' });
    }
    try { line.setMarkers(markers); } catch (e) {}
  }

  function addMacdPanel(wrap, panels) {
    if (!panels?.macd || !AP.hasLC()) return;
    const { div } = AP.addPanel(wrap, 'MACD');
    const chart = AP.makeChart(div, 140);
    const macd = chart.addLineSeries({ color: '#198754', lineWidth: 2 });
    const sig = chart.addLineSeries({ color: '#dc3545', lineWidth: 2 });
    AP.setSeries(macd, panels.macd.macd);
    AP.setSeries(sig, panels.macd.signal);
    const hist = chart.addHistogramSeries({});
    const histColored = (panels.macd.hist || []).map(x => ({
      time: x.time, value: x.value, color: x.value >= 0 ? 'rgba(25,135,84,0.5)' : 'rgba(220,53,69,0.5)'
    }));
    AP.setSeries(hist, histColored);
  }

  function addStochPanel(wrap, panels) {
    if (!panels?.stoch || !AP.hasLC()) return;
    const { div } = AP.addPanel(wrap, 'Stochastic');
    const chart = AP.makeChart(div, 120);
    const k = chart.addLineSeries({ color: '#6f42c1', lineWidth: 2 });
    const d = chart.addLineSeries({ color: '#ffc107', lineWidth: 2 });
    AP.setSeries(k, panels.stoch.k);
    AP.setSeries(d, panels.stoch.d);
    try {
      k.createPriceLine({ price: 20, color: '#adb5bd', lineStyle: LightweightCharts.LineStyle.Dashed, axisLabelVisible: true });
      k.createPriceLine({ price: 80, color: '#adb5bd', lineStyle: LightweightCharts.LineStyle.Dashed, axisLabelVisible: true });
    } catch (e) {}
    const km = panels.stoch.k, dm = panels.stoch.d; const markers = [];
    for (let i = 1; i < km.length; i++) {
      const prevUp = km[i - 1].value > dm[i - 1].value;
      const nowUp = km[i].value > dm[i].value;
      if (!prevUp && nowUp && km[i].value < 20) markers.push({ time: km[i].time, position: 'belowBar', color: '#198754', shape: 'arrowUp', text: 'K↑D' });
      if (prevUp && !nowUp && km[i].value > 80) markers.push({ time: km[i].time, position: 'aboveBar', color: '#dc3545', shape: 'arrowDown', text: 'K↓D' });
    }
    try { k.setMarkers(markers); } catch (e) {}
  }

  function addBBandsPanel(wrap, panels, candles) {
    if (!panels?.bbands || !AP.hasLC()) return;
    const { div } = AP.addPanel(wrap, 'Bollinger Bands');
    const chart = AP.makeChart(div, 130);
    const up = chart.addLineSeries({ color: '#6c757d', lineWidth: 1 });
    const mid = chart.addLineSeries({ color: '#495057', lineWidth: 1 });
    const dn = chart.addLineSeries({ color: '#6c757d', lineWidth: 1 });
    AP.setSeries(up, panels.bbands.up); AP.setSeries(mid, panels.bbands.mid); AP.setSeries(dn, panels.bbands.dn);
    const closeMap = new Map((candles || []).map(c => [c.time, c.close])); const markers = [];
    for (let i = 0; i < panels.bbands.up.length; i++) {
      const t = panels.bbands.up[i].time; const c = closeMap.get(t); if (c === undefined) continue;
      const u = panels.bbands.up[i].value; const d = panels.bbands.dn[i]?.value ?? NaN;
      if (c >= u) markers.push({ time: t, position: 'aboveBar', color: '#fd7e14', shape: 'arrowDown', text: 'touch↑' });
      else if (c <= d) markers.push({ time: t, position: 'belowBar', color: '#0dcaf0', shape: 'arrowUp', text: 'touch↓' });
    }
    try { mid.setMarkers(markers); } catch (e) {}
  }

  function addATRPanel(wrap, panels) {
    if (!panels?.atr || !AP.hasLC()) return;
    const { div } = AP.addPanel(wrap, 'ATR');
    const chart = AP.makeChart(div, 120);
    const l = chart.addLineSeries({ color: '#fd7e14', lineWidth: 2 });
    AP.setSeries(l, panels.atr);
  }

  function addEMAPanel(wrap, panels) {
    if (!panels?.ema || !AP.hasLC()) return;
    const { div } = AP.addPanel(wrap, 'EMA');
    const chart = AP.makeChart(div, 130);
    const colors = ['#0d6efd', '#198754', '#fd7e14', '#6f42c1', '#0dcaf0', '#ffc107', '#795548', '#e83e8c'];
    let i = 0;
    for (const p of Object.keys(panels.ema)) {
      const ls = chart.addLineSeries({ color: colors[i % colors.length], lineWidth: 1 });
      AP.setSeries(ls, panels.ema[p]); i++;
    }
  }

  function addSMAPanel(wrap, panels) {
    if (!panels?.sma || !AP.hasLC()) return;
    const { div } = AP.addPanel(wrap, 'SMA');
    const chart = AP.makeChart(div, 130);
    const colors = ['#6c757d', '#a3cfbb', '#ffcd39', '#d0b3e2', '#80cbc4', '#ffe69c'];
    let i = 0;
    for (const p of Object.keys(panels.sma)) {
      const ls = chart.addLineSeries({ color: colors[i % colors.length], lineWidth: 1 });
      AP.setSeries(ls, panels.sma[p]); i++;
    }
  }

  function addSimpleLine(wrap, data, title, color = '#6c757d') {
    if (!data || !data.length || !AP.hasLC()) return;
    const { div } = AP.addPanel(wrap, title);
    const chart = AP.makeChart(div, 120);
    const l = chart.addLineSeries({ color, lineWidth: 2 });
    AP.setSeries(l, data);
  }

  function addROCPanel(wrap, panels) {
    if (!panels?.roc || !AP.hasLC()) return;
    const { div } = AP.addPanel(wrap, 'ROC');
    const chart = AP.makeChart(div, 140);
    const colors = ['#0dcaf0', '#e83e8c', '#fd7e14', '#198754', '#0d6efd'];
    let i = 0;
    for (const p of Object.keys(panels.roc)) {
      const ls = chart.addLineSeries({ color: colors[i % colors.length], lineWidth: 1 });
      AP.setSeries(ls, panels.roc[p]); i++;
    }
  }

  function addNewsList(wrap, news) {
    if (!Array.isArray(news) || news.length === 0) return;
    const { ul } = AP.addListPanel(wrap, 'Новости, учтённые в сигнале');
    ul.innerHTML = '';
    news.forEach(n => {
      const li = document.createElement('li');
      li.className = 'list-group-item';
      const when = n.time ? new Date(n.time).toLocaleString() : '';
      const sent = (n.sentiment !== null && n.sentiment !== undefined) ? ' | Sent: ' + Number(n.sentiment).toFixed(2) : '';
      const prov = n.provider ? ' [' + n.provider + ']' : '';
      const syms = n.symbols ? ' (' + n.symbols + ')' : '';
      const link = n.url ? '<a href="' + n.url + '" target="_blank" rel="noopener noreferrer">' + (n.title || '(link)') + '</a>' : (n.title || '(no title)');
      li.innerHTML = '<div class="d-flex flex-column">' +
        '<div><strong>' + when + '</strong>' + prov + sent + syms + '</div>' +
        '<div>' + link + '</div>' +
        '</div>';
      ul.appendChild(li);
    });
  }

  // Экспорт
  AP.addRsiPanel = addRsiPanel;
  AP.addMacdPanel = addMacdPanel;
  AP.addStochPanel = addStochPanel;
  AP.addBBandsPanel = addBBandsPanel;
  AP.addATRPanel = addATRPanel;
  AP.addEMAPanel = addEMAPanel;
  AP.addSMAPanel = addSMAPanel;
  AP.addSimpleLine = addSimpleLine;
  AP.addROCPanel = addROCPanel;
  AP.addNewsList = addNewsList;
})();