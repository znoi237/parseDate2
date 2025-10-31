import threading
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from config import Config
from database import DatabaseManager
from data_manager import CCXTDataManager
from model_manager import ModelManager
from websocket_manager import WebsocketManager
from signal_engine import aggregate_signal, decide_entry, decide_exit


def _atr14(df: pd.DataFrame) -> float:
    if df is None or df.empty or len(df) < 2:
        return 0.0
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    close = df["close"].astype(float)
    prev = close.shift(1)
    tr = pd.concat([(high - low), (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)
    return float(tr.rolling(14, min_periods=1).mean().iloc[-1])


class BotManager:
    """
    Bot runner: мягкая иерархия по всем ТФ (aggregate_signal), вход по decide_entry,
    выход по decide_exit или SL/TP/таймаут. Торгует только в testnet.
    """
    def __init__(self, db: DatabaseManager, data: CCXTDataManager, models: ModelManager, ws: Optional[WebsocketManager]):
        self.db = db
        self.data = data
        self.models = models
        self.ws = ws
        self._locks: Dict[str, threading.Lock] = {}
        self._threads: Dict[str, threading.Thread] = {}
        self._stops: Dict[str, threading.Event] = {}
        self._intervals: Dict[str, int] = {}
        self._timeframes: Dict[str, List[str]] = {}

    def start_bot(self, symbol: str, timeframes: List[str], interval_sec: int = 60) -> Tuple[bool, str]:
        if symbol in self._threads:
            return False, f"Bot for {symbol} already running"
        stop_ev = threading.Event()
        self._stops[symbol] = stop_ev
        self._locks[symbol] = threading.Lock()
        self._intervals[symbol] = max(10, int(interval_sec or 60))
        self._timeframes[symbol] = timeframes or Config.TIMEFRAMES

        t = threading.Thread(target=self._run, args=(symbol,), daemon=True)
        self._threads[symbol] = t
        t.start()
        try:
            self.db.add_bot(symbol, status="running", stats={"interval_sec": self._intervals[symbol], "timeframes": self._timeframes[symbol]})
        except Exception:
            pass
        return True, f"Started bot for {symbol} (testnet) with interval {self._intervals[symbol]}s"

    def stop_bot(self, symbol: str) -> Tuple[bool, str]:
        if symbol not in self._threads:
            return False, f"Bot for {symbol} is not running"
        self._stops[symbol].set()
        self._threads[symbol].join(timeout=5)
        self._threads.pop(symbol, None)
        self._stops.pop(symbol, None)
        self._intervals.pop(symbol, None)
        self._timeframes.pop(symbol, None)
        self._locks.pop(symbol, None)
        try:
            self.db.update_bot(symbol, status="stopped")
        except Exception:
            pass
        return True, f"Stopped bot for {symbol}"

    def _run(self, symbol: str):
        interval = self._intervals.get(symbol, 60)
        while not self._stops.get(symbol).is_set():
            try:
                with self._locks[symbol]:
                    self._tick(symbol)
            except Exception:
                pass
            finally:
                self._stops[symbol].wait(interval)

    def _gather_latest_windows(self, symbol: str, tfs: List[str]) -> Dict[str, pd.DataFrame]:
        latest_windows: Dict[str, pd.DataFrame] = {}
        # 1) WS
        if self.ws:
            for tf in tfs:
                data = self.ws.get_live_candles(symbol, tf, limit=200)
                if data:
                    try:
                        df = pd.DataFrame(data)
                        # возможные ключи: open_time или time
                        if "open_time" in df.columns:
                            df["open_time"] = pd.to_datetime(df["open_time"])
                            df.set_index("open_time", inplace=True)
                        elif "time" in df.columns:
                            df["time"] = pd.to_datetime(df["time"])
                            df.set_index("time", inplace=True)
                        latest_windows[tf] = df[["open", "high", "low", "close", "volume"]].astype(float)
                    except Exception:
                        pass
        # 2) DB fallback
        for tf in tfs:
            if tf not in latest_windows:
                df = self.db.load_ohlcv(symbol, tf, since=None, limit=400)
                if df is not None and not df.empty:
                    latest_windows[tf] = df
        return latest_windows

    def _effective_signal_params(self) -> Dict[str, float]:
        sp = self.db.load_signal_params() or {}
        return {
            "entry_threshold": float(sp.get("entry_threshold", Config.SIG_ENTRY_THRESHOLD)),
            "exit_threshold": float(sp.get("exit_threshold", Config.SIG_EXIT_THRESHOLD)),
            "min_support": float(sp.get("min_support", Config.SIG_MIN_SUPPORT)),
            "hold_margin_min": float(sp.get("hold_margin_min", Config.SIG_HOLD_MARGIN_MIN)),
            "exit_on_flip": bool(sp.get("exit_on_flip", Config.EXIT_ON_FLIP)),
            "sl_atr_mult": float(sp.get("sl_atr_mult", Config.BT_SL_ATR)),
            "tp_atr_mult": float(sp.get("tp_atr_mult", Config.BT_TP_ATR)),
            "max_bars_in_trade": int(sp.get("max_bars_in_trade", Config.BT_MAX_BARS)),
        }

    def _latest_probs_by_tf(self, symbol: str, tfs: List[str], latest: Dict[str, pd.DataFrame]) -> Tuple[Dict[str, Dict[str, float]], str]:
        """
        Возвращает probs_by_tf и выбранный базовый ТФ.
        Использует публичный интерфейс ModelManager.predict_proba_for_tf.
        """
        probs_by_tf: Dict[str, Dict[str, float]] = {}
        # порядок ТФ как в исходной логике
        order = [tf for tf in ["1w", "1d", "4h", "1h", "15m"] if tf in tfs]
        base_tf = order[-1] if order else (tfs[-1] if tfs else "15m")

        for tf in order:
            df = latest.get(tf)
            if df is None or df.empty:
                continue
            try:
                res = self.models.predict_proba_for_tf(symbol, tf, df.tail(600))
            except Exception:
                res = None
            if not res:
                continue
            try:
                pb = {
                    "buy": float(res["pb_buy"][-1]),
                    "hold": float(res["pb_hold"][-1]),
                    "sell": float(res["pb_sell"][-1]),
                }
            except Exception:
                continue
            probs_by_tf[tf] = pb

        if not probs_by_tf:
            return {}, base_tf
        if base_tf not in probs_by_tf:
            base_tf = list(probs_by_tf.keys())[-1]
        return probs_by_tf, base_tf

    def _tick(self, symbol: str):
        tfs = self._timeframes.get(symbol, Config.TIMEFRAMES)
        params = self._effective_signal_params()
        latest = self._gather_latest_windows(symbol, tfs)
        if not latest:
            return

        probs_by_tf, base_tf = self._latest_probs_by_tf(symbol, tfs, latest)
        if not probs_by_tf:
            return

        agg = aggregate_signal(probs_by_tf, base_tf, getattr(Config, "HIERARCHY_WEIGHTS", {}), lookback_scores=None)
        base_pb = probs_by_tf.get(base_tf, {"buy": 0.0, "hold": 0.0, "sell": 0.0})

        df_b = latest.get(base_tf)
        if df_b is None or df_b.empty:
            return
        last_ts = df_b.index[-1]
        close_price = float(df_b["close"].iloc[-1])
        hi = float(df_b["high"].iloc[-1])
        lo = float(df_b["low"].iloc[-1])
        atr_now = _atr14(df_b.tail(200))

        opens = self.db.get_open_trades_by_symbol_network(symbol, "testnet")
        open_trade = opens[0] if opens else None

        if open_trade is None:
            ok, dir_sig, _ = decide_entry(
                agg,
                base_pb,
                entry_threshold=params["entry_threshold"],
                min_support=params["min_support"],
                hold_margin_min=params["hold_margin_min"],
            )
            if ok and dir_sig != 0:
                if dir_sig == 1:
                    sl = close_price - params["sl_atr_mult"] * atr_now
                    tp = close_price + params["tp_atr_mult"] * atr_now
                    side = "BUY"
                else:
                    sl = close_price + params["sl_atr_mult"] * atr_now
                    tp = close_price - params["tp_atr_mult"] * atr_now
                    side = "SELL"
                self.db.add_trade(
                    symbol=symbol,
                    side=side,
                    entry_price=close_price,
                    quantity=1.0,
                    entry_time=last_ts.to_pydatetime(),
                    network="testnet",
                    origin="bot",
                )
                self.db.update_bot(symbol, stats={"entry_time": last_ts.isoformat(), "side": side, "sl": sl, "tp": tp, "score": agg["score"], "support": agg["support"]})
        else:
            side = (open_trade.get("side") or "BUY").upper()
            entry_price = float(open_trade.get("entry_price") or close_price)
            if side == "BUY":
                sl_level = entry_price - params["sl_atr_mult"] * atr_now
                tp_level = entry_price + params["tp_atr_mult"] * atr_now
                hit = "sl" if lo <= sl_level else ("tp" if hi >= tp_level else None)
            else:
                sl_level = entry_price + params["sl_atr_mult"] * atr_now
                tp_level = entry_price - params["tp_atr_mult"] * atr_now
                hit = "sl" if hi >= sl_level else ("tp" if lo <= tp_level else None)

            exit_reason = None
            exit_price = None
            if hit is None:
                should_exit = decide_exit(
                    agg,
                    open_dir=(1 if side == "BUY" else -1),
                    base_pb=base_pb,
                    exit_threshold=params["exit_threshold"],
                    min_support=params["min_support"],
                    hold_margin_min=params["hold_margin_min"],
                    exit_on_flip=params["exit_on_flip"],
                )
                if should_exit:
                    exit_reason = "signal_exit"
                    exit_price = close_price
            else:
                exit_reason = hit
                exit_price = tp_level if hit == "tp" else sl_level

            if exit_reason:
                self.db.close_all_open_trades_for_symbol(symbol, "testnet", exit_price, last_ts.to_pydatetime())
                self.db.update_bot(symbol, stats={"exit_time": last_ts.isoformat(), "exit_reason": exit_reason, "exit_price": exit_price, "score": agg["score"], "support": agg["support"]})