from __future__ import annotations
import pandas as pd
from typing import Dict, List
from .indicators import sma, ema, rsi, macd, bollinger

def compute_indicators_block(df: pd.DataFrame) -> Dict[str, List]:
    c = df["close"]
    s20 = sma(c, 20)
    e50 = ema(c, 50)
    ma, bb_up, bb_lo = bollinger(c, 20, 2.0)
    r = rsi(c, 14)
    macd_line, signal_line, hist = macd(c)
    return {
        "sma20": s20.tolist(),
        "ema50": e50.tolist(),
        "bb_mid": ma.tolist(),
        "bb_upper": bb_up.tolist(),
        "bb_lower": bb_lo.tolist(),
        "rsi14": r.tolist(),
        "macd": {
            "line": macd_line.tolist(),
            "signal": signal_line.tolist(),
            "hist": hist.tolist()
        }
    }