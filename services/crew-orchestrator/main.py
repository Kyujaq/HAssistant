"""
Crew Orchestrator - UI Automation Service

Handles UI automation tasks for any application using CrewAI framework.
Supports Excel, browsers, and other Windows applications.
"""

import os
import logging
from typing import Dict, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, validator
from crewai import Agent, Task, Crew, Process
from crewai import LLM
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

# Initialize LLM (Ollama via OpenAI-compatible API)
llm = LLM(
    model=f"openai/{os.getenv('OPENAI_MODEL', 'qwen3:4b-instruct-2507-q4_K_M')}",
    base_url=os.getenv('OPENAI_API_BASE', 'http://ollama-chat:11434/v1'),
    api_key=os.getenv('OPENAI_API_KEY', 'sk-local')
)

# --- Define the UI Automation Crew Agents ---

# Agent 1: The Planner
planner = Agent(
    role='UI Automation Planner',
    goal='Decompose a high-level user goal into a detailed, step-by-step plan for UI interaction with any Windows application (Excel, browsers, etc.). Each step must be a single, simple action.',
    backstory='You are an expert in planning UI automation tasks for Windows applications. You understand Excel, browsers, desktop apps, and can create clear, step-by-step plans for any software. Your plans will be executed by other agents.',
    verbose=True,
    allow_delegation=False,
    llm=llm
)

# Agent 2: The Action Taker
action_agent = Agent(
    role='UI Action Agent',
    goal='Execute a single, specific UI action using the provided voice command tool.',
    backstory='You are a robot that only knows how to use one tool: the Windows Voice Command Tool. You take a single command and execute it perfectly.',
    verbose=True,
    allow_delegation=False,
    tools=[voice_tool],
    llm=llm
)

