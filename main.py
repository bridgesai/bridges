"""
Custom Agent Runner API
A FastAPI service for running Ridges AI agents with custom problems and files
"""
import asyncio
import uuid
import time
import zipfile
import io
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn
from models import RunRequest, RunStatus, RunResult, AgentInfo
from agent_manager import AgentManager
from docker_runner import DockerRunner
runs_db: Dict[str, RunResult] = {}
agent_manager: AgentManager = None
docker_runner: DockerRunner = None
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup"""
    global agent_manager, docker_runner
    
    agent_manager = AgentManager()
    docker_runner = DockerRunner()
    
    try:
        await agent_manager.fetch_top_agents()
        print(f"Pre-loaded {len(agent_manager.agents_cache)} agents")
    except Exception as e:
        print(f"Warning: Failed to pre-fetch agents: {e}")
    
    yield
    
    if docker_runner:
        await docker_runner.cleanup()
app = FastAPI(
    title="Custom Agent Runner API",
    description="Run Ridges AI agents with custom problems and files",
    version="1.0.0",
    lifespan=lifespan
)
@app.get("/")
async def root():
    """Health check and API info"""
    return {
        "service": "Custom Agent Runner API",
        "status": "running",
        "endpoints": {
            "POST /run": "Submit a new agent run",
            "GET /runs/{run_id}": "Get run status and results",
            "GET /agents": "List available agents",
            "GET /agents/{version_id}": "Get specific agent info"
        }
    }
@app.post("/run", response_model=RunResult)
async def submit_run(
    background_tasks: BackgroundTasks,
    agent_id: str = Form(..., description="Agent version ID from Ridges AI"),
    problem_statement: str = Form(..., description="Problem description for the agent"),
    inference_url: str = Form(..., description="API URL for LLM inference"),
    api_key: str = Form(..., description="API key for the inference provider"),
    files_zip: Optional[UploadFile] = File(None, description="ZIP file with additional files for agent")
):
    """
    Submit a new agent run with custom problem and files
    
    Parameters:
    - agent_id: Version ID of the agent from Ridges AI
    - problem_statement: The problem/task description
    - inference_url: URL of the inference API (e.g., OpenAI, Anthropic, or custom)
    - api_key: API key for authentication with the inference provider
    - files_zip: Optional ZIP file containing files the agent should have access to
    
    Note: Agents select their own models internally based on their implementation
    """
    
    run_id = str(uuid.uuid4())
    
    run_result = RunResult(
        run_id=run_id,
        agent_id=agent_id,
        status=RunStatus.PENDING,
        created_at=datetime.utcnow(),
        problem_statement=problem_statement
    )
    
    runs_db[run_id] = run_result
    
    extracted_files = None
    if files_zip:
        try:
            zip_content = await files_zip.read()
            extracted_files = extract_zip_files(zip_content)
            run_result.files_count = len(extracted_files)
        except Exception as e:
            run_result.status = RunStatus.FAILED
            run_result.error = f"Failed to extract ZIP file: {str(e)}"
            run_result.completed_at = datetime.utcnow()
            return run_result
    
    try:
        agent_path = await agent_manager.download_agent(agent_id)
        run_result.agent_path = agent_path
    except Exception as e:
        run_result.status = RunStatus.FAILED
        run_result.error = f"Failed to download agent: {str(e)}"
        run_result.completed_at = datetime.utcnow()
        return run_result
    
    background_tasks.add_task(
        execute_agent_run,
        run_id=run_id,
        agent_path=agent_path,
        problem_statement=problem_statement,
        inference_url=inference_url,
        api_key=api_key,
        extracted_files=extracted_files
    )
    
    run_result.status = RunStatus.QUEUED
    return run_result
@app.get("/runs/{run_id}", response_model=RunResult)
async def get_run_status(run_id: str):
    """
    Get the status and results of a specific run
    
    Parameters:
    - run_id: The unique identifier of the run
    """
    if run_id not in runs_db:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    return runs_db[run_id]
@app.get("/runs", response_model=List[RunResult])
async def list_runs(
    limit: int = 50,
    status: Optional[RunStatus] = None
):
    """
    List all runs, optionally filtered by status
    
    Parameters:
    - limit: Maximum number of runs to return
    - status: Filter by run status
    """
    all_runs = list(runs_db.values())
    
    if status:
        all_runs = [r for r in all_runs if r.status == status]
    
    all_runs.sort(key=lambda x: x.created_at, reverse=True)
    
    return all_runs[:limit]
@app.get("/agents", response_model=List[AgentInfo])
async def list_agents(num_agents: int = 15):
    """
    Get the top agents from Ridges AI platform
    
    Parameters:
    - num_agents: Number of top agents to retrieve (default: 15)
    """
    try:
        agents = await agent_manager.fetch_top_agents(num_agents)
        return agents
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch agents: {str(e)}")
@app.get("/agents/{version_id}", response_model=AgentInfo)
async def get_agent_info(version_id: str):
    """
    Get information about a specific agent
    
    Parameters:
    - version_id: The version ID of the agent
    """
    if version_id in agent_manager.agents_cache:
        return agent_manager.agents_cache[version_id]
    
    try:
        agents = await agent_manager.fetch_top_agents()
        for agent in agents:
            if agent.version_id == version_id:
                return agent
        
        raise HTTPException(status_code=404, detail=f"Agent {version_id} not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch agent info: {str(e)}")
@app.delete("/runs/{run_id}")
async def delete_run(run_id: str):
    """
    Delete a run and its associated data
    
    Parameters:
    - run_id: The unique identifier of the run to delete
    """
    if run_id not in runs_db:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    run_result = runs_db[run_id]
    
    if run_result.status in [RunStatus.RUNNING, RunStatus.QUEUED]:
        try:
            await docker_runner.stop_run(run_id)
        except Exception as e:
            print(f"Warning: Failed to stop container for run {run_id}: {e}")
    
    del runs_db[run_id]
    
    return {"message": f"Run {run_id} deleted successfully"}
def extract_zip_files(zip_content: bytes) -> Dict[str, bytes]:
    """Extract files from ZIP content"""
    extracted = {}
    
    with zipfile.ZipFile(io.BytesIO(zip_content), 'r') as zf:
        for file_info in zf.filelist:
            if not file_info.is_dir():
                file_path = file_info.filename
                file_content = zf.read(file_path)
                extracted[file_path] = file_content
    
    return extracted
async def execute_agent_run(
    run_id: str,
    agent_path: str,
    problem_statement: str,
    inference_url: str,
    api_key: str,
    extracted_files: Optional[Dict[str, bytes]]
):
    """Execute an agent run in the background"""
    print(f"DEBUG: Starting execute_agent_run for run_id={run_id}")
    run_result = runs_db[run_id]
    
    try:
        run_result.status = RunStatus.RUNNING
        run_result.started_at = datetime.utcnow()
        print(f"DEBUG: Updated status to RUNNING for run_id={run_id}")
        
        print(f"DEBUG: Calling docker_runner.run_agent for run_id={run_id}")
        result = await docker_runner.run_agent(
            run_id=run_id,
            agent_path=agent_path,
            problem_statement=problem_statement,
            inference_url=inference_url,
            api_key=api_key,
            files=extracted_files
        )
        print(f"DEBUG: docker_runner.run_agent completed for run_id={run_id}, result={result}")
        
        run_result.status = RunStatus.COMPLETED if result.get("success") else RunStatus.FAILED
        run_result.output = result.get("output", {})
        
        patch = ""
        if isinstance(run_result.output, dict):
            patch = run_result.output.get("patch", "")
            if not patch and "result" in run_result.output:
                if isinstance(run_result.output["result"], dict):
                    patch = run_result.output["result"].get("patch", "")
                elif isinstance(run_result.output["result"], str):
                    patch = run_result.output["result"]
        
        run_result.patch = patch
        run_result.error = result.get("error")
        run_result.logs = result.get("logs", [])
        run_result.completed_at = datetime.utcnow()
        
        if run_result.started_at:
            duration = (run_result.completed_at - run_result.started_at).total_seconds()
            run_result.duration_seconds = duration
        
    except asyncio.TimeoutError:
        print(f"DEBUG: Timeout error for run_id={run_id}")
        run_result.status = RunStatus.TIMEOUT
        run_result.error = "Agent execution timed out"
        run_result.completed_at = datetime.utcnow()
    except Exception as e:
        print(f"DEBUG: Exception in execute_agent_run for run_id={run_id}: {str(e)}")
        import traceback
        print(f"DEBUG: Traceback: {traceback.format_exc()}")
        run_result.status = RunStatus.FAILED
        run_result.error = f"Execution error: {str(e)}"
        run_result.completed_at = datetime.utcnow()
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8888,
        reload=True,
        log_level="info"
    )