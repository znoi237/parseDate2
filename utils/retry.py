from __future__ import annotations
from typing import Callable, TypeVar, Optional
import time
import sqlite3

T = TypeVar("T")


def with_retries(
    fn: Callable[[], T],
    tries: int = 12,
    delay: float = 0.12,
    backoff: float = 1.6,
    max_delay: float = 2.0,
    locked_only: bool = True,
) -> Optional[T]:
    """
    Универсальный ретрай-вызов.

    Параметры:
    - tries: количество попыток.
    - delay: стартовая задержка между попытками.
    - backoff: множитель экспоненциальной задержки.
    - max_delay: верхняя граница задержки.
    - locked_only: если True — ретраим только при sqlite3.OperationalError с текстом 'locked'.

    Возвращает результат fn() или None, если все попытки исчерпаны.
    """
    last_err: Exception | None = None
    d = delay
    for _ in range(max(1, tries)):
        try:
            return fn()
        except sqlite3.OperationalError as e:
            last_err = e
            if locked_only and "locked" not in str(e).lower():
                break
            time.sleep(d)
            d = min(max_delay, d * backoff)
        except Exception as e:
            last_err = e
            break
    return None