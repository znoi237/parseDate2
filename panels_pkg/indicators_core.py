from __future__ import annotations
from typing import Dict, Any, List
import numpy as np
import pandas as pd

def _src(df: pd.DataFrame, name: str) -> pd.Series:
    name = (name or "close").lower()
    if name == "hlc3":
        return (df["high"] + df["low"] + df["close"]) / 3.0
    if name == "ohlc4":
        return (df["open"] + df["high"] + df["low"] + df["close"]) / 4.0
    return df.get(name, df["close"]).astype(float)

def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=max(1, int(n)), adjust=False).mean()

def _sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(max(1, int(n)), min_periods=1).mean()

def _rsi(src: pd.Series, n: int) -> pd.Series:
    delta = src.diff()
    gain = (delta.clip(lower=0)).rolling(n, min_periods=1).mean()
    loss = (-delta.clip(upper=0)).rolling(n, min_periods=1).mean()
    rs = gain / (loss.replace(0, np.nan))
    rsi = 100.0 - (100.0 / (1.0 + rs.replace(0, np.nan)))
    return rsi.fillna(50.0).clip(0, 100)

def _stoch(df: pd.DataFrame, k: int, d: int, smooth: int) -> pd.DataFrame:
    ll = df["low"].rolling(k, min_periods=1).min()
    hh = df["high"].rolling(k, min_periods=1).max()
    k_raw = (df["close"] - ll) / (hh - ll + 1e-12) * 100.0
    k_s = _sma(k_raw, max(1, smooth))
    d_s = _sma(k_s, max(1, d))
    return pd.DataFrame({"k": k_s, "d": d_s})

def _macd(src: pd.Series, fast: int, slow: int, signal: int) -> pd.DataFrame:
    ema_f = _ema(src, fast)
    ema_s = _ema(src, slow)
    macd = ema_f - ema_s
    sig = _ema(macd, signal)
    hist = macd - sig
    return pd.DataFrame({"macd": macd, "signal": sig, "hist": hist})

def _bbands(src: pd.Series, n: int, k: float) -> pd.DataFrame:
    m = _sma(src, n)
    std = src.rolling(n, min_periods=1).std(ddof=0)
    up = m + k * std
    dn = m - k * std
    return pd.DataFrame({"mid": m, "up": up, "dn": dn})

def _atr(df: pd.DataFrame, n: int) -> pd.Series:
    h, l, c = df["high"], df["low"], df["close"]
    prev = c.shift(1)
    tr = pd.concat([(h - l), (h - prev).abs(), (l - prev).abs()], axis=1).max(axis=1)
    return tr.rolling(n, min_periods=1).mean()

def _cci(df: pd.DataFrame, n: int) -> pd.Series:
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    sma = _sma(tp, n)
    md = (tp - sma).abs().rolling(n, min_periods=1).mean()
    cci = (tp - sma) / (0.015 * (md.replace(0, np.nan)))
    return cci.fillna(0.0)

def _roc(src: pd.Series, n: int) -> pd.Series:
    return src.pct_change(max(1, n)).replace([np.inf, -np.inf], np.nan).fillna(0.0)

def _willr(df: pd.DataFrame, n: int) -> pd.Series:
    hh = df["high"].rolling(n, min_periods=1).max()
    ll = df["low"].rolling(n, min_periods=1).min()
    return (-100.0 * (hh - df["close"]) / (hh - ll + 1e-12)).fillna(0.0)

def _mfi(df: pd.DataFrame, n: int) -> pd.Series:
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    mf = tp * df["volume"].astype(float)
    pos = mf.where(tp > tp.shift(1), 0.0).rolling(n, min_periods=1).sum()
    neg = mf.where(tp < tp.shift(1), 0.0).rolling(n, min_periods=1).sum()
    ratio = pos / (neg.replace(0, np.nan))
    mfi = 100.0 - (100.0 / (1.0 + ratio.replace(0, np.nan)))
    return mfi.fillna(50.0).clip(0, 100)

def _obv(df: pd.DataFrame) -> pd.Series:
    chg = np.sign(df["close"].diff().fillna(0.0))
    vol = df["volume"].astype(float)
    return (chg * vol).cumsum()

def _series(index: pd.DatetimeIndex, values: pd.Series | np.ndarray) -> List[Dict[str, float]]:
    vals = pd.Series(values, index=index)
    out = []
    for ts, v in vals.items():
        try:
            fv = float(v)
            if not np.isfinite(fv):
                continue
        except Exception:
            continue
        out.append({"time": ts.isoformat(), "value": fv})
    return out