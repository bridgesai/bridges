"""
Proxy Server for handling agent inference requests
This runs as a separate service that agents can call for LLM inference
"""
import os
import logging
from typing import Dict, List, Any
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import uvicorn
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
class InferenceRequest(BaseModel):
    """Request model for inference"""
    messages: List[Dict[str, str]]
    model: str
    temperature: float = 0.0
    run_id: str
    max_tokens: int = 4096
class InferenceResponse(BaseModel):
    """Response model for inference"""
    choices: List[Dict[str, Any]]
app = FastAPI(title="Agent Inference Proxy")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
run_configs: Dict[str, Dict[str, str]] = {}
@app.post("/register_run")
async def register_run(run_id: str, inference_url: str, api_key: str):
    """Register a run with its inference configuration"""
    run_configs[run_id] = {
        "inference_url": inference_url,
        "api_key": api_key
    }
    return {"status": "registered", "run_id": run_id}
@app.post("/agents/inference")
async def handle_inference(request: InferenceRequest):
    """
    Handle inference requests from agents
    This endpoint mimics the expected interface for agents
    """
    run_id = request.run_id
    
    if run_id not in run_configs:
        inference_url = os.getenv("INFERENCE_URL", "https://api.openai.com/v1/chat/completions")
        api_key = os.getenv("API_KEY", "")
        
        if not api_key:
            raise HTTPException(status_code=401, detail="No API key configured for this run")
        
        config = {"inference_url": inference_url, "api_key": api_key}
    else:
        config = run_configs[run_id]
    
    headers = {
        "Content-Type": "application/json"
    }
    
    api_key = config['api_key']
    if api_key.startswith('Bearer '):
        headers["Authorization"] = api_key
    elif 'chutes' in config['inference_url'] or 'Bearer' in api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    else:
        headers["Authorization"] = f"Bearer {api_key}"
    
    provider_request = {
        "messages": request.messages,
        "model": request.model,
        "temperature": request.temperature,
        "max_tokens": request.max_tokens
    }
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                config['inference_url'],
                json=provider_request,
                headers=headers
            )
            
            if response.status_code != 200:
                logger.error(f"Inference error: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Inference provider error: {response.text}"
                )
            
            result = response.json()
            
            if "choices" in result:
                return result
            else:
                return {
                    "choices": [{
                        "message": {
                            "role": "assistant",
                            "content": result.get("text", str(result))
                        }
                    }]
                }
    
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Inference request timed out")
    except httpx.RequestError as e:
        logger.error(f"Request error: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to connect to inference provider: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
@app.delete("/unregister_run/{run_id}")
async def unregister_run(run_id: str):
    """Remove a run's configuration"""
    if run_id in run_configs:
        del run_configs[run_id]
        return {"status": "unregistered", "run_id": run_id}
    return {"status": "not_found", "run_id": run_id}
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "registered_runs": len(run_configs)}
if __name__ == "__main__":
    port = int(os.getenv("PROXY_PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")