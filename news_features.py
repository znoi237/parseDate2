import pandas as pd
import numpy as np
from datetime import timedelta
from typing import List
from config import Config
from database import DatabaseManager

def _windows_for_tf(timeframe: str) -> List[int]:
    # окна в минутах
    mapping = getattr(Config, "NEWS_WINDOWS_BY_TF", None)
    if mapping and timeframe in mapping:
        return mapping[timeframe]
    if timeframe == "15m":
        return [60, 180, 720]           # 1ч, 3ч, 12ч
    if timeframe == "1h":
        return [180, 720, 1440]         # 3ч, 12ч, 1д
    if timeframe == "4h":
        return [720, 2880, 10080]       # 12ч, 2д, 7д
    if timeframe == "1d":
        return [1440, 4320, 10080]      # 1д, 3д, 7д
    if timeframe == "1w":
        return [10080, 43200]           # 1н, 30н
    return [60, 180, 720]

def aggregate_news_features(
    db: DatabaseManager,
    ohlc_index: pd.DatetimeIndex,
    timeframe: str,
) -> pd.DataFrame:
    """
    Возвращает матрицу фундаментальных признаков по новостям,
    выровненную по индексам OHLC (open_time).
    Признаки на каждый бар: для каждого окна (в минутах):
      - news_ct_<win>: количество новостей в окне (t - win, t]
      - news_sent_mean_<win>: средний сентимент в окне
    """
    if ohlc_index is None or len(ohlc_index) == 0:
        return pd.DataFrame(index=pd.DatetimeIndex([], name="open_time"))

    wins = _windows_for_tf(timeframe)
    max_win = max(wins)

    start_time = pd.Timestamp(ohlc_index[0]).to_pydatetime() - timedelta(minutes=max_win + 60)
    end_time = pd.Timestamp(ohlc_index[-1]).to_pydatetime()

    # Загружаем все новости с запасом (лимит большой, для локальной БД ок)
    news_df = db.news_since(start_time, limit=100000)
    if news_df is None or news_df.empty:
        cols = []
        for w in wins:
            cols += [f"news_ct_{w}", f"news_sent_mean_{w}"]
        return pd.DataFrame(0.0, index=ohlc_index, columns=cols)

    news_df = news_df[news_df["published_at"] <= end_time]
    if news_df.empty:
        cols = []
        for w in wins:
            cols += [f"news_ct_{w}", f"news_sent_mean_{w}"]
        return pd.DataFrame(0.0, index=ohlc_index, columns=cols)

    # Приводим к минутной сетке
    news_df = news_df.copy()
    news_df["published_at"] = pd.to_datetime(news_df["published_at"])
    # pandas: 'T' устарел, используем 'min'
    news_df["minute"] = news_df["published_at"].dt.floor("min")

    # Считаем по минутам количество и сумму сентимента
    per_min = news_df.groupby("minute").agg(
        news_ct=("sentiment", "count"),
        sent_sum=("sentiment", "sum")
    ).sort_index()

    # Равномерная минутная шкала
    minute_index = pd.date_range(
        start=start_time.replace(second=0, microsecond=0),
        end=end_time.replace(second=0, microsecond=0),
        freq="min"
    )
    per_min = per_min.reindex(minute_index).fillna(0.0)

    # Для каждого окна — роллинг по минутам
    feats = pd.DataFrame(index=minute_index)
    for w in wins:
        ct = per_min["news_ct"].rolling(window=w, min_periods=1).sum()
        sent_sum = per_min["sent_sum"].rolling(window=w, min_periods=1).sum()
        sent_mean = sent_sum / np.maximum(ct, 1.0)
        feats[f"news_ct_{w}"] = ct
        feats[f"news_sent_mean_{w}"] = sent_mean

    # Выровнять по индексам OHLC (open_time) — берём значения на момент open_time
    feats = feats.reindex(ohlc_index, method="pad").fillna(0.0)
    feats = feats.replace([np.inf, -np.inf], 0.0).fillna(0.0)
    return feats