"""
Crew Orchestrator - UI Automation Service

Handles UI automation tasks for any application using CrewAI framework.
Supports Excel, browsers, and other Windows applications.
"""

import logging
from typing import Dict, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, validator
from crewai import Agent, Task, Crew, Process
from crew_tools import VoiceCommandTool, VisionVerificationTool

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("crew-orchestrator")

# FastAPI app
app = FastAPI(title="Crew Orchestrator", version="1.0.0")

# Initialize Tools
voice_tool = VoiceCommandTool()
vision_tool = VisionVerificationTool()

# --- Define the UI Automation Crew Agents ---

# Agent 1: The Planner
planner = Agent(
    role='UI Automation Planner',
    goal='Decompose a high-level user goal into a detailed, step-by-step plan for UI interaction with any Windows application (Excel, browsers, etc.). Each step must be a single, simple action.',
    backstory='You are an expert in planning UI automation tasks for Windows applications. You understand Excel, browsers, desktop apps, and can create clear, step-by-step plans for any software. Your plans will be executed by other agents.',
    verbose=True,
    allow_delegation=False
)

# Agent 2: The Action Taker
action_agent = Agent(
    role='UI Action Agent',
    goal='Execute a single, specific UI action using the provided voice command tool.',
    backstory='You are a robot that only knows how to use one tool: the Windows Voice Command Tool. You take a single command and execute it perfectly.',
    verbose=True,
    allow_delegation=False,
    tools=[voice_tool]
)

# Agent 3: The Verifier
verification_agent = Agent(
    role='Screen State Verifier',
    goal='Verify that a UI action was successful by asking a question to the vision tool.',
    backstory='You are a meticulous inspector. After an action is performed, you use your vision tool to check if the screen is in the expected state.',
    verbose=True,
    allow_delegation=False,
    tools=[vision_tool]
)


class CrewTask(BaseModel):
    """Request model for crew tasks"""
    goal: str = Field(..., min_length=1, max_length=500, description="The goal to accomplish")
    application: str = Field(default="Excel", description="Target application (e.g., 'Excel', 'Chrome', 'Notepad')")

    @validator('goal')
    def validate_goal(cls, v):
        """Validate that goal is meaningful"""
        if not v or not v.strip():
            raise ValueError("Goal cannot be empty or whitespace only")
        return v.strip()

    @validator('application')
    def validate_application(cls, v):
        """Normalize application name"""
        return v.strip() if v else "Excel"


@app.get("/")
async def root():
    """Root endpoint with service info"""
    return {
        "service": "Crew Orchestrator",
        "version": "1.0.0",
        "status": "operational",
        "endpoints": {
            "health": "/healthz",
            "kickoff_excel": "/crew/excel/kickoff",
            "kickoff_task": "/crew/task/kickoff"
        }
    }


@app.get("/healthz")
async def health_check():
    """Health check endpoint"""
    try:
        # Verify tools are initialized
        if not voice_tool or not vision_tool:
            return {"ok": False, "service": "crew-orchestrator", "error": "Tools not initialized"}
        
        # Verify agents are initialized
        if not planner or not action_agent or not verification_agent:
            return {"ok": False, "service": "crew-orchestrator", "error": "Agents not initialized"}
        
        return {
            "ok": True, 
            "service": "crew-orchestrator",
            "agents": {
                "planner": "initialized",
                "action_agent": "initialized",
                "verification_agent": "initialized"
            },
            "tools": {
                "voice_command": "initialized",
                "vision_verification": "initialized"
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {"ok": False, "service": "crew-orchestrator", "error": str(e)}


@app.post("/crew/excel/kickoff")
async def kickoff_excel_task(task: CrewTask) -> Dict[str, Any]:
    """
    Kickoff an Excel-related task using CrewAI (Legacy endpoint for compatibility)

    Args:
        task: Task definition with goal

    Returns:
        Task execution result
    """
    # Force application to Excel
    task.application = "Excel"
    return await kickoff_task(task)


@app.post("/crew/task/kickoff")
async def kickoff_task(task: CrewTask) -> Dict[str, Any]:
    """
    Kickoff a UI automation task for any application using CrewAI

    Args:
        task: Task definition with goal and target application

    Returns:
        Task execution result

    Raises:
        HTTPException: If task execution fails
    """
    try:
        logger.info(f"Received task for {task.application} with goal: {task.goal}")

        if not task.goal:
            raise HTTPException(status_code=400, detail="Goal cannot be empty")

        # Task 1: Create the plan
        planning_task = Task(
            description=f"Create a step-by-step plan to achieve this goal in {task.application}: '{task.goal}'. "
                        "For each step, define the exact voice command to speak (e.g., 'Open {task.application}', 'Click menu File', 'Type hello') "
                        "and a verification question to ask (e.g., 'Is {task.application} open?', 'Is the File menu visible?'). "
                        "Be specific about {task.application}'s UI elements and commands. "
                        "The final output must be just the plan itself, clearly listing each step's voice command and verification question.",
            expected_output="A numbered list of steps. Each step includes a 'voice_command' and a 'verification_query'.",
            agent=planner
        )

        # Create the crew and execute
        automation_crew = Crew(
            agents=[planner],
            tasks=[planning_task],
            process=Process.sequential,
            verbose=2
        )

        logger.info(f"Starting crew execution for {task.application}: {task.goal}")
        result = automation_crew.kickoff()
        logger.info(f"Crew execution completed successfully")

        return {
            "status": "success",
            "application": task.application,
            "goal": task.goal,
            "result": str(result),
            "note": "This is the PLAN. Execution with verification loop is next phase."
        }

    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing task: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Task execution failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8084)
