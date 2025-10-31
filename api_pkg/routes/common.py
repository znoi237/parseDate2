import sqlite3
import time
from flask import jsonify, request, current_app

from config import Config


def _sv():
    return current_app.extensions["services"]


def register(bp):
    @bp.route("/ping", methods=["GET"])
    def ping():
        return jsonify({"ok": True})

    @bp.route("/symbols", methods=["GET"])
    def symbols():
        return jsonify({"data": getattr(Config, "SYMBOLS", [])})

    @bp.route("/keys", methods=["GET", "POST"])
    def keys():
        sv = _sv()
        if request.method == "GET":
            network = request.args.get("network", "mainnet")
            keys = sv.db.load_api_keys(network)
            if not keys:
                return jsonify({"data": None})

            def mask(s: str, keep: int = 4):
                return s if not s or len(s) <= keep * 2 else (s[:keep] + "..." + s[-keep:])
            return jsonify({"data": {
                "network": network,
                "api_key": mask(keys["api_key"]),
                "api_secret": mask(keys["api_secret"]),
            }})
        body = request.get_json(force=True) or {}
        network = body.get("network")
        api_key = body.get("api_key")
        api_secret = body.get("api_secret")
        if network not in ("mainnet", "testnet"):
            return jsonify({"error": "network must be mainnet|testnet"}), 400
        if not api_key or not api_secret:
            return jsonify({"error": "api_key/api_secret required"}), 400
        sv.db.save_api_keys(network, api_key, api_secret)
        return jsonify({"status": "ok"})

    @bp.route("/account", methods=["GET"])
    def account():
        sv = _sv()
        network = request.args.get("network", "testnet")
        acc = sv.accounts.get_balance_usdt(network)
        trades = sv.db.get_trades(limit=1000, network=network)
        open_count = len([t for t in trades if t["status"] == "open"])
        closed = [t for t in trades if t["status"] == "closed"]
        pnl = sum([float(t["pnl_percent"] or 0.0) for t in closed]) if closed else 0.0
        resp = {
            "network": network,
            "connected": bool(acc.get("connected")),
            "balance_usdt": acc.get("balance_usdt"),
            "open_positions": open_count,
            "closed_trades": len(closed),
            "total_pnl_percent": pnl,
            "last_checked": acc.get("last_checked"),
            "error": acc.get("error"),
        }
        return jsonify({"data": resp})

    @bp.route("/pairs_status", methods=["GET"])
    def pairs_status():
        sv = _sv()
        symbols = request.args.getlist("symbol") or getattr(Config, "SYMBOLS", [])
        data = sv.db.get_pairs_status(symbols, getattr(Config, "TIMEFRAMES", []))
        return jsonify({"data": data})

    @bp.route("/sync_history", methods=["POST"])
    def sync_history():
        sv = _sv()
        body = request.get_json(force=True) or {}
        symbol = body.get("symbol")
        timeframes = body.get("timeframes") or getattr(Config, "TIMEFRAMES", [])
        years = int(body.get("years", getattr(Config, "HISTORY_YEARS", 2)))
        force = bool(body.get("force", False))
        if symbol:
            for tf in timeframes:
                sv.data.fetch_ohlcv_incremental(symbol, tf, years, force_full=force)
        else:
            for sym in getattr(Config, "SYMBOLS", []):
                for tf in timeframes:
                    sv.data.fetch_ohlcv_incremental(sym, tf, years, force_full=force)
        return jsonify({"status": "ok", "force": force})