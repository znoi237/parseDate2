from __future__ import annotations
import pandas as pd
from typing import Dict, List

def detect_candle_patterns(df: pd.DataFrame) -> List[Dict]:
    out: List[Dict] = []
    o = df["open"].values
    h = df["high"].values
    l = df["low"].values
    c = df["close"].values
    idx = df.index
    for i in range(1, len(df)):
        body = abs(c[i] - o[i])
        rng = max(h[i] - l[i], 1e-12)
        if body / rng <= 0.1:
            out.append({"time": idx[i].isoformat(), "type": "doji", "note": "Doji (неопределенность)"})
        prev_body = abs(c[i-1] - o[i-1])
        cur_body = abs(c[i] - o[i])
        if (c[i] > o[i]) and (c[i-1] < o[i-1]) and (cur_body > prev_body) and (o[i] <= c[i-1]) and (c[i] >= o[i-1]):
            out.append({"time": idx[i].isoformat(), "type": "bullish_engulfing", "note": "Бычье поглощение"})
        if (c[i] < o[i]) and (c[i-1] > o[i-1]) and (cur_body > prev_body) and (o[i] >= c[i-1]) and (c[i] <= o[i-1]):
            out.append({"time": idx[i].isoformat(), "type": "bearish_engulfing", "note": "Медвежье поглощение"})
    return out

def detect_opportunities(df: pd.DataFrame) -> List[Dict]:
    from .indicators import rsi as _rsi, macd as _macd, bollinger as _boll
    out: List[Dict] = []
    close = df["close"]
    r = _rsi(close, 14)
    macd_line, signal_line, hist = _macd(close)
    ma, bb_up, bb_lo = _boll(close)
    idx = df.index
    for i in range(1, len(df)):
        t = idx[i].isoformat()
        if r.iloc[i] <= 30:
            out.append({"time": t, "type": "rsi_oversold", "note": f"RSI {r.iloc[i]:.1f} — потенциальный отскок"})
        if r.iloc[i] >= 70:
            out.append({"time": t, "type": "rsi_overbought", "note": f"RSI {r.iloc[i]:.1f} — риск отката"})
        if (macd_line.iloc[i-1] <= signal_line.iloc[i-1]) and (macd_line.iloc[i] > signal_line.iloc[i]):
            out.append({"time": t, "type": "macd_bull_cross", "note": "MACD пересечение вверх"})
        if (macd_line.iloc[i-1] >= signal_line.iloc[i-1]) and (macd_line.iloc[i] < signal_line.iloc[i]):
            out.append({"time": t, "type": "macd_bear_cross", "note": "MACD пересечение вниз"})
        if close.iloc[i] <= bb_lo.iloc[i]:
            out.append({"time": t, "type": "bb_touch_lower", "note": "Касание нижней полосы Боллинджера"})
        if close.iloc[i] >= bb_up.iloc[i]:
            out.append({"time": t, "type": "bb_touch_upper", "note": "Касание верхней полосы Боллинджера"})
    return out