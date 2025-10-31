from __future__ import annotations
from typing import Dict, Any, List
import numpy as np

from config import Config
from precompute_cache import build_precompute
from signal_engine import aggregate_signal, decide_entry

def build_signal_panel(
    db,
    models,
    symbol: str,
    timeframe: str,
    limit: int,
    entry_threshold: float,
    min_support: float,
    hold_margin_min: float,
) -> Dict[str, Any]:
    precomp = build_precompute(db, models, symbol, timeframe, limit=max(limit, 600))
    if precomp is None:
        return {"score": [], "support": [], "dir": [], "entry": [], "thresholds": {"entry": entry_threshold, "min_support": min_support, "hold_margin_min": hold_margin_min}}
    X_idx_all = precomp["X_idx"]
    take = X_idx_all[-limit:]
    base = precomp["base"]
    higher = precomp["higher"]
    weights_cfg = getattr(Config, "HIERARCHY_WEIGHTS", {})

    base_buy_all = base["pb_buy"][-len(take):]
    base_hold_all = base["pb_hold"][-len(take):]
    base_sell_all = base["pb_sell"][-len(take):]

    score_out: List[Dict] = []
    sup_out: List[Dict] = []
    dir_out: List[Dict] = []
    entry_out: List[Dict] = []

    lookbacks: List[float] = []
    for i, ts in enumerate(take):
        probs_by_tf: Dict[str, Dict[str, float]] = {
            timeframe: {"buy": float(base_buy_all[i]), "hold": float(base_hold_all[i]), "sell": float(base_sell_all[i])}
        }
        for tf, obj in higher.items():
            idx_h = obj["idx"]
            pos = idx_h.searchsorted(ts, side="right") - 1
            if pos >= 0:
                probs_by_tf[tf] = {"buy": float(obj["pb_buy"][pos]), "hold": float(obj["pb_hold"][pos]), "sell": float(obj["pb_sell"][pos])}
        agg = aggregate_signal(probs_by_tf, timeframe, weights_cfg, lookback_scores=lookbacks)
        base_pb = probs_by_tf.get(timeframe, {"buy": 0.0, "hold": 0.0, "sell": 0.0})
        lookbacks.append(agg["score"])
        if len(lookbacks) > max(1, Config.SIG_LOOKBACK * 3):
            lookbacks.pop(0)

        ok, dir_sig, _ = decide_entry(agg, base_pb, entry_threshold=entry_threshold, min_support=min_support, hold_margin_min=hold_margin_min)
        t_iso = ts.isoformat()
        score_out.append({"time": t_iso, "value": float(agg["score"])})
        sup_out.append({"time": t_iso, "value": float(agg["support"])})
        dir_out.append({"time": t_iso, "value": int(np.sign(agg["score"]))})
        entry_out.append({"time": t_iso, "value": 1.0 if (ok and dir_sig != 0) else 0.0})

    return {
        "score": score_out,
        "support": sup_out,
        "dir": dir_out,
        "entry": entry_out,
        "thresholds": {"entry": entry_threshold, "min_support": min_support, "hold_margin_min": hold_margin_min}
    }