import os
import asyncio
import uuid
import logging
import aiosqlite
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("telemetry")

# Load environment variables
load_dotenv()

# We resolve the absolute path to the database file in the project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "diligence.db")

async def write_signal(table: str, payload: dict) -> bool:
    """
    Asynchronously write telemetry data to the specified table in the SQLite database.
    Fails silently with a structured warning log if an error occurs to ensure
    the active agent run is never blocked or crashed.
    """
    # Allowed tables list for security validation
    allowed_tables = {
        "validation_sessions",
        "saturation_signals",
        "cac_ltv_benchmarks",
        "failure_taxonomy"
    }

    if table not in allowed_tables:
        logger.warning(f"Telemetry: Table '{table}' is not recognized. Skipping write.")
        return False

    try:
        # If payload does not contain an id, generate one (since SQLite doesn't default UUIDs automatically)
        data = payload.copy()
        if "id" not in data:
            data["id"] = str(uuid.uuid4())

        # Build insert query dynamically based on payload keys
        columns = list(data.keys())
        values = list(data.values())
        
        col_names = ", ".join(columns)
        placeholders = ", ".join(f":" + col for col in columns)
        query = f"INSERT OR REPLACE INTO {table} ({col_names}) VALUES ({placeholders})"

        # Establish connection with a strict timeout
        async with aiosqlite.connect(DB_PATH, timeout=5.0) as conn:
            await conn.execute(query, data)
            await conn.commit()
            
        logger.info(f"Telemetry: Successfully wrote signal to SQLite table '{table}'.")
        return True

    except Exception as e:
        logger.warning(f"Telemetry write failed: An unexpected error occurred while writing to SQLite table '{table}': {str(e)}")
    
    return False
