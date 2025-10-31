from datetime import timedelta
import pandas as pd
from flask import jsonify, request, current_app, render_template

from config import Config
from analysis_utils import compute_indicators_block, detect_candle_patterns, detect_opportunities
from indicator_settings import get_indicator_settings, sanitize_indicator_settings, default_indicator_settings
from indicators_panels import build_indicator_panels, build_signal_panel
from precompute_cache import build_precompute
from signal_engine import aggregate_signal
from backtest import run_backtest


def _sv():
    return current_app.extensions["services"]


def register(bp):
    @bp.route("/analysis/view", methods=["GET"])
    def analysis_view():
        symbol = request.args.get("symbol") or (getattr(Config, "SYMBOLS", ["BTC/USDT"])[0])
        timeframe = request.args.get("timeframe", "15m")
        try:
            limit = int(request.args.get("limit", "500"))
        except Exception:
            limit = 500
        return render_template("analysis.html", symbol=symbol, timeframe=timeframe, limit=limit)

    @bp.route("/analysis", methods=["GET"])
    def analysis():
        sv = _sv()
        symbol = request.args.get("symbol")
        timeframe = request.args.get("timeframe", "15m")
        try:
            limit = int(request.args.get("limit", "500"))
        except Exception:
            limit = 500
        network = request.args.get("network", "testnet")

        if not symbol:
            return jsonify({"error": "symbol is required"}), 400
        if timeframe not in getattr(Config, "TIMEFRAMES", []):
            return jsonify({"error": f"timeframe must be one of {getattr(Config, 'TIMEFRAMES', [])}"}), 400

        trained_any = any((sv.db.load_model(symbol, tf) or {}).get("model") for tf in getattr(Config, "TIMEFRAMES", []))
        if not trained_any:
            return jsonify({"data": {"trained": False, "reason": "model_not_trained"}})

        df = sv.db.load_ohlcv(symbol, timeframe)
        if df is None or df.empty:
            return jsonify({"data": {"trained": True, "candles": [], "trades": [], "markers": [], "indicator_panels": {}, "signal_panel": {}, "news_used": [], "summary": ""}})

        df = df.tail(max(50, limit))

        indicators = compute_indicators_block(df)
        patterns = detect_candle_patterns(df)
        opportunities = detect_opportunities(df)

        ind_settings = get_indicator_settings(sv.db) or default_indicator_settings()
        indicator_panels = build_indicator_panels(df, sanitize_indicator_settings(ind_settings))

        sp = sv.db.get_signal_profiles()
        active_params = sp["profiles"].get(sp["active"], {})
        signal_panel = build_signal_panel(
            sv.db,
            sv.models,
            symbol,
            timeframe,
            limit=max(300, limit),
            entry_threshold=float(active_params.get("entry_threshold", getattr(Config, "SIG_ENTRY_THRESHOLD", 0.6))),
            min_support=float(active_params.get("min_support", getattr(Config, "SIG_MIN_SUPPORT", 0.1))),
            hold_margin_min=float(active_params.get("hold_margin_min", getattr(Config, "SIG_HOLD_MARGIN_MIN", 0.02))),
        )

        # Инлайн‑прогноз по TF и старшим TF
        prediction = {"consensus": 0, "confidence": 0.0, "by_tf": {}}
        try:
            precomp = build_precompute(sv.db, sv.models, symbol, timeframe, limit=max(600, limit))
            if precomp is not None:
                X_idx = precomp["X_idx"]
                ts_last = X_idx[-1]
                probs_by_tf = {}
                base = precomp["base"]
                probs_by_tf[timeframe] = {
                    "buy": float(base["pb_buy"][-1]),
                    "hold": float(base["pb_hold"][-1]),
                    "sell": float(base["pb_sell"][-1]),
                }
                for tf, obj in precomp["higher"].items():
                    idx_h = obj["idx"]
                    pos = idx_h.searchsorted(ts_last, side="right") - 1
                    if pos >= 0:
                        probs_by_tf[tf] = {
                            "buy": float(obj["pb_buy"][pos]),
                            "hold": float(obj["pb_hold"][pos]),
                            "sell": float(obj["pb_sell"][pos]),
                        }
                agg = aggregate_signal(probs_by_tf, timeframe, getattr(Config, "HIERARCHY_WEIGHTS", {}), lookback_scores=None)
                prediction = {
                    "consensus": (1 if agg["score"] > 0 else (-1 if agg["score"] < 0 else 0)),
                    "confidence": float(abs(agg["score"])),
                    "by_tf": probs_by_tf
                }
        except Exception:
            pass

        # Бэктест на окне
        tuned = sv.db.load_model_params(symbol, timeframe) or {}
        bt = run_backtest(
            sv.db, sv.models, symbol, timeframe,
            limit=max(300, limit),
            signal_threshold=float(tuned.get("signal_threshold", getattr(Config, "SIGNAL_THRESHOLD", 0.6))),
            hold_margin=float(tuned.get("hold_margin", getattr(Config, "SIGNAL_HOLD_MARGIN", 0.05))),
            min_confirmed_higher=int(tuned.get("min_confirmed_higher", 0)),
            sl_atr_mult=float(active_params.get("sl_atr_mult", getattr(Config, "BT_SL_ATR", 1.0))),
            tp_atr_mult=float(active_params.get("tp_atr_mult", getattr(Config, "BT_TP_ATR", 2.0))),
            max_bars_in_trade=int(active_params.get("max_bars_in_trade", getattr(Config, "BT_MAX_BARS", 200))),
        )

        # Реальные сделки бота (оверлей)
        start_ts = df.index[0].to_pydatetime()
        end_ts = df.index[-1].to_pydatetime()
        real_trades = sv.db.get_trades(limit=None, network=network, symbol=symbol, since=start_ts, until=end_ts, origin="bot")
        bot_markers = []
        for t in real_trades:
            if t.get("entry_time"):
                bot_markers.append({
                    "time": pd.to_datetime(t["entry_time"]).isoformat(),
                    "type": "bot_entry_buy" if (t.get("side", "").upper() == "BUY") else "bot_entry_sell",
                    "note": f"BOT {t.get('side', '').upper()} {float(t.get('entry_price') or 0.0):.2f}",
                    "color": "#00BCD4"
                })
            if t.get("exit_time"):
                bot_markers.append({
                    "time": pd.to_datetime(t["exit_time"]).isoformat(),
                    "type": "bot_exit",
                    "note": f"BOT EXIT {float(t.get('exit_price') or 0.0):.2f} PnL {float(t.get('pnl_percent') or 0.0):.2f}%",
                    "color": "#546E7A"
                })

        # Новости в окне TF
        news_used = []
        try:
            windows_min = getattr(Config, "NEWS_WINDOWS_BY_TF", {}).get(timeframe, [])
            lookback_min = max(windows_min) if windows_min else 0
            if lookback_min > 0:
                since_news = end_ts - timedelta(minutes=int(lookback_min))
                df_news = sv.db.news_since(since_news, limit=2000)
                if df_news is not None and not df_news.empty:
                    df_news = df_news[df_news["published_at"] <= end_ts]
                    base = (symbol.split("/")[0] if "/" in symbol else symbol).upper()

                    def match_sym(symcsv: str) -> bool:
                        if not symcsv:
                            return True
                        try:
                            items = [x.strip().upper() for x in str(symcsv).split(",") if x.strip()]
                            return (base in items)
                        except Exception:
                            return True

                    df_news = df_news[df_news["symbols"].apply(match_sym)]
                    news_used = [{
                        "time": pd.to_datetime(r["published_at"]).isoformat() if pd.notna(r["published_at"]) else None,
                        "provider": r.get("provider"),
                        "title": r.get("title"),
                        "url": r.get("url"),
                        "sentiment": float(r.get("sentiment")) if r.get("sentiment") is not None else None,
                        "symbols": r.get("symbols") or ""
                    } for _, r in df_news.sort_values("published_at", ascending=False).iterrows()]
        except Exception:
            news_used = []

        # Резюме
        dir_map = {-1: "продажа", 0: "ожидание", 1: "покупка"}
        consensus = int(prediction.get("consensus", 0))
        conf = float(prediction.get("confidence", 0.0))
        last_close = float(df["close"].iloc[-1])
        summary = f"Текущая цена {last_close:.2f}. Рекомендация ИИ: {dir_map.get(consensus, 'ожидание')} (уверенность {conf*100:.0f}%). "
        if bt.get("stats", {}).get("count", 0) > 0:
            summary += f"Бэктест: сделок {bt['stats']['count']}, winrate {bt['stats']['winrate']:.0f}%."
        else:
            summary += "На окне сигналов не было."

        candles = [{
            "time": idx.isoformat(),
            "open": float(r["open"]),
            "high": float(r["high"]),
            "low": float(r["low"]),
            "close": float(r["close"]),
            "volume": float(r["volume"])
        } for idx, r in df.iterrows()]

        return jsonify({"data": {
            "trained": True,
            "timeframe": timeframe,
            "candles": candles,
            "indicators": indicators,
            "patterns": patterns[-100:],
            "opportunities": opportunities[-100:],
            "prediction": prediction,
            "trades": bt.get("trades", []),
            "markers": bt.get("markers", []),
            "bot_markers": bot_markers,
            "indicator_panels": indicator_panels,
            "signal_panel": signal_panel,
            "news_used": news_used,
            "summary": summary
        }})