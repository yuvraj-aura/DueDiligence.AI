import os
import sqlite3
import logging
from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger("services.daily_cron")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "diligence.db")

def increment_current_day():
    """
    Cron job function that increments the current_day column
    by +1 for every active roadmap session.
    """
    logger.info("DailyCron: Running scheduled increment of active roadmap sessions...")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute(
            "UPDATE roadmap_sessions SET current_day = current_day + 1 WHERE status = 'active'"
        )
        conn.commit()
        
        affected_rows = cursor.rowcount
        conn.close()
        
        logger.info(f"DailyCron: Successfully advanced current_day for {affected_rows} active session(s).")
    except Exception as e:
        logger.error(f"DailyCron: Failed to execute daily increment: {e}")

def run_weekly_checkins_sync():
    """
    Runs the async process_weekly_checkins function inside a sync job context.
    """
    import asyncio
    from services.checkin_scheduler import process_weekly_checkins
    logger.info("DailyCron: Starting weekly check-ins processing job...")
    try:
        asyncio.run(process_weekly_checkins())
    except Exception as e:
        logger.error(f"DailyCron: Failed to run weekly check-ins job: {e}")

def start_scheduler():
    """
    Initializes and starts the background daily cron scheduler.
    """
    logger.info("DailyCron: Initializing background scheduler...")
    scheduler = BackgroundScheduler()
    
    # Run once daily at midnight
    scheduler.add_job(
        increment_current_day,
        trigger="cron",
        hour=0,
        minute=0,
        id="daily_roadmap_increment",
        replace_existing=True
    )
    
    # Run check-in processing daily at 00:05 AM
    scheduler.add_job(
        run_weekly_checkins_sync,
        trigger="cron",
        hour=0,
        minute=5,
        id="daily_weekly_checkins",
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("DailyCron: Background daily cron scheduler started successfully.")
    return scheduler
