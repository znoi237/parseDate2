from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from config import Config
from features import build_features


@dataclass
class TrainResult:
    timeframe: str
    n_samples: int
    n_features: int
    classes: List[int]
    acc: Optional[float]
    meta: Dict[str, Any]


def _make_labels(close: pd.Series, horizon: int = 1, eps: float = 0.0) -> pd.Series:
    fwd = close.shift(-horizon) / close - 1.0
    y = pd.Series(0, index=close.index, dtype=int)
    y[fwd > eps] = 1
    y[fwd < -eps] = -1
    return y


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


class Trainer:
    """
    - Тех.фичи: features.build_features
    - Фундаментал: news_features.aggregate_news_features (если доступно)
    - Классификатор: LogisticRegression + StandardScaler
    - Сохранение: bundle целиком в model_blob (совместимо с db_pkg/models_store.py), с перезаписью
    - Параллель: обучение по таймфреймам в ThreadPoolExecutor (TRAIN_MAX_WORKERS)
    """

    def __init__(self, db):
        self.db = db

    def _save_bundle(self, symbol: str, timeframe: str, bundle: Dict[str, Any], *, last_full_end=None):
        # Удаляем прошлую запись, если поддерживается
        try:
            if hasattr(self.db, "delete_model"):
                self.db.delete_model(symbol, timeframe)
        except Exception:
            pass

        # Ретрай на случай SQLite busy/locked
        algo = "logreg_v1"
        classes = sorted({-1, 0, 1})
        feature_names = bundle.get("feature_names", [])
        last_err: Optional[Exception] = None
        for attempt in range(5):
            try:
                self.db.save_model(
                    symbol=symbol,
                    timeframe=timeframe,
                    algo=algo,
                    model=bundle,                 # bundle целиком в blob
                    classes=classes,
                    features=feature_names,
                    last_full_end=last_full_end,
                    last_incr_end=None,
                    metrics={},
                )
                return
            except Exception as e:
                last_err = e
                time.sleep(0.1 * (attempt + 1))
        if last_err:
            raise last_err

    def _train_one_tf(
        self,
        symbol: str,
        timeframe: str,
        years: int,
        job_id: Optional[int],
        mode: str,
    ) -> TrainResult:
        df = self.db.load_ohlcv(symbol, timeframe, since=None, limit=None)
        if df is None or df.empty:
            return TrainResult(timeframe, 0, 0, [], None, {"reason": "no_data"})

        if isinstance(df.index, pd.DatetimeIndex) and years and years > 0:
            cutoff = df.index.max() - pd.Timedelta(days=365 * years)
            df = df[df.index >= cutoff]
            if df.empty:
                return TrainResult(timeframe, 0, 0, [], None, {"reason": "no_data_after_cut"})

        feats_settings: Dict[str, Any] = {}
        try:
            meta = self.db.load_model(symbol, timeframe) or {}
            feats_settings = (meta.get("meta") or {}).get("features_settings") or {}
        except Exception:
            feats_settings = {}
        feats_settings.setdefault("label_horizon", 1)
        feats_settings.setdefault("label_eps", 0.0)

        # Тех.фичи
        X_tech = build_features(df, feats_settings)
        if X_tech is None or X_tech.empty:
            return TrainResult(timeframe, 0, 0, [], None, {"reason": "no_features"})

        # Фундаментальные фичи
        X_news = _build_news_features_safe(self.db, df, timeframe)
        if X_news is not None and not X_news.empty:
            X = X_tech.join(X_news, how="left")
        else:
            X = X_tech.copy()

        X = X.replace([np.inf, -np.inf], np.nan).fillna(0.0)

        # Метки
        y = _make_labels(
            df["close"].astype(float),
            horizon=int(feats_settings.get("label_horizon", 1)),
            eps=float(feats_settings.get("label_eps", 0.0)),
        )
        XY = X.join(y.rename("y"), how="inner").replace([np.inf, -np.inf], np.nan).dropna()
        if XY.empty:
            return TrainResult(timeframe, 0, 0, [], None, {"reason": "no_samples_after_clean"})

        Xc = XY.drop(columns=["y"])
        yc = XY["y"].astype(int)

        # Скейлер и Модель
        scaler = StandardScaler()
        Xs = scaler.fit_transform(Xc.values)
        clf = LogisticRegression(
            max_iter=int(getattr(Config, "LR_MAX_ITER", 1000)),
            C=float(getattr(Config, "LR_C", 1.0)),
            class_weight=getattr(Config, "LR_CLASS_WEIGHT", None),
            solver=str(getattr(Config, "LR_SOLVER", "lbfgs")),
        )
        clf.fit(Xs, yc.values)

        # Оценка на обучении (для отчёта)
        try:
            acc = float((clf.predict(Xs) == yc.values).mean())
        except Exception:
            acc = None

        feature_names = list(map(str, Xc.columns))
        last_full_end = df.index.max().to_pydatetime() if isinstance(df.index, pd.DatetimeIndex) else None
        bundle = {
            "model": clf,
            "scaler": scaler,
            "feature_names": feature_names,
            "features_settings": feats_settings,
            "meta": {
                "symbol": symbol,
                "timeframe": timeframe,
                "n_samples": int(len(Xc)),
                "n_features": int(len(feature_names)),
                "acc_train": acc,
            }
        }

        self._save_bundle(symbol, timeframe, bundle, last_full_end=last_full_end)

        return TrainResult(
            timeframe=timeframe,
            n_samples=int(len(Xc)),
            n_features=int(len(feature_names)),
            classes=sorted(list({int(v) for v in yc.unique()})),
            acc=acc,
            meta=bundle["meta"],
        )

    def train_symbol(self, symbol: str, timeframes: List[str], years: int, job_id: Optional[int] = None, mode: str = "auto") -> Dict[str, Any]:
        # Параллель по ТФ
        max_workers = max(1, int(getattr(Config, "TRAIN_MAX_WORKERS", 2)))
        tfs = list(timeframes)

        results: List[TrainResult] = []
        if len(tfs) <= 1 or max_workers == 1:
            # Последовательно
            for tf in tfs:
                try:
                    r = self._train_one_tf(symbol, tf, years, job_id=job_id, mode=mode)
                except Exception as e:
                    r = TrainResult(tf, 0, 0, [], None, {"reason": f"exception:{e}"})
                results.append(r)
        else:
            # Пул потоков
            futures = {}
            with ThreadPoolExecutor(max_workers=min(len(tfs), max_workers)) as pool:
                for tf in tfs:
                    futures[pool.submit(self._train_one_tf, symbol, tf, years, job_id, mode)] = tf
                for fut in as_completed(futures):
                    tf = futures[fut]
                    try:
                        r = fut.result()
                    except Exception as e:
                        r = TrainResult(tf, 0, 0, [], None, {"reason": f"exception:{e}"})
                    results.append(r)

            # Сортируем по порядку запрошенных ТФ
            order = {tf: i for i, tf in enumerate(tfs)}
            results.sort(key=lambda r: order.get(r.timeframe, 1_000_000))

        return {
            "symbol": symbol,
            "years": years,
            "results": [
                {
                    "timeframe": r.timeframe,
                    "n_samples": r.n_samples,
                    "n_features": r.n_features,
                    "classes": r.classes,
                    "acc_train": r.acc,
                    "meta": r.meta,
                }
                for r in results
            ],
        }
