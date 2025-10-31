"""
Proxy-слой для обратной совместимости.
Оставляем импорт как был: from data_manager import CCXTDataManager
Реальная логика вынесена в пакет data_pkg.
"""
from data_pkg.ccxt_manager import CCXTDataManager  # noqa: F401