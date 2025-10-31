from __future__ import annotations
from typing import Dict, Any, Optional
import pandas as pd

from config import Config
from precompute_cache import build_precompute
from .trader import simulate_trades


def run_backtest(
    db,
    models,
    symbol: str,
    timeframe: str,
    limit: int,
    signal_threshold: float,
    hold_margin: float,
    min_confirmed_higher: int,
    sl_atr_mult: float,
    tp_atr_mult: float,
    max_bars_in_trade: int,
    precompute: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    df = db.load_ohlcv(symbol, timeframe)
    if df is None or df.empty:
        return {"trades": [], "markers": [], "stats": {"count": 0, "winrate": 0.0}}

    df = df.tail(max(600, limit))
    precomp = precompute or build_precompute(db, models, symbol, timeframe, limit=max(limit, 600))
    if precomp is None:
        return {"trades": [], "markers": [], "stats": {"count": 0, "winrate": 0.0}}

    trades, markers, stats = simulate_trades(
        df=df,
        precomp=precomp,
        symbol=symbol,
        timeframe=timeframe,
        limit=limit,
        entry_threshold=float(signal_threshold),
        min_support=float(getattr(Config, "SIG_MIN_SUPPORT", 0.3)),
        hold_margin_min=float(hold_margin),
        min_confirmed_higher=int(min_confirmed_higher or 0),
        sl_atr_mult=float(sl_atr_mult),
        tp_atr_mult=float(tp_atr_mult),
        max_bars_in_trade=int(max_bars_in_trade),
    )
    return {"trades": trades, "markers": markers, "stats": stats}