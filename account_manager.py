import ccxt
import logging
from datetime import datetime
from typing import Dict, Any
from database import DatabaseManager
from config import Config

logger = logging.getLogger("account")

class AccountManager:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def _build_exchange(self, network: str, api_key: str, api_secret: str):
        ex = getattr(ccxt, Config.EXCHANGE_ID)({
            "enableRateLimit": True,
            "timeout": 30000,
            "apiKey": api_key,
            "secret": api_secret,
            "options": {
                "defaultType": "spot",
                "adjustForTimeDifference": True,
            },
        })
        if network == "testnet":
            try:
                ex.set_sandbox_mode(True)
            except Exception as e:
                logger.warning("set_sandbox_mode failed: %s", e)
        return ex

    def get_balance_usdt(self, network: str) -> Dict[str, Any]:
        keys = self.db.load_api_keys(network)
        if not keys:
            return {"connected": False, "balance_usdt": None, "error": "no_api_keys", "last_checked": datetime.utcnow().isoformat()}
        ex = None
        try:
            ex = self._build_exchange(network, keys["api_key"], keys["api_secret"])
            try:
                ex.load_markets()
            except Exception as e:
                logger.debug("load_markets issue (%s): %s", network, e)
            bal = ex.fetch_balance()
            usdt_total = None
            total = bal.get("total") or {}
            free = bal.get("free") or {}
            if "USDT" in total:
                usdt_total = float(total["USDT"])
            elif "USDT" in free:
                usdt_total = float(free["USDT"])
            else:
                usdt_total = float(total.get("USDT", free.get("USDT", 0.0)))
            return {"connected": True, "balance_usdt": usdt_total, "error": None, "last_checked": datetime.utcnow().isoformat()}
        except ccxt.AuthenticationError as e:
            logger.warning("auth error (%s): %s", network, e)
            return {"connected": False, "balance_usdt": None, "error": "auth_error", "last_checked": datetime.utcnow().isoformat()}
        except Exception as e:
            logger.warning("balance fetch error (%s): %s", network, e)
            return {"connected": False, "balance_usdt": None, "error": "network_error", "last_checked": datetime.utcnow().isoformat()}
        finally:
            ex = None