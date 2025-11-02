"""UTCP Client for universal tool calling."""

import httpx
import json
import os
from typing import Dict, Any, List, Optional
from pathlib import Path


class UTCPClient:
    """Universal Tool Calling Protocol client."""
    
    def __init__(self, tools_config: str = "utcp-tools.json"):
        config_path = Path(tools_config)
        if not config_path.exists():
            config_path = Path(__file__).parent.parent.parent / tools_config
        
        with open(config_path) as f:
            self.tools = json.load(f)["tools"]
        
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def call_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Call a tool via UTCP protocol."""
        tool = next((t for t in self.tools if t["name"] == tool_name), None)
        if not tool:
            raise ValueError(f"Tool {tool_name} not found")
        
        url = tool["endpoint"].format(**kwargs)
        method = tool["method"]
        headers = {}
        params = {}
        
        # Handle authentication
        auth_config = tool.get("auth", {})
        auth_type = auth_config.get("type")
        
        if auth_type == "bearer":
            api_key = self._get_api_key(tool_name)
            headers["Authorization"] = f"Bearer {api_key}"
        elif auth_type == "header":
            header_name = auth_config.get("header")
            api_key = self._get_api_key(tool_name)
            headers[header_name] = api_key
        elif auth_type == "query_params":
            for param in auth_config.get("params", []):
                params[param] = self._get_api_key(f"{tool_name}_{param}")
        
        # Add parameters
        for key, value in kwargs.items():
            if key not in url:
                params[key] = value
        
        # Make request
        if method == "GET":
            response = await self.client.get(url, params=params, headers=headers)
        elif method == "POST":
            response = await self.client.post(url, json=kwargs, headers=headers)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        response.raise_for_status()
        return response.json()
    
    def _get_api_key(self, key_name: str) -> str:
        """Get API key from environment."""
        env_key = key_name.upper().replace("-", "_")
        api_key = os.getenv(env_key)
        if not api_key:
            raise ValueError(f"API key {env_key} not found in environment")
        return api_key
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
