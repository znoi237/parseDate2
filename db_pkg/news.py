from __future__ import annotations
import pandas as pd
import logging

logger = logging.getLogger("db")


class _NewsMixin:
    # -------- News ----------
    def add_news(self, provider, title, url, published_at, summary, sentiment, symbols_csv=""):
        conn = self._conn()
        c = conn.cursor()
        try:
            c.execute(
                """
            INSERT OR IGNORE INTO news(provider,title,url,published_at,summary,sentiment,symbols)
            VALUES(?,?,?,?,?,?,?)
            """,
                (provider, title, url, published_at, summary, sentiment, symbols_csv),
            )
            conn.commit()
        except Exception as e:
            logger.warning("news insert error: %s", e)
        finally:
            conn.close()

    def news_since(self, since_dt, limit=200):
        conn = self._conn()
        df = pd.read_sql_query(
            """
            SELECT provider,title,url,published_at,summary,sentiment,symbols
            FROM news WHERE published_at >= ? ORDER BY published_at DESC LIMIT ?
        """,
            conn,
            params=[since_dt, limit],
            parse_dates=["published_at"],
        )
        conn.close()
        return df