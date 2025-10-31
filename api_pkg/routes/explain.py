from datetime import timedelta
import pandas as pd
from flask import jsonify, request, current_app

from config import Config
from precompute_cache import build_precompute
from signal_engine import aggregate_signal, decide_entry, _tf_score_from_pb
from indicators_panels import _rsi, _stoch, _macd, _ema


def _sv():
    return current_app.extensions["services"]


def register(bp):
    @bp.route("/explain_signal", methods=["GET"])
    def explain_signal():
        sv = _sv()
        symbol = request.args.get("symbol")
        timeframe = request.args.get("timeframe", "15m")
        time_iso = request.args.get("time")
        if not symbol or not time_iso:
            return jsonify({"ok": False, "message": "symbol and time are required"}), 400
        try:
            t_dt = pd.to_datetime(time_iso)
        except Exception:
            return jsonify({"ok": False, "message": "invalid time format"}), 400

        precomp = build_precompute(sv.db, sv.models, symbol, timeframe, limit=5000)
        if precomp is None:
            return jsonify({"ok": False, "message": "no precompute/model"}), 400

        X_idx = precomp["X_idx"]
        pos = X_idx.searchsorted(t_dt, side="right") - 1
        if pos < 0:
            return jsonify({"ok": False, "message": "time outside range"}), 400

        ts = X_idx[pos]
        df_use = precomp["df_use"]
        close_price = float(df_use.loc[ts, "close"])
        base = precomp["base"]
        higher = precomp["higher"]
        probs_by_tf = {timeframe: {
            "buy": float(base["pb_buy"][pos]), "hold": float(base["pb_hold"][pos]), "sell": float(base["pb_sell"][pos]),
        }}
        for tf, obj in higher.items():
            idx_h = obj["idx"]
            hpos = idx_h.searchsorted(ts, side="right") - 1
            if hpos >= 0:
                probs_by_tf[tf] = {
                    "buy": float(obj["pb_buy"][hpos]),
                    "hold": float(obj["pb_hold"][hpos]),
                    "sell": float(obj["pb_sell"][hpos]),
                }

        weights_cfg = getattr(Config, "HIERARCHY_WEIGHTS", {})
        agg = aggregate_signal(probs_by_tf, timeframe, weights_cfg, lookback_scores=None)
        base_pb = probs_by_tf.get(timeframe, {"buy": 0.0, "hold": 0.0, "sell": 0.0})

        sp = sv.db.get_signal_profiles()
        active = sp["active"]
        prof = sp["profiles"].get(active, {})
        entry_th = float(prof.get("entry_threshold", getattr(Config, "SIG_ENTRY_THRESHOLD", 0.6)))
        min_sup = float(prof.get("min_support", getattr(Config, "SIG_MIN_SUPPORT", 0.1)))
        hold_m = float(prof.get("hold_margin_min", getattr(Config, "SIG_HOLD_MARGIN_MIN", 0.02)))

        ok, dir_sig, strength = decide_entry(agg, base_pb, entry_threshold=entry_th, min_support=min_sup, hold_margin_min=hold_m)
        dir_map = {-1: "SELL", 0: "HOLD", 1: "BUY"}
        decision = dir_map.get(dir_sig if ok else 0, "HOLD")

        def w_of(tf): return float(weights_cfg.get(tf, 1.0))
        tf_rows = []
        for tf, pb in probs_by_tf.items():
            tf_rows.append({
                "tf": tf, "weight": w_of(tf),
                "pb_buy": float(pb["buy"]), "pb_hold": float(pb["hold"]), "pb_sell": float(pb["sell"]),
                "score_tf": float(_tf_score_from_pb(pb))
            })
        tf_rows.sort(key=lambda r: (-r["weight"], -abs(r["score_tf"])))

        hist = df_use.loc[:ts].tail(400)
        snap = {}
        try:
            rsi_val = float(_rsi(hist["close"], 14).iloc[-1])
            st = _stoch(hist, 14, 3, 3)
            st_k = float(st["k"].iloc[-1]); st_d = float(st["d"].iloc[-1])
            mac = _macd(hist["close"], 12, 26, 9)
            mac_hist = float(mac["hist"].iloc[-1])
            ema50 = float(_ema(hist["close"], 50).iloc[-1])
            ema200 = float(_ema(hist["close"], 200).iloc[-1])
            snap = {"rsi14": rsi_val, "stoch_k": st_k, "stoch_d": st_d, "macd_hist": mac_hist, "ema50": ema50, "ema200": ema200}
        except Exception:
            pass

        lines = []
        lines.append(f"Бар: {ts.isoformat()}, цена закрытия {close_price:.4f}.")
        lines.append(f"Итоговый скор: {agg['score']:.3f} (поддержка старших ТФ {agg['support']:.2f}). Активный профиль: entry>={entry_th:.2f}, support>={min_sup:.2f}, hold_margin>={hold_m:.2f}.")
        margin_hold = max(base_pb["buy"], base_pb["sell"]) - base_pb["hold"]
        conds = []
        conds.append(f"|score| {'>=' if abs(agg['score'])>=entry_th else '<'} {entry_th:.2f}")
        conds.append(f"support {'>=' if agg['support']>=min_sup else '<'} {min_sup:.2f}")
        conds.append(f"hold_margin({margin_hold:.2f}) {'>=' if margin_hold>=hold_m else '<'} {hold_m:.2f}")
        lines.append("Условия входа: " + ", ".join(conds) + f" -> решение: {decision}.")
        lines.append("Вероятности на базовом ТФ: buy={:.2f}, hold={:.2f}, sell={:.2f}.".format(base_pb['buy'], base_pb['hold'], base_pb['sell']))

        return jsonify({
            "ok": True,
            "data": {
                "time": ts.isoformat(),
                "decision": decision,
                "score": float(agg["score"]),
                "support": float(agg["support"]),
                "thresholds": {"entry": entry_th, "min_support": min_sup, "hold_margin_min": hold_m},
                "base_probs": base_pb,
                "per_timeframe": tf_rows,
                "indicators": snap,
                "text": "\n".join(lines)
            }
        })