from datetime import datetime
from flask import jsonify, request, current_app

from config import Config


def _sv():
    return current_app.extensions["services"]


def _latest_exit_price_for_symbol(sv, symbol: str) -> float:
    if sv.ws:
        data = sv.ws.get_live_candles(symbol, "15m", limit=1)
        if data:
            try:
                v = float(data[-1]["close"])
                if v > 0:
                    return v
            except Exception:
                pass
    for tf in ["15m", "1h", "4h", "1d", "1w"]:
        if tf not in getattr(Config, "TIMEFRAMES", []):
            continue
        df = sv.db.load_ohlcv(symbol, tf, limit=1)
        if df is not None and not df.empty:
            try:
                v = float(df["close"].iloc[-1])
                if v > 0:
                    return v
            except Exception:
                continue
    return 0.0


def register(bp):
    @bp.route("/bots/start", methods=["POST"])
    def bots_start():
        sv = _sv()
        body = request.get_json(force=True) or {}
        symbol = body.get("symbol")
        network = body.get("network", "testnet")
        if not symbol:
            return jsonify({"ok": False, "message": "symbol is required"}), 400
        if network != "testnet":
            return jsonify({"ok": False, "message": "Trading is allowed only on testnet"}), 400
        timeframes = body.get("timeframes") or getattr(Config, "TIMEFRAMES", [])
        interval_sec = int(body.get("interval_sec", 60))
        ok, msg = sv.bots.start_bot(symbol, timeframes, interval_sec)
        code = 200 if ok else 400
        return jsonify({"ok": ok, "message": msg, "network": network}), code

    @bp.route("/bots/stop", methods=["POST"])
    def bots_stop():
        sv = _sv()
        body = request.get_json(force=True) or {}
        symbol = body.get("symbol")
        network = body.get("network", "testnet")
        if not symbol:
            return jsonify({"ok": False, "message": "symbol is required"}), 400
        if network != "testnet":
            return jsonify({"ok": False, "message": "Trading is allowed only on testnet"}), 400
        ok, msg = sv.bots.stop_bot(symbol)
        now = datetime.utcnow()
        exit_price = _latest_exit_price_for_symbol(sv, symbol)
        if exit_price <= 0.0:
            df = sv.db.load_ohlcv(symbol, "1h", limit=1)
            if df is not None and not df.empty:
                try:
                    exit_price = float(df["close"].iloc[-1])
                except Exception:
                    pass
        closed = sv.db.close_all_open_trades_for_symbol(symbol, network, exit_price, now)
        resp_msg = f"{msg}. Closed {closed} open trade(s) at {exit_price:.8f}"
        return jsonify({"ok": True, "message": resp_msg, "closed_trades": closed, "exit_price": exit_price, "network": network}), 200

    @bp.route("/bots", methods=["GET"])
    def bots_list():
        sv = _sv()
        data = sv.db.bots_summary()
        return jsonify({"data": data})