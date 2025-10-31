from __future__ import annotations
import os
import sqlite3
import json
import logging

from config import Config
from .utils import default_signal_params, logger


class _ConnInitMixin:
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or Config.DB_PATH
        d = os.path.dirname(self.db_path)
        if d:
            os.makedirs(d, exist_ok=True)
        self._init_db()

    def _conn(self):
        # detect_types важен для корректных дат
        return sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)

    def _init_db(self):
        conn = self._conn()
        c = conn.cursor()
        c.executescript(
            """
        PRAGMA journal_mode=WAL;

        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            network TEXT NOT NULL CHECK(network IN ('mainnet','testnet')),
            api_key TEXT NOT NULL,
            api_secret TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS historical_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            open_time DATETIME NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume REAL NOT NULL,
            source TEXT DEFAULT 'binance',
            UNIQUE(symbol, timeframe, open_time)
        );

        CREATE INDEX IF NOT EXISTS idx_hist_sym_tf_time ON historical_data(symbol,timeframe,open_time);

        CREATE TABLE IF NOT EXISTS models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            algo TEXT NOT NULL,
            metrics TEXT,
            last_full_train_end TEXT,
            last_incremental_train_end TEXT,
            model_blob BLOB,
            classes_blob BLOB,
            features JSON,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(symbol, timeframe)
        );

        CREATE TABLE IF NOT EXISTS training_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timeframes TEXT NOT NULL,
            status TEXT NOT NULL,
            progress REAL DEFAULT 0,
            message TEXT,
            started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS training_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            ts DATETIME DEFAULT CURRENT_TIMESTAMP,
            level TEXT DEFAULT 'INFO',
            phase TEXT,
            message TEXT NOT NULL,
            data JSON
        );
        CREATE INDEX IF NOT EXISTS idx_tlogs_job_ts ON training_logs(job_id, ts);
        CREATE INDEX IF NOT EXISTS idx_tlogs_job_id ON training_logs(job_id);

        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            entry_price REAL,
            exit_price REAL,
            quantity REAL,
            pnl_percent REAL,
            entry_time DATETIME,
            exit_time DATETIME,
            status TEXT NOT NULL DEFAULT 'closed',
            network TEXT DEFAULT 'testnet',
            origin  TEXT DEFAULT 'bot'
        );

        CREATE TABLE IF NOT EXISTS bots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            stats JSON
        );

        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT,
            title TEXT,
            url TEXT,
            published_at DATETIME,
            summary TEXT,
            sentiment REAL,
            symbols TEXT,
            UNIQUE(url)
        );

        CREATE TABLE IF NOT EXISTS model_params (
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            params JSON NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(symbol, timeframe)
        );

        -- Глобальные настройки приложения (JSON)
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value JSON,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
        )
        # миграции trades (на случай старых БД)
        try:
            c.execute("PRAGMA table_info(trades)")
            cols = {row[1] for row in c.fetchall()}
            if "network" not in cols:
                c.execute("ALTER TABLE trades ADD COLUMN network TEXT DEFAULT 'testnet'")
            if "origin" not in cols:
                c.execute("ALTER TABLE trades ADD COLUMN origin TEXT DEFAULT 'bot'")
            conn.commit()
        except Exception as e:
            logger.warning("trades migrate add columns failed: %s", e)

        # Инициализация профиля сигналов по умолчанию при первом запуске
        try:
            cur = conn.cursor()
            cur.execute("SELECT value FROM app_settings WHERE key='signal_profiles'")
            row = cur.fetchone()
            if not row:
                profiles = {"default": default_signal_params()}
                cur.execute("INSERT INTO app_settings(key,value) VALUES(?,?)", ("signal_profiles", json.dumps(profiles)))
                cur.execute("INSERT INTO app_settings(key,value) VALUES(?,?)", ("signal_profile_active", json.dumps("default")))
                conn.commit()
            else:
                cur.execute("SELECT value FROM app_settings WHERE key='signal_profile_active'")
                row2 = cur.fetchone()
                if not row2:
                    cur.execute("INSERT INTO app_settings(key,value) VALUES(?,?)", ("signal_profile_active", json.dumps("default")))
                    conn.commit()
        except Exception as e:
            logger.warning("init profiles failed: %s", e)

        conn.commit()
        conn.close()
        logger.info("Database initialized at %s", self.db_path)
