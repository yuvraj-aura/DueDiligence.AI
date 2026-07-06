import uuid
import hashlib
import time
import asyncio
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from api.schemas import ValidationRequest, PreValidateRequest
from api.session_cache import SessionCache
from data_layer.telemetry import write_signal
from agents.orchestrator import run_pipeline  # Move import to the top to avoid route import latency
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Proactively initialize cache in the background during app startup
    asyncio.create_task(cache.initialize())
    
    # Start daily cron job scheduler
    from services.daily_cron import start_scheduler
    app.state.scheduler = start_scheduler()
    
    yield
    
    # Shutdown scheduler
    app.state.scheduler.shutdown()

app = FastAPI(title="AI Due Diligence Gateway API", lifespan=lifespan)
cache = SessionCache()
session_service = InMemorySessionService()

# Add CORS middleware to support local testing and external Antigravity components
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def slugify(text: str) -> str:
    return "-".join(text.lower().split())

@app.post("/pre-validate")
async def pre_validate(request: PreValidateRequest):
    from agents.gatekeeper import pre_flight_agent
    
    session_id = str(uuid.uuid4())
    runner = Runner(
        agent=pre_flight_agent,
        session_service=session_service,
        app_name="ai-due-diligence",
        auto_create_session=True
    )
    
    prompt_input = (
        f"Thesis: {request.thesis}\n"
        f"Target Micro-Niche: {request.target_micro_niche}\n"
        f"Monetization Model: {request.monetization_model}\n"
    )
    
    user_content = types.Content(
        role="user",
        parts=[types.Part(text=prompt_input)]
    )
    
    try:
        async for event in runner.run_async(
            user_id="default_user",
            session_id=session_id,
            new_message=user_content
        ):
            pass
            
        session = await session_service.get_session(
            app_name="ai-due-diligence",
            user_id="default_user",
            session_id=session_id
        )
        
        pre_flight_result = session.state.get("pre_flight_output")
        if not pre_flight_result:
            raise HTTPException(status_code=500, detail="Gatekeeper failed to evaluate thesis.")
            
        if not pre_flight_result.get("passed", False):
            raise HTTPException(status_code=400, detail=pre_flight_result.get("reason", "Thesis validation failed."))
            
        return {"status": "success", "message": "Pre-flight check passed."}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal pre-flight check error: {str(e)}")

@app.post("/validate", status_code=202)
async def validate_idea(request: ValidationRequest, background_tasks: BackgroundTasks):
    start_time = time.time()
    
    # Generate session ID and calculate SHA-256 hash
    session_id = str(uuid.uuid4())
    session_hash = hashlib.sha256(session_id.encode('utf-8')).hexdigest()
    
    # Initialize cache record
    session_data = {
        "session_id": session_id,
        "session_hash": session_hash,
        "status": "PENDING",
        "inputs": request.dict(),
        "created_at": time.time()
    }
    
    # Write to Redis/In-memory cache
    await cache.set_session(session_id, session_data)
    
    # Asynchronously trigger the orchestrator validation pipeline
    background_tasks.add_task(run_pipeline, session_id, session_hash, request.dict())
    
    # Check execution duration to ensure < 200ms target is met
    duration_ms = (time.time() - start_time) * 1000
    if duration_ms > 200:
        print(f"Warning: /validate took {duration_ms:.2f}ms which exceeds the 200ms threshold!")
    
    return {
        "session_id": session_id,
        "session_hash": session_hash,
        "status": "PENDING"
    }

@app.get("/status/{session_id}")
async def get_status(session_id: str):
    session_data = await cache.get_session(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return session_data

@app.get("/stream/{session_id}")
async def stream_status(session_id: str):
    """
    Server-Sent Events (SSE) stream endpoint to yield real-time pipeline status.
    Feeds updates to the frontend Status Tracker page.
    """
    async def event_generator():
        last_status = None
        retry_limit = 60  # Wait up to 5 minutes max
        retries = 0
        
        while retries < retry_limit:
            session_data = await cache.get_session(session_id)
            if not session_data:
                yield f"data: {json.dumps({'status': 'not_found'})}\n\n"
                await asyncio.sleep(2.0)
                retries += 1
                continue
                
            status = session_data.get("status")
            # Always yield the current state
            yield f"data: {json.dumps(session_data)}\n\n"
            
            # Stop streaming if final state is reached
            if status in ["builder_complete", "killed", "error", "builder_failed"]:
                logger_msg = f"SSE Stream ended for session {session_id} with status: {status}"
                print(logger_msg)
                break
                
            await asyncio.sleep(1.0)
            retries = 0  # reset retries since session is active
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

# Register workspace router
from api.routes.workspace import router as workspace_router
app.include_router(workspace_router)

# Mount frontend client UI directory
app.mount("/ui", StaticFiles(directory="ui", html=True), name="ui")
