"""
Tool registry for the autonomous agent.
Manages available tools and their execution.
"""

import logging
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum
from ..models.agent import ToolExecutionResult
from ..mcp.manager import MCPServerManager
from ..config import Settings
from ..aws.eventbridge import EventBridgeScheduler, ScheduledTask, ScheduleType

logger = logging.getLogger(__name__)


class ToolCategory(Enum):
    """Categories of available tools."""
    AIRTABLE = "airtable"
    WHATSAPP = "whatsapp"
    SYSTEM = "system"
    UTILITY = "utility"


@dataclass
class ToolDefinition:
    """Definition of a tool available to the agent."""
    name: str
    category: ToolCategory
    description: str
    parameters: Dict[str, Any]
    required_permissions: List[str]
    execution_function: Callable
    examples: List[Dict[str, Any]]


class ToolRegistry:
    """Registry of tools available to the autonomous agent."""
    
    def __init__(self, mcp_manager: MCPServerManager, settings: Optional[Settings] = None):
        """Initialize tool registry."""
        self.logger = logging.getLogger(__name__)
        self.mcp_manager = mcp_manager
        self.settings = settings
        self.tools: Dict[str, ToolDefinition] = {}
        self.eventbridge_scheduler = None
        if self.settings:
            try:
                self.eventbridge_scheduler = EventBridgeScheduler(self.settings)
            except Exception as e:
                self.logger.warning(f"Failed to initialize EventBridge scheduler: {e}")
        self._register_default_tools()
        
    def _register_default_tools(self):
        """Register default tools available to the agent."""
        self.register_tool(ToolDefinition(
            name="list_airtable_records",
            category=ToolCategory.AIRTABLE,
            description="List records from an Airtable table with optional filtering",
            parameters={
                "table_name": {"type": "string", "required": True, "description": "Name of the table"},
                "base_id": {"type": "string", "required": False, "description": "Airtable base ID"},
                "filter_formula": {"type": "string", "required": False, "description": "Airtable filter formula"},
                "max_records": {"type": "integer", "required": False, "description": "Maximum number of records to return"},
                "sort": {"type": "array", "required": False, "description": "Sort configuration"}
            },
            required_permissions=["airtable:read"],
            execution_function=self._execute_airtable_list_records,
            examples=[
                {
                    "description": "List all contacts",
                    "parameters": {"table_name": "Contacts"}
                },
                {
                    "description": "List active projects",
                    "parameters": {
                        "table_name": "Projects",
                        "filter_formula": "{Status} = 'Active'"
                    }
                }
            ]
        ))
        self.register_tool(ToolDefinition(
            name="get_airtable_record",
            category=ToolCategory.AIRTABLE,
            description="Get a specific record from Airtable by ID",
            parameters={
                "table_name": {"type": "string", "required": True, "description": "Name of the table"},
                "record_id": {"type": "string", "required": True, "description": "Record ID"},
                "base_id": {"type": "string", "required": False, "description": "Airtable base ID"}
            },
            required_permissions=["airtable:read"],
            execution_function=self._execute_airtable_get_record,
            examples=[
                {
                    "description": "Get specific contact",
                    "parameters": {
                        "table_name": "Contacts",
                        "record_id": "recXXXXXXXXXXXXXX"
                    }
                }
            ]
        ))
        self.register_tool(ToolDefinition(
            name="create_airtable_record",
            category=ToolCategory.AIRTABLE,
            description="Create a new record in Airtable",
            parameters={
                "table_name": {"type": "string", "required": True, "description": "Name of the table"},
                "fields": {"type": "object", "required": True, "description": "Record fields"},
                "base_id": {"type": "string", "required": False, "description": "Airtable base ID"}
            },
            required_permissions=["airtable:write"],
            execution_function=self._execute_airtable_create_record,
            examples=[
                {
                    "description": "Create new contact",
                    "parameters": {
                        "table_name": "Contacts",
                        "fields": {
                            "Name": "John Doe",
                            "Phone": "+1234567890",
                            "Email": "john@example.com"
                        }
                    }
                }
            ]
        ))
        self.register_tool(ToolDefinition(
            name="update_airtable_record",
            category=ToolCategory.AIRTABLE,
            description="Update an existing record in Airtable",
            parameters={
                "table_name": {"type": "string", "required": True, "description": "Name of the table"},
                "record_id": {"type": "string", "required": True, "description": "Record ID"},
                "fields": {"type": "object", "required": True, "description": "Fields to update"},
                "base_id": {"type": "string", "required": False, "description": "Airtable base ID"}
            },
            required_permissions=["airtable:write"],
            execution_function=self._execute_airtable_update_record,
            examples=[
                {
                    "description": "Update contact phone",
                    "parameters": {
                        "table_name": "Contacts",
                        "record_id": "recXXXXXXXXXXXXXX",
                        "fields": {"Phone": "+1987654321"}
                    }
                }
            ]
        ))
        self.register_tool(ToolDefinition(
            name="search_airtable_records",
            category=ToolCategory.AIRTABLE,
            description="Search records in Airtable using text search",
            parameters={
                "table_name": {"type": "string", "required": True, "description": "Name of the table"},
                "search_term": {"type": "string", "required": True, "description": "Search term"},
                "fields": {"type": "array", "required": False, "description": "Fields to search in"},
                "base_id": {"type": "string", "required": False, "description": "Airtable base ID"}
            },
            required_permissions=["airtable:read"],
            execution_function=self._execute_airtable_search_records,
            examples=[
                {
                    "description": "Search for contacts by name",
                    "parameters": {
                        "table_name": "Contacts",
                        "search_term": "John",
                        "fields": ["Name", "Email"]
                    }
                }
            ]
        ))
        self.register_tool(ToolDefinition(
            name="send_whatsapp_message",
            category=ToolCategory.WHATSAPP,
            description="Send a text message via WhatsApp",
            parameters={
                "to": {"type": "string", "required": True, "description": "Recipient phone number"},
                "message": {"type": "string", "required": True, "description": "Message text"},
                "preview_url": {"type": "boolean", "required": False, "description": "Enable URL preview"}
            },
            required_permissions=["whatsapp:send"],
            execution_function=self._execute_whatsapp_send_message,
            examples=[
                {
                    "description": "Send notification to collaborator",
                    "parameters": {
                        "to": "+1234567890",
                        "message": "Project update: Task completed successfully."
                    }
                }
            ]
        ))
        self.register_tool(ToolDefinition(
            name="send_whatsapp_template",
            category=ToolCategory.WHATSAPP,
            description="Send a template message via WhatsApp",
            parameters={
                "to": {"type": "string", "required": True, "description": "Recipient phone number"},
                "template_name": {"type": "string", "required": True, "description": "Template name"},
                "language": {"type": "string", "required": True, "description": "Language code"},
                "components": {"type": "array", "required": False, "description": "Template components"}
            },
            required_permissions=["whatsapp:send"],
            execution_function=self._execute_whatsapp_send_template,
            examples=[
                {
                    "description": "Send project reminder template",
                    "parameters": {
                        "to": "+1234567890",
                        "template_name": "project_reminder",
                        "language": "en"
                    }
                }
            ]
        ))
        self.register_tool(ToolDefinition(
            name="send_whatsapp_media",
            category=ToolCategory.WHATSAPP,
            description="Send media (image, document, etc.) via WhatsApp",
            parameters={
                "to": {"type": "string", "required": True, "description": "Recipient phone number"},
                "media_type": {"type": "string", "required": True, "description": "Media type (image, document, audio, video)"},
                "media_url": {"type": "string", "required": True, "description": "Media URL"},
                "caption": {"type": "string", "required": False, "description": "Media caption"},
                "filename": {"type": "string", "required": False, "description": "File name for documents"}
            },
            required_permissions=["whatsapp:send"],
            execution_function=self._execute_whatsapp_send_media,
            examples=[
                {
                    "description": "Send project report",
                    "parameters": {
                        "to": "+1234567890",
                        "media_type": "document",
                        "media_url": "https://example.com/report.pdf",
                        "filename": "project_report.pdf",
                        "caption": "Monthly project report"
                    }
                }
            ]
        ))
        self.register_tool(ToolDefinition(
            name="schedule_task",
            category=ToolCategory.SYSTEM,
            description="Schedule a recurring task using AWS EventBridge",
            parameters={
                "task_name": {"type": "string", "required": True, "description": "Task name"},
                "schedule_expression": {"type": "string", "required": True, "description": "Cron or rate expression"},
                "task_description": {"type": "string", "required": True, "description": "Task description"},
                "parameters": {"type": "object", "required": False, "description": "Task parameters"}
            },
            required_permissions=["system:schedule"],
            execution_function=self._execute_schedule_task,
            examples=[
                {
                    "description": "Schedule weekly project check",
                    "parameters": {
                        "task_name": "weekly_project_check",
                        "schedule_expression": "rate(7 days)",
                        "task_description": "Check project progress and send updates"
                    }
                }
            ]
        ))
        self.register_tool(ToolDefinition(
            name="format_phone_number",
            category=ToolCategory.UTILITY,
            description="Format and validate phone numbers",
            parameters={
                "phone_number": {"type": "string", "required": True, "description": "Phone number to format"},
                "country_code": {"type": "string", "required": False, "description": "Default country code"}
            },
            required_permissions=[],
            execution_function=self._execute_format_phone_number,
            examples=[
                {
                    "description": "Format US phone number",
                    "parameters": {
                        "phone_number": "1234567890",
                        "country_code": "US"
                    }
                }
            ]
        ))
        self.logger.info(f"Registered {len(self.tools)} default tools")
        
    def register_tool(self, tool: ToolDefinition):
        """Register a new tool."""
        self.tools[tool.name] = tool
        self.logger.debug(f"Registered tool: {tool.name}")
        
    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """Get tool definition by name."""
        return self.tools.get(name)
        
    def get_tools_by_category(self, category: ToolCategory) -> List[ToolDefinition]:
        """Get all tools in a category."""
        return [tool for tool in self.tools.values() if tool.category == category]
        
    def get_available_tools(self, permissions: List[str]) -> List[ToolDefinition]:
        """Get tools available with given permissions."""
        available = []
        for tool in self.tools.values():
            if not tool.required_permissions or all(perm in permissions for perm in tool.required_permissions):
                available.append(tool)
        return available
        
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any], user_permissions: List[str]) -> ToolExecutionResult:
        """Execute a tool with given parameters."""
        tool = self.tools.get(tool_name)
        if not tool:
            return ToolExecutionResult(success=False, result=None, error=f"Tool '{tool_name}' not found", execution_time=0.0)
        if tool.required_permissions and not all(perm in user_permissions for perm in tool.required_permissions):
            missing_perms = [perm for perm in tool.required_permissions if perm not in user_permissions]
            return ToolExecutionResult(success=False, result=None, error=f"Missing permissions: {missing_perms}", execution_time=0.0)
        validation_error = self._validate_parameters(tool, parameters)
        if validation_error:
            return ToolExecutionResult(success=False, result=None, error=validation_error, execution_time=0.0)
        try:
            import time
            import inspect
            start_time = time.time()
            if inspect.iscoroutinefunction(tool.execution_function):
                result = await tool.execution_function(parameters)
            else:
                result = tool.execution_function(parameters)
            execution_time = time.time() - start_time
            return ToolExecutionResult(success=True, result=result, error=None, execution_time=execution_time)
        except Exception as e:
            self.logger.error(f"Tool execution error for {tool_name}: {str(e)}")
            return ToolExecutionResult(success=False, result=None, error=str(e), execution_time=0.0)
            
    def get_tool_schema(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get OpenAI function schema for a tool."""
        tool = self.tools.get(tool_name)
        if not tool:
            return None
        return {
            "name": tool.name,
            "description": tool.description,
            "parameters": {
                "type": "object",
                "properties": tool.parameters,
                "required": [param_name for param_name, param_def in tool.parameters.items() if param_def.get("required", False)]
            }
        }
        
    def get_all_tool_schemas(self, permissions: List[str]) -> List[Dict[str, Any]]:
        """Get OpenAI function schemas for all available tools."""
        available_tools = self.get_available_tools(permissions)
        return [self.get_tool_schema(tool.name) for tool in available_tools]
        
    def _validate_parameters(self, tool: ToolDefinition, parameters: Dict[str, Any]) -> Optional[str]:
        """Validate tool parameters."""
        for param_name, param_def in tool.parameters.items():
            if param_def.get("required", False) and param_name not in parameters:
                return f"Missing required parameter: {param_name}"
        return None

    async def _execute_airtable_list_records(self, parameters: Dict[str, Any]) -> Any:
        """Execute Airtable list records tool."""
        return await self.mcp_manager.call_tool(
            "airtable",
            "list_records",
            parameters
        )
        
    async def _execute_airtable_get_record(self, parameters: Dict[str, Any]) -> Any:
        """Execute Airtable get record tool."""
        return await self.mcp_manager.call_tool(
            "airtable",
            "get_record",
            parameters
        )
        
    async def _execute_airtable_create_record(self, parameters: Dict[str, Any]) -> Any:
        """Execute Airtable create record tool."""
        return await self.mcp_manager.call_tool(
            "airtable",
            "create_record",
            parameters
        )
        
    async def _execute_airtable_update_record(self, parameters: Dict[str, Any]) -> Any:
        """Execute Airtable update record tool."""
        return await self.mcp_manager.call_tool(
            "airtable",
            "update_record",
            parameters
        )
        
    async def _execute_airtable_search_records(self, parameters: Dict[str, Any]) -> Any:
        """Execute Airtable search records tool."""
        return await self.mcp_manager.call_tool(
            "airtable",
            "search_records",
            parameters
        )
        
    async def _execute_whatsapp_send_message(self, parameters: Dict[str, Any]) -> Any:
        """Execute WhatsApp send message tool."""
        return await self.mcp_manager.call_tool(
            "whatsapp",
            "send_text_message",
            parameters
        )
        
    async def _execute_whatsapp_send_template(self, parameters: Dict[str, Any]) -> Any:
        """Execute WhatsApp send template tool."""
        return await self.mcp_manager.call_tool(
            "whatsapp",
            "send_template_message",
            parameters
        )
        
    async def _execute_whatsapp_send_media(self, parameters: Dict[str, Any]) -> Any:
        """Execute WhatsApp send media tool."""
        return await self.mcp_manager.call_tool(
            "whatsapp",
            "send_media_message",
            parameters
        )
        
    async def _execute_schedule_task(self, parameters: Dict[str, Any]) -> Any:
        """Execute schedule task tool."""
        if not self.eventbridge_scheduler:
            return {"success": False, "error": "EventBridge scheduler not available. Please check AWS configuration.", "task_name": parameters.get("task_name", "unknown")}
        try:
            task_name = parameters["task_name"]
            schedule_expression = parameters["schedule_expression"]
            task_description = parameters.get("task_description", "")
            target_function = parameters.get("target_function", "default_task_handler")
            payload = parameters.get("payload", {})
            enabled = parameters.get("enabled", True)
            schedule_type = ScheduleType.RATE
            if schedule_expression.startswith("cron("):
                schedule_type = ScheduleType.CRON
            elif schedule_expression.startswith("at("):
                schedule_type = ScheduleType.ONE_TIME
            scheduled_task = ScheduledTask(
                name=task_name,
                description=task_description,
                schedule_expression=schedule_expression,
                schedule_type=schedule_type,
                target_function=target_function,
                payload=payload,
                enabled=enabled,
                tags={"CreatedBy": "AutonomousAgent", "Component": "TaskScheduler"}
            )
            self.eventbridge_scheduler.register_task(scheduled_task)
            success = await self.eventbridge_scheduler.create_schedule(task_name)
            if success:
                return {
                    "success": True,
                    "task_id": task_name,
                    "status": "scheduled",
                    "schedule": schedule_expression,
                    "description": task_description,
                    "enabled": enabled,
                    "target_function": target_function,
                    "message": f"Successfully scheduled task '{task_name}'"
                }
            else:
                return {"success": False, "error": f"Failed to create schedule for task '{task_name}'", "task_name": task_name}
        except KeyError as e:
            return {"success": False, "error": f"Missing required parameter: {str(e)}", "task_name": parameters.get("task_name", "unknown")}
        except Exception as e:
            self.logger.error(f"Error scheduling task: {str(e)}")
            return {"success": False, "error": f"Unexpected error: {str(e)}", "task_name": parameters.get("task_name", "unknown")}
        
    def _execute_format_phone_number(self, parameters: Dict[str, Any]) -> Any:
        """Execute format phone number tool."""
        import re
        phone = parameters["phone_number"]
        country_code = parameters.get("country_code", "US")
        digits = re.sub(r'\D', '', phone)
        if country_code == "US" and len(digits) == 10:
            formatted = f"+1{digits}"
        elif digits.startswith("1") and len(digits) == 11:
            formatted = f"+{digits}"
        elif not digits.startswith("+"):
            formatted = f"+{digits}"
        else:
            formatted = digits
        return {
            "original": phone,
            "formatted": formatted,
            "country_code": country_code,
            "is_valid": len(digits) >= 10
        }