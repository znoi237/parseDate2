// Построение AI Signal (score/support/entries) и клик с объяснением сигнала.
(function () {
  var AP = window.AnalysisPanels || (window.AnalysisPanels = {});
  if (!AP.makeChart) return;

  function buildActiveScoreSegments(sp) {
    const thr = (sp.thresholds && typeof sp.thresholds.entry === 'number') ? sp.thresholds.entry : 0.6;
    const minSup = (sp.thresholds && typeof sp.thresholds.min_support === 'number') ? sp.thresholds.min_support : 0.3;
    const score = sp.score || [];
    const support = sp.support || [];
    const baseLine = score.map(p => ({ time: p.time, value: p.value }));
    const buySeg = [], sellSeg = [];
    const supMap = new Map(support.map(p => [p.time, p.value]));
    for (const p of score) {
      const sup = (supMap.get(p.time) ?? 0);
      const active = Math.abs(p.value) >= thr && sup >= minSup;
      if (active) (p.value >= 0 ? buySeg : sellSeg).push({ time: p.time, value: p.value });
    }
    return { baseLine, buySeg, sellSeg, thr, minSup };
  }

  function renderSignalPanel(wrap, sp, ctx, rootId = 'chart-root') {
    if (!sp || (!sp.score?.length && !sp.support?.length) || !AP.hasLC()) return;
    const section = AP.addPanel(wrap, 'AI Signal (score/support/entries)');
    const chart = AP.makeChart(section.div, 160);

    const segs = buildActiveScoreSegments(sp);
    const scoreBase = chart.addLineSeries({ color: 'rgba(0,123,255,0.4)', lineWidth: 2 });
    AP.setSeries(scoreBase, segs.baseLine);
    const scoreBuy = chart.addLineSeries({ color: '#2e7d32', lineWidth: 3 });
    const scoreSell = chart.addLineSeries({ color: '#c62828', lineWidth: 3 });
    AP.setSeries(scoreBuy, segs.buySeg); AP.setSeries(scoreSell, segs.sellSeg);

    const support = chart.addLineSeries({ color: '#2e7d32', lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dotted });
    AP.setSeries(support, sp.support || []);

    AP.createPriceLine(scoreBase, segs.thr);
    AP.createPriceLine(scoreBase, -segs.thr);

    if (sp.entry?.length) {
      const bars = sp.entry.map(x => ({ time: x.time, value: x.value ? 0.95 : 0, color: x.value ? 'rgba(255,193,7,0.7)' : 'rgba(0,0,0,0)' }));
      const entrySeries = chart.addHistogramSeries({ priceScaleId: 'left' });
      AP.setSeries(entrySeries, bars);
    }

    chart.subscribeClick(async function (param) {
      try {
        const tIso = AP.nearestTimeIso(sp.score || sp.support || [], param?.time);
        const symbol = (ctx && ctx.symbol) || AP.CTX.symbol;
        const timeframe = (ctx && ctx.timeframe) || AP.CTX.timeframe || '15m';
        if (!tIso || !symbol) return;
        const q = '/api/explain_signal?symbol=' + encodeURIComponent(symbol) +
          '&timeframe=' + encodeURIComponent(timeframe) +
          '&time=' + encodeURIComponent(tIso);
        const js = await AP.fetchJson(q);
        AP.updateExplainPanelText(js.ok && js.data ? js.data.text : (js.message || 'Не удалось получить объяснение'), rootId);
      } catch (e) {
        AP.updateExplainPanelText('Ошибка получения объяснения', rootId);
      }
    });
  }

  // Экспорт
  AP.buildActiveScoreSegments = buildActiveScoreSegments;
  AP.renderSignalPanel = renderSignalPanel;
})();