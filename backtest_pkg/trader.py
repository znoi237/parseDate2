from __future__ import annotations
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
import numpy as np
import pandas as pd

from config import Config
from signal_engine import aggregate_signal, decide_entry
from .utils import atr, build_probs_at_i, consistent_support_count


@dataclass
class Trade:
    entry_time: pd.Timestamp
    entry_price: float
    side: str  # BUY/SELL
    sl: float
    tp: float
    max_bars: int
    bars_held: int = 0
    exit_time: Optional[pd.Timestamp] = None
    exit_price: Optional[float] = None
    status: str = "open"  # open/closed
    pnl_percent: float = 0.0

    def close(self, t: pd.Timestamp, price: float):
        self.exit_time = t
        self.exit_price = price
        self.status = "closed"
        if self.side == "BUY":
            self.pnl_percent = (self.exit_price / self.entry_price - 1.0) * 100.0
        else:
            self.pnl_percent = (self.entry_price / self.exit_price - 1.0) * 100.0


def simulate_trades(
    df: pd.DataFrame,
    precomp: Dict[str, Any],
    symbol: str,
    timeframe: str,
    limit: int,
    entry_threshold: float,
    min_support: float,
    hold_margin_min: float,
    min_confirmed_higher: int,
    sl_atr_mult: float,
    tp_atr_mult: float,
    max_bars_in_trade: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, float]]:
    X_idx: pd.DatetimeIndex = precomp["X_idx"]
    use_len = min(len(X_idx), limit)
    start = len(X_idx) - use_len
    atr_series = atr(df, n=getattr(Config, "BT_ATR_PERIOD", 14))

    open_trade: Optional[Trade] = None
    trades: List[Dict[str, Any]] = []
    markers: List[Dict[str, Any]] = []

    weights_cfg = getattr(Config, "HIERARCHY_WEIGHTS", {})
    exit_on_flip = bool(getattr(Config, "EXIT_ON_FLIP", False))

    for i in range(start, len(X_idx)):
        ts, probs_by_tf = build_probs_at_i(precomp, timeframe, i)
        base_pb = probs_by_tf[timeframe]
        agg = aggregate_signal(probs_by_tf, timeframe, weights_cfg, lookback_scores=None)

        ok, dir_sig, _ = decide_entry(
            agg, base_pb,
            entry_threshold=entry_threshold,
            min_support=min_support,
            hold_margin_min=hold_margin_min,
        )

        if ok and min_confirmed_higher > 0:
            consistent = consistent_support_count(int(np.sign(agg["score"])), probs_by_tf, timeframe)
            if consistent < int(min_confirmed_higher):
                ok = False

        if ts not in df.index:
            continue
        row = df.loc[ts]
        close = float(row["close"])
        high = float(row["high"])
        low = float(row["low"])
        atr_now = float(atr_series.loc[ts]) if ts in atr_series.index else float(atr_series.iloc[-1])

        if open_trade:
            open_trade.bars_held += 1
            if open_trade.side == "BUY":
                hit_sl = low <= open_trade.sl
                hit_tp = high >= open_trade.tp
            else:
                hit_sl = high >= open_trade.sl
                hit_tp = low <= open_trade.tp

            if hit_sl:
                open_trade.close(ts, open_trade.sl)
            elif hit_tp:
                open_trade.close(ts, open_trade.tp)
            elif exit_on_flip and ok and dir_sig != 0 and ((open_trade.side == "BUY" and dir_sig < 0) or (open_trade.side == "SELL" and dir_sig > 0)):
                open_trade.close(ts, close)
            elif open_trade.bars_held >= max_bars_in_trade:
                open_trade.close(ts, close)

            if open_trade.status == "closed":
                trades.append({
                    "entry_time": open_trade.entry_time.isoformat(),
                    "exit_time": open_trade.exit_time.isoformat() if open_trade.exit_time else None,
                    "entry_price": open_trade.entry_price,
                    "exit_price": open_trade.exit_price,
                    "side": open_trade.side,
                    "pnl_percent": open_trade.pnl_percent,
                    "status": open_trade.status,
                    "symbol": symbol,
                    "timeframe": timeframe,
                })
                markers.append({
                    "time": open_trade.entry_time.isoformat(),
                    "type": "entry_buy" if open_trade.side == "BUY" else "entry_sell",
                    "note": f"{open_trade.side} {open_trade.entry_price:.4f}",
                    "color": "#66BB6A" if open_trade.side == "BUY" else "#EF5350"
                })
                if open_trade.exit_time:
                    markers.append({
                        "time": open_trade.exit_time.isoformat(),
                        "type": "exit",
                        "note": f"EXIT {open_trade.exit_price:.4f} PnL {open_trade.pnl_percent:.2f}%",
                        "color": "#78909C"
                    })
                open_trade = None

        if open_trade is None and ok and dir_sig != 0:
            side = "BUY" if dir_sig > 0 else "SELL"
            if side == "BUY":
                sl = close - sl_atr_mult * atr_now
                tp = close + tp_atr_mult * atr_now
            else:
                sl = close + sl_atr_mult * atr_now
                tp = close - tp_atr_mult * atr_now
            open_trade = Trade(
                entry_time=ts,
                entry_price=close,
                side=side,
                sl=sl,
                tp=tp,
                max_bars=int(max_bars_in_trade),
                bars_held=0
            )

    if open_trade and open_trade.status == "open":
        last_ts = df.index[-1]
        last_close = float(df["close"].iloc[-1])
        open_trade.close(last_ts, last_close)
        trades.append({
            "entry_time": open_trade.entry_time.isoformat(),
            "exit_time": open_trade.exit_time.isoformat() if open_trade.exit_time else None,
            "entry_price": open_trade.entry_price,
            "exit_price": open_trade.exit_price,
            "side": open_trade.side,
            "pnl_percent": open_trade.pnl_percent,
            "status": open_trade.status,
            "symbol": symbol,
            "timeframe": timeframe,
        })
        markers.append({
            "time": open_trade.entry_time.isoformat(),
            "type": "entry_buy" if open_trade.side == "BUY" else "entry_sell",
            "note": f"{open_trade.side} {open_trade.entry_price:.4f}",
            "color": "#66BB6A" if open_trade.side == "BUY" else "#EF5350"
        })
        if open_trade.exit_time:
            markers.append({
                "time": open_trade.exit_time.isoformat(),
                "type": "exit",
                "note": f"EXIT {open_trade.exit_price:.4f} PnL {open_trade.pnl_percent:.2f}%",
                "color": "#78909C"
            })

    closed = [t for t in trades if t.get("status") == "closed"]
    count = len(closed)
    win = len([t for t in closed if t.get("pnl_percent", 0.0) > 0.0])
    winrate = float(win) / count * 100.0 if count > 0 else 0.0

    stats = {"count": int(count), "winrate": float(winrate)}
    return trades, markers, stats