"""
Agent Manager for fetching and caching agents from Ridges AI platform
"""
import time
import asyncio
import aiohttp
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from models import AgentInfo
class AgentManager:
    """Manages fetching and caching of agents from Ridges AI"""
    
    def __init__(self, cache_dir: str = "./agent_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        self.agents_cache: Dict[str, AgentInfo] = {}
        self.last_fetch: float = 0
        self.cache_ttl: int = 300
        
        self.headers = {
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
            'Origin': 'https://www.ridges.ai',
            'Referer': 'https://www.ridges.ai/',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
            'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36',
            'sec-ch-ua': '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"'
        }
    
    async def fetch_top_agents(self, num_agents: int = 15) -> List[AgentInfo]:
        """
        Fetch the top agents from Ridges AI platform
        
        Parameters:
        - num_agents: Number of top agents to fetch
        
        Returns:
        - List of AgentInfo objects
        """
        if time.time() - self.last_fetch < self.cache_ttl and self.agents_cache:
            return list(self.agents_cache.values())[:num_agents]
        
        url = f"https://platform.ridges.ai/retrieval/top-agents?num_agents={num_agents}"
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, headers=self.headers) as response:
                    response.raise_for_status()
                    agents_data = await response.json()
                    
                    self.agents_cache = {}
                    for agent_data in agents_data:
                        if isinstance(agent_data.get('created_at'), str):
                            agent_data['created_at'] = datetime.fromisoformat(
                                agent_data['created_at'].replace('Z', '+00:00')
                            )
                        
                        agent = AgentInfo(**agent_data)
                        self.agents_cache[agent.version_id] = agent
                    
                    self.last_fetch = time.time()
                    return list(self.agents_cache.values())
                    
            except aiohttp.ClientError as e:
                raise Exception(f"Failed to fetch agents from Ridges AI: {str(e)}")
            except Exception as e:
                raise Exception(f"Error processing agents data: {str(e)}")
    
    async def download_agent(self, version_id: str) -> str:
        """
        Download an agent file and return the path
        
        Parameters:
        - version_id: The version ID of the agent to download
        
        Returns:
        - Path to the downloaded agent file
        """
        agent_path = self.cache_dir / f"{version_id}.py"
        if agent_path.exists():
            print(f"Agent {version_id} already cached at {agent_path}")
            return str(agent_path)
        
        url = f"https://platform.ridges.ai/retrieval/agent-version-file?version_id={version_id}&return_as_text=true"
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, headers=self.headers) as response:
                    response.raise_for_status()
                    response_text = await response.text()
                    
                    import json
                    try:
                        agent_code = json.loads(response_text)
                    except json.JSONDecodeError:
                        agent_code = response_text
                    
                    with open(agent_path, 'w', encoding='utf-8') as f:
                        f.write(agent_code)
                    
                    print(f"Downloaded agent {version_id} to {agent_path}")
                    return str(agent_path)
                    
            except aiohttp.ClientError as e:
                raise Exception(f"Failed to download agent {version_id}: {str(e)}")
            except Exception as e:
                raise Exception(f"Error saving agent {version_id}: {str(e)}")
    
    async def get_agent_info(self, version_id: str) -> Optional[AgentInfo]:
        """
        Get information about a specific agent
        
        Parameters:
        - version_id: The version ID of the agent
        
        Returns:
        - AgentInfo object or None if not found
        """
        if version_id in self.agents_cache:
            return self.agents_cache[version_id]
        
        agents = await self.fetch_top_agents()
        for agent in agents:
            if agent.version_id == version_id:
                return agent
        
        return None
    
    def clear_cache(self):
        """Clear the in-memory metadata cache"""
        self.agents_cache = {}
        self.last_fetch = 0
    
    def clear_agent_files(self):
        """Remove all cached agent files"""
        for agent_file in self.cache_dir.glob("*.py"):
            agent_file.unlink()
        print(f"Cleared all agent files from {self.cache_dir}")
    
    async def prefetch_agents(self, num_agents: int = 5):
        """
        Pre-download the top N agents for faster execution
        
        Parameters:
        - num_agents: Number of top agents to pre-download
        """
        agents = await self.fetch_top_agents(num_agents)
        
        download_tasks = []
        for agent in agents[:num_agents]:
            download_tasks.append(self.download_agent(agent.version_id))
        
        results = await asyncio.gather(*download_tasks, return_exceptions=True)
        
        successful = sum(1 for r in results if not isinstance(r, Exception))
        print(f"Pre-downloaded {successful}/{num_agents} agents")
        
        return results