"""
Оптимизация параметров пост-сигнального движка (без переобучения модели).
Совместимый API для api_pkg/jobs/training_runner.py:
  - GridDefaults: словарь сетки параметров
  - grid_size(grid): количество комбинаций
  - optimize_symbol_tf(db, models, symbol, timeframe, on_progress=None)

Есть утилита optimize_and_retrain(...) для сценариев с немедленным переобучением.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional, Callable, Iterable, Tuple
import itertools

try:
    from config import Config
except Exception:
    class Config:
        SIGNAL_THRESHOLD = 0.6


GridDefaults: Dict[str, List[Any]] = {
    "signal_threshold": [0.55, 0.6, 0.65],
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


def optimize_symbol_tf(
    db,
    models,
    symbol: str,
    timeframe: str,
    on_progress: Optional[Callable[[Dict[str, Any]], None]] = None,
    grid: Optional[Dict[str, List[Any]]] = None,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    from backtest import run_backtest
    try:
        from precompute_cache import build_precompute
    except Exception:
        build_precompute = None

    grid = grid or GridDefaults
    total = grid_size(grid)
    if on_progress:
        on_progress({"tf": timeframe, "i": 0, "total": total, "phase": "start"})

    precomp = None
    if build_precompute:
        try:
            precomp = build_precompute(db, models, symbol, timeframe, limit=(limit or 2000))
        except Exception:
            precomp = None

    bt_limit = int(limit or getattr(Config, "BACKTEST_OPTIM_LIMIT", 2000))

    best = {"score": None, "params": None, "stats": None}
    for i, params in enumerate(_iter_grid(grid), start=1):
        try:
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
            winrate = stats.get("winrate"); count = stats.get("count")
            if winrate is not None:
                cur_score: Tuple[float, int] = (float(winrate), int(count or 0))
                prev: Optional[Tuple[float, int]] = best["score"]
                if (prev is None) or (cur_score > prev):
                    best = {"score": cur_score, "params": dict(params), "stats": dict(stats)}
        except Exception:
            pass
        finally:
            if on_progress:
                on_progress({"tf": timeframe, "i": i, "total": total, "phase": "step", "best": best})

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


def optimize_and_retrain(
    db,
    symbol: str,
    timeframes: List[str],
    years: int,
    new_params: Optional[Dict[str, Any]] = None,
    job_id: Optional[int] = None,
) -> Dict[str, Any]:
    if new_params:
        try:
            db.save_training_params(symbol, new_params)
        except Exception:
            pass

    from model_manager import ModelManager
    mm = ModelManager(db)
    report = mm.train_symbol(symbol, timeframes, years, job_id=job_id, mode="auto")
    return {"ok": True, "report": report}
