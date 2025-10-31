from __future__ import annotations
import json
from datetime import datetime
from typing import Any, Dict
import logging

from config import Config

logger = logging.getLogger("db")


def to_iso(val: Any) -> str | None:
    if val is None:
        return None
    try:
        if isinstance(val, str):
            return val
        if hasattr(val, "isoformat"):
            return val.isoformat()
        return str(val)
    except Exception:
        return str(val)


def default_signal_params() -> Dict[str, Any]:
    return {
        "entry_threshold": float(Config.SIG_ENTRY_THRESHOLD),
        "exit_threshold": float(Config.SIG_EXIT_THRESHOLD),
        "min_support": float(Config.SIG_MIN_SUPPORT),
        "hold_margin_min": float(Config.SIG_HOLD_MARGIN_MIN),
        "exit_on_flip": bool(Config.EXIT_ON_FLIP),
        "sl_atr_mult": float(Config.BT_SL_ATR),
        "tp_atr_mult": float(Config.BT_TP_ATR),
        "max_bars_in_trade": int(Config.BT_MAX_BARS),
    }