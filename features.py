# === FILE: features.py ===
import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple
from config import Config
from indicator_settings import sanitize_indicator_settings
from news_features import aggregate_news_features


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


def _macd(src: pd.Series, fast: int, slow: int, signal: int) -> Tuple[pd.Series, pd.Series, pd.Series]:
    ema_f = _ema(src, fast)
    ema_s = _ema(src, slow)
    macd = ema_f - ema_s
    sig = _ema(macd, signal)
    hist = macd - sig
    return macd, sig, hist


def _stoch(df: pd.DataFrame, k: int, d: int, smooth: int) -> Tuple[pd.Series, pd.Series]:
    ll = df["low"].rolling(k, min_periods=1).min()
    hh = df["high"].rolling(k, min_periods=1).max()
    k_raw = (df["close"] - ll) / (hh - ll + 1e-12) * 100.0
    k_s = _sma(k_raw, max(1, smooth))
    d_s = _sma(k_s, max(1, d))
    return k_s, d_s


def build_features(df: pd.DataFrame, settings: Dict[str, Any], db=None, timeframe: str = "1h", include_news: bool = True) -> pd.DataFrame:
    """
    Формирует обучающую матрицу X из OHLCV + индикаторы + (опционально) новостные признаки.
    """
    s = sanitize_indicator_settings(settings)
    out = pd.DataFrame(index=df.index)
    src = _src(df, s["rsi"]["source"])

    # --- Технические признаки ---
    if s["rsi"]["enabled"]:
        out["rsi"] = _rsi(src, int(s["rsi"]["period"]))
    if s["stoch"]["enabled"]:
        k, d = _stoch(df, int(s["stoch"]["k"]), int(s["stoch"]["d"]), int(s["stoch"]["smooth"]))
        out["stoch_k"] = k
        out["stoch_d"] = d
    if s["macd"]["enabled"]:
        macd, sig, hist = _macd(src, int(s["macd"]["fast"]), int(s["macd"]["slow"]), int(s["macd"]["signal"]))
        out["macd"], out["macd_signal"], out["macd_hist"] = macd, sig, hist
    if s["ema"]["enabled"]:
        for p in s["ema"]["periods"]:
            out[f"ema_{p}"] = _ema(df["close"], int(p))
    if s["sma"]["enabled"]:
        for p in s["sma"]["periods"]:
            out[f"sma_{p}"] = _sma(df["close"], int(p))

    # --- Фундаментальные признаки (новости) ---
    if include_news and db is not None:
        try:
            news_feats = aggregate_news_features(db, df.index, timeframe)
            if news_feats is not None and not news_feats.empty:
                # нормализуем новостные признаки в [0,1]
                nf = news_feats.copy()
                for c in nf.columns:
                    arr = nf[c].values.astype(float)
                    mn, mx = np.nanmin(arr), np.nanmax(arr)
                    if np.isfinite(mn) and np.isfinite(mx) and mx > mn:
                        arr = (arr - mn) / (mx - mn)
                    else:
                        arr = np.zeros_like(arr)
                    nf[c] = arr
                out = pd.concat([out, nf], axis=1)
        except Exception as e:
            print(f"[WARN] Failed to add news features: {e}")

    # --- Очистка ---
    out = out.replace([np.inf, -np.inf], np.nan).fillna(method="ffill").fillna(method="bfill").fillna(0.0)

    return out.astype(float)


def make_labels(df: pd.DataFrame, horizon: int = 1, up_threshold: float = 0.002, down_threshold: float = -0.002) -> pd.Series:
    """
    Классы:
      +1 — рост выше порога
       0 — флет
      -1 — падение ниже порога
    """
    fwd = df["close"].shift(-horizon) / df["close"] - 1.0
    y = pd.Series(0, index=df.index)
    y[fwd > up_threshold] = 1
    y[fwd < down_threshold] = -1
    return y.astype(int)
