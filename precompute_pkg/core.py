import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, List, Optional

from config import Config
from features import build_features

# -------------------- Helpers --------------------

def _extract_model_bundle(db, models, symbol: str, timeframe: str) -> Dict[str, Any]:
    """
    Пытаемся достать обученный пакет модели из БД (приоритет) или менеджера моделей.
    Ожидаемые ключи (любые доступны частично):
      - model: классификатор со свойствами .predict_proba, .classes_
      - scaler: StandardScaler (или совместимый)
      - feature_names: список фич, использовавшихся при обучении
      - features_settings: настройки построения фич
    """
    bundle = (db.load_model(symbol, timeframe) or {}).copy()
    if not bundle or "model" not in bundle:
        # на всякий случай попробуем через менеджер (если он так умеет)
        if hasattr(models, "get_model_bundle"):
            mb = models.get_model_bundle(symbol, timeframe) or {}
            bundle.update(mb)
    # унифицируем возможные варианты имён
    if "scaler" not in bundle:
        for k in ("scaler_b", "scaler_base"):
            if k in bundle:
                bundle["scaler"] = bundle[k]
                break
    if "features_settings" not in bundle:
        # если настройки фич где-то в meta
        meta = bundle.get("meta") or {}
        if "features_settings" in meta:
            bundle["features_settings"] = meta["features_settings"]
    if "feature_names" not in bundle:
        meta = bundle.get("meta") or {}
        if "feature_names" in meta:
            bundle["feature_names"] = meta["feature_names"]
    return bundle


def _expected_feature_names(bundle: Dict[str, Any], scaler) -> Optional[List[str]]:
    """
    Возвращает ожидаемый список фич, если он сохранён вместе с моделью.
    """
    fn = bundle.get("feature_names")
    if isinstance(fn, (list, tuple)) and len(fn) > 0:
        return list(fn)
    # иначе None — перейдём к эвристикам по числу признаков
    return None


def _expected_n_features(scaler) -> Optional[int]:
    """
    Возвращает ожидаемое количество признаков из scaler, если возможно.
    """
    if scaler is None:
        return None
    n = getattr(scaler, "n_features_in_", None)
    if isinstance(n, (int, np.integer)) and n > 0:
        return int(n)
    # sklearn >= 1.0: mean_ присутствует у StandardScaler
    m = getattr(scaler, "mean_", None)
    if isinstance(m, np.ndarray) and m.ndim == 1 and m.size > 0:
        return int(m.size)
    return None


