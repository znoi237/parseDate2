"""
Proxy-слой для обратной совместимости.
Оставляем импорт как был: from backtest import run_backtest
Реальная логика вынесена в пакет backtest_pkg.
"""
from backtest_pkg.runner import run_backtest  # noqa: F401