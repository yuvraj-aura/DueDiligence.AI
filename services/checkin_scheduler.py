import os
import logging
from datetime import datetime, timedelta
import aiosqlite
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from services.progress_calculator import calculate_progress

logger = logging.getLogger("services.checkin_scheduler")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "diligence.db")

SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")

async def send_checkin_email(email_address: str, roadmap_session_id: str, progress_data: dict):
    """
    Sends check-in email via SendGrid, then updates roadmap_sessions.last_checkin_at.
    """
    logger.info(f"CheckinScheduler: Preparing check-in email for session {roadmap_session_id}")
    
    completion_pct = progress_data.get("completion_pct", 0.0)
    completed_tasks = progress_data.get("completed_tasks", 0)
    total_tasks = progress_data.get("total_tasks", 90)
    slippage_days = progress_data.get("slippage_days", 0)
    on_track = progress_data.get("on_track", True)
    
    workspace_link = f"http://localhost:8000/ui/workspace.html?id={roadmap_session_id}"
    
    if on_track:
        subject = "🚀 Great work! You are on track with your validation roadmap."
        body_content = (
            f"Hi Founder,\n\n"
            f"Congratulations! You are making great progress and are on track with your 90-day execution plan.\n"
            f"You have completed {completed_tasks}/{total_tasks} tasks ({completion_pct}% completion).\n\n"
            f"Keep up the momentum! Access your Workspace dashboard here: {workspace_link}\n\n"
            f"Best,\nDueDiligence.AI Team"
        )
    else:
        subject = "⚠️ Action Required: You are falling behind on your validation roadmap."
        body_content = (
            f"Hi Founder,\n\n"
            f"Warning: You are currently {slippage_days} days behind schedule on your 90-day execution plan.\n"
            f"You have completed {completed_tasks}/{total_tasks} tasks ({completion_pct}% completion).\n"
            f"There are {total_tasks - completed_tasks} open tasks remaining.\n\n"
            f"Catch up by accessing your Workspace dashboard here: {workspace_link}\n\n"
            f"Best,\nDueDiligence.AI Team"
        )

    # 1. Dispatch SendGrid request
    if SENDGRID_API_KEY:
        try:
            message = Mail(
                from_email="no-reply@duediligence.ai",
                to_emails=email_address,
                subject=subject,
                plain_text_content=body_content
            )
            sg = SendGridAPIClient(SENDGRID_API_KEY)
            
            # Run in executor to prevent blocking
            import asyncio
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, sg.send, message)
            logger.info(f"CheckinScheduler: Successfully sent SendGrid email to {email_address}")
        except Exception as e:
            logger.error(f"CheckinScheduler: SendGrid API call failed: {e}")
    else:
        logger.info(
            f"CheckinScheduler (MOCK): Sending checkin email to {email_address} (SENDGRID_API_KEY is not set)\n"
            f"Subject: {subject}\n"
            f"Body:\n{body_content}"
        )

    # 2. Update last_checkin_at timestamp to now
    current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "UPDATE roadmap_sessions SET last_checkin_at = ? WHERE id = ?",
            (current_time, roadmap_session_id)
        )
        await conn.commit()
    logger.info(f"CheckinScheduler: Updated last_checkin_at for session {roadmap_session_id}")

async def process_weekly_checkins():
    """
    Selects active roadmap sessions on day 7, 14, 21 etc. and sends check-in emails.
    Ensures duplicate check-ins are not sent within 5 days.
    """
    logger.info("CheckinScheduler: Running check-in process...")
    
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        
        # Select active sessions on weekly interval days, excluding duplicates within last 5 days
        async with conn.execute(
            """
            SELECT id, session_id, current_day, last_checkin_at 
            FROM roadmap_sessions 
            WHERE status = 'active' 
              AND current_day % 7 = 0
              AND (
                  last_checkin_at IS NULL 
                  OR datetime(last_checkin_at) < datetime('now', '-5 days')
              )
            """
        ) as cursor:
            sessions = await cursor.fetchall()
            
        logger.info(f"CheckinScheduler: Found {len(sessions)} session(s) due for weekly check-in.")
        
        for session in sessions:
            roadmap_session_id = session["id"]
            
            # Recalculate progress first
            progress = await calculate_progress(roadmap_session_id)
            
            # Dispatch check-in email (defaulting to founder fallback email)
            await send_checkin_email("founder@example.com", roadmap_session_id, progress)
