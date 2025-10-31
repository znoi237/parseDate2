from typing import Dict, Any
from config import Config
from database import DatabaseManager

def default_indicator_settings() -> Dict[str, Any]:
    return {
        "rsi": {"enabled": True, "period": 14, "source": "close"},
        "stoch": {"enabled": True, "k": 14, "d": 3, "smooth": 3},
        "macd": {"enabled": True, "fast": 12, "slow": 26, "signal": 9},
        "ema": {"enabled": True, "periods": [5, 10, 20, 50, 100, 200]},
        "sma": {"enabled": False, "periods": [5, 20, 50, 200]},
        "bbands": {"enabled": True, "period": 20, "stddev": 2.0},
        "atr": {"enabled": True, "period": 14},
        "cci": {"enabled": False, "period": 20},
        "roc": {"enabled": False, "periods": [5, 10]},
        "willr": {"enabled": False, "period": 14},
        "mfi": {"enabled": False, "period": 14},
        "obv": {"enabled": False},
        "lags": {"enabled": True, "max_lag": 3}
    }

def sanitize_indicator_settings(s: Dict[str, Any] | None) -> Dict[str, Any]:
    d = default_indicator_settings()
    s = s or {}
    out = {}
    for key, val in d.items():
        cur = s.get(key, {})
        if isinstance(val, dict):
            ov = {}
            for k2, v2 in val.items():
                ov[k2] = cur.get(k2, v2)
            out[key] = ov
        else:
            out[key] = s.get(key, val)
    # типы
    try:
        out["rsi"]["period"] = int(out["rsi"]["period"])
        out["stoch"]["k"] = int(out["stoch"]["k"])
        out["stoch"]["d"] = int(out["stoch"]["d"])
        out["stoch"]["smooth"] = int(out["stoch"]["smooth"])
        out["macd"]["fast"] = int(out["macd"]["fast"])
        out["macd"]["slow"] = int(out["macd"]["slow"])
        out["macd"]["signal"] = int(out["macd"]["signal"])
        out["ema"]["periods"] = [int(x) for x in (out["ema"]["periods"] or [])]
        out["sma"]["periods"] = [int(x) for x in (out["sma"]["periods"] or [])]
        out["bbands"]["period"] = int(out["bbands"]["period"])
        out["bbands"]["stddev"] = float(out["bbands"]["stddev"])
        out["atr"]["period"] = int(out["atr"]["period"])
        out["cci"]["period"] = int(out["cci"]["period"])
        out["roc"]["periods"] = [int(x) for x in (out["roc"]["periods"] or [])]
        out["willr"]["period"] = int(out["willr"]["period"])
        out["mfi"]["period"] = int(out["mfi"]["period"])
        out["lags"]["max_lag"] = int(out["lags"]["max_lag"])
    except Exception:
        pass
    return out

def get_indicator_settings(db: DatabaseManager) -> Dict[str, Any]:
    raw = db.get_setting("indicators") or {}
    return sanitize_indicator_settings(raw)