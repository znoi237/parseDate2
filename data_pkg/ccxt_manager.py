import ccxt
import pandas as pd
from datetime import datetime, timedelta
from config import Config
from database import DatabaseManager
import logging
import time

logger = logging.getLogger("data")

TF_TO_MS = {
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "2h": 7_200_000,
    "4h": 14_400_000,
    "1d": 86_400_000,
    "1w": 604_800_000,
}


class CCXTDataManager:
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.exchange = getattr(ccxt, Config.EXCHANGE_ID)(
            {
                "enableRateLimit": True,
                "timeout": 30000,
                "options": {
                    "defaultType": "spot",
                    "adjustForTimeDifference": True,
                },
            }
        )
        try:
            self.exchange.load_markets()
        except Exception as e:
            logger.warning("load_markets warning: %s", e)

    def _to_binance_symbol(self, s: str):
        return s.replace("/", "")

    def fetch_ohlcv_incremental(self, symbol: str, timeframe: str, years: int, force_full: bool = False):
        """
        Инкрементально (или принудительно) подкачивает OHLCV в БД:
        - force_full=True: всегда берём since = now - years (игнорируем last_time в БД).
        - force_full=False: since = last_time + 1*tf, иначе now - years.
        """
        ms_per_tf = TF_TO_MS[timeframe]

        if force_full:
            since_dt = datetime.utcnow() - timedelta(days=365 * max(1, years))
            since_ms = int(since_dt.timestamp() * 1000)
        else:
            last_time = self.db.get_last_ohlcv_time(symbol, timeframe)
            if last_time:
                since_ms = int(pd.Timestamp(last_time).timestamp() * 1000 + ms_per_tf)
            else:
                since_dt = datetime.utcnow() - timedelta(days=365 * max(1, years))
                since_ms = int(since_dt.timestamp() * 1000)

        # не ходим в будущее
        now_ms = int(datetime.utcnow().timestamp() * 1000)
        if since_ms > now_ms - ms_per_tf:
            since_ms = now_ms - ms_per_tf

        market = self._to_binance_symbol(symbol)
        all_rows = []
        limit = 1000
        logger.info("Fetching %s %s since %s (force_full=%s)", symbol, timeframe, datetime.utcfromtimestamp(since_ms / 1000), force_full)
        while True:
            try:
                chunk = self.exchange.fetch_ohlcv(market, timeframe=timeframe, since=since_ms, limit=limit)
                if not chunk:
                    break
                df = pd.DataFrame(chunk, columns=["ts", "open", "high", "low", "close", "volume"])
                df["open_time"] = pd.to_datetime(df["ts"], unit="ms", utc=True).dt.tz_convert(None)
                df.set_index("open_time", inplace=True)
                df.drop(columns=["ts"], inplace=True)
                all_rows.append(df[["open", "high", "low", "close", "volume"]])
                since_ms = int(df.index[-1].timestamp() * 1000 + ms_per_tf)
                if len(chunk) < limit:
                    break
                time.sleep(self.exchange.rateLimit / 1000)
            except ccxt.NetworkError as e:
                logger.warning("Network error: %s; retrying", e)
                time.sleep(1)
            except ccxt.DDoSProtection as e:
                logger.warning("DDoS protection: %s; backing off", e)
                time.sleep(2)
            except Exception as e:
                logger.exception("fetch_ohlcv error: %s", e)
                break

        if not all_rows:
            logger.info("No new candles for %s %s", symbol, timeframe)
            return 0

        full_df = pd.concat(all_rows).sort_index()
        saved = self.db.upsert_ohlcv(symbol, timeframe, full_df, source="binance")
        logger.info("Saved %s candles for %s %s", saved, symbol, timeframe)
        return saved