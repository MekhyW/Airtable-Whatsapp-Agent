"""
External MCP client for communicating with public MCP servers.
"""

import logging
from typing import Any, Dict, List, Optional
import httpx
from pydantic import BaseModel
from .base import MCPRequest, MCPResponse
from ..utils.error_handling import error_handler, retry_on_failure, EXTERNAL_MCP_RETRY_CONFIG
from ..utils.rate_limiter import RateLimiter, RateLimitMiddleware, EXTERNAL_MCP_RATE_LIMIT

logger = logging.getLogger(__name__)


class ExternalMCPServerConfig(BaseModel):
    """Configuration for external MCP server."""
    name: str
    url: str
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0


class ExternalMCPClient:
    """Client for communicating with external MCP servers."""
    
    def __init__(self, config: ExternalMCPServerConfig):
        """Initialize external MCP client."""
        self.config = config
        self.client = httpx.AsyncClient(timeout=config.timeout)
        self.rate_limiter = RateLimiter(EXTERNAL_MCP_RATE_LIMIT)
        self.rate_limit_middleware = RateLimitMiddleware(self.rate_limiter)
        self.logger = logging.getLogger(f"{__name__}.{config.name}")
        self.circuit_breaker = error_handler.register_circuit_breaker(
            f"external_mcp_{config.name}",
            {
                "failure_threshold": 5,
                "recovery_timeout": 60,
                "name": f"external_mcp_{config.name}"
            }
        )
    
    async def initialize(self) -> None:
        """Initialize the client and test connection."""
        try:
            await self.test_connection()
            self.logger.info(f"External MCP client for {self.config.name} initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize external MCP client for {self.config.name}: {e}")
            raise
    
    async def cleanup(self) -> None:
        """Cleanup resources."""
        await self.client.aclose()
    
    @retry_on_failure(EXTERNAL_MCP_RETRY_CONFIG)
    async def test_connection(self) -> bool:
        """Test connection to the external MCP server."""
        try:
            response = await self.client.get(f"{self.config.url}/health")
            response.raise_for_status()
            return True
        except Exception as e:
            self.logger.error(f"Connection test failed for {self.config.name}: {e}")
            raise
    
    @retry_on_failure(EXTERNAL_MCP_RETRY_CONFIG)
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools from the external MCP server."""
        try:
            response = await self.rate_limit_middleware(self._list_tools_impl)()
            return response
        except Exception as e:
            self.logger.error(f"Failed to list tools from {self.config.name}: {e}")
            raise
    
    async def _list_tools_impl(self) -> List[Dict[str, Any]]:
        """Implementation for listing tools."""
        response = await self.client.post(f"{self.config.url}/mcp/listTools", json={})
        response.raise_for_status()
        data = response.json()
        return data.get("tools", [])
    
    @retry_on_failure(EXTERNAL_MCP_RETRY_CONFIG)
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on the external MCP server."""
        try:
            response = await self.rate_limit_middleware(self._call_tool_impl)(tool_name, arguments)
            return response
        except Exception as e:
            self.logger.error(f"Failed to call tool {tool_name} on {self.config.name}: {e}")
            raise
    
    async def _call_tool_impl(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Implementation for calling a tool."""
        payload = {"name": tool_name, "arguments": arguments}
        response = await self.client.post(f"{self.config.url}/mcp/callTool", json=payload)
        response.raise_for_status()
        return response.json()
    
    async def handle_request(self, request: MCPRequest) -> MCPResponse:
        """Handle MCP request by forwarding to external server."""
        try:
            result = await self.call_tool(request.method, request.params or {})
            return MCPResponse(result=result, id=request.id)
        except Exception as e:
            self.logger.error(f"Error handling request for {self.config.name}: {e}")
            return MCPResponse(error={"code": "EXTERNAL_SERVER_ERROR", "message": str(e)}, id=request.id)


class ExternalMCPManager:
    """Manager for multiple external MCP clients."""
    
    def __init__(self):
        """Initialize external MCP manager."""
        self.clients: Dict[str, ExternalMCPClient] = {}
        self.logger = logging.getLogger(__name__)
    
    def add_server(self, config: ExternalMCPServerConfig) -> None:
        """Add an external MCP server."""
        client = ExternalMCPClient(config)
        self.clients[config.name] = client
        self.logger.info(f"Added external MCP server: {config.name}")
    
    async def initialize_all(self) -> None:
        """Initialize all external MCP clients."""
        self.logger.info("Initializing external MCP clients")
        for name, client in self.clients.items():
            try:
                await client.initialize()
            except Exception as e:
                self.logger.error(f"Failed to initialize {name}: {e}")
        self.logger.info(f"Initialized {len(self.clients)} external MCP clients")
    
    async def cleanup_all(self) -> None:
        """Cleanup all external MCP clients."""
        for client in self.clients.values():
            try:
                await client.cleanup()
            except Exception as e:
                self.logger.error(f"Error during cleanup: {e}")
    
    def get_client(self, name: str) -> Optional[ExternalMCPClient]:
        """Get external MCP client by name."""
        return self.clients.get(name)
    
    def list_servers(self) -> List[str]:
        """List available external MCP servers."""
        return list(self.clients.keys())
    
    async def get_server_tools(self, server_name: str) -> List[Dict[str, Any]]:
        """Get tools for a specific external server."""
        client = self.clients.get(server_name)
        if not client:
            return []
        try:
            return await client.list_tools()
        except Exception as e:
            self.logger.error(f"Failed to get tools for {server_name}: {e}")
            return []
    
    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on a specific external server."""
        client = self.clients.get(server_name)
        if not client:
            raise ValueError(f"External MCP server '{server_name}' not found")
        return await client.call_tool(tool_name, arguments)
    
    async def handle_request(self, server_name: str, request: MCPRequest) -> MCPResponse:
        """Handle MCP request for a specific external server."""
        client = self.clients.get(server_name)
        if not client:
            return MCPResponse(error={"code": "SERVER_NOT_FOUND", "message": f"External MCP server '{server_name}' not found"}, id=request.id)
        return await client.handle_request(request)