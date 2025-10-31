import os
import threading
import asyncio
from flask import Blueprint

from config import Config
from database import DatabaseManager
from data_manager import CCXTDataManager
from websocket_manager import WebsocketManager
from model_manager import ModelManager
from news_ingestor import NewsIngestor
from bots_manager import BotManager
from account_manager import AccountManager
from utils.sqlite_wal import enable_wal_for_dbmanager

api_bp = Blueprint("api", __name__)


class Services:
    def __init__(self, db, data, ws, models, news, bots, accounts, executor, loop):
        self.db: DatabaseManager = db
        self.data: CCXTDataManager = data
        self.ws: WebsocketManager | None = ws
        self.models: ModelManager = models
        self.news: NewsIngestor = news
        self.bots: BotManager = bots
        self.accounts: AccountManager = accounts
        self.executor = executor
        self.loop: asyncio.AbstractEventLoop = loop


def make_services(app):
    # ограничим потоки BLAS для стабильности пулов
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")

    db = DatabaseManager()

    # Включаем WAL и busy_timeout на активном соединении SQLite (если возможно обнаружить)
    try:
        enable_wal_for_dbmanager(db)
    except Exception:
        # не падаем, если конкретная реализация БД не SQLite или недоступна
        pass

    data = CCXTDataManager(db)
    ws = WebsocketManager() if getattr(Config, "ENABLE_WS", False) else None
    if ws:
        ws.start()
        ws.subscribe(getattr(Config, "SYMBOLS", []), getattr(Config, "TIMEFRAMES", []))

    models = ModelManager(db)
    news = NewsIngestor(db)

    loop = asyncio.new_event_loop()
    t = threading.Thread(target=loop.run_forever, daemon=True)
    t.start()
    try:
        import asyncio as _asyncio  # для надёжности на разных средах
        _asyncio.run_coroutine_threadsafe(news.start(), loop)
    except Exception:
        pass

    bots = BotManager(db, data, models, ws)
    accounts = AccountManager(db)

    # Ленивая импортировка, чтобы не тянуть concurrent в рантайм импорта
    from concurrent.futures import ThreadPoolExecutor
    executor = ThreadPoolExecutor(max_workers=getattr(Config, "MAX_WORKERS", 4))

    services = Services(db, data, ws, models, news, bots, accounts, executor, loop)
    app.extensions["services"] = services

    # Регистрация маршрутов, разбитых по модулям
    from .routes import common, training, analysis, explain, bots as bots_routes, market, news_trades, indicators_profiles, settings_pages
    common.register(api_bp)
    training.register(api_bp)
    analysis.register(api_bp)
    explain.register(api_bp)
    bots_routes.register(api_bp)
    market.register(api_bp)
    news_trades.register(api_bp)
    indicators_profiles.register(api_bp)
    settings_pages.register(api_bp)

    return services