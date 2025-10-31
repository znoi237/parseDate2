from __future__ import annotations
from typing import Dict, List
import numpy as np
from config import Config

# Тип pb: {"buy": float, "hold": float, "sell": float}

def _tf_score_from_pb(pb: Dict[str, float]) -> float:
    """
    Преобразует вероятности одного ТФ в скалярный скор в диапазоне [-1, 1]:
      - положительное -> long, отрицательное -> short
      - "hold" снижает силу сигнала
    Формула: s_dir = (buy - sell); s_hold = max(buy,sell) - hold; score = s_dir * max(s_hold, 0)
    """
    b = float(pb.get("buy", 0.0))
    s = float(pb.get("sell", 0.0))
    h = float(pb.get("hold", 0.0))
    s_dir = b - s
    s_hold = max(b, s) - h
    if s_hold < 0:
        s_hold = 0.0
    score = s_dir * s_hold
    return float(np.clip(score, -1.0, 1.0))


def _normalize_weights(weights: Dict[str, float]) -> Dict[str, float]:
    s = sum(max(0.0, float(v)) for v in weights.values())
    if s <= 0:
        n = max(1, len(weights))
        return {k: 1.0 / n for k in weights}
    return {k: float(max(0.0, float(v)) / s) for k, v in weights.items()}


def aggregate_signal(
    probs_by_tf: Dict[str, Dict[str, float]],
    base_tf: str,
    weights_cfg: Dict[str, float] | None = None,
    lookback_scores: List[float] | None = None,
) -> Dict:
    """
    Агрегирует сигналы из нескольких ТФ в один общий.
    Возвращает: {score [-1..1], dir {-1,0,1}, confidence [0..1], support [0..1], per_tf: {tf: score_tf}}
    """
    weights_cfg = weights_cfg or Config.HIERARCHY_WEIGHTS
    usable = {tf: probs_by_tf[tf] for tf in probs_by_tf if tf in weights_cfg}
    if not usable:
        usable = probs_by_tf
        weights = _normalize_weights({tf: 1.0 for tf in usable})
    else:
        weights = _normalize_weights({tf: weights_cfg[tf] for tf in usable})

    per_tf_scores: Dict[str, float] = {tf: _tf_score_from_pb(pb) for tf, pb in usable.items()}
    agg = float(sum(per_tf_scores[tf] * weights.get(tf, 0.0) for tf in per_tf_scores))

    if lookback_scores:
        lk = list(lookback_scores)[-Config.SIG_LOOKBACK:]
        if lk:
            agg = float(np.mean(lk + [agg]))

    dir_sign = 0
    if agg > 1e-9:
        dir_sign = 1
    elif agg < -1e-9:
        dir_sign = -1

    if dir_sign == 0:
        support = 0.0
    else:
        total_w = sum(weights.values()) or 1.0
        agree_w = sum(weights.get(tf, 0.0) for tf, s in per_tf_scores.items() if np.sign(s) == dir_sign and abs(s) > 0)
        support = float(agree_w / total_w)

    confidence = abs(agg)
    return {
        "score": float(np.clip(agg, -1.0, 1.0)),
        "dir": int(dir_sign),
        "confidence": float(np.clip(confidence, 0.0, 1.0)),
        "support": float(np.clip(support, 0.0, 1.0)),
        "per_tf": per_tf_scores,
    }