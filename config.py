import os
import logging

def _auto_workers(env_value: str, aggressive: bool = False) -> int:
    """
    Преобразует переменную окружения в число воркеров.
    0 или не задано -> авто:
      - обычный: max(1, cpu-1), не более 32
      - агрессивный: max(4, cpu), не более 64
    """
    try:
        v = int(env_value) if env_value is not None else 0
    except Exception:
        v = 0
    if v > 0:
        return v
    cpu = (os.cpu_count() or 2)
    if aggressive:
        return min(64, max(4, cpu))
    return min(32, max(1, cpu - 1))

class Config:
    # Paths
    DB_PATH = os.environ.get("DB_PATH", "ai_trader.db")
    MODELS_DIR = os.environ.get("MODELS_DIR", "models")

    # Market config
    SYMBOLS = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT", "ADA/USDT"]
    TIMEFRAMES = ["15m", "1h", "4h", "1d", "1w"]
    HISTORY_YEARS = int(os.environ.get("HISTORY_YEARS", "3"))

    # Exchange / WS
    EXCHANGE_ID = os.environ.get("EXCHANGE_ID", "binance")
    ENABLE_WS = True

    # WebSocket manager defaults
    WS_CACHE_MAX = int(os.environ.get("WS_CACHE_MAX", "3000"))
    WS_RECONNECT_SEC = float(os.environ.get("WS_RECONNECT_SEC", "5"))
    WS_PING_INTERVAL = float(os.environ.get("WS_PING_INTERVAL", "30"))

    # Training / inference
    MAX_WORKERS = int(os.environ.get("MAX_WORKERS", "4"))
    TRAIN_MAX_WORKERS = int(os.environ.get("TRAIN_MAX_WORKERS", "4"))

    # Parallelism for tuning/backtest (агрессивные дефолты, можно переопределить ENV)
    OPTIMIZE_MAX_WORKERS = _auto_workers(os.environ.get("OPTIMIZE_MAX_WORKERS"), aggressive=True)
    BACKTEST_MAX_WORKERS = _auto_workers(os.environ.get("BACKTEST_MAX_WORKERS"), aggressive=True)

    # Signal engine thresholds (мягкая иерархия)
    SIG_ENTRY_THRESHOLD = float(os.environ.get("SIG_ENTRY_THRESHOLD", "0.60"))  # порог входа по |score|
    SIG_EXIT_THRESHOLD = float(os.environ.get("SIG_EXIT_THRESHOLD", "0.40"))    # порог выхода по |score|
    SIG_MIN_SUPPORT = float(os.environ.get("SIG_MIN_SUPPORT", "0.30"))          # мин. доля взвешенной поддержки старших ТФ
    SIG_LOOKBACK = int(os.environ.get("SIG_LOOKBACK", "2"))                     # скользящее среднее score
    EXIT_ON_FLIP = True  # закрывать сразу при смене знака score

    # Базовые пороги (для обратной совместимости отдельных мест)
    SIGNAL_THRESHOLD = float(os.environ.get("SIGNAL_THRESHOLD", "0.8"))
    SIGNAL_THRESHOLD_BY_TF = {
        "15m": 0.60,
        "1h":  0.65,
        "4h":  0.70,
        "1d":  0.75,
        "1w":  0.80,
    }
    SIGNAL_HOLD_MARGIN = float(os.environ.get("SIGNAL_HOLD_MARGIN", "0.05"))

    # Иерархия и веса таймфреймов (бОльшие веса старшим ТФ)
    MIN_CONFIRMED_HIGHER_BY_TF = {
        "15m": 1,
        "1h":  1,
        "4h":  1,
        "1d":  1,
        "1w":  0,
    }
    HIERARCHY_WEIGHTS = {
        "15m": 1.0,
        "1h":  1.2,
        "4h":  1.4,
        "1d":  1.6,
        "1w":  1.8,
    }

    # Backtest defaults
    BT_SL_ATR = float(os.environ.get("BT_SL_ATR", "1.0"))
    BT_TP_ATR = float(os.environ.get("BT_TP_ATR", "2.0"))
    BT_MAX_BARS = int(os.environ.get("BT_MAX_BARS", "200"))

    # Auto tuning
    OPTIMIZE_AFTER_TRAIN = True

    # News
    NEWS_FEEDS = [
        "https://www.binance.com/en/support/announcement/rss",
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "https://cointelegraph.com/rss"
    ]
    NEWS_AGG_MINUTES = int(os.environ.get("NEWS_AGG_MINUTES", "60"))
    NEWS_WINDOWS_BY_TF = {
        "15m": [60, 180, 720],
        "1h":  [180, 720, 1440],
        "4h":  [720, 2880, 10080],
        "1d":  [1440, 4320, 10080],
        "1w":  [10080, 43200],
    }


def configure_logging(level=logging.INFO):
    logging.basicConfig(
        level=level,
        format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    )
