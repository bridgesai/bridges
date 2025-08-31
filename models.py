"""
Data models for the Custom Agent Runner API
"""
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
class RunStatus(str, Enum):
    """Status of an agent run"""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
class RunRequest(BaseModel):
    """Request model for submitting a new run"""
    agent_id: str = Field(..., description="Agent version ID from Ridges AI")
    problem_statement: str = Field(..., description="Problem description for the agent")
    inference_url: str = Field(..., description="API URL for LLM inference")
    api_key: str = Field(..., description="API key for the inference provider")
    files: Optional[Dict[str, str]] = Field(None, description="Additional files for the agent")
class RunResult(BaseModel):
    """Result model for a run"""
    run_id: str = Field(..., description="Unique identifier for the run")
    agent_id: str = Field(..., description="Agent version ID used")
    status: RunStatus = Field(..., description="Current status of the run")
    created_at: datetime = Field(..., description="When the run was created")
    started_at: Optional[datetime] = Field(None, description="When execution started")
    completed_at: Optional[datetime] = Field(None, description="When execution completed")
    duration_seconds: Optional[float] = Field(None, description="Execution duration in seconds")
    problem_statement: str = Field(..., description="The problem statement")
    output: Optional[Dict[str, Any]] = Field(None, description="Agent output")
    patch: Optional[str] = Field(None, description="Generated patch if any")
    error: Optional[str] = Field(None, description="Error message if failed")
    logs: Optional[List[str]] = Field(None, description="Execution logs")
    files_count: Optional[int] = Field(None, description="Number of files provided")
    agent_path: Optional[str] = Field(None, description="Path to downloaded agent")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
class AgentInfo(BaseModel):
    """Information about an agent from Ridges AI"""
    version_id: str = Field(..., description="Unique version identifier")
    miner_hotkey: str = Field(..., description="Miner's hotkey address")
    version_num: int = Field(..., description="Version number")
    created_at: datetime = Field(..., description="When the agent was created")
    score: Optional[float] = Field(None, description="Agent's score")
    block_uploaded: Optional[int] = Field(None, description="Block number when uploaded")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
class InferenceRequest(BaseModel):
    """Request model for proxy inference endpoint"""
    messages: List[Dict[str, str]] = Field(..., description="Chat messages")
    model: str = Field(..., description="Model to use (selected by agent)")
    temperature: float = Field(0.0, description="Temperature for generation")
    run_id: str = Field(..., description="Run ID for tracking")
class InferenceResponse(BaseModel):
    """Response model for proxy inference endpoint"""
    text_response: str = Field(..., description="Generated text response")
    code_response: Optional[str] = Field("", description="Generated code if any")