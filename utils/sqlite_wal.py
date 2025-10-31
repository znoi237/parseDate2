from __future__ import annotations
from typing import Any, Optional


def _enable_pragmas_on_conn(conn: Any):
    """
    Применяет набор PRAGMA для повышения конкурентности SQLite.
    Безопасно для повторных вызовов.
    """
    try:
        cur = conn.cursor()
        # Включаем WAL-журналирование (возвращает строку режима, игнорируем)
        cur.execute("PRAGMA journal_mode=WAL;")
        # Ставим разумный таймаут ожидания блокировок (мс)
        cur.execute("PRAGMA busy_timeout=5000;")
        # Снижаем синхронность до NORMAL ради скорости (компромисс надёжности/скорости)
        cur.execute("PRAGMA synchronous=NORMAL;")
        # Храним временные таблицы в памяти
        cur.execute("PRAGMA temp_store=MEMORY;")
        # Опционально можно увеличить mmap, но оставим по умолчанию для совместимости
        # cur.execute("PRAGMA mmap_size=134217728;")  # 128 MiB
        try:
            conn.commit()
        except Exception:
            # Если автокоммит, commit не требуется
            pass
    except Exception:
        # Не падаем: если соединение не SQLite или PRAGMA не поддерживается
        pass


def enable_wal_for_dbmanager(dbm: Any) -> bool:
    """
    Пытается найти активное соединение SQLite в объекте DatabaseManager и включить WAL/busy_timeout.
    Возвращает True, если удалось применить PRAGMA хотя бы к одному соединению.
    """
    # Популярные имена атрибутов соединения
    candidates = ["conn", "_conn", "connection", "_connection", "db", "_db"]
    applied = False

    for name in candidates:
        try:
            conn = getattr(dbm, name, None)
            if conn is not None:
                _enable_pragmas_on_conn(conn)
                applied = True
        except Exception:
            continue

    # Иногда менеджер БД предоставляет метод получения соединения
    if not applied:
        try:
            if hasattr(dbm, "get_connection") and callable(dbm.get_connection):
                conn = dbm.get_connection()
                if conn is not None:
                    _enable_pragmas_on_conn(conn)
                    applied = True
        except Exception:
            pass

    return applied