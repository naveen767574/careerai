"""
app/services/scraper_scheduler.py

Production-grade scraper scheduler built on stdlib threading only
(no APScheduler dependency needed).

Features:
  - Single global lock — only one scraper run can execute at any time,
    across the scheduled tick AND the manual POST /agent/scraper/run endpoint
  - Retry-with-backoff on failure (up to MAX_RETRIES attempts per scheduled tick)
  - Misfire tracking — if the server was down during a scheduled window, the
    next startup fires immediately instead of waiting another full interval
  - Structured logging with wall-clock timing for every phase
  - Thread-safe status reporting for /health endpoint
"""

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("scraper.scheduler")

# ── Configuration ─────────────────────────────────────────────────────────────

INTERVAL_HOURS: int = 24          # how often the scheduled job fires
MAX_RETRIES: int = 3              # attempts per scheduled tick before giving up
RETRY_BACKOFF_SECONDS: int = 300  # wait between retries (5 minutes)
# If the last run was this many seconds ago when the server restarts,
# fire immediately instead of waiting a full interval (misfire recovery).
MISFIRE_GRACE_SECONDS: int = INTERVAL_HOURS * 3600 * 1.5  # 36 h

# ── Module-level state (shared across threads) ────────────────────────────────

_lock = threading.Lock()           # trylock — prevents concurrent scraper runs
_status: dict = {
    "last_run_at": None,           # ISO string or None
    "last_run_result": None,       # dict from scrape_all() or None
    "last_error": None,            # str or None
    "is_running": False,           # True while a run is in-flight
    "total_runs": 0,
    "total_failures": 0,
}
_status_lock = threading.Lock()    # protects _status dict reads/writes


def get_status() -> dict:
    """Return a copy of the current scheduler status (thread-safe)."""
    with _status_lock:
        return dict(_status)


def _update_status(**kwargs) -> None:
    with _status_lock:
        _status.update(kwargs)


# ── Core run logic ────────────────────────────────────────────────────────────

def _refresh_all_user_recommendations() -> None:
    """
    Regenerate recommendations for every user who has an uploaded resume.
    Called automatically after a scrape run inserts new internships.
    """
    from app.database import SessionLocal
    from app.models.resume import Resume
    from app.services.recommendation_engine import RecommendationEngine

    db = SessionLocal()
    try:
        user_ids = [row[0] for row in db.execute(
            __import__("sqlalchemy").text("SELECT DISTINCT user_id FROM resumes")
        ).fetchall()]
    except Exception as exc:
        logger.error("rec_refresh.fetch_users_failed error=%s", exc, exc_info=True)
        db.close()
        return

    logger.info("rec_refresh.post_scrape starting user_count=%d", len(user_ids))
    t_all = time.perf_counter()
    success, failed = 0, 0
    for uid in user_ids:
        try:
            t0 = time.perf_counter()
            result = RecommendationEngine(db).refresh_for_user(uid)
            elapsed = round(time.perf_counter() - t0, 2)
            logger.info(
                "rec_refresh.user_done user_id=%d recommendations=%d elapsed_s=%.2f",
                uid, result.get("recommendations", 0), elapsed,
            )
            success += 1
        except Exception as exc:
            logger.error(
                "rec_refresh.user_failed user_id=%d error=%s", uid, exc, exc_info=True
            )
            failed += 1

    db.close()
    logger.info(
        "rec_refresh.post_scrape_complete total_users=%d success=%d failed=%d elapsed_s=%.2f",
        len(user_ids), success, failed, round(time.perf_counter() - t_all, 2),
    )


def run_pipeline_once(*, reason: str = "scheduled") -> bool:
    """
    Attempt to acquire the global scraper lock and run the full pipeline
    (scrape + embed).  Returns True if the run completed, False if another
    run was already in-flight (lock not acquired).

    This is the single entry point used by BOTH the scheduler thread and
    the manual POST /agent/scraper/run endpoint — the lock ensures they
    cannot overlap regardless of call origin.
    """
    acquired = _lock.acquire(blocking=False)
    if not acquired:
        logger.warning("scraper.lock_busy reason=%s — another run is in-flight, skipping", reason)
        return False

    _update_status(is_running=True, last_error=None)
    t_total = time.perf_counter()
    logger.info("scraper.run_start reason=%s", reason)

    try:
        from app.scraper.run import run_scraper, run_embedding

        # ── Phase 1: scrape ────────────────────────────────────────────
        t0 = time.perf_counter()
        scrape_results = run_scraper()
        scrape_elapsed = round(time.perf_counter() - t0, 2)
        logger.info(
            "scraper.phase_done phase=scrape elapsed_s=%.2f "
            "inserted=%d updated=%d skipped=%d failed=%d",
            scrape_elapsed,
            scrape_results.get("inserted", 0),
            scrape_results.get("updated", 0),
            scrape_results.get("skipped", 0),
            scrape_results.get("failed", 0),
        )

        # ── Phase 2: embed ─────────────────────────────────────────────
        t0 = time.perf_counter()
        embed_results = run_embedding()
        embed_elapsed = round(time.perf_counter() - t0, 2)
        logger.info(
            "scraper.phase_done phase=embed elapsed_s=%.2f embedded=%d failed=%d",
            embed_elapsed,
            embed_results.get("embedded", 0),
            embed_results.get("failed", 0),
        )

        total_elapsed = round(time.perf_counter() - t_total, 2)
        now_iso = datetime.now(timezone.utc).isoformat()
        logger.info(
            "scraper.run_complete reason=%s total_elapsed_s=%.2f inserted=%d",
            reason, total_elapsed, scrape_results.get("inserted", 0),
        )

        _update_status(
            last_run_at=now_iso,
            last_run_result={
                "scrape": scrape_results,
                "embed": embed_results,
                "elapsed_s": total_elapsed,
            },
            is_running=False,
            total_runs=_status["total_runs"] + 1,
        )

        # Auto-refresh recommendations for all users who have resumes, so
        # high_match counts and recommendation lists stay current after new
        # internships are scraped.  Runs inline (not a sub-thread) so the lock
        # remains held — prevents the manual trigger from racing rec refresh.
        if scrape_results.get("inserted", 0) > 0:
            _refresh_all_user_recommendations()

        return True

    except Exception as exc:
        total_elapsed = round(time.perf_counter() - t_total, 2)
        logger.error(
            "scraper.run_failed reason=%s elapsed_s=%.2f error=%s",
            reason, total_elapsed, exc,
            exc_info=True,   # full traceback in structured logs
        )
        _update_status(
            last_error=str(exc),
            is_running=False,
            total_failures=_status["total_failures"] + 1,
        )
        return False
    finally:
        _lock.release()


