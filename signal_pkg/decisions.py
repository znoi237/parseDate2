from __future__ import annotations
from typing import Dict, Tuple
import numpy as np
from config import Config


def decide_entry(
    agg: Dict,
    base_pb: Dict[str, float],
    entry_threshold: float | None = None,
    min_support: float | None = None,
    hold_margin_min: float | None = None,
) -> Tuple[bool, int, float]:
    """
    Правило входа. Возвращает (ok, dir, strength).
    """
    entry_threshold = float(entry_threshold if entry_threshold is not None else Config.SIG_ENTRY_THRESHOLD)
    min_support = float(min_support if min_support is not None else Config.SIG_MIN_SUPPORT)
    hold_margin_min = float(hold_margin_min if hold_margin_min is not None else Config.SIG_HOLD_MARGIN_MIN)

    margin_hold = max(float(base_pb.get("buy", 0.0)), float(base_pb.get("sell", 0.0))) - float(base_pb.get("hold", 0.0))
    ok = (abs(agg["score"]) >= entry_threshold) and (agg["support"] >= min_support) and (margin_hold >= hold_margin_min)
    return bool(ok), int(agg["dir"]), float(abs(agg["score"]))


def decide_exit(
    agg: Dict,
    open_dir: int,
    base_pb: Dict[str, float],
    exit_threshold: float | None = None,
    min_support: float | None = None,
    hold_margin_min: float | None = None,
    exit_on_flip: bool | None = None,
) -> bool:
    """
    Правило выхода.
    """
    exit_threshold = float(exit_threshold if exit_threshold is not None else Config.SIG_EXIT_THRESHOLD)
    min_support = float(min_support if min_support is not None else Config.SIG_MIN_SUPPORT)
    hold_margin_min = float(hold_margin_min if hold_margin_min is not None else Config.SIG_HOLD_MARGIN_MIN)
    exit_on_flip = bool(Config.EXIT_ON_FLIP if exit_on_flip is None else exit_on_flip)

    margin_hold = max(float(base_pb.get("buy", 0.0)), float(base_pb.get("sell", 0.0))) - float(base_pb.get("hold", 0.0))
    flip = (np.sign(agg["score"]) != np.sign(open_dir)) and (open_dir != 0)
    weak = abs(agg["score"]) < exit_threshold
    weak_sup = agg["support"] < min_support
    hold_weak = margin_hold < hold_margin_min

    if exit_on_flip and flip:
        return True
    return bool(weak or weak_sup or hold_weak)