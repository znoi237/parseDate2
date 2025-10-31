"""
Proxy-слой для обратной совместимости.
Оставляем импорт как был: from indicators_panels import build_indicator_panels, build_signal_panel
и внутренние функции (_rsi, _stoch, _macd, _ema) для explain.
"""
from panels_pkg.panels import build_indicator_panels  # noqa: F401
from panels_pkg.signal_panel import build_signal_panel  # noqa: F401
# Реэкспорт внутренних индикаторных функций для explain:
from panels_pkg.indicators_core import _rsi, _stoch, _macd, _ema  # noqa: F401