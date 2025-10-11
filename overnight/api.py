# overnight/api.py
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import logging
import asyncio
from typing import Dict, Any, Optional
import os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

try:
    from .orchestrator import OvernightOrchestrator
except ImportError:
    from orchestrator import OvernightOrchestrator  # type: ignore[no-redef]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Overnight Service API",
    description="API for triggering and monitoring long-running overnight tasks.",
    version="0.1.0",
)

ENABLE_INTERNAL_SCHEDULER = os.getenv("ENABLE_INTERNAL_SCHEDULER", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

orchestrator = OvernightOrchestrator()
scheduler: Optional[AsyncIOScheduler] = AsyncIOScheduler() if ENABLE_INTERNAL_SCHEDULER else None

# In-memory store for task status
# For a more robust solution, a database or Redis could be used.
task_status: Dict[str, Any] = {
    "status": "idle",
    "last_run_id": None,
    "last_run_result": None
}

async def run_cycle_background():
    """The actual background task runner."""
    if task_status["status"] == "running":
        logger.warning("Attempted to start a new cycle while one is already running.")
        return

    task_status["status"] = "running"
    logger.info("Starting new overnight cycle.")
    try:
        result = await orchestrator.run_overnight_cycle()
        task_status["last_run_result"] = result
        task_status["status"] = "completed"
        task_status["last_run_id"] = result.get("cycle_id")
        logger.info(f"Overnight cycle {task_status['last_run_id']} completed successfully.")
    except Exception as e:
        logger.error(f"Overnight cycle failed in background: {e}", exc_info=True)
        task_status["status"] = "failed"
        task_status["last_run_result"] = {"error": str(e)}

@app.on_event("startup")
async def startup_event():
    """
    On startup, schedule the nightly run.
    """
    if not ENABLE_INTERNAL_SCHEDULER:
        logger.info("Internal scheduler disabled; external automation should trigger /run-cycle.")
        return

    schedule_hour = int(os.getenv("OVERNIGHT_SCHEDULE_HOUR", "2"))
    logger.info(f"Scheduling nightly overnight cycle to run at {schedule_hour}:00 local time.")
    
    assert scheduler is not None  # For type checkers

    scheduler.add_job(
        run_cycle_background,
        trigger=CronTrigger(hour=schedule_hour, minute=0),
        id="nightly_cycle_job",
        name="Nightly Overnight Cycle",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started.")

@app.on_event("shutdown")
async def shutdown_event():
    """
    On shutdown, stop the scheduler.
    """
    if scheduler:
        logger.info("Scheduler shutting down.")
        scheduler.shutdown()

@app.post("/run-cycle", status_code=202, tags=["Lifecycle"])
async def trigger_overnight_cycle(background_tasks: BackgroundTasks):
    """
    Triggers a full overnight intelligence cycle in the background.
    """
    if task_status["status"] == "running":
        raise HTTPException(status_code=409, detail="An overnight cycle is already in progress.")
    
    logger.info("Manually triggering overnight cycle in the background.")
    background_tasks.add_task(run_cycle_background)
    
    return {"message": "Overnight cycle triggered successfully."}


@app.get("/status", tags=["Lifecycle"])
async def get_cycle_status():
    """
    Gets the current status of the overnight service.
    
    Returns:
        - status: "idle", "running", "completed", or "failed"
        - last_run_id: The UUID of the last completed or failed run.
        - last_run_result: A summary of the last run's results.
    """
    return task_status

@app.get("/healthz", tags=["System"])
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}

