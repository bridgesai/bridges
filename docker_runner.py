"""
Docker Runner for executing agents in isolated containers
"""
import asyncio
import json
import tempfile
import shutil
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
import docker
from docker.errors import ContainerError, ImageNotFound, APIError
import aiofiles
import logging
import time
logger = logging.getLogger(__name__)
class DockerRunner:
    """Manages Docker container execution for agents"""
    
    def __init__(self, 
                 image: str = "python:3.11-slim",
                 timeout: int = 300,
                 memory_limit: str = "2g",
                 cpu_limit: float = 2.0):
        """
        Initialize Docker runner
        
        Parameters:
        - image: Docker image to use for agent execution
        - timeout: Maximum execution time in seconds
        - memory_limit: Memory limit for containers (e.g., "512m", "1g")
        - cpu_limit: CPU limit (1.0 = 1 CPU core)
        """
        self.image = image
        self.timeout = timeout
        self.memory_limit = memory_limit
        self.cpu_limit = cpu_limit
        self.client = docker.from_env()
        self.running_containers = {}
        
        self._ensure_image()
    
    def _ensure_image(self):
        """Ensure the Docker image is available locally"""
        try:
            self.client.images.get(self.image)
            logger.info(f"Docker image {self.image} is available")
        except ImageNotFound:
            logger.info(f"Pulling Docker image {self.image}...")
            self.client.images.pull(self.image)
            logger.info(f"Successfully pulled {self.image}")
    
    async def run_agent(self,
                       run_id: str,
                       agent_path: str,
                       problem_statement: str,
                       inference_url: str,
                       api_key: str,
                       files: Optional[Dict[str, bytes]] = None) -> Dict[str, Any]:
        """
        Run an agent in a Docker container
        
        Parameters:
        - run_id: Unique identifier for this run
        - agent_path: Path to the agent Python file
        - problem_statement: The problem to solve
        - inference_url: URL for LLM inference
        - api_key: API key for inference
        - files: Optional dictionary of additional files
        
        Returns:
        - Dictionary with execution results
        """
        temp_dir = None
        container = None
        
        try:
            temp_dir = tempfile.mkdtemp(prefix=f"agent_run_{run_id}_")
            logger.info(f"Created temp directory: {temp_dir}")
            
            agent_file = Path(temp_dir) / "agent.py"
            shutil.copy(agent_path, agent_file)
            logger.info(f"Copied agent file to: {agent_file}")
            
            if files:
                files_dir = Path(temp_dir) / "files"
                files_dir.mkdir(exist_ok=True)
                logger.info(f"Creating files directory with {len(files)} files")
                for file_path, file_content in files.items():
                    file_full_path = files_dir / file_path
                    file_full_path.parent.mkdir(parents=True, exist_ok=True)
                    file_full_path.write_bytes(file_content)
                    logger.info(f"Written file: {file_full_path}")
            
            runner_script = self._create_runner_script(
                problem_statement=problem_statement,
                inference_url=inference_url,
                api_key=api_key,
                run_id=run_id,
                has_files=bool(files)
            )
            
            runner_path = Path(temp_dir) / "runner.py"
            runner_path.write_text(runner_script)
            
            requirements = """
requests>=2.31.0
pytest>=7.4.0
numpy>=1.24.0
pandas>=2.0.0
scipy>=1.10.0
matplotlib>=3.7.0
scikit-learn>=1.3.0
python-dotenv>=1.0.0
aiohttp>=3.9.0
beautifulsoup4>=4.12.0
lxml>=4.9.0
"""
            (Path(temp_dir) / "requirements.txt").write_text(requirements)
            
            logger.info(f"Files in {temp_dir}:")
            for p in Path(temp_dir).rglob('*'):
                if p.is_file():
                    logger.info(f"  - {p.relative_to(temp_dir)}")
            
            docker_cmd = [
                "bash", "-c",
                "apt-get update -qq && apt-get install -y -qq git && pip install -q -r requirements.txt && python runner.py"
            ]
            
            import requests
            try:
                proxy_urls = ["http://localhost:8001", "http://proxy:8001", "http://172.17.0.1:8001"]
                proxy_register_url = None
                
                for url in proxy_urls:
                    try:
                        test_url = f"{url}/health"
                        resp = requests.get(test_url, timeout=2)
                        if resp.status_code == 200:
                            proxy_register_url = f"{url}/register_run"
                            break
                    except:
                        continue
                
                if proxy_register_url:
                    register_data = {
                        "run_id": run_id,
                        "inference_url": inference_url,
                        "api_key": api_key
                    }
                    requests.post(proxy_register_url, params=register_data, timeout=5)
                    logger.info(f"Registered run {run_id} with proxy server at {proxy_register_url}")
                else:
                    logger.warning("Could not find accessible proxy server, continuing anyway")
            except Exception as e:
                logger.warning(f"Failed to register run with proxy: {e}")
            
            internal_proxy_url = "http://proxy:8001"
            
            container_config = {
                "image": self.image,
                "command": docker_cmd,
                "working_dir": "/workspace",
                "volumes": {
                    temp_dir: {"bind": "/workspace", "mode": "rw"}
                },
                "mem_limit": self.memory_limit,
                "cpu_quota": int(self.cpu_limit * 100000),
                "cpu_period": 100000,
                "network": "custom_runner_runner_network",
                "detach": True,
                "remove": False,
                "environment": {
                    "PYTHONUNBUFFERED": "1",
                    "AI_PROXY_URL": internal_proxy_url,
                    "API_KEY": api_key
                }
            }
            
            logger.info(f"Starting container for run {run_id}")
            logger.info(f"Container config: image={container_config['image']}, volumes={container_config['volumes']}")
            container = self.client.containers.run(**container_config)
            self.running_containers[run_id] = container
            logger.info(f"Container {container.id[:12]} started for run {run_id}")
            
            start_time = time.time()
            result = await self._wait_for_container(container, self.timeout)
            execution_time = time.time() - start_time
            
            logs = container.logs(stdout=True, stderr=True).decode('utf-8')
            logger.info(f"Container logs preview for {run_id}: {logs[:500]}")
            
            output_file = Path(temp_dir) / "output.json"
            logger.info(f"Looking for output file at: {output_file}")
            if output_file.exists():
                logger.info(f"Output file found, size: {output_file.stat().st_size} bytes")
                output = json.loads(output_file.read_text())
                logger.info(f"Output loaded successfully, keys: {list(output.keys()) if isinstance(output, dict) else 'not a dict'}")
            else:
                logger.warning(f"Output file not found at {output_file}, extracting from logs")
                output = self._extract_output_from_logs(logs)
            
            return {
                "success": result['exit_code'] == 0,
                "output": output,
                "logs": logs.split('\n'),
                "execution_time": execution_time,
                "exit_code": result['exit_code']
            }
            
        except asyncio.TimeoutError:
            logger.error(f"Container for run {run_id} timed out")
            if container:
                try:
                    container.stop()
                except:
                    pass
            return {
                "success": False,
                "error": f"Execution timed out after {self.timeout} seconds",
                "logs": []
            }
            
        except Exception as e:
            logger.error(f"Error running agent for {run_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "logs": []
            }
            
        finally:
            if container:
                try:
                    container.remove(force=True)
                except:
                    pass
                if run_id in self.running_containers:
                    del self.running_containers[run_id]
            
            try:
                import requests
                requests.delete(f"http://localhost:8001/unregister_run/{run_id}", timeout=5)
                logger.info(f"Unregistered run {run_id} from proxy server")
            except:
                pass
            
            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                except:
                    pass
    
    def _create_runner_script(self, 
                             problem_statement: str,
                             inference_url: str,
                             api_key: str,
                             run_id: str,
                             has_files: bool) -> str:
        """Create the Python script that will run the agent"""
        
        problem_statement = problem_statement.replace("\\", "\\\\").replace('"', '\\"').replace('\n', '\\n')
        
        return f'''
import sys
import json
import os
import traceback
from pathlib import Path

# Set up environment - proxy URL is already set by Docker
# The AI_PROXY_URL environment variable points to internal proxy
proxy_url = os.environ.get("AI_PROXY_URL", "http://proxy:8001")
api_key = os.environ.get("API_KEY", "{api_key}")

# Import the agent
try:
    import agent
except ImportError as e:
    print(f"Error importing agent: {{e}}", file=sys.stderr)
    sys.exit(1)

# Prepare input
input_dict = {{
    "problem_statement": "{problem_statement}",
    "run_id": "{run_id}",
    "proxy_url": proxy_url  # Use the internal proxy URL
}}

# Change to files directory if it exists
if {has_files} and os.path.exists("/workspace/files"):
    os.chdir("/workspace/files")
    # Initialize git repo if not already initialized (needed for patch generation)
    if not os.path.exists(".git"):
        os.system("git init -q")
        os.system("git config --global user.email 'agent@ridges.ai'")
        os.system("git config --global user.name 'Ridges Agent'")
        os.system("git add -A")
        os.system("git commit -q -m 'Initial commit'")

# Run the agent
try:
    # Check if agent has agent_main function
    if hasattr(agent, 'agent_main'):
        # Pass the current directory as repo_dir since we changed to /workspace/files
        result = agent.agent_main(input_dict, repo_dir="." if {has_files} else "/workspace")
    else:
        # Fallback to module-level execution
        print("Warning: agent_main not found, attempting module execution", file=sys.stderr)
        result = {{"error": "agent_main function not found"}}
    
    # Extract patch if it exists in the result
    patch = None
    if isinstance(result, dict) and 'patch' in result:
        patch = result['patch']
    elif isinstance(result, str):
        # If result is directly the patch string
        patch = result
    
    # Try to read patch from git if not in result
    if not patch and {has_files}:
        try:
            import subprocess
            git_result = subprocess.run(["git", "diff", "HEAD"], capture_output=True, text=True)
            if git_result.returncode == 0 and git_result.stdout:
                patch = git_result.stdout
        except:
            pass
    
    # Save output
    output = {{
        "result": result,
        "patch": patch,
        "success": True
    }}
    
except Exception as e:
    print(f"Error running agent: {{e}}", file=sys.stderr)
    print(traceback.format_exc(), file=sys.stderr)
    output = {{
        "error": str(e),
        "traceback": traceback.format_exc(),
        "success": False
    }}

# Write output to file
output_path = "/workspace/output.json"
print(f"Writing output to {{output_path}}", file=sys.stderr)
with open(output_path, "w") as f:
    json.dump(output, f, indent=2, default=str)
print(f"Output written successfully, patch length: {{len(output.get('patch', ''))}}", file=sys.stderr)

print("Agent execution completed")
sys.exit(0)  # Ensure clean exit
'''
    
    async def _wait_for_container(self, container, timeout: int) -> Dict[str, Any]:
        """Wait for container to complete with timeout"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            container.reload()
            if container.status in ['exited', 'dead']:
                return {
                    'exit_code': container.attrs['State']['ExitCode'],
                    'status': container.status
                }
            await asyncio.sleep(1)
        
        raise asyncio.TimeoutError(f"Container did not complete within {timeout} seconds")
    
    def _extract_output_from_logs(self, logs: str) -> Dict[str, Any]:
        """Try to extract structured output from logs"""
        lines = logs.split('\n')
        for line in reversed(lines):
            if line.strip().startswith('{') and line.strip().endswith('}'):
                try:
                    return json.loads(line)
                except:
                    continue
        
        return {"logs": logs}
    
    async def stop_run(self, run_id: str):
        """Stop a running container"""
        if run_id in self.running_containers:
            container = self.running_containers[run_id]
            try:
                container.stop()
                container.remove(force=True)
            except:
                pass
            del self.running_containers[run_id]
    
    async def cleanup(self):
        """Clean up all running containers"""
        for run_id in list(self.running_containers.keys()):
            await self.stop_run(run_id)