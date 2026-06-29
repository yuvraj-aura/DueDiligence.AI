import os
import asyncio
import aiosqlite

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "diligence.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")

async def main():
    print(f"Connecting to SQLite database at {DB_PATH}...")
    
    # Read schema file
    with open(SCHEMA_PATH, "r") as f:
        schema_sql = f.read()

    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            print("Applying schema.sql...")
            await conn.executescript(schema_sql)
            await conn.commit()
            print("SQLite Schema applied successfully!")
    except Exception as e:
        print(f"Failed to apply SQLite schema: {e}")

if __name__ == "__main__":
    asyncio.run(main())
