from __future__ import annotations
from typing import Dict, Any, List
import pandas as pd

from indicator_settings import sanitize_indicator_settings
from .indicators_core import (
    _src, _ema, _sma, _rsi, _stoch, _macd, _bbands, _atr, _cci, _roc, _willr, _mfi, _obv, _series
)

def build_indicator_panels(df: pd.DataFrame, settings: Dict[str, Any]) -> Dict[str, Any]:
    s = sanitize_indicator_settings(settings)
    out: Dict[str, Any] = {}
    if s["rsi"]["enabled"]:
        rsi_series = _rsi(_src(df, s["rsi"]["source"]), int(s["rsi"]["period"]))
        out["rsi"] = _series(df.index, rsi_series)
    if s["stoch"]["enabled"]:
        st = _stoch(df, int(s["stoch"]["k"]), int(s["stoch"]["d"]), int(s["stoch"]["smooth"]))
        out["stoch"] = {"k": _series(df.index, st["k"]), "d": _series(df.index, st["d"])}
    if s["macd"]["enabled"]:
        mac = _macd(_src(df, "close"), int(s["macd"]["fast"]), int(s["macd"]["slow"]), int(s["macd"]["signal"]))
        out["macd"] = {"macd": _series(df.index, mac["macd"]), "signal": _series(df.index, mac["signal"]), "hist": _series(df.index, mac["hist"])}
    if s["ema"]["enabled"]:
        em: Dict[str, List[Dict[str, float]]] = {}
        for p in s["ema"]["periods"]:
            em[str(int(p))] = _series(df.index, _ema(df["close"], int(p)))
        out["ema"] = em
    if s["sma"]["enabled"]:
        sm: Dict[str, List[Dict[str, float]]] = {}
        for p in s["sma"]["periods"]:
            sm[str(int(p))] = _series(df.index, _sma(df["close"], int(p)))
        out["sma"] = sm
    if s["bbands"]["enabled"]:
        bb = _bbands(_src(df, "close"), int(s["bbands"]["period"]), float(s["bbands"]["stddev"]))
        out["bbands"] = {"up": _series(df.index, bb["up"]), "mid": _series(df.index, bb["mid"]), "dn": _series(df.index, bb["dn"])}
    if s["atr"]["enabled"]:
        out["atr"] = _series(df.index, _atr(df, int(s["atr"]["period"])))
    if s["cci"]["enabled"]:
        out["cci"] = _series(df.index, _cci(df, int(s["cci"]["period"])))
    if s["roc"]["enabled"]:
        rr: Dict[str, List[Dict[str, float]]] = {}
        for p in s["roc"]["periods"]:
            rr[str(int(p))] = _series(df.index, _roc(df["close"], int(p)))
        out["roc"] = rr
    if s["willr"]["enabled"]:
        out["willr"] = _series(df.index, _willr(df, int(s["willr"]["period"])))
    if s["mfi"]["enabled"]:
        out["mfi"] = _series(df.index, _mfi(df, int(s["mfi"]["period"])))
    if s["obv"]["enabled"]:
        out["obv"] = _series(df.index, _obv(df))
    return out