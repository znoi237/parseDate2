from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import time

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression

from indicator_settings import get_indicator_settings, sanitize_indicator_settings
from features import build_features, make_labels
from .save_compat import save_model_compat


def _feats_settings(db) -> Dict[str, Any]:
    return sanitize_indicator_settings(get_indicator_settings(db))


def _build_train_data(df: pd.DataFrame, feats_settings: Dict[str, Any]) -> Tuple[pd.DataFrame, pd.Series]:
    X = build_features(df, feats_settings)
    y = make_labels(df, horizon=1, up_threshold=0.002, down_threshold=-0.002)
    y = y.reindex(X.index).fillna(0).astype(int)
    return X, y


def _fit_model(X: pd.DataFrame, y: pd.Series) -> Tuple[StandardScaler, LogisticRegression, List[str]]:
    scaler = StandardScaler()
    Xs = scaler.fit_transform(X.values)
    clf = LogisticRegression(
        max_iter=800,
        class_weight="balanced",
        solver="lbfgs"
    )
    clf.fit(Xs, y.values)
    feature_names = list(X.columns)
    return scaler, clf, feature_names


class Trainer:
    def __init__(self, db):
        self.db = db

    def _log(self, job_id: Optional[int], level: str, phase: str, msg: str, data: Optional[Dict[str, Any]] = None):
        if not job_id:
            return
        try:
            self.db.add_training_log(job_id, level, phase, msg, data or {})
        except Exception:
            pass

    def train_symbol(self, symbol: str, timeframes: List[str], years: int, job_id: Optional[int] = None, mode: str = "auto"):
        """
        Обучение по каждому ТФ с сохранением модели в БД (совместимость со старым/новым API сохранения).
        """
        feats_settings = _feats_settings(self.db)
        since_dt = datetime.utcnow() - timedelta(days=int(max(1, years)) * 365)

        for tf in timeframes:
            try:
                self._log(job_id, "INFO", "train", f"prepare {symbol} {tf}")
                df = self.db.load_ohlcv(symbol, tf, since=since_dt)
                if df is None or df.empty or len(df) < 300:
                    self._log(job_id, "WARN", "train", f"skip {symbol} {tf}: not enough data")
                    meta = {"trained_rows": 0, "trained_at": time.time(), "symbol": symbol, "timeframe": tf, "mode": mode, "job_id": job_id}
                    ok = save_model_compat(self.db, symbol, tf, None, None, [], feats_settings, meta)
                    if ok:
                        self._log(job_id, "INFO", "train", f"saved empty model {symbol} {tf}")
                    else:
                        self._log(job_id, "ERROR", "train", f"save_model incompatible API for {symbol} {tf}")
                    continue

                X, y = _build_train_data(df, feats_settings)
                scaler, clf, feature_names = _fit_model(X, y)
                meta = {
                    "trained_rows": int(len(X)),
                    "trained_at": time.time(),
                    "symbol": symbol,
                    "timeframe": tf,
                    "mode": mode,
                    "job_id": job_id
                }
                ok = save_model_compat(self.db, symbol, tf, clf, scaler, feature_names, feats_settings, meta)
                if ok:
                    self._log(job_id, "INFO", "train", f"saved model {symbol} {tf}", {"rows": int(len(X))})
                else:
                    self._log(job_id, "ERROR", "train", f"save_model incompatible API for {symbol} {tf}")
            except Exception as e:
                self._log(job_id, "ERROR", "train", f"train fail {symbol} {tf}: {e}")