"""
Proxy-слой для обратной совместимости.
Оставляем импорт как был: from model_manager import ModelManager
Реальная логика вынесена в пакет model_pkg.
"""
from model_pkg.manager import ModelManager  # noqa: F401