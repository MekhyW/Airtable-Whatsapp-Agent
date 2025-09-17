"""
Base MCP server implementation and configuration.
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
import httpx


logger = logging.getLogger(__name__)


class MCPServerConfig(BaseModel):
    """Configuration for MCP servers."""

    name: str = Field(..., description="Server name")
    host: str = Field(default="localhost", description="Server host")
    port: int = Field(default=8080, description="Server port")
    api_key: Optional[str] = Field(None, description="API key for authentication")
    base_url: Optional[str] = Field(None, description="Base URL for the server")
    timeout: int = Field(default=30, description="Request timeout in seconds")
    max_retries: int = Field(default=3, description="Maximum number of retries")
    retry_delay: float = Field(default=1.0, description="Delay between retries in seconds")
    headers: Dict[str, str] = Field(default_factory=dict, description="Additional headers")
    ssl_verify: bool = Field(default=True, description="Whether to verify SSL certificates")
    rate_limit: Optional[int] = Field(None, description="Rate limit per minute")
    
    class Config:
        """Pydantic configuration."""
        extra = "allow"


class MCPRequest(BaseModel):
    """MCP request model."""
    
    method: str = Field(..., description="Request method")
    params: Dict[str, Any] = Field(default_factory=dict, description="Request parameters")
    id: Optional[str] = Field(None, description="Request ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Request timestamp")
    
    class Config:
        """Pydantic configuration."""
        json_encoders = { datetime: lambda v: v.isoformat() if v else None }


class MCPResponse(BaseModel):
    """MCP response model."""
    
    result: Optional[Any] = Field(None, description="Response result")
    error: Optional[Dict[str, Any]] = Field(None, description="Error information")
    id: Optional[str] = Field(None, description="Request ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
    
    @property
    def is_success(self) -> bool:
        """Check if response is successful."""
        return self.error is None
    
    class Config:
        """Pydantic configuration."""
        json_encoders = { datetime: lambda v: v.isoformat() if v else None }


class MCPTool(BaseModel):
    """MCP tool definition."""
    
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Tool parameters schema")
    required: List[str] = Field(default_factory=list, description="Required parameters")
    examples: List[Dict[str, Any]] = Field(default_factory=list, description="Usage examples")
    
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate tool parameters."""
        for required_param in self.required:
            if required_param not in params:
                return False
        return True


class BaseMCPServer(ABC):
    """Base class for MCP servers."""
    
    def __init__(self, config: MCPServerConfig):
        """Initialize MCP server."""
        self.config = config
        self.client = httpx.AsyncClient(timeout=config.timeout, verify=config.ssl_verify, headers=config.headers)
        self.tools: Dict[str, MCPTool] = {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()
        
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the MCP server."""
        pass
        
    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup resources."""
        pass
        
    @abstractmethod
    async def handle_request(self, request: MCPRequest) -> MCPResponse:
        """Handle MCP request."""
        pass
        
    def register_tool(self, tool: MCPTool) -> None:
        """Register a tool with the server."""
        self.tools[tool.name] = tool
        self.logger.info(f"Registered tool: {tool.name}")
        
    def get_tool(self, name: str) -> Optional[MCPTool]:
        """Get a tool by name."""
        return self.tools.get(name)
        
    def list_tools(self) -> List[MCPTool]:
        """List all available tools."""
        return list(self.tools.values())
        
    async def call_tool(self, name: str, params: Dict[str, Any]) -> MCPResponse:
        """Call a tool with parameters."""
        tool = self.get_tool(name)
        if not tool:
            return MCPResponse(error={"code": "TOOL_NOT_FOUND", "message": f"Tool '{name}' not found"})
        if not tool.validate_params(params):
            return MCPResponse(error={"code": "INVALID_PARAMS", "message": f"Invalid parameters for tool '{name}'"})
        try:
            result = await self._execute_tool(name, params)
            return MCPResponse(result=result)
        except Exception as e:
            self.logger.error(f"Error executing tool '{name}': {e}")
            return MCPResponse(error={"code": "EXECUTION_ERROR", "message": str(e)})
            
    @abstractmethod
    async def _execute_tool(self, name: str, params: Dict[str, Any]) -> Any:
        """Execute a tool with parameters."""
        pass
        
    async def make_request(self, method: str, url: str, data: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, retries: Optional[int] = None) -> MCPResponse:
        """Make HTTP request with retry logic."""
        if retries is None:
            retries = self.config.max_retries
        request_headers = self.config.headers.copy()
        if headers:
            request_headers.update(headers)
        for attempt in range(retries + 1):
            try:
                if method.upper() == "GET":
                    response = await self.client.get(url, headers=request_headers)
                elif method.upper() == "POST":
                    response = await self.client.post(url, json=data, headers=request_headers)
                elif method.upper() == "PUT":
                    response = await self.client.put(url, json=data, headers=request_headers)
                elif method.upper() == "DELETE":
                    response = await self.client.delete(url, headers=request_headers)
                else:
                    return MCPResponse(error={"code": "INVALID_METHOD", "message": f"Unsupported HTTP method: {method}"})
                response.raise_for_status()
                try:
                    result = response.json()
                except json.JSONDecodeError:
                    result = response.text
                return MCPResponse(result=result)
            except httpx.HTTPStatusError as e:
                if attempt == retries:
                    return MCPResponse(error={"code": "HTTP_ERROR", "message": f"HTTP {e.response.status_code}: {e.response.text}"})
            except Exception as e:
                if attempt == retries:
                    return MCPResponse(error={"code": "REQUEST_ERROR", "message": str(e)})
            if attempt < retries:
                await asyncio.sleep(self.config.retry_delay * (2 ** attempt))
        return MCPResponse(error={"code": "MAX_RETRIES_EXCEEDED", "message": f"Maximum retries ({retries}) exceeded"})
        
    async def health_check(self) -> bool:
        """Perform health check."""
        try:
            # Override in subclasses for specific health checks
            return True
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False
            
    def get_server_info(self) -> Dict[str, Any]:
        """Get server information."""
        return {
            "name": self.config.name,
            "host": self.config.host,
            "port": self.config.port,
            "tools": [tool.name for tool in self.tools.values()],
            "status": "running"
        }