def _align_features(
    X_df: pd.DataFrame,
    feature_names_saved: Optional[List[str]],
    scaler
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Выравнивает признаки под ожидаемые моделью:
      - если есть feature_names_saved: добавляет отсутствующие колонки (0.0), упорядочивает, лишние отбрасывает;
      - иначе ориентируется на количество признаков scaler: берёт стабильный порядок (лексикографически отсортированные имена),
        при нехватке — дополняет нулевыми столбцами, при избытке — обрезает.
    Возвращает (X_aligned, used_names).
    """
    X_df = X_df.copy()
    X_df = X_df.replace([np.inf, -np.inf], np.nan).fillna(0.0)

    if feature_names_saved:
        # добавить недостающие и упорядочить
        for col in feature_names_saved:
            if col not in X_df.columns:
                X_df[col] = 0.0
        X_aligned = X_df[feature_names_saved].astype(float)
        return X_aligned, list(feature_names_saved)

    # фолбэк: по количеству фич у scaler
    n_exp = _expected_n_features(scaler)
    cols_sorted = sorted(list(map(str, X_df.columns)))
    # сохраним исходное числовое представление, но порядок по имени — стабилен
    X_df_sorted = X_df[cols_sorted].astype(float)

    if n_exp is None or n_exp == X_df_sorted.shape[1]:
        return X_df_sorted, list(X_df_sorted.columns)

    if X_df_sorted.shape[1] > n_exp:
        # обрежем лишнее (слева направо по алфавиту имён)
        keep_cols = cols_sorted[:n_exp]
        return X_df_sorted[keep_cols], keep_cols

    # если признаков меньше — дополним нулями
    used_cols = cols_sorted.copy()
    pad_needed = n_exp - X_df_sorted.shape[1]
    for i in range(pad_needed):
        pad_name = f"_pad_{i}"
        X_df_sorted[pad_name] = 0.0
        used_cols.append(pad_name)
    return X_df_sorted[used_cols], used_cols


def _proba_to_buy_hold_sell(clf, proba: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Преобразует predict_proba к (pb_buy, pb_hold, pb_sell) по классам 1, 0, -1.
    Держит корректность, даже если модель бинарная (нет одного/двух классов).
    """
    n = proba.shape[0]
    pb_buy = np.zeros(n, dtype=float)
    pb_hold = np.zeros(n, dtype=float)
    pb_sell = np.zeros(n, dtype=float)

    classes = getattr(clf, "classes_", None)
    if classes is None:
        # нет информации — примем всё нейтральным
        return pb_buy, pb_hold, pb_sell

    # построим индекс классов
    idx_map = {int(c): i for i, c in enumerate(classes)}

    if 1 in idx_map:
        pb_buy = proba[:, idx_map[1]]
    if 0 in idx_map:
        pb_hold = proba[:, idx_map[0]]
    if -1 in idx_map:
        pb_sell = proba[:, idx_map[-1]]

    # если бинарная: восполним hold как остаток
    if 0 not in idx_map:
        rest = 1.0 - (pb_buy + pb_sell)
        pb_hold = np.clip(rest, 0.0, 1.0)

    # нормализовать (на всякий случай) до суммы ~1
    s = pb_buy + pb_hold + pb_sell
    s[s == 0.0] = 1.0
    pb_buy /= s; pb_hold /= s; pb_sell /= s

    return pb_buy, pb_hold, pb_sell


def _calc_bundle_proba(
    db, models,
    symbol: str, timeframe: str,
    limit: int
) -> Tuple[pd.DatetimeIndex, Dict[str, Any], pd.DataFrame]:
    """
    Строит proba для заданного ТФ с аккуратным выравниванием фич.
    Возвращает: (index, result_dict, df_used)
      result_dict: {"pb_buy": np.ndarray, "pb_hold": np.ndarray, "pb_sell": np.ndarray, "idx": index}
    """
    # 1) История
    df = db.load_ohlcv(symbol, timeframe)
    if df is None or df.empty:
        return pd.DatetimeIndex([]), {"pb_buy": np.array([]), "pb_hold": np.array([]), "pb_sell": np.array([]), "idx": pd.DatetimeIndex([])}, pd.DataFrame()

    df = df.tail(max(1000, limit))  # берём больше, чтобы не обрезать контекст

    # 2) Модельный пакет
    bundle = _extract_model_bundle(db, models, symbol, timeframe)
    clf = bundle.get("model")
    scaler = bundle.get("scaler")
    feats_settings = bundle.get("features_settings") or {}
    if clf is None:
        # нет модели — возвращаем "пустышку"
        return df.index, {"pb_buy": np.zeros(len(df)), "pb_hold": np.ones(len(df)), "pb_sell": np.zeros(len(df)), "idx": df.index}, df

    # 3) Фичи + выравнивание
    X = build_features(df, feats_settings)
    feat_names_saved = _expected_feature_names(bundle, scaler)
    X_aligned, _ = _align_features(X, feat_names_saved, scaler)

    # 4) Масштабирование
    Xs = X_aligned.values
    if scaler is not None:
        try:
            Xs = scaler.transform(Xs)
        except ValueError:
            # ещё одна попытка на случай несовпадения размеров — перестраховка
            n_exp = _expected_n_features(scaler) or X_aligned.shape[1]
            if X_aligned.shape[1] != n_exp:
                # приведём размерность жёстко
                cols = list(X_aligned.columns)
                if len(cols) >= n_exp:
                    Xs = scaler.transform(X_aligned[cols[:n_exp]].values)
                else:
                    pad = np.zeros((Xs.shape[0], n_exp - X_aligned.shape[1]), dtype=float)
                    Xs = np.hstack([Xs, pad])
                    Xs = scaler.transform(Xs)
            else:
                Xs = scaler.transform(Xs)

    # 5) Предсказание вероятностей
    try:
        P = clf.predict_proba(Xs)
    except Exception:
        # если вдруг модель без proba — подстрахуемся через decision_function (условно)
        if hasattr(clf, "decision_function"):
            dec = clf.decision_function(Xs)
            # приведём к 3 вероятностям грубо
            if getattr(dec, "ndim", 1) == 1:
                # бинарь: dec>0 -> buy, <0 -> sell
                z = 1 / (1 + np.exp(-np.clip(dec, -10, 10)))
                P = np.vstack([1 - z, z]).T  # без hold
            else:
                # много классов: softmax
                ex = np.exp(dec - np.max(dec, axis=1, keepdims=True))
                P = ex / np.clip(ex.sum(axis=1, keepdims=True), 1e-9, None)
        else:
            # совсем без шансов — нейтраль
            P = np.zeros((len(df), 3), dtype=float)
            P[:, 1] = 1.0  # HOLD

    pb_buy, pb_hold, pb_sell = _proba_to_buy_hold_sell(clf, P)

    res = {
        "pb_buy": pb_buy,
        "pb_hold": pb_hold,
        "pb_sell": pb_sell,
        "idx": df.index
    }
    return df.index, res, df


# -------------------- Public: build_precompute --------------------

def build_precompute(
    db,
    models,
    symbol: str,
    timeframe: str,
    limit: int = 5000
) -> Optional[Dict[str, Any]]:
    """
    Строит предрасчёт вероятностей для базового и старших ТФ, возвращая структуру:
    {
      "df_use": df_base,
      "X_idx": index_base,
      "base": { "pb_buy": np.ndarray, "pb_hold": np.ndarray, "pb_sell": np.ndarray, "idx": index_base },
      "higher": {
          "1h": { "pb_buy": ..., "pb_hold": ..., "pb_sell": ..., "idx": DatetimeIndex },
          ...
      }
    }
    Возвращает None, если модель для базового ТФ не найдена и нечего считать.
    """
    # База
    idx_base, base_res, df_base = _calc_bundle_proba(db, models, symbol, timeframe, limit)
    if df_base is None or df_base.empty:
        return None

    # Старшие ТФ — возьмём из набора доступных, исключая базовый
    higher: Dict[str, Dict[str, Any]] = {}
    for tf in Config.TIMEFRAMES:
        if tf == timeframe:
            continue
        try:
            idx_h, res_h, _dfh = _calc_bundle_proba(db, models, symbol, tf, limit)
            # добавим только если есть хоть какие-то данные
            if len(res_h.get("pb_buy", [])) > 0:
                higher[tf] = {
                    "pb_buy": res_h["pb_buy"],
                    "pb_hold": res_h["pb_hold"],
                    "pb_sell": res_h["pb_sell"],
                    "idx": res_h["idx"],
                }
        except Exception:
            # не роняем весь расчёт, если нет модели для конкретного TF
            continue

    out = {
        "df_use": df_base,
        "X_idx": idx_base,
        "base": base_res,
        "higher": higher
    }
    return out