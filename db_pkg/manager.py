from __future__ import annotations
from typing import Any
from .conn_init import _ConnInitMixin
from .settings import _SettingsMixin
from .api_keys import _ApiKeysMixin
from .historical import _HistoricalMixin
from .models_store import _ModelsMixin
from .training_jobs import _TrainingJobsMixin
from .training_logs import _TrainingLogsMixin
from .trades import _TradesMixin
from .bots import _BotsMixin
from .news import _NewsMixin
from .model_params import _ModelParamsMixin
from .utils import to_iso as _to_iso  # re-export helper for models_store


class DatabaseManager(
    _ConnInitMixin,
    _SettingsMixin,
    _ApiKeysMixin,
    _HistoricalMixin,
    _ModelsMixin,
    _TrainingJobsMixin,
    _TrainingLogsMixin,
    _TradesMixin,
    _BotsMixin,
    _NewsMixin,
    _ModelParamsMixin,
):
    """
    Композитный менеджер БД, полностью совместимый с прежним интерфейсом.
    """
    # Пробрасываем util в виде метода, чтобы не менять логику save_model
    _to_iso = staticmethod(_to_iso)