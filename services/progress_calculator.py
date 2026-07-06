import os
import logging
import aiosqlite

logger = logging.getLogger("services.progress_calculator")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "diligence.db")

async def calculate_progress(roadmap_session_id: str) -> dict:
    """
    Calculates completion percentage and slippage metrics for a roadmap session
    and persists completion_pct to roadmap_sessions.
    """
    logger.info(f"ProgressCalculator: Calculating progress for roadmap session {roadmap_session_id}")

    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        
        # 1. Fetch parent session to get current_day
        async with conn.execute(
            "SELECT current_day FROM roadmap_sessions WHERE id = ?",
            (roadmap_session_id,)
        ) as cursor:
            session = await cursor.fetchone()
            
        if not session:
            logger.error(f"ProgressCalculator: Roadmap session {roadmap_session_id} not found.")
            return {}

        current_day = session["current_day"]

        # 2. Fetch all tasks for the session
        async with conn.execute(
            "SELECT day_number, status FROM roadmap_tasks WHERE roadmap_session_id = ?",
            (roadmap_session_id,)
        ) as cursor:
            tasks = await cursor.fetchall()

        total = len(tasks)
        if total == 0:
            logger.warning(f"ProgressCalculator: Session {roadmap_session_id} has 0 tasks.")
            return {
                "completion_pct": 0.0,
                "completed_tasks": 0,
                "total_tasks": 0,
                "slippage_days": 0,
                "on_track": True
            }

        completed = sum(1 for t in tasks if t["status"] == "complete")
        completion_pct = round((completed / total) * 100, 2)

        # 3. Update parent session with completion percentage
        await conn.execute(
            "UPDATE roadmap_sessions SET completion_pct = ? WHERE id = ?",
            (completion_pct, roadmap_session_id)
        )
        await conn.commit()

        # 4. Calculate last completed day
        completed_days = [t["day_number"] for t in tasks if t["status"] == "complete"]
        last_completed_day = max(completed_days) if completed_days else 0

        # 5. Slippage calculation: calendar day elapsed (current_day) vs last completed day number
        slippage_days = current_day - last_completed_day

        on_track = slippage_days <= 2

        metrics = {
            "completion_pct": completion_pct,
            "completed_tasks": completed,
            "total_tasks": total,
            "slippage_days": max(slippage_days, 0),
            "on_track": on_track
        }
        
        logger.info(f"ProgressCalculator: Session {roadmap_session_id} metrics: {metrics}")
        return metrics
