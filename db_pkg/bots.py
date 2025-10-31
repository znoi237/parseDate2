from __future__ import annotations
import json


class _BotsMixin:
    # -------- Bots ----------
    def add_bot(self, symbol, status, stats=None):
        conn = self._conn()
        c = conn.cursor()
        c.execute("INSERT INTO bots(symbol,status,stats) VALUES(?,?,?)", (symbol, status, json.dumps(stats or {})))
        conn.commit()
        conn.close()

    def update_bot(self, symbol, status=None, stats=None):
        conn = self._conn()
        c = conn.cursor()
        sets, params = [], []
        if status is not None:
            sets.append("status=?")
            params.append(status)
        if stats is not None:
            sets.append("stats=?")
            params.append(json.dumps(stats))
        if not sets:
            conn.close()
            return
        params.append(symbol)
        c.execute(f"UPDATE bots SET {', '.join(sets)} WHERE symbol=?", params)
        conn.commit()
        conn.close()

    def bots_summary(self):
        import json as _json
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT symbol,status,stats,started_at FROM bots ORDER BY started_at DESC")
        rows = c.fetchall()
        conn.close()
        out = []
        for r in rows:
            try:
                stats = _json.loads(r[2]) if r[2] else {}
            except Exception:
                stats = {}
            out.append({"symbol": r[0], "status": r[1], "stats": stats, "started_at": r[3]})
        return out