from __future__ import annotations
import json
import pandas as pd


class _TrainingLogsMixin:
    # -------- Training logs ----------
    def add_training_log(self, job_id: int, level: str, phase: str, message: str, data: dict | None = None):
        conn = self._conn()
        c = conn.cursor()
        c.execute(
            "INSERT INTO training_logs(job_id,level,phase,message,data) VALUES(?,?,?,?,?)",
            (job_id, level or "INFO", phase, message, json.dumps(data or {})),
        )
        conn.commit()
        new_id = c.lastrowid
        conn.close()
        return new_id

    def get_training_logs(self, job_id: int, since_id: int | None = None, limit: int | None = 200):
        conn = self._conn()
        params = [job_id]
        q = "SELECT id, ts, level, phase, message, data FROM training_logs WHERE job_id=?"
        if since_id:
            q += " AND id > ?"
            params.append(since_id)
        q += " ORDER BY id ASC"
        if limit:
            q += " LIMIT ?"
            params.append(limit)
        df = pd.read_sql_query(q, conn, params=params, parse_dates=["ts"])
        conn.close()
        return df.to_dict(orient="records")