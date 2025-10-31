from __future__ import annotations
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd

from features import build_features
from .utils import align_features_for_bundle, expected_n_features, tf_score_from_probs
from config import Config


def get_model_bundle(db, symbol: str, timeframe: str) -> Dict[str, Any]:
    """
    Совместимый загрузчик бандла.
    - Если в models_store лежит bundle целиком в model_blob (dict), разворачиваем его в плоский словарь.
    - Если лежит только модель, возвращаем минимум (модель, feature_names), scaler может отсутствовать.
    """
    m = db.load_model(symbol, timeframe) or {}
    blob = m.get("model")
    # кейс: в model_blob сохранён весь bundle (dict)
    if isinstance(blob, dict):
        out = dict(blob)  # копия
        # подстрахуем feature_names
        if "feature_names" not in out:
            out["feature_names"] = out.get("features") or m.get("features") or []
        return out
    # кейс: сохранена только модель
    return {
        "model": blob,
        "scaler": m.get("scaler"),  # вероятно None при старом формате
        "feature_names": m.get("features") or [],
        "features_settings": (m.get("meta") or {}).get("features_settings") if isinstance(m.get("meta"), dict) else {},
        "meta": m.get("meta") or {},
    }


def _build_news_features_safe(db, df: pd.DataFrame, timeframe: str) -> Optional[pd.DataFrame]:
    try:
        from news_features import aggregate_news_features
    except Exception:
        return None
    try:
        if not isinstance(df.index, pd.DatetimeIndex) or df.index.size == 0:
            return None
        feats = aggregate_news_features(db, df.index, timeframe)
        if feats is None or feats.empty:
            return None
        feats = feats.reindex(df.index, method="pad").fillna(0.0)
        feats = feats.replace([np.inf, -np.inf], 0.0).fillna(0.0)
        return feats
    except Exception:
        return None


def predict_proba_for_tf(db, symbol: str, timeframe: str, df_window: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """
    Вернёт вероятности на каждом баре df_window для классов {-1,0,1}.
    Формат:
      { "idx": DatetimeIndex, "pb_buy": np.ndarray, "pb_hold": np.ndarray, "pb_sell": np.ndarray }
    """
    bundle = get_model_bundle(db, symbol, timeframe)
    clf = bundle.get("model")
    scaler = bundle.get("scaler")
    if clf is None or df_window is None or df_window.empty:
        return None

    feats_settings = bundle.get("features_settings") or {}

    # Совпадение фичей с обучением: тех + фундаментал
    X_tech = build_features(df_window, feats_settings) or pd.DataFrame(index=df_window.index)
    X_news = _build_news_features_safe(db, df_window, timeframe)
    if X_news is not None and not X_news.empty:
        X = X_tech.join(X_news, how="left")
    else:
        X = X_tech

    X = X.replace([np.inf, -np.inf], np.nan).fillna(0.0)

    feature_names_saved = bundle.get("feature_names") or bundle.get("features") or []
    X_aligned, _ = align_features_for_bundle(X, feature_names_saved, scaler)

    Xs = X_aligned.values
    if scaler is not None:
        try:
            Xs = scaler.transform(Xs)
        except Exception:
            n_exp = expected_n_features(scaler) or Xs.shape[1]
            if Xs.shape[1] > n_exp:
                Xs = Xs[:, :n_exp]
            elif Xs.shape[1] < n_exp:
                pad = np.zeros((Xs.shape[0], n_exp - Xs.shape[1]), dtype=float)
                Xs = np.hstack([Xs, pad])
            Xs = scaler.transform(Xs)

    try:
        P = clf.predict_proba(Xs)
    except Exception:
        if hasattr(clf, "decision_function"):
            dec = clf.decision_function(Xs)
            if isinstance(dec, np.ndarray) and dec.ndim == 1:
                z = 1 / (1 + np.exp(-np.clip(dec, -10, 10)))
                P = np.vstack([1 - z, z]).T
            else:
                ex = np.exp(dec - np.max(dec, axis=1, keepdims=True))
                P = ex / np.clip(ex.sum(axis=1, keepdims=True), 1e-9, None)
        else:
            P = np.zeros((len(df_window), 3), dtype=float)
            P[:, 1] = 1.0

    classes = getattr(clf, "classes_", None) or []
    idx_map = {int(c): i for i, c in enumerate(classes)}

    n = len(df_window)
    pb_buy = np.zeros(n, dtype=float)
    pb_hold = np.zeros(n, dtype=float)
    pb_sell = np.zeros(n, dtype=float)

    if 1 in idx_map:
        pb_buy = P[:, idx_map[1]]
    if 0 in idx_map:
        pb_hold = P[:, idx_map[0]]
    if -1 in idx_map:
        pb_sell = P[:, idx_map[-1]]

    if 0 not in idx_map:
        rest = 1.0 - (pb_buy + pb_sell)
        pb_hold = np.clip(rest, 0.0, 1.0)

    s = pb_buy + pb_hold + pb_sell
    s[s == 0.0] = 1.0
    pb_buy /= s; pb_hold /= s; pb_sell /= s

    return {
        "idx": df_window.index,
        "pb_buy": pb_buy,
        "pb_hold": pb_hold,
        "pb_sell": pb_sell
    }


def predict_hierarchical(db, symbol: str, timeframes: List[str], latest_windows: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
    by_tf: Dict[str, Dict[str, float]] = {}
    for tf in timeframes:
        dfw = latest_windows.get(tf)
        if dfw is None or dfw.empty:
            continue
        res = predict_proba_for_tf(db, symbol, tf, dfw.tail(600))
        if not res:
            continue
        pb = {
            "buy": float(res["pb_buy"][-1]) if len(res["pb_buy"]) else 0.0,
            "hold": float(res["pb_hold"][-1]) if len(res["pb_hold"]) else 0.0,
            "sell": float(res["pb_sell"][-1]) if len(res["pb_sell"]) else 0.0,
        }
        by_tf[tf] = pb

    if not by_tf:
        return {"consensus": 0, "confidence": 0.0, "by_tf": {}}

    weights_cfg = getattr(Config, "HIERARCHY_WEIGHTS", {})
    total_w = 0.0
    agg_score = 0.0
    for tf, pb in by_tf.items():
        w = float(weights_cfg.get(tf, 1.0))
        total_w += w
        agg_score += w * tf_score_from_probs(pb)
    if total_w <= 0.0:
        total_w = 1.0
    score = agg_score / total_w

    consensus = 1 if score > 0 else (-1 if score < 0 else 0)
    confidence = float(abs(score))

    return {"consensus": consensus, "confidence": confidence, "by_tf": by_tf}
