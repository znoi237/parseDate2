from __future__ import annotations
from typing import Dict, Any, List, Optional
import pandas as pd

from .trainers import Trainer
from .predict import get_model_bundle as _get_bundle
from .predict import predict_proba_for_tf as _predict_tf
from .predict import predict_hierarchical as _predict_h


class ModelManager:
    """
    Совместимый интерфейс:
      - train_symbol(symbol, timeframes, years, job_id=None, mode="auto")
      - get_model_bundle(symbol, timeframe)
      - predict_proba_for_tf(symbol, timeframe, df_window)
      - predict_hierarchical(symbol, timeframes, latest_windows)
    """
    def __init__(self, db):
        self.db = db
        self._trainer = Trainer(db)

    # Обучение
    def train_symbol(self, symbol: str, timeframes: List[str], years: int, job_id: Optional[int] = None, mode: str = "auto"):
        return self._trainer.train_symbol(symbol, timeframes, years, job_id=job_id, mode=mode)

    # Модель/бандл
    def get_model_bundle(self, symbol: str, timeframe: str) -> Dict[str, Any]:
        return _get_bundle(self.db, symbol, timeframe)

    # Предсказания
    def predict_proba_for_tf(self, symbol: str, timeframe: str, df_window: pd.DataFrame) -> Optional[Dict[str, Any]]:
        return _predict_tf(self.db, symbol, timeframe, df_window)

    def predict_hierarchical(self, symbol: str, timeframes: List[str], latest_windows: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        return _predict_h(self.db, symbol, timeframes, latest_windows)