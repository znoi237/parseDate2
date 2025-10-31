#!/usr/bin/env python3
"""
Проверка лимита строк в файлах (по умолчанию ≤300 строк) для исходников.
По умолчанию проверяются расширения: .py, .js
Исключаются стандартные служебные каталоги.
Параметры окружения:
  MAX_LINES=300
  INCLUDE_EXT=".py,.js"
  EXCLUDE_DIRS=".git,__pycache__,venv,node_modules,.github,logs,static/vendor"
"""
from __future__ import annotations
import os
import sys

DEFAULT_EXT = {".py", ".js"}
DEFAULT_EXCL_DIRS = {".git", "__pycache__", "venv", "env", ".env", "node_modules", ".github", ".idea", ".vscode", "logs"}

def parse_set(env_val: str | None, default: set[str]) -> set[str]:
    if not env_val:
        return set(default)
    return {x.strip() for x in env_val.split(",") if x.strip()}

def should_check(path: str, include_ext: set[str], exclude_dirs: set[str]) -> bool:
    rp = path.replace("\\", "/")
    parts = rp.split("/")
    if any(p in exclude_dirs for p in parts[:-1]):
        return False
    _, ext = os.path.splitext(path)
    return ext.lower() in include_ext

def count_lines(path: str) -> int:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0

def main():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    max_lines = int(os.environ.get("MAX_LINES", "300"))
    include_ext = parse_set(os.environ.get("INCLUDE_EXT"), DEFAULT_EXT)
    exclude_dirs = parse_set(os.environ.get("EXCLUDE_DIRS"), DEFAULT_EXCL_DIRS)

    offenders: list[tuple[str, int]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            if not should_check(full, include_ext, exclude_dirs):
                continue
            n = count_lines(full)
            if n > max_lines:
                offenders.append((os.path.relpath(full, root).replace("\\", "/"), n))

    if offenders:
        print("Files exceeding MAX_LINES={}:".format(max_lines))
        for p, n in sorted(offenders):
            print("  - {} ({} lines)".format(p, n))
        return 1

    print("OK: no files exceed {} lines for extensions {}".format(max_lines, ",".join(sorted(include_ext))))
    return 0

if __name__ == "__main__":
    sys.exit(main())