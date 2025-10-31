"""
Proxy-слой для обратной совместимости.
Оставляем импорт как был: from analysis_utils import compute_indicators_block, detect_candle_patterns, detect_opportunities, sma, ema, rsi, macd, bollinger
Реальная логика вынесена в пакет analysis_pkg.
"""
from analysis_pkg.blocks import compute_indicators_block  # noqa: F401
from analysis_pkg.patterns import detect_candle_patterns, detect_opportunities  # noqa: F401
from analysis_pkg.indicators import sma, ema, rsi, macd, bollinger  # noqa: F401