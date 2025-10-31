"""
Proxy-слой для обратной совместимости.
Оставляем импорт как был: from database import DatabaseManager
Реальная логика вынесена в пакет db_pkg.
"""
from db_pkg.manager import DatabaseManager  # noqa: F401