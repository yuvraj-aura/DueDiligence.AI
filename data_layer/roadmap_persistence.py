import os
import uuid
import json
import logging
import aiosqlite

logger = logging.getLogger("data_layer.roadmap_persistence")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "diligence.db")

async def persist_roadmap(session_id: str, thesis_summary: str, builder_output_json) -> str:
    """
    Persists the 90-day execution roadmap into SQLite diligence.db.
    """
    logger.info(f"RoadmapPersistence: Starting ingestion for session {session_id}...")
    
    # Parse inputs
    if isinstance(builder_output_json, str):
        try:
            data = json.loads(builder_output_json)
        except Exception as e:
            logger.error(f"RoadmapPersistence: Failed to parse JSON string: {e}")
            raise
    elif isinstance(builder_output_json, dict):
        data = builder_output_json
    else:
        try:
            data = builder_output_json.dict()
        except Exception:
            data = {}

    roadmap_list = data.get("roadmap", [])
    if not roadmap_list:
        logger.warning("RoadmapPersistence: No roadmap data found in builder output.")
        return ""

    roadmap_session_id = uuid.uuid4().hex

    async with aiosqlite.connect(DB_PATH) as conn:
        # Insert parent session record
        await conn.execute(
            """
            INSERT INTO roadmap_sessions (
                id, session_id, thesis_summary, total_days, current_day, completion_pct, status
            ) VALUES (?, ?, ?, 90, 1, 0.0, 'active')
            """,
            (roadmap_session_id, session_id, thesis_summary)
        )

        # Prepare bulk tasks
        tasks_data = []
        for item in roadmap_list:
            task_id = uuid.uuid4().hex
            day = item.get("day", 1)
            week = item.get("week", 1)
            task_text = item.get("task", "")
            owner = item.get("owner", "Solo Developer")
            deliverable = item.get("deliverable", "")

            task_title = task_text[:150] if len(task_text) > 150 else task_text
            task_description = task_text

            tasks_data.append((
                task_id,
                roadmap_session_id,
                day,
                week,
                task_title,
                task_description,
                owner,
                deliverable,
                "pending"
            ))

        # Bulk insert exactly 90 tasks
        await conn.executemany(
            """
            INSERT INTO roadmap_tasks (
                id, roadmap_session_id, day_number, week_number,
                task_title, task_description, owner, deliverable, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            tasks_data
        )

        await conn.commit()
        logger.info(f"RoadmapPersistence: Successfully saved parent session {roadmap_session_id} and {len(tasks_data)} tasks.")
        return roadmap_session_id
