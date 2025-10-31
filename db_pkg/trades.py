from __future__ import annotations
import pandas as pd


class _TradesMixin:
    # -------- Trades ----------
    def add_trade(self, symbol, side, entry_price, quantity, entry_time, network="testnet", origin="bot"):
        conn = self._conn()
        c = conn.cursor()
        c.execute(
            """INSERT INTO trades(symbol,side,entry_price,quantity,entry_time,status,network,origin) VALUES(?,?,?,?,?,?,?,?)""",
            (symbol, side, float(entry_price or 0.0), float(quantity or 0.0), entry_time, "open", network, origin),
        )
        tid = c.lastrowid
        conn.commit()
        conn.close()
        return tid

    def close_trade(self, trade_id, exit_price, pnl_percent, exit_time):
        conn = self._conn()
        c = conn.cursor()
        c.execute(
            """UPDATE trades SET exit_price=?, pnl_percent=?, exit_time=?, status='closed' WHERE id=?""",
            (float(exit_price or 0.0), float(pnl_percent or 0.0), exit_time, trade_id),
        )
        conn.commit()
        conn.close()

    def get_trades(self, limit=200, network=None, symbol=None, status=None, origin=None, since=None, until=None):
        """
        Возвращает список сделок.
        - Даты приводятся к ISO-строкам, NaT -> None (чтобы Flask JSON не падал).
        - Числовые NaN -> None.
        """
        conn = self._conn()
        where = []
        params = []
        if network:
            where.append("network=?"); params.append(network)
        if symbol:
            where.append("symbol=?"); params.append(symbol)
        if status:
            where.append("status=?"); params.append(status)
        if origin:
            where.append("origin=?"); params.append(origin)
        if since:
            where.append("COALESCE(exit_time, entry_time) >= ?"); params.append(since)
        if until:
            where.append("COALESCE(exit_time, entry_time) <= ?"); params.append(until)
        q = """
            SELECT id, symbol, side, entry_price, exit_price, quantity, pnl_percent, entry_time, exit_time, status, network, origin
            FROM trades
        """
        if where:
            q += " WHERE " + " AND ".join(where)
        q += " ORDER BY COALESCE(exit_time, entry_time) DESC"
        if limit:
            q += " LIMIT ?"; params.append(limit)
        df = pd.read_sql_query(q, conn, params=params, parse_dates=["entry_time","exit_time"])
        conn.close()

        if "entry_time" in df.columns:
            df["entry_time"] = df["entry_time"].apply(lambda x: x.isoformat() if pd.notna(x) else None)
        if "exit_time" in df.columns:
            df["exit_time"] = df["exit_time"].apply(lambda x: x.isoformat() if pd.notna(x) else None)
        for col in ["entry_price", "exit_price", "quantity", "pnl_percent"]:
            if col in df.columns:
                df[col] = df[col].where(pd.notna(df[col]), None)

        return df.to_dict(orient="records")

    def get_open_trades_by_symbol_network(self, symbol: str, network: str):
        conn = self._conn()
        df = pd.read_sql_query(
            """
            SELECT id, symbol, side, entry_price, quantity, entry_time, network
            FROM trades WHERE symbol=? AND network=? AND status='open'
            ORDER BY entry_time ASC
            """,
            conn,
            params=[symbol, network],
            parse_dates=["entry_time"],
        )
        conn.close()
        return df.to_dict(orient="records")

    def close_all_open_trades_for_symbol(self, symbol: str, network: str, exit_price: float, exit_time):
        opens = self.get_open_trades_by_symbol_network(symbol, network)
        closed = 0
        for t in opens:
            entry_price = float(t["entry_price"] or 0.0)
            side = (t["side"] or "").upper()
            px = float(exit_price or 0.0)
            if px <= 0.0:
                px = entry_price
            if entry_price <= 0:
                pnl = 0.0
            else:
                if side == "BUY":
                    pnl = (px - entry_price) / entry_price * 100.0
                else:
                    pnl = (entry_price - px) / entry_price * 100.0
            self.close_trade(t["id"], px, pnl, exit_time)
            closed += 1
        return closed