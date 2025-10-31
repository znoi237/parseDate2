from __future__ import annotations
import json


class _ModelParamsMixin:
    # -------- Model params (tuning) ----------
    def save_model_params(self, symbol: str, timeframe: str, params: dict):
        conn = self._conn()
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO model_params(symbol,timeframe,params) VALUES(?,?,?)
            ON CONFLICT(symbol,timeframe) DO UPDATE SET
              params=excluded.params,
              updated_at=CURRENT_TIMESTAMP
            """,
            (symbol, timeframe, json.dumps(params)),
        )
        conn.commit()
        conn.close()

    def load_model_params(self, symbol: str, timeframe: str):
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT params FROM model_params WHERE symbol=? AND timeframe=?", (symbol, timeframe))
        row = c.fetchone()
        conn.close()
        if not row:
            return None
        try:
            return json.loads(row[0])
        except Exception:
            return None