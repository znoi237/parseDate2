#!/usr/bin/env python3
"""
Генератор индекса кода:
- Складывает список файлов репозитория в codemap.json (путь, SHA1, размер, число строк).
- Пишет краткий человекочитаемый обзор в CODEMAP.md.
Запускать локально или из CI. Не требует внешних зависимостей.
"""
from __future__ import annotations
import os
import sys
import io
import json
import hashlib
from datetime import datetime
from typing import Dict, List, Tuple

# Настройки
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CODEMAP_JSON = os.path.join(ROOT, "codemap.json")
CODEMAP_MD = os.path.join(ROOT, "CODEMAP.md")

EXCLUDE_DIRS = {
    ".git", ".github", "__pycache__", ".mypy_cache", ".pytest_cache",
    "venv", "env", ".env", "node_modules", ".idea", ".vscode"
}
# Исключаем бинарники и крупные ассеты из индекса (их можно добавить по желанию)
EXCLUDE_EXT = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".zip", ".tar", ".gz", ".rar", ".7z",
    ".pdf", ".woff", ".woff2", ".ttf", ".eot",
}

def is_text_file(path: str) -> bool:
    _, ext = os.path.splitext(path)
    return ext.lower() not in EXCLUDE_EXT

def sha1_of_file(path: str) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def count_lines(path: str) -> int:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0

def walk_files(root: str) -> List[str]:
    files: List[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # фильтруем исключаемые каталоги
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root)
            # пропускаем сам индекс и workflow-артефакты
            if rel in ("codemap.json", "CODEMAP.md"):
                continue
            if not is_text_file(rel):
                continue
            files.append(rel.replace("\\", "/"))
    files.sort()
    return files

def build_codemap(root: str) -> Dict:
    files = walk_files(root)
    items = []
    for rel in files:
        p = os.path.join(root, rel)
        try:
            size = os.path.getsize(p)
        except Exception:
            size = 0
        items.append({
            "path": rel,
            "size_bytes": int(size),
            "lines": int(count_lines(p)),
            "sha1": sha1_of_file(p),
        })
    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "root": os.path.basename(root),
        "files": items,
        "counts": {
            "total_files": len(items),
            "total_bytes": sum(i["size_bytes"] for i in items),
            "total_lines": sum(i["lines"] for i in items),
        },
        "note": "Автогенерация scripts/generate_codemap.py. Не редактируйте вручную."
    }

def write_json(path: str, obj: Dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def write_markdown(path: str, codemap: Dict):
    buf = io.StringIO()
    buf.write("# Code Map\n\n")
    buf.write(f"- Generated at: {codemap.get('generated_at')}\n")
    buf.write(f"- Total files: {codemap.get('counts', {}).get('total_files', 0)}\n")
    buf.write(f"- Total lines: {codemap.get('counts', {}).get('total_lines', 0)}\n")
    buf.write(f"- Total bytes: {codemap.get('counts', {}).get('total_bytes', 0)}\n")
    buf.write("\n")
    buf.write("> Авто‑файл. Обновляется скриптом scripts/generate_codemap.py.\n\n")
    buf.write("## Files\n\n")
    buf.write("| Path | Lines | Size (bytes) | SHA1 |\n")
    buf.write("|------|------:|-------------:|------|\n")
    for it in codemap.get("files", []):
        path = it["path"]
        lines = it["lines"]
        size = it["size_bytes"]
        sha1 = it["sha1"][:12]
        buf.write(f"| {path} | {lines} | {size} | `{sha1}` |\n")
    with open(path, "w", encoding="utf-8") as f:
        f.write(buf.getvalue())

def main():
    codemap = build_codemap(ROOT)
    write_json(CODEMAP_JSON, codemap)
    write_markdown(CODEMAP_MD, codemap)
    print(f"Wrote {CODEMAP_JSON} and {CODEMAP_MD}")
    return 0

if __name__ == "__main__":
    sys.exit(main())