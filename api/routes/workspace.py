import os
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import aiosqlite
from services.progress_calculator import calculate_progress

router = APIRouter(prefix="/workspace", tags=["workspace"])

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_ROOT, "diligence.db")

class TaskStatusUpdate(BaseModel):
    status: str = Field(..., description="Target status: pending, complete, or skipped")

@router.get("/{roadmap_session_id}")
async def get_workspace(roadmap_session_id: str):
    """
    Returns the workspace session details and all 90 tasks grouped by week.
    Handles lookup by both internal roadmap session ID and parent session_id.
    """
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        
        # 1. Fetch parent session (by id or session_id)
        async with conn.execute(
            "SELECT * FROM roadmap_sessions WHERE id = ? OR session_id = ?",
            (roadmap_session_id, roadmap_session_id)
        ) as cursor:
            session = await cursor.fetchone()
            
        if not session:
            raise HTTPException(status_code=404, detail="Roadmap session not found.")
            
        session_id_val = session["id"]
        
        # 2. Fetch all tasks
        async with conn.execute(
            "SELECT * FROM roadmap_tasks WHERE roadmap_session_id = ? ORDER BY day_number ASC",
            (session_id_val,)
        ) as cursor:
            rows = await cursor.fetchall()
            
        # Group tasks by week
        weeks = {}
        for row in rows:
            week_num = str(row["week_number"])
            if week_num not in weeks:
                weeks[week_num] = []
            weeks[week_num].append({
                "id": row["id"],
                "day_number": row["day_number"],
                "week_number": row["week_number"],
                "task_title": row["task_title"],
                "task_description": row["task_description"],
                "owner": row["owner"],
                "deliverable": row["deliverable"],
                "status": row["status"],
                "completed_at": row["completed_at"]
            })
            
        # Fetch dynamic progress stats
        progress = await calculate_progress(session_id_val)
            
        return {
            "roadmap_session_id": session_id_val,
            "session_id": session["session_id"],
            "thesis_summary": session["thesis_summary"],
            "current_day": session["current_day"],
            "completion_pct": progress.get("completion_pct", session["completion_pct"]),
            "status": session["status"],
            "progress_metrics": progress,
            "weeks": weeks
        }

@router.patch("/tasks/{task_id}")
async def patch_task(task_id: str, payload: TaskStatusUpdate):
    """
    Updates status of a roadmap task and triggers progress recalculation.
    """
    status_val = payload.status.lower()
    if status_val not in ["pending", "complete", "skipped"]:
        raise HTTPException(status_code=400, detail="Invalid status. Must be 'pending', 'complete', or 'skipped'.")
        
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        
        # 1. Verify task exists
        async with conn.execute(
            "SELECT roadmap_session_id FROM roadmap_tasks WHERE id = ?",
            (task_id,)
        ) as cursor:
            task = await cursor.fetchone()
            
        if not task:
            raise HTTPException(status_code=404, detail="Task not found.")
            
        roadmap_session_id = task["roadmap_session_id"]
        
        # Determine completed_at timestamp
        completed_at = None
        if status_val in ["complete", "skipped"]:
            completed_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            
        # 2. Update task row
        await conn.execute(
            "UPDATE roadmap_tasks SET status = ?, completed_at = ? WHERE id = ?",
            (status_val, completed_at, task_id)
        )
        await conn.commit()
        
    # 3. Recalculate progress metrics
    progress = await calculate_progress(roadmap_session_id)
    
    return {
        "status": "success",
        "task_id": task_id,
        "new_status": status_val,
        "completed_at": completed_at,
        "progress_metrics": progress
    }

@router.patch("/{roadmap_session_id}/pause")
async def pause_workspace(roadmap_session_id: str):
    """
    Pauses a roadmap workspace session, changing its status to 'paused'.
    This ensures that daily cron increments and weekly checkins skip it.
    """
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        
        # 1. Fetch parent session to ensure it exists
        async with conn.execute(
            "SELECT * FROM roadmap_sessions WHERE id = ? OR session_id = ?",
            (roadmap_session_id, roadmap_session_id)
        ) as cursor:
            session = await cursor.fetchone()
            
        if not session:
            raise HTTPException(status_code=404, detail="Roadmap session not found.")
            
        session_id_val = session["id"]
        
        # 2. Update status to 'paused'
        await conn.execute(
            "UPDATE roadmap_sessions SET status = 'paused' WHERE id = ?",
            (session_id_val,)
        )
        await conn.commit()
        
    return {
        "status": "success",
        "roadmap_session_id": session_id_val,
        "new_status": "paused"
    }
