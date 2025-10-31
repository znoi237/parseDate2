from __future__ import annotations
from typing import Dict, Any, List, Optional
import inspect


def save_model_compat(
    db,
    symbol: str,
    timeframe: str,
    clf,
    scaler,
    feature_names: List[str],
    feats_settings: Dict[str, Any],
    meta: Dict[str, Any],
) -> bool:
    """
    Сохранение модели с поддержкой разных сигнатур DatabaseManager.save_model.
    Возвращает True, если сохранение прошло успешно.
    """
    classes = list(getattr(clf, "classes_", [-1, 0, 1])) if clf is not None else [-1, 0, 1]

    # Попытка №1: новое API — одним bundle
    bundle = {
        "model": clf,
        "scaler": scaler,
        "feature_names": feature_names,
        "features_settings": feats_settings,
        "meta": meta
    }
    try:
        sig = inspect.signature(db.save_model)
        params = set(sig.parameters.keys())
        if "bundle" in params:
            db.save_model(symbol, timeframe, bundle=bundle)
            return True
    except Exception:
        try:
            db.save_model(symbol, timeframe, bundle=bundle)
            return True
        except Exception:
            pass

    # Попытка №2: старое API — именованные аргументы
    try:
        sig = inspect.signature(db.save_model)
        params = set(sig.parameters.keys())
        kwargs: Dict[str, Any] = {}
        if "symbol" in params: kwargs["symbol"] = symbol
        if "timeframe" in params: kwargs["timeframe"] = timeframe
        if "model" in params: kwargs["model"] = clf
        if "classes" in params: kwargs["classes"] = classes
        if "features" in params: kwargs["features"] = feature_names
        if "feature_names" in params and "features" not in params: kwargs["feature_names"] = feature_names
        if "scaler" in params: kwargs["scaler"] = scaler
        if "features_settings" in params: kwargs["features_settings"] = feats_settings
        if "meta" in params: kwargs["meta"] = meta
        if kwargs:
            db.save_model(**kwargs)
            return True
    except Exception:
        pass

    # Попытка №3: позиционный вызов по порядку сигнатуры
    try:
        sig = inspect.signature(db.save_model)
        names = list(sig.parameters.keys())
        if names and names[0] in ("self",):
            names = names[1:]
        value_map = {
            "symbol": symbol,
            "timeframe": timeframe,
            "model": clf,
            "classes": classes,
            "features": feature_names,
            "feature_names": feature_names,
            "scaler": scaler,
            "features_settings": feats_settings,
            "meta": meta,
        }
        args = [value_map.get(n, None) for n in names]
        db.save_model(*args)
        return True
    except Exception:
        pass

    return False