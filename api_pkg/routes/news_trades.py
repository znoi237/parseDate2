from datetime import datetime, timedelta
from flask import jsonify, request, current_app

from config import Config


def _sv():
    return current_app.extensions["services"]


def register(bp):
    @bp.route("/trades", methods=["GET"])
    def trades():
        sv = _sv()
        limit = request.args.get("limit")
        try:
            limit = int(limit) if limit is not None else 200
        except Exception:
            limit = 200
        network = request.args.get("network", "testnet")
        symbol = request.args.get("symbol")
        status = request.args.get("status")
        origin = request.args.get("origin")
        data = sv.db.get_trades(limit=limit, network=network, symbol=symbol, status=status, origin=origin)
        return jsonify({"data": data})

    @bp.route("/news", methods=["GET"])
    def news():
        sv = _sv()
        hours = int(request.args.get("hours", "24"))
        since = datetime.utcnow() - timedelta(hours=hours)
        df = sv.db.news_since(since)
        return jsonify({"data": df.to_dict(orient="records")})

    @bp.route("/debug/hist_stats", methods=["GET"])
    def hist_stats():
        sv = _sv()
        symbol = request.args.get("symbol")
        timeframe = request.args.get("timeframe")

        if symbol and timeframe:
            stats = sv.db.get_hist_stats(symbol, timeframe)
            return jsonify({"data": stats})

        if symbol:
            out = {tf: sv.db.get_hist_stats(symbol, tf) for tf in getattr(Config, "TIMEFRAMES", [])}
            return jsonify({"data": out})

        out = {}
        for sym in getattr(Config, "SYMBOLS", []):
            out[sym] = {tf: sv.db.get_hist_stats(sym, tf) for tf in getattr(Config, "TIMEFRAMES", [])}
        return jsonify({"data": out})