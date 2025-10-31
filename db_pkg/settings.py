from __future__ import annotations
import json
from .utils import default_signal_params


class _SettingsMixin:
    # -------- Settings ----------
    def get_setting(self, key: str):
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT value FROM app_settings WHERE key=?", (key,))
        row = c.fetchone()
        conn.close()
        if not row or row[0] is None:
            return None
        try:
            return json.loads(row[0])
        except Exception:
            return None

    def set_setting(self, key: str, value):
        import json as _json
        conn = self._conn()
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO app_settings(key,value) VALUES(?,?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP
            """,
            (key, _json.dumps(value or {})),
        )
        conn.commit()
        conn.close()
        return True

    # Профили сигналов
    def get_signal_profiles(self):
        profiles = self.get_setting("signal_profiles") or {}
        active = self.get_setting("signal_profile_active") or "default"
        if not profiles:
            profiles = {"default": default_signal_params()}
            self.set_setting("signal_profiles", profiles)
        if active not in profiles:
            active = "default"
            self.set_setting("signal_profile_active", active)
        return {"active": active, "profiles": profiles}

    def set_signal_profiles(self, profiles: dict, active: str | None = None):
        if not profiles or not isinstance(profiles, dict):
            profiles = {"default": default_signal_params()}
        self.set_setting("signal_profiles", profiles)
        if not active:
            active = self.get_setting("signal_profile_active") or "default"
        if active not in profiles:
            active = "default"
        self.set_setting("signal_profile_active", active)
        return True

    def save_signal_profile(self, name: str, params: dict):
        data = self.get_signal_profiles()
        profiles = data["profiles"]
        profiles[name] = params or default_signal_params()
        self.set_setting("signal_profiles", profiles)
        return True

    def delete_signal_profile(self, name: str):
        data = self.get_signal_profiles()
        profiles = data["profiles"]
        active = data["active"]
        if name in profiles:
            profiles.pop(name, None)
            if not profiles:
                profiles["default"] = default_signal_params()
                active = "default"
            if active == name:
                active = "default" if "default" in profiles else next(iter(profiles.keys()))
            self.set_setting("signal_profiles", profiles)
            self.set_setting("signal_profile_active", active)
        return True

    def set_active_signal_profile(self, name: str):
        data = self.get_signal_profiles()
        profiles = data["profiles"]
        if name in profiles:
            self.set_setting("signal_profile_active", name)
            return True
        return False

    def load_signal_params(self):
        data = self.get_signal_profiles()
        return data["profiles"].get(data["active"], default_signal_params())

    def save_signal_params(self, params: dict):
        data = self.get_signal_profiles()
        active = data["active"]
        cur = data["profiles"].get(active, default_signal_params())
        cur.update(params or {})
        data["profiles"][active] = cur
        self.set_setting("signal_profiles", data["profiles"])
        return True