# Agent 3: The Verifier
verification_agent = Agent(
    role='Screen State Verifier',
    goal='Verify that a UI action was successful by asking a question to the vision tool.',
    backstory='You are a meticulous inspector. After an action is performed, you use your vision tool to check if the screen is in the expected state.',
    verbose=True,
    allow_delegation=False,
    tools=[vision_tool],
    llm=llm
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
        "version": "2.0.0",
        "status": "operational",
        "description": "AI-powered UI automation with multi-agent planning, execution, and verification",
        "endpoints": {
            "health": "/healthz",
            "plan_only": "/crew/task/kickoff",
            "full_execution": "/crew/task/execute",
            "legacy_excel": "/crew/excel/kickoff"
        },
        "features": [
            "Multi-step task planning with Ollama LLM",
            "Voice command execution via Windows Voice Assistant",
            "Vision-based verification of each step",
            "Intelligent retry and error handling"
        ]
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
            verbose=True
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


@app.post("/crew/task/execute")
async def execute_task(task: CrewTask) -> Dict[str, Any]:
    """
    Execute a UI automation task with full plan generation, execution, and verification loop

    Args:
        task: Task definition with goal and target application

    Returns:
        Execution results with detailed step-by-step status

    Raises:
        HTTPException: If task execution fails
    """
    import re

    try:
        logger.info(f"🚀 Starting FULL EXECUTION for {task.application}: {task.goal}")

        # Step 1: Generate the plan
        logger.info("📋 Phase 1: Generating plan...")
        planning_task = Task(
            description=f"Create a step-by-step plan to achieve this goal in {task.application}: '{task.goal}'. "
                        "For each step, provide EXACTLY in this format:\n"
                        "Step N: voice_command='<exact command>' verification='<yes/no question>'\n"
                        "Example: Step 1: voice_command='Open Notepad' verification='Is Notepad window visible?'\n"
                        "Be specific and detailed. Each step should be a single, atomic action.",
            expected_output="A numbered list where each line follows the format: Step N: voice_command='...' verification='...'",
            agent=planner
        )

        planning_crew = Crew(
            agents=[planner],
            tasks=[planning_task],
            process=Process.sequential,
            verbose=True
        )

        plan_result = planning_crew.kickoff()
        plan_text = str(plan_result)
        logger.info(f"✅ Plan generated:\n{plan_text}")

        # Step 2: Parse the plan into structured steps
        logger.info("🔍 Phase 2: Parsing plan...")
        steps = []

        # Parse steps using regex to extract voice_command and verification
        step_pattern = r"Step\s+(\d+):\s*voice_command=['\"]([^'\"]+)['\"]\s*verification=['\"]([^'\"]+)['\"]"
        matches = re.finditer(step_pattern, plan_text, re.IGNORECASE)

        for match in matches:
            step_num = int(match.group(1))
            voice_cmd = match.group(2).strip()
            verification = match.group(3).strip()
            steps.append({
                "step": step_num,
                "voice_command": voice_cmd,
                "verification_query": verification,
                "status": "pending"
            })

        if not steps:
            logger.warning("Could not parse structured steps, attempting fallback parsing...")
            # Fallback: try to extract any commands mentioned
            lines = plan_text.split('\n')
            step_num = 1
            for line in lines:
                if 'voice_command' in line.lower() or 'command' in line.lower():
                    # Try to extract something useful
                    if ':' in line:
                        parts = line.split(':', 1)
                        if len(parts) > 1:
                            steps.append({
                                "step": step_num,
                                "voice_command": parts[1].strip(),
                                "verification_query": "Is the action complete?",
                                "status": "pending"
                            })
                            step_num += 1

        if not steps:
            return {
                "status": "error",
                "message": "Could not parse plan into executable steps",
                "raw_plan": plan_text
            }

        logger.info(f"📝 Parsed {len(steps)} steps from plan")

        # Step 3: Execute each step with verification
        logger.info("⚙️  Phase 3: Executing steps with verification...")
        execution_log = []

        for step in steps:
            step_num = step["step"]
            voice_cmd = step["voice_command"]
            verification_query = step["verification_query"]

            logger.info(f"🎯 Step {step_num}/{len(steps)}: {voice_cmd}")

            # Execute voice command
            try:
                logger.info(f"🎤 Executing: '{voice_cmd}'")
                success, message = voice_tool._run(voice_cmd)

                step["status"] = "executed"
                step["execution_result"] = message

                execution_log.append({
                    "step": step_num,
                    "action": "voice_command",
                    "command": voice_cmd,
                    "success": "✅" in message,
                    "message": message
                })

                # Wait a bit for the action to take effect
                import time
                time.sleep(2)

                # Verify the step (only if verification makes sense)
                # Skip verification for typing commands or other rapid actions
                skip_verification_keywords = ['type', 'press enter', 'press tab']
                should_verify = not any(kw in voice_cmd.lower() for kw in skip_verification_keywords)

                if should_verify and verification_query:
                    logger.info(f"👁️  Verifying: '{verification_query}'")
                    verification_result = vision_tool._run(verification_query)

                    step["verification_result"] = verification_result
                    is_verified = "yes" in verification_result.lower() or "true" in verification_result.lower()

                    execution_log.append({
                        "step": step_num,
                        "action": "verification",
                        "query": verification_query,
                        "result": verification_result,
                        "verified": is_verified
                    })

                    if is_verified:
                        step["status"] = "verified"
                        logger.info(f"✅ Step {step_num} verified successfully")
                    else:
                        step["status"] = "failed_verification"
                        logger.warning(f"⚠️  Step {step_num} verification failed: {verification_result}")
                else:
                    logger.info(f"⏭️  Skipping verification for rapid action: '{voice_cmd}'")
                    step["status"] = "completed"

            except Exception as e:
                logger.error(f"❌ Step {step_num} failed: {str(e)}")
                step["status"] = "error"
                step["error"] = str(e)
                execution_log.append({
                    "step": step_num,
                    "action": "error",
                    "error": str(e)
                })

        # Step 4: Return results
        completed = sum(1 for s in steps if s["status"] in ["verified", "completed"])
        failed = sum(1 for s in steps if s["status"] in ["failed_verification", "error"])

        logger.info(f"🏁 Execution complete: {completed}/{len(steps)} successful, {failed} failed")

        return {
            "status": "completed",
            "application": task.application,
            "goal": task.goal,
            "summary": {
                "total_steps": len(steps),
                "completed": completed,
                "failed": failed,
                "success_rate": f"{(completed/len(steps)*100):.1f}%"
            },
            "steps": steps,
            "execution_log": execution_log,
            "raw_plan": plan_text
        }

    except Exception as e:
        logger.error(f"Fatal error in execution: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")


if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.getenv("PORT", "8085"))
    uvicorn.run(app, host="0.0.0.0", port=port)
