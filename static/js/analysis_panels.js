// Loader-обёртка для разнесённых модулей панелей анализа.
// Оставляет прежний импорт одного файла: <script src="analysis_panels.js"></script>
// Динамически подгружает модули и экспортирует в window:
//   - window.setAnalysisContext(symbol, timeframe)
//   - window.renderIndicatorPanelsFromAnalysis(analysisData, ctxOrRootId, maybeRootId)
(function () {
  if (window.renderIndicatorPanelsFromAnalysis && window.setAnalysisContext) {
    // Уже инициализировано
    return;
  }

  function loadScript(src) {
    return new Promise(function (resolve, reject) {
      var s = document.createElement('script');
      s.src = src;
      s.async = false;
      s.onload = function () { resolve(src); };
      s.onerror = function (e) { reject(new Error('Failed to load ' + src)); };
      document.head.appendChild(s);
    });
  }

  function basePath() {
    try {
      var s = document.currentScript;
      if (s && s.src) {
        var idx = s.src.lastIndexOf('/');
        return idx >= 0 ? s.src.substring(0, idx + 1) : '';
      }
    } catch (e) {}
    return '';
  }

  var base = basePath();
  var files = [
    'analysis_panels_core.js',
    'analysis_panels_renderers.js',
    'analysis_panels_signal.js',
    'analysis_panels_main.js'
  ];

  // Грузим по порядку
  files.reduce(function (p, f) {
    return p.then(function () { return loadScript(base + f); });
  }, Promise.resolve()).catch(function (e) {
    console.error('[analysis_panels] loader error:', e);
  });
})();