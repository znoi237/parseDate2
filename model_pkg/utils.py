from __future__ import annotations
from typing import Optional, Dict, List, Tuple
import numpy as np
import pandas as pd


def expected_n_features(scaler) -> Optional[int]:
    if scaler is None:
        return None
    n = getattr(scaler, "n_features_in_", None)
    if isinstance(n, (int, np.integer)) and n > 0:
        return int(n)
    m = getattr(scaler, "mean_", None)
    if isinstance(m, np.ndarray) and m.ndim == 1 and m.size > 0:
        return int(m.size)
    return None


def align_features_for_bundle(
    X_df: pd.DataFrame,
    feature_names_saved: Optional[List[str]],
    scaler,
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Аккуратно выровнять X_df под ожидания модели:
      - если есть feature_names_saved — добавляем недостающие столбцы (0.0), упорядочиваем и отбрасываем лишнее;
      - иначе подгоняем количество признаков под scaler: сортируем имена, обрезаем/дополняем нулями.
    """
    X_df = X_df.copy()
    X_df = X_df.replace([np.inf, -np.inf], np.nan).fillna(0.0)

    if feature_names_saved:
        for col in feature_names_saved:
            if col not in X_df.columns:
                X_df[col] = 0.0
        X_aligned = X_df[feature_names_saved].astype(float)
        return X_aligned, list(feature_names_saved)

    n_exp = expected_n_features(scaler)
    cols_sorted = sorted(list(map(str, X_df.columns)))
    X_df_sorted = X_df[cols_sorted].astype(float)

    if n_exp is None or n_exp == X_df_sorted.shape[1]:
        return X_df_sorted, list(X_df_sorted.columns)

    if X_df_sorted.shape[1] > n_exp:
        keep_cols = cols_sorted[:n_exp]
        return X_df_sorted[keep_cols], keep_cols

    used_cols = cols_sorted.copy()
    pad_needed = n_exp - X_df_sorted.shape[1]
    for i in range(pad_needed):
        pad_name = f"_pad_{i}"
        X_df_sorted[pad_name] = 0.0
        used_cols.append(pad_name)
    return X_df_sorted[used_cols], used_cols


def tf_score_from_probs(pb: Dict[str, float]) -> float:
    buy = float(pb.get("buy", 0.0))
    hold = float(pb.get("hold", 0.0))
    sell = float(pb.get("sell", 0.0))
    return (buy - sell) * (1.0 - hold)