from __future__ import annotations
from typing import Dict, Any, Tuple
import numpy as np
import pandas as pd
from config import Config

def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    h, l, c = df["high"].astype(float), df["low"].astype(float), df["close"].astype(float)
    prev = c.shift(1)
    tr = pd.concat([(h - l), (h - prev).abs(), (l - prev).abs()], axis=1).max(axis=1)
    return tr.rolling(n, min_periods=1).mean().bfill()

def consistent_support_count(base_dir: int, probs_by_tf: Dict[str, Dict[str, float]], base_tf: str) -> int:
    count = 0
    for tf, pb in probs_by_tf.items():
        if tf == base_tf:
            continue
        s = np.sign(pb["buy"] - pb["sell"])
        if base_dir != 0 and s == base_dir:
            count += 1
    return count

def pick_higher_probs_at_ts(higher: Dict[str, Dict[str, Any]], ts: pd.Timestamp) -> Dict[str, Dict[str, float]]:
    out = {}
    for tf, obj in higher.items():
        idx_h: pd.DatetimeIndex = obj["idx"]
        pos = idx_h.searchsorted(ts, side="right") - 1
        if pos >= 0:
            out[tf] = {
                "buy": float(obj["pb_buy"][pos]),
                "hold": float(obj["pb_hold"][pos]),
                "sell": float(obj["pb_sell"][pos]),
            }
    return out

def build_probs_at_i(precomp: Dict[str, Any], base_tf: str, i: int) -> Tuple[pd.Timestamp, Dict[str, Dict[str, float]]]:
    idx = precomp["X_idx"]
    ts = idx[i]
    base = precomp["base"]
    probs_by_tf = {
        base_tf: {
            "buy": float(base["pb_buy"][i]),
            "hold": float(base["pb_hold"][i]),
            "sell": float(base["pb_sell"][i]),
        }
    }
    higher_now = pick_higher_probs_at_ts(precomp["higher"], ts)
    probs_by_tf.update(higher_now)
    return ts, probs_by_tf