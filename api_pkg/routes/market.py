from datetime import datetime, timedelta
from flask import jsonify, request, current_app


def _sv():
    return current_app.extensions["services"]


def register(bp):
    @bp.route("/live_candles", methods=["GET"])
    def live_candles():
        sv = _sv()
        symbol = request.args.get("symbol")
        tf = request.args.get("timeframe", "1h")
        limit = int(request.args.get("limit", "200"))
        data = sv.ws.get_live_candles(symbol, tf, limit=limit) if sv.ws else []
        if not data:
            df = sv.db.load_ohlcv(symbol, tf, since=datetime.utcnow() - timedelta(days=30))
            if df is not None and not df.empty:
                data = [{
                    "open_time": idx.isoformat(),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row["volume"]),
                } for idx, row in df.tail(limit).iterrows()]
        return jsonify({"data": data})