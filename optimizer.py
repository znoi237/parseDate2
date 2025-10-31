"""
Proxy-слой для обратной совместимости.
Оставляем импорт как был: from optimizer import optimize_symbol_tf, GridDefaults, grid_size
Реальная логика вынесена в пакет optimizer_pkg.
"""
from optimizer_pkg.runner import optimize_symbol_tf  # noqa: F401
from optimizer_pkg.grid import GridDefaults, grid_size  # noqa: F401