from __future__ import annotations
import pandas as pd


class _HistoricalMixin:
    # -------- Historical data ----------
    def upsert_ohlcv(self, symbol, timeframe, df: pd.DataFrame, source="binance"):
        conn = self._conn()
        c = conn.cursor()
        saved = 0
        for ts, r in df.iterrows():
            c.execute(
                """
                INSERT INTO historical_data(symbol,timeframe,open_time,open,high,low,close,volume,source)
                VALUES(?,?,?,?,?,?,?,?,?)
                ON CONFLICT(symbol,timeframe,open_time) DO UPDATE SET 
                    open=excluded.open,
                    high=excluded.high,
                    low=excluded.low,
                    close=excluded.close,
                    volume=excluded.volume,
                    source=excluded.source
            """,
                (
                    symbol,
                    timeframe,
                    ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts,
                    float(r.open),
                    float(r.high),
                    float(r.low),
                    float(r.close),
                    float(r.volume),
                    source,
                ),
            )
            saved += 1
        conn.commit()
        conn.close()
        return saved

    def get_last_ohlcv_time(self, symbol, timeframe):
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT MAX(open_time) FROM historical_data WHERE symbol=? AND timeframe=?", (symbol, timeframe))
        row = c.fetchone()
        conn.close()
        return row[0] if row and row[0] else None

    def load_ohlcv(self, symbol, timeframe, since=None, limit=None):
        conn = self._conn()
        q = "SELECT open_time, open, high, low, close, volume FROM historical_data WHERE symbol=? AND timeframe=?"
        params = [symbol, timeframe]
        if since:
            q += " AND open_time >= ?"
            params.append(since)
        q += " ORDER BY open_time ASC"
        if limit:
            q += " LIMIT ?"
            params.append(limit)
        df = pd.read_sql_query(q, conn, params=params, parse_dates=["open_time"], index_col="open_time")
        conn.close()
        return df

    def get_hist_stats(self, symbol, timeframe):
        from .utils import to_iso
        conn = self._conn()
        c = conn.cursor()
        c.execute(
            "SELECT COUNT(*), MIN(open_time), MAX(open_time) FROM historical_data WHERE symbol=? AND timeframe=?",
            (symbol, timeframe),
        )
        row = c.fetchone()
        conn.close()
        count = int(row[0]) if row and row[0] is not None else 0
        first = to_iso(row[1]) if row and row[1] else None
        last = to_iso(row[2]) if row and row[2] else None
        return {"symbol": symbol, "timeframe": timeframe, "count": count, "first": first, "last": last}