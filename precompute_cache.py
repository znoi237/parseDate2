"""
Proxy-слой для обратной совместимости.
Оставляем импорт как был: from precompute_cache import build_precompute
Реальная логика вынесена в пакет precompute_pkg.
"""
from precompute_pkg.core import build_precompute  # noqa: F401