def _run_with_retry(*, reason: str) -> None:
    """
    Calls run_pipeline_once up to MAX_RETRIES times with exponential-ish
    backoff between attempts.  The lock is released between retries so a
    manual trigger can still run if the scheduled job is sleeping after a
    failure.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        logger.info("scraper.attempt attempt=%d/%d reason=%s", attempt, MAX_RETRIES, reason)
        success = run_pipeline_once(reason=reason)
        if success:
            return
        if attempt < MAX_RETRIES:
            wait = RETRY_BACKOFF_SECONDS * attempt   # 5 min, 10 min, …
            logger.warning(
                "scraper.retry_wait attempt=%d wait_s=%d reason=%s",
                attempt, wait, reason,
            )
            time.sleep(wait)

    logger.error(
        "scraper.all_retries_exhausted attempts=%d reason=%s",
        MAX_RETRIES, reason,
    )


# ── Scheduler thread ──────────────────────────────────────────────────────────

def _scheduler_loop(stop_event: threading.Event) -> None:
    """
    Main loop for the background scheduler daemon thread.

    Misfire detection: on the first iteration we check how long ago the last
    run was.  If it was more than MISFIRE_GRACE_SECONDS ago (e.g. server was
    restarted after a long outage), we fire immediately instead of sleeping a
    full interval first.
    """
    interval_s = INTERVAL_HOURS * 3600
    logger.info(
        "scheduler.started interval_hours=%d retry_max=%d backoff_s=%d",
        INTERVAL_HOURS, MAX_RETRIES, RETRY_BACKOFF_SECONDS,
    )

    first_tick = True
    while not stop_event.is_set():
        if first_tick:
            first_tick = False
            last_run = _status.get("last_run_at")
            if last_run:
                last_ts = datetime.fromisoformat(last_run).timestamp()
                age_s = time.time() - last_ts
                if age_s > MISFIRE_GRACE_SECONDS:
                    logger.info(
                        "scheduler.misfire_recovery last_run_age_s=%.0f threshold_s=%.0f — firing now",
                        age_s, MISFIRE_GRACE_SECONDS,
                    )
                    _run_with_retry(reason="misfire_recovery")
                    stop_event.wait(timeout=interval_s)
                    continue
            # Normal first startup: wait a full interval before the first
            # scheduled tick so we don't double-run alongside run_scraper_if_empty.
            logger.info("scheduler.waiting_first_tick interval_hours=%d", INTERVAL_HOURS)
            stop_event.wait(timeout=interval_s)
            continue

        if stop_event.is_set():
            break

        _run_with_retry(reason="scheduled")
        stop_event.wait(timeout=interval_s)

    logger.info("scheduler.stopped")


# ── Public API ────────────────────────────────────────────────────────────────

_stop_event: Optional[threading.Event] = None
_scheduler_thread: Optional[threading.Thread] = None


def start() -> None:
    """Start the background scheduler daemon thread. Safe to call at startup."""
    global _stop_event, _scheduler_thread
    if _scheduler_thread and _scheduler_thread.is_alive():
        logger.warning("scheduler.already_running — ignoring duplicate start()")
        return
    _stop_event = threading.Event()
    _scheduler_thread = threading.Thread(
        target=_scheduler_loop,
        args=(_stop_event,),
        daemon=True,
        name="scraper-scheduler",
    )
    _scheduler_thread.start()
    logger.info("scheduler.thread_started name=%s", _scheduler_thread.name)


def stop() -> None:
    """Signal the scheduler thread to stop. Used in tests or graceful shutdown."""
    global _stop_event
    if _stop_event:
        _stop_event.set()
