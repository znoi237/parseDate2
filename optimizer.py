"""
Оптимизация параметров пост-сигнального движка.
Совместимый API для api_pkg/jobs/training_runner.py:
  - GridDefaults: словарь сетки параметров
  - grid_size(grid): количество комбинаций
  - optimize_symbol_tf(db, models, symbol, timeframe, on_progress=None)

Перебор сетки выполняется параллельно в ThreadPoolExecutor
с числом воркеров из Config.OPTIMIZE_MAX_WORKERS (по умолчанию 4).
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional, Callable, Iterable, Tuple
import itertools
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from config import Config
except Exception:
    class Config:
        SIGNAL_THRESHOLD = 0.6
        OPTIMIZE_MAX_WORKERS = 4


# --------- Сетка параметров и сервисные функции ----------

GridDefaults: Dict[str, List[Any]] = {
    "signal_threshold": [0.55, 0.60, 0.65],
    "hold_margin": [0.03, 0.05, 0.07],
    "min_confirmed_higher": [0, 1, 2],
    "sl_atr_mult": [0.8, 1.0, 1.2],
    "tp_atr_mult": [1.6, 2.0, 2.4],
    "max_bars_in_trade": [100, 150, 200],
}

def grid_size(grid: Dict[str, List[Any]]) -> int:
    total = 1
    for arr in grid.values():
        total *= max(1, len(arr))
    return total

def _iter_grid(grid: Dict[str, List[Any]]) -> Iterable[Dict[str, Any]]:
    keys = list(grid.keys())
    for combo in itertools.product(*[grid[k] for k in keys]):
        yield {k: v for k, v in zip(keys, combo)}


# --------- Основная оптимизация (параллельно) ----------

def optimize_symbol_tf(
    db,
    models,
    symbol: str,
    timeframe: str,
    on_progress: Optional[Callable[[Dict[str, Any]], None]] = None,
    grid: Optional[Dict[str, List[Any]]] = None,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Перебирает сетку параметров параллельно и выбирает лучшую конфигурацию по метрике:
      - максимальный winrate (stats['winrate'])
      - при равенстве — большее число сделок (stats['count'])

    Итоги:
      - сохраняет best params в БД через db.save_model_params(symbol, timeframe, tuned)
      - возвращает {"ok": True, "best": {...}, "tuned": {...}}

    Прогресс:
      - on_progress получает dict {tf, i, total, phase, best}, где i — число выполненных комбинаций.
    """
    from backtest import run_backtest
    try:
        from precompute_cache import build_precompute
    except Exception:
        build_precompute = None

    grid = grid or GridDefaults
    combos = list(_iter_grid(grid))
    total = len(combos)
    if on_progress:
        on_progress({"tf": timeframe, "i": 0, "total": total, "phase": "start"})

    # Общие заготовки
    precomp = None
    if build_precompute:
        try:
            precomp = build_precompute(db, models, symbol, timeframe, limit=(limit or getattr(Config, "BACKTEST_OPTIM_LIMIT", 2000)))
        except Exception:
            precomp = None

    bt_limit = int(limit or getattr(Config, "BACKTEST_OPTIM_LIMIT", 2000))
    max_workers = max(1, int(getattr(Config, "OPTIMIZE_MAX_WORKERS", 4)))

    # Задача для пула
    def _eval(params: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        bt = run_backtest(
            db, models, symbol, timeframe,
            bt_limit,
            float(params.get("signal_threshold", getattr(Config, "SIGNAL_THRESHOLD", 0.6))),
            float(params.get("hold_margin", 0.05)),
            int(params.get("min_confirmed_higher", 0)),
            float(params.get("sl_atr_mult", 1.0)),
            float(params.get("tp_atr_mult", 2.0)),
            int(params.get("max_bars_in_trade", 200)),
            precomp,
        )
        stats = (bt or {}).get("stats", {}) if bt else {}
        return params, stats

    best = {"score": None, "params": None, "stats": None}

    def _score(stats: Dict[str, Any]) -> Optional[Tuple[float, int]]:
        wr = stats.get("winrate")
        if wr is None:
            return None
        return float(wr), int(stats.get("count") or 0)

    done = 0
    # Пул потоков: параллельно считаем бэктесты для разных комбинаций
    with ThreadPoolExecutor(max_workers=min(max_workers, total)) as pool:
        futures = {pool.submit(_eval, p): p for p in combos}
        for fut in as_completed(futures):
            params = futures[fut]
            try:
                p, stats = fut.result()
                sc = _score(stats)
                if sc is not None:
                    if (best["score"] is None) or (sc > best["score"]):
                        best = {"score": sc, "params": dict(p), "stats": dict(stats)}
            except Exception:
                # игнорируем отдельные ошибки комбинаций
                pass
            finally:
                done += 1
                if on_progress:
                    on_progress({"tf": timeframe, "i": done, "total": total, "phase": "step", "best": best})

    tuned = best["params"] or {
        "signal_threshold": float(getattr(Config, "SIGNAL_THRESHOLD", 0.6)),
        "hold_margin": 0.05,
        "min_confirmed_higher": 0,
        "sl_atr_mult": 1.0,
        "tp_atr_mult": 2.0,
        "max_bars_in_trade": 200,
    }

    try:
        db.save_model_params(symbol, timeframe, tuned)
    except Exception:
        pass

    if on_progress:
        on_progress({"tf": timeframe, "i": total, "total": total, "phase": "final", "best": best})

    return {"ok": True, "best": best, "tuned": tuned}
