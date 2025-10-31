"""
Proxy-слой для обратной совместимости.
Оставляем импорт как был: from bots_manager import BotManager
Реальная логика вынесена в пакет bots_pkg.
"""
from bots_pkg.manager import BotManager  # noqa: F401