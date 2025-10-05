from fastapi import FastAPI
from pydantic import BaseModel
from crewai import Agent, Task, Crew, Process
from crew_tools import VoiceCommandTool, VisionVerificationTool

# Initialize Tools
voice_tool = VoiceCommandTool()
vision_tool = VisionVerificationTool()

# --- Define the Excel Crew ---

# Agent 1: The Planner
planner = Agent(
    role='UI Automation Planner',
    goal='Decompose a high-level user goal into a detailed, step-by-step plan for UI interaction. Each step must be a single, simple action.',
    backstory='You are an expert in planning UI automation tasks. You think step-by-step and create clear, machine-readable plans. Your plans will be executed by other agents.',
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

# --- FastAPI Server Setup ---

app = FastAPI()

class KickoffPayload(BaseModel):
    goal: str

@app.post("/crew/excel/kickoff")
async def kickoff_excel_crew(payload: KickoffPayload):
    goal = payload.goal

    # Task 1: Create the plan
    planning_task = Task(
        description=f"Create a step-by-step plan to achieve the goal: '{goal}'. "
                    "For each step, define the exact voice command to speak and the verification question to ask. "
                    "The final output must be just the plan itself, clearly listing each step's voice command and verification question.",
        expected_output="A numbered list of steps. Each step includes a 'voice_command' and a 'verification_query'.",
        agent=planner
    )

    # For now, we are only creating the planning task.
    # The logic to execute the full plan step-by-step will be built upon this.
    excel_crew = Crew(
        agents=[planner],
        tasks=[planning_task],
        process=Process.sequential,
        verbose=2
    )

    result = excel_crew.kickoff()
    return {"status": "success", "result": result}

# Add a root endpoint for health checks
@app.get("/")
def read_root():
    return {"status": "Crew Orchestrator is running"}
