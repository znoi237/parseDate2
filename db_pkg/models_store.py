from __future__ import annotations
import json
import io
import joblib


class _ModelsMixin:
    # -------- Models ----------
    def save_model(
        self,
        symbol,
        timeframe,
        algo,
        model,
        classes,
        features,
        last_full_end=None,
        last_incr_end=None,
        metrics=None,
    ):
        conn = self._conn()
        c = conn.cursor()
        mbuf = io.BytesIO()
        joblib.dump(model, mbuf)
        cbuf = io.BytesIO()
        joblib.dump(classes, cbuf)
        last_full_str = self._to_iso(last_full_end)
        last_incr_str = self._to_iso(last_incr_end)

        c.execute(
            """
            INSERT INTO models(symbol,timeframe,algo,metrics,last_full_train_end,last_incremental_train_end,model_blob,classes_blob,features)
            VALUES(?,?,?,?,?,?,?,?,?)
            ON CONFLICT(symbol,timeframe) DO UPDATE SET 
                algo=excluded.algo,
                metrics=excluded.metrics,
                last_full_train_end=excluded.last_full_train_end,
                last_incremental_train_end=excluded.last_incremental_train_end,
                model_blob=excluded.model_blob,
                classes_blob=excluded.classes_blob,
                features=excluded.features
        """,
            (
                symbol,
                timeframe,
                algo,
                json.dumps(metrics or {}),
                last_full_str,
                last_incr_str,
                mbuf.getvalue(),
                cbuf.getvalue(),
                json.dumps(features),
            ),
        )
        conn.commit()
        conn.close()

    def update_model_metrics(self, symbol: str, timeframe: str, new_metrics: dict):
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT metrics FROM models WHERE symbol=? AND timeframe=?", (symbol, timeframe))
        row = c.fetchone()
        cur = {}
        if row and row[0]:
            try:
                cur = json.loads(row[0]) or {}
            except Exception:
                cur = {}
        cur.update(new_metrics or {})
        c.execute("UPDATE models SET metrics=? WHERE symbol=? AND timeframe=?", (json.dumps(cur), symbol, timeframe))
        conn.commit()
        conn.close()

    def load_model(self, symbol, timeframe):
        conn = self._conn()
        c = conn.cursor()
        c.execute(
            "SELECT algo, metrics, last_full_train_end, last_incremental_train_end, model_blob, classes_blob, features FROM models WHERE symbol=? AND timeframe=?",
            (symbol, timeframe),
        )
        row = c.fetchone()
        conn.close()
        if not row:
            return None
        algo, metrics, full_end, incr_end, mb, cb, feats = row
        model = joblib.load(io.BytesIO(mb)) if mb else None
        classes = joblib.load(io.BytesIO(cb)) if cb else None
        features = json.loads(feats) if feats else []
        return {
            "algo": algo,
            "metrics": json.loads(metrics or "{}"),
            "last_full_train_end": full_end,
            "last_incremental_train_end": incr_end,
            "model": model,
            "classes": classes,
            "features": features,
        }

    def get_pairs_status(self, symbols, timeframes):
        from .utils import to_iso
        import json as _json
        conn = self._conn()
        c = conn.cursor()
        res = []
        for sym in symbols:
            c.execute(
                "SELECT timeframe,last_full_train_end,last_incremental_train_end,metrics FROM models WHERE symbol=?",
                (sym,),
            )
            rows = c.fetchall()
            if not rows:
                res.append(
                    {
                        "symbol": sym,
                        "is_trained": False,
                        "last_full_train_end": None,
                        "last_incremental_train_end": None,
                        "accuracy": None,
                    }
                )
                continue

            full_iso = [to_iso(r[1]) for r in rows if r[1]]
            incr_iso = [to_iso(r[2]) for r in rows if r[2]]
            latest_full = max(full_iso) if full_iso else None
            latest_incr = max(incr_iso) if incr_iso else None

            accs = []
            for r in rows:
                try:
                    m = _json.loads(r[3]) if r[3] else {}
                    if "accuracy" in m:
                        accs.append(float(m["accuracy"]))
                except Exception:
                    pass

            res.append(
                {
                    "symbol": sym,
                    "is_trained": True,
                    "last_full_train_end": latest_full,
                    "last_incremental_train_end": latest_incr,
                    "accuracy": (sum(accs) / len(accs)) if accs else None,
                }
            )
        conn.close()
        return res