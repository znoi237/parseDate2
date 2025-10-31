from __future__ import annotations


class _TrainingJobsMixin:
    # -------- Training jobs ----------
    def create_training_job(self, symbol, timeframes):
        conn = self._conn()
        c = conn.cursor()
        c.execute(
            "INSERT INTO training_jobs(symbol,timeframes,status,progress) VALUES(?,?,?,?)",
            (symbol, ",".join(timeframes), "queued", 0),
        )
        jid = c.lastrowid
        conn.commit()
        conn.close()
        return jid

    def update_training_job(self, job_id, status=None, progress=None, message=None):
        conn = self._conn()
        c = conn.cursor()
        sets = []
        params = []
        if status is not None:
            sets.append("status=?")
            params.append(status)
        if progress is not None:
            sets.append("progress=?")
            params.append(progress)
        if message is not None:
            sets.append("message=?")
            params.append(message)
        sets.append("updated_at=CURRENT_TIMESTAMP")
        q = f"UPDATE training_jobs SET {', '.join(sets)} WHERE id=?"
        params.append(job_id)
        c.execute(q, params)
        conn.commit()
        conn.close()

    def get_training_job(self, job_id):
        conn = self._conn()
        c = conn.cursor()
        c.execute(
            "SELECT id,symbol,timeframes,status,progress,message,started_at,updated_at FROM training_jobs WHERE id=?",
            (job_id,),
        )
        row = c.fetchone()
        conn.close()
        if not row:
            return None
        return {
            "id": row[0],
            "symbol": row[1],
            "timeframes": row[2].split(","),
            "status": row[3],
            "progress": row[4],
            "message": row[5],
            "started_at": row[6],
            "updated_at": row[7],
        }

    def get_active_training_job(self):
        conn = self._conn()
        c = conn.cursor()
        c.execute(
            """
            SELECT id,symbol,timeframes,status,progress,message,started_at,updated_at
            FROM training_jobs
            WHERE status IN ('queued','running')
            ORDER BY updated_at DESC
            LIMIT 1
            """
        )
        row = c.fetchone()
        conn.close()
        if not row:
            return None
        return {
            "id": row[0],
            "symbol": row[1],
            "timeframes": row[2].split(","),
            "status": row[3],
            "progress": row[4],
            "message": row[5],
            "started_at": row[6],
            "updated_at": row[7],
        }