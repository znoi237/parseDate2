from __future__ import annotations


class _ApiKeysMixin:
    # -------- API keys ----------
    def save_api_keys(self, network, api_key, api_secret):
        conn = self._conn()
        c = conn.cursor()
        c.execute("DELETE FROM api_keys WHERE network=?", (network,))
        c.execute("INSERT INTO api_keys (network, api_key, api_secret) VALUES (?,?,?)", (network, api_key, api_secret))
        conn.commit()
        conn.close()
        return True

    def load_api_keys(self, network):
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT api_key, api_secret FROM api_keys WHERE network=? ORDER BY id DESC LIMIT 1", (network,))
        row = c.fetchone()
        conn.close()
        if row:
            return {"api_key": row[0], "api_secret": row[1], "network": network}
        return None