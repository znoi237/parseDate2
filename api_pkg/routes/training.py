import sqlite3
import time
from flask import jsonify, request, current_app, render_template

from config import Config
from ..status_cache import read_status_cache
from ..jobs.training_runner import start_training_job


def _sv():
    return current_app.extensions["services"]


def register(bp):
    @bp.route("/train", methods=["POST"])
    def train():
        sv = _sv()
        body = request.get_json(force=True) or {}
        symbol = body.get("symbol")
        if not symbol:
            return jsonify({"error": "symbol is required"}), 400
        timeframes = body.get("timeframes") or getattr(Config, "TIMEFRAMES", [])
        years = int(body.get("years", getattr(Config, "HISTORY_YEARS", 2)))
        mode = body.get("mode", "auto")
        do_opt = bool(body.get("optimize", getattr(Config, "OPTIMIZE_AFTER_TRAIN", True)))
        job_id = start_training_job(sv, symbol, timeframes, years, mode, do_opt)
        return jsonify({"job_id": job_id, "status": "queued", "mode": mode, "optimize": do_opt})

    @bp.route("/training/<int:job_id>", methods=["GET"])
    def training_status(job_id: int):
        sv = _sv()
        job = sv.db.get_training_job(job_id)
        if not job:
            return jsonify({"error": "not found"}), 404
        sc = read_status_cache(job_id)
        if sc:
            job["status"] = sc.get("status", job.get("status"))
            job["progress"] = sc.get("progress", job.get("progress"))
            job["message"] = sc.get("message", job.get("message"))
        return jsonify({"data": job})

    @bp.route("/training/active", methods=["GET"])
    def training_active():
        sv = _sv()
        job = sv.db.get_active_training_job()
        if not job:
            return jsonify({"data": None})
        sc = read_status_cache(job["id"])
        if sc:
            job["status"] = sc.get("status", job.get("status"))
            job["progress"] = sc.get("progress", job.get("progress"))
            job["message"] = sc.get("message", job.get("message"))
        return jsonify({"data": job})

    @bp.route("/training/<int:job_id>/logs", methods=["GET"])
    def training_logs(job_id: int):
        sv = _sv()
        since_id = request.args.get("since_id")
        limit = request.args.get("limit")
        try:
            since_id = int(since_id) if since_id is not None else None
        except Exception:
            since_id = None
        try:
            limit = int(limit) if limit is not None else 200
        except Exception:
            limit = 200
        rows = sv.db.get_training_logs(job_id, since_id=since_id, limit=limit)
        return jsonify({"data": rows})

    @bp.route("/training/active/logs", methods=["GET"])
    def training_active_logs():
        sv = _sv()
        job = sv.db.get_active_training_job()
        if not job:
            return jsonify({"data": []})
        since_id = request.args.get("since_id")
        limit = request.args.get("limit")
        try:
            since_id = int(since_id) if since_id is not None else None
        except Exception:
            since_id = None
        try:
            limit = int(limit) if limit is not None else 200
        except Exception:
            limit = 200
        rows = sv.db.get_training_logs(job["id"], since_id=since_id, limit=limit)
        return jsonify({"data": rows})

    @bp.route("/training/view", methods=["GET"])
    def training_view():
        return render_template("training.html")