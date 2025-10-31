// Сборка всех панелей и публичный API рендера из данных /api/analysis.
(function () {
  var AP = window.AnalysisPanels || (window.AnalysisPanels = {});
  if (!AP.ensureContainer) return;

  async function renderIndicatorPanelsFromAnalysis(analysisData, ctxOrRootId, maybeRootId) {
    let ctx = null; let rootId = 'chart-root';
    if (typeof ctxOrRootId === 'string') rootId = ctxOrRootId;
    else if (typeof ctxOrRootId === 'object' && ctxOrRootId) { ctx = ctxOrRootId; rootId = typeof maybeRootId === 'string' ? maybeRootId : 'chart-root'; }
    if (ctx && ctx.symbol) AP.setAnalysisContext(ctx.symbol, ctx.timeframe || '15m');

    const wrap = AP.ensureContainer(rootId);
    AP.ensureExplainPanel(rootId);

    const panels = analysisData?.indicator_panels || {};
    const sigPanel = analysisData?.signal_panel || {};
    const news = analysisData?.news_used || [];
    const candles = analysisData?.candles || [];

    AP.renderSignalPanel(wrap, sigPanel, ctx, rootId);
    AP.addRsiPanel(wrap, panels);
    AP.addMacdPanel(wrap, panels);
    AP.addStochPanel(wrap, panels);
    AP.addBBandsPanel(wrap, panels, candles);
    AP.addATRPanel(wrap, panels);
    AP.addEMAPanel(wrap, panels);
    AP.addSMAPanel(wrap, panels);
    if (panels.cci) AP.addSimpleLine(wrap, panels.cci, 'CCI', '#80cbc4');
    if (panels.willr) AP.addSimpleLine(wrap, panels.willr, 'Williams %R', '#e83e8c');
    if (panels.mfi) AP.addSimpleLine(wrap, panels.mfi, 'MFI', '#0dcaf0');
    if (panels.obv) AP.addSimpleLine(wrap, panels.obv, 'OBV', '#795548');
    AP.addROCPanel(wrap, panels);
    AP.addNewsList(wrap, news);
  }

  // Публичные функции (совместимость)
  window.renderIndicatorPanelsFromAnalysis = renderIndicatorPanelsFromAnalysis;
  window.setAnalysisContext = AP.setAnalysisContext;
})();