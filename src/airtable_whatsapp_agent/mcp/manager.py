"""
MCP server manager for coordinating multiple MCP servers.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional
from .base import MCPRequest, MCPResponse
from .external_client import ExternalMCPManager, ExternalMCPServerConfig
from ..config import Settings


logger = logging.getLogger(__name__)


class MCPServerManager:
    """Manager for coordinating multiple MCP servers."""
    
    def __init__(self, settings: Settings):
        """Initialize MCP server manager."""
        self.settings = settings
        self.external_manager = ExternalMCPManager()
        self.logger = logging.getLogger(__name__)
        
    async def initialize(self) -> None:
        """Initialize all MCP servers."""
        self.logger.info("Initializing MCP server manager")
        
        # Initialize external MCP servers
        if self.settings.mcp.airtable_server_url:
            await self._initialize_airtable_server()
        if self.settings.mcp.whatsapp_server_url:
            await self._initialize_whatsapp_server()
            
        await self.external_manager.initialize_all()
        self.logger.info(f"Initialized {len(self.external_manager.list_servers())} external MCP servers")
        
    async def cleanup(self) -> None:
        """Cleanup all MCP servers."""
        self.logger.info("Cleaning up MCP servers")
        await self.external_manager.cleanup_all()
        
    async def _initialize_airtable_server(self) -> None:
        """Initialize external Airtable MCP server."""
        try:
            config = ExternalMCPServerConfig(
                name="airtable",
                url=self.settings.mcp.airtable_server_url,
                timeout=self.settings.mcp.timeout,
                max_retries=self.settings.mcp.max_retries,
                retry_delay=self.settings.mcp.retry_delay
            )
            self.external_manager.add_server(config)
            self.logger.info("External Airtable MCP server configured successfully")
        except Exception as e:
            self.logger.error(f"Failed to configure external Airtable MCP server: {e}")
            raise
            
    async def _initialize_whatsapp_server(self) -> None:
        """Initialize external WhatsApp MCP server."""
        try:
            config = ExternalMCPServerConfig(
                name="whatsapp",
                url=self.settings.mcp.whatsapp_server_url,
                timeout=self.settings.mcp.timeout,
                max_retries=self.settings.mcp.max_retries,
                retry_delay=self.settings.mcp.retry_delay
            )
            self.external_manager.add_server(config)
            self.logger.info("External WhatsApp MCP server configured successfully")
        except Exception as e:
            self.logger.error(f"Failed to configure external WhatsApp MCP server: {e}")
            raise
            
    async def call_tool(self, server_name: str, tool_name: str, params: Dict[str, Any]) -> Any:
        """Call a tool on a specific MCP server."""
        return await self.external_manager.call_tool(server_name, tool_name, params)
        
    async def handle_request(self, server_name: str, request: MCPRequest) -> MCPResponse:
        """Handle MCP request for a specific server."""
        return await self.external_manager.handle_request(server_name, request)
        
    def get_server(self, name: str) -> Optional[Any]:
        """Get MCP server by name."""
        return self.external_manager.get_client(name)
        
    def list_servers(self) -> List[str]:
        """List available MCP servers."""
        return self.external_manager.list_servers()
        
    async def get_server_tools(self, server_name: str) -> List[Dict[str, Any]]:
        """Get tools for a specific server."""
        return await self.external_manager.get_server_tools(server_name)
        
    async def get_all_tools(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all tools from all servers."""
        all_tools = {}
        for server_name in self.external_manager.list_servers():
            all_tools[server_name] = await self.get_server_tools(server_name)
        return all_tools
        
    async def health_check(self) -> Dict[str, bool]:
        """Perform health check on all servers."""
        health_status = {}
        for server_name in self.external_manager.list_servers():
            try:
                client = self.external_manager.get_client(server_name)
                if client:
                    health_status[server_name] = await client.test_connection()
                else:
                    health_status[server_name] = False
            except Exception as e:
                self.logger.error(f"Health check failed for {server_name}: {e}")
                health_status[server_name] = False
        return health_status
        
    async def get_server_info(self, server_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific server."""
        client = self.external_manager.get_client(server_name)
        if not client:
            return None
        
        tools = await self.get_server_tools(server_name)
        return {
            "name": client.config.name,
            "url": client.config.url,
            "timeout": client.config.timeout,
            "tools": len(tools),
            "tool_names": [tool.get("name", "") for tool in tools]
        }
        
    async def get_all_server_info(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all servers."""
        server_info = {}
        for server_name in self.external_manager.list_servers():
            info = await self.get_server_info(server_name)
            if info:
                server_info[server_name] = info
        return server_info
        
    async def execute_batch_requests(self, requests: List[tuple[str, MCPRequest]]) -> List[MCPResponse]:
        """Execute multiple requests in batch."""
        tasks = []
        for server_name, request in requests:
            task = self.handle_request(server_name, request)
            tasks.append(task)
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        processed_responses = []
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                processed_responses.append(MCPResponse(error={"code": "BATCH_ERROR", "message": str(response)}, id=requests[i][1].id))
            else:
                processed_responses.append(response)
        return processed_responses
        
    async def broadcast_to_servers(self, method: str, params: Dict[str, Any], server_filter: Optional[List[str]] = None) -> Dict[str, Any]:
        """Broadcast a method call to multiple servers."""
        target_servers = server_filter or self.external_manager.list_servers()
        results = {}
        for server_name in target_servers:
            client = self.external_manager.get_client(server_name)
            if not client:
                results[server_name] = {"error": f"Server {server_name} not found"}
                continue
            try:
                if hasattr(client, method):
                    result = await getattr(client, method)(**params)
                    results[server_name] = {"result": result}
                else:
                    results[server_name] = {"error": f"Method {method} not found on server {server_name}"}
            except Exception as e:
                results[server_name] = {"error": str(e)}
        return results