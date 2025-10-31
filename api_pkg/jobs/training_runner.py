import time
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

from flask import current_app

from config import Config
from ..status_cache import append_job_file, write_status_cache
from precompute_cache import build_precompute
from optimizer import optimize_symbol_tf, GridDefaults, grid_size
from backtest import run_backtest
from utils.retry import with_retries


def _sv():
    return current_app.extensions["services"]


def start_training_job(sv, symbol: str, timeframes: list[str], years: int, mode: str, do_opt: bool) -> int:
    job_id = sv.db.create_training_job(symbol, timeframes)

    def add_log(level: str, phase: str, message: str, data: dict | None = None):
        append_job_file(job_id, level, phase, message, data)
        with_retries(lambda: sv.db.add_training_log(job_id, level, phase, message, data or {}))

    def update_job(msg: str, prog: float, status: str = "running"):
        write_status_cache(job_id, status, prog, msg)
        with_retries(lambda: sv.db.update_training_job(job_id, status=status, progress=prog, message=msg))

    def backtest_and_update_metrics_parallel(tfs: list[str]):
        workers = min(len(tfs), max(1, int(getattr(Config, "BACKTEST_MAX_WORKERS", 4))))
        timeout_sec = int(getattr(Config, "BACKTEST_TIMEOUT_SEC", 180))
        add_log("INFO", "backtest", f"start post-backtest parallel for {tfs}", {"workers": workers})
        precomps = {}
        for tf in tfs:
            try:
                precomps[tf] = build_precompute(sv.db, sv.models, symbol, tf, limit=5000)
            except Exception as e:
                precomps[tf] = None
                add_log("ERROR", "backtest", f"precompute failed {symbol} {tf}: {e}")

        done, total = 0, len(tfs)
        update_job(f"backtesting 0/{total}", 0.97, "running")
        results = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {}
            for tf in tfs:
                tuned = sv.db.load_model_params(symbol, tf) or {}
                futures[pool.submit(
                    run_backtest,
                    sv.db, sv.models, symbol, tf,
                    5000,
                    float(tuned.get("signal_threshold", getattr(Config, "SIGNAL_THRESHOLD", 0.6))),
                    float(tuned.get("hold_margin", 0.05)),
                    int(tuned.get("min_confirmed_higher", 0)),
                    float(tuned.get("sl_atr_mult", 1.0)),
                    float(tuned.get("tp_atr_mult", 2.0)),
                    int(tuned.get("max_bars_in_trade", 200)),
                    precomps.get(tf)
                )] = (tf, tuned)
            deadline = time.time() + timeout_sec
            pending = set(futures.keys())
            while pending:
                remaining = max(0.0, deadline - time.time())
                if remaining == 0:
                    break
                try:
                    for fut in as_completed(list(pending), timeout=remaining):
                        pending.remove(fut)
                        tf, tuned = futures[fut]
                        try:
                            bt = fut.result()
                            results.append((tf, tuned, bt))
                        except Exception as e:
                            add_log("ERROR", "backtest", f"post-backtest failed {symbol} {tf}: {e}")
                        finally:
                            done += 1
                            prog = 0.97 + 0.02 * (done / max(1, total))
                            update_job(f"backtesting {done}/{total}", prog, "running")
                except TimeoutError:
                    break

            if pending:
                for fut in list(pending):
                    tf, tuned = futures[fut]
                    fut.cancel()
                    add_log("ERROR", "backtest", f"timeout, fallback sync {symbol} {tf}", {"timeout": timeout_sec})
                    try:
                        bt = run_backtest(
                            sv.db, sv.models, symbol, tf,
                            5000,
                            float(tuned.get("signal_threshold", getattr(Config, "SIGNAL_THRESHOLD", 0.6))),
                            float(tuned.get("hold_margin", 0.05)),
                            int(tuned.get("min_confirmed_higher", 0)),
                            float(tuned.get("sl_atr_mult", 1.0)),
                            float(tuned.get("tp_atr_mult", 2.0)),
                            int(tuned.get("max_bars_in_trade", 200)),
                            precomps.get(tf)
                        )
                        results.append((tf, tuned, bt))
                    finally:
                        done += 1
                        prog = 0.97 + 0.02 * (done / max(1, total))
                        update_job(f"backtesting {done}/{total}", prog, "running")

        for tf, tuned, bt in results:
            stats = (bt or {}).get("stats", {}) if bt else {}
            def _upd():
                sv.db.update_model_metrics(symbol, tf, {
                    "bt_winrate": stats.get("winrate"),
                    "bt_trades_count": stats.get("count"),
                    "tuned_params": tuned or None
                })
            with_retries(_upd)
            add_log("INFO", "backtest", f"done backtest {symbol} {tf}", {"stats": stats})

    def task():
        try:
            add_log("INFO", "sync", f"history sync start {symbol} tfs={timeframes} years={years} mode={mode}")
            update_job("sync history", 0.0)
            for tf in timeframes:
                add_log("INFO", "sync", f"fetch {symbol} {tf}")
                sv.data.fetch_ohlcv_incremental(symbol, tf, years, force_full=(mode == "full"))
            add_log("INFO", "sync", "history sync complete")
            update_job("training", 0.05, "running")

            add_log("INFO", "train", f"train start {symbol} tfs={timeframes} mode={mode}")
            sv.models.train_symbol(symbol, timeframes, years, job_id=job_id, mode=mode)
            add_log("INFO", "train", f"train complete {symbol}")
            update_job("optimizing", 0.80, "running")

            if do_opt:
                totals = {tf: grid_size(GridDefaults) for tf in timeframes}
                tf_done = {tf: 0 for tf in timeframes}

                def on_prog(ev: dict):
                    tf = ev.get("tf")
                    i = int(ev.get("i", 0)); total = int(ev.get("total", 1))
                    tf_done[tf] = max(tf_done.get(tf, 0), min(i, total))
                    frac = (sum(tf_done.values()) / max(1, sum(totals.values())))
                    p = 0.80 + 0.17 * min(1.0, frac)
                    p = min(0.97, max(0.80, p))
                    write_status_cache(job_id, "running", p, f"optimizing {tf} {i}/{total}")
                    if ev.get("phase") == "final" or i % 50 == 0 or i == total:
                        add_log("DEBUG", "optimize", f"tf {tf} step {i}/{total}", {"best": ev.get("best")})
                add_log("INFO", "optimize", f"opt start {symbol} tfs={timeframes}")
                for tf in timeframes:
                    optimize_symbol_tf(sv.db, sv.models, symbol, tf, on_progress=on_prog)
                    add_log("INFO", "optimize", f"tf {tf} finished")
                add_log("INFO", "optimize", f"opt complete {symbol}")
                write_status_cache(job_id, "running", 0.97, "backtesting with tuned params")

                backtest_and_update_metrics_parallel(timeframes)

                write_status_cache(job_id, "finished", 1.0, "Completed")
                with_retries(lambda: sv.db.update_training_job(job_id, status="finished", progress=1.0, message="Completed"), tries=4)
                add_log("INFO", "final", "training pipeline completed", {"symbol": symbol, "tfs": timeframes})
            else:
                write_status_cache(job_id, "finished", 1.0, "Completed")
                with_retries(lambda: sv.db.update_training_job(job_id, status="finished", progress=1.0, message="Completed"), tries=4)
                add_log("INFO", "final", "training completed (optimize disabled)", {"symbol": symbol, "tfs": timeframes})

        except Exception as e:
            write_status_cache(job_id, "error", 0.0, str(e))
            with_retries(lambda: sv.db.update_training_job(job_id, status="error", message=str(e)), tries=3, delay=0.2, locked_only=False)
            append_job_file(job_id, "ERROR", "error", f"train task error: {e}")

    sv.executor.submit(task)
    return job_id