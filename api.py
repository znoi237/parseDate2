"""
Proxy-слой для обратной совместимости.
Оставляем импорт как был: from api import api_bp, make_services
Реальная логика вынесена в пакет api_pkg.
"""
from api_pkg import api_bp, make_services  # noqa: F401