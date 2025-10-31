import json
import time
import os
from datetime import datetime


def ensure_dir():
    os.makedirs("logs/training", exist_ok=True)


def job_log_path(job_id: int) -> str:
    ensure_dir()
    return os.path.join("logs", "training", f"job_{job_id}.log")


def status_cache_path(job_id: int) -> str:
    ensure_dir()
    return os.path.join("logs", "training", f"job_{job_id}.status.json")


def append_job_file(job_id: int, level: str, phase: str, message: str, data: dict | None = None):
    try:
        p = job_log_path(job_id)
        line = json.dumps(
            {"ts": datetime.utcnow().isoformat(), "level": level or "INFO", "phase": phase, "message": message, "data": data or {}},
            ensure_ascii=False,
        )
        with open(p, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def write_status_cache(job_id: int, status: str, progress: float, message: str):
    try:
        payload = {"ts": time.time(), "status": status, "progress": float(progress or 0.0), "message": message or ""}
        with open(status_cache_path(job_id), "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
    except Exception:
        pass


def read_status_cache(job_id: int) -> dict | None:
    try:
        with open(status_cache_path(job_id), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None