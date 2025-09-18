"""
Workflow manager for the autonomous agent.
Orchestrates the execution of agent workflows and manages concurrent sessions.
"""

import logging
import asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import uuid
from .state_manager import StateManager, AgentGraphState
from .graph_builder import GraphBuilder
from .tool_registry import ToolRegistry
from ..models.agent import AgentState, WorkflowStatus
from ..mcp.manager import MCPServerManager
from ..config import Settings


logger = logging.getLogger(__name__)


class WorkflowManager:
    """Manages agent workflows and concurrent session execution."""
    
    def __init__(self, mcp_manager: MCPServerManager, openai_api_key: str, settings: Optional[Settings] = None, max_concurrent_sessions: int = 10, session_timeout_minutes: int = 30, model_name: str = "gpt-4-turbo-preview", temperature: float = 0.5, max_tokens: int = 2000):
        """Initialize workflow manager."""
        self.logger = logging.getLogger(__name__)
        self.mcp_manager = mcp_manager
        self.openai_api_key = openai_api_key
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_concurrent_sessions = max_concurrent_sessions
        self.session_timeout = timedelta(minutes=session_timeout_minutes)
        self.state_manager = StateManager()
        self.tool_registry = ToolRegistry(mcp_manager, settings=settings)
        self.graph_builder = GraphBuilder(self.state_manager, self.tool_registry, openai_api_key, model_name=model_name, temperature=temperature, max_tokens=max_tokens)
        self.active_workflows: Dict[str, Dict[str, Any]] = {}
        self.executor = ThreadPoolExecutor(max_workers=max_concurrent_sessions)
        self.metrics = {
            "total_sessions": 0,
            "successful_sessions": 0,
            "failed_sessions": 0,
            "average_session_duration": 0.0,
            "tool_usage_count": {},
            "error_count": 0
        }
        self._cleanup_task = None
        self._start_cleanup_task()
        
    async def start_workflow(self, user_phone: str, initial_message: Optional[str] = None, context: Optional[Dict[str, Any]] = None, session_id: Optional[str] = None) -> str:
        """Start a new agent workflow session."""
        if not session_id:
            session_id = str(uuid.uuid4())
        self.logger.info(f"Starting workflow for user {user_phone}, session {session_id}")
        if len(self.active_workflows) >= self.max_concurrent_sessions:
            raise Exception("Maximum concurrent sessions reached")
        initial_state = self.state_manager.create_initial_state(session_id=session_id, user_phone=user_phone, initial_message=initial_message, context=context)
        self.active_workflows[session_id] = {
            "user_phone": user_phone,
            "start_time": datetime.utcnow(),
            "status": WorkflowStatus.RUNNING,
            "message_count": 0,
            "last_activity": datetime.utcnow()
        }
        self.metrics["total_sessions"] += 1
        asyncio.create_task(self._execute_workflow(session_id, initial_state))
        return session_id
        
    async def send_message(self, session_id: str, message: str, message_type: str = "text", metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Send a message to an active workflow session."""
        if session_id not in self.active_workflows:
            self.logger.warning(f"Session {session_id} not found")
            return False
        self.active_workflows[session_id]["last_activity"] = datetime.utcnow()
        self.active_workflows[session_id]["message_count"] += 1
        state = self.state_manager.get_state(session_id)
        if not state:
            return False
        updates = {
            "current_message": message,
            "message_type": message_type,
            "current_state": AgentState.PROCESSING
        }
        if metadata:
            updates["metadata"].update(metadata)
        self.state_manager.update_state(session_id, updates)
        asyncio.create_task(self._resume_workflow(session_id))
        return True
        
    async def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a workflow session."""
        if session_id not in self.active_workflows:
            return None
        workflow_info = self.active_workflows[session_id]
        state_summary = self.state_manager.get_session_summary(session_id)
        return {
            **workflow_info,
            **state_summary,
            "duration_minutes": (datetime.utcnow() - workflow_info["start_time"]).total_seconds() / 60
        }
        
    async def stop_session(self, session_id: str, reason: str = "user_request") -> bool:
        """Stop an active workflow session."""
        if session_id not in self.active_workflows:
            return False
        self.logger.info(f"Stopping session {session_id}, reason: {reason}")
        self.active_workflows[session_id]["status"] = WorkflowStatus.STOPPED
        self.active_workflows[session_id]["stop_reason"] = reason
        self.state_manager.cleanup_session(session_id)
        del self.active_workflows[session_id]
        return True
        
    async def get_active_sessions(self) -> List[Dict[str, Any]]:
        """Get list of all active sessions."""
        sessions = []
        for session_id in self.active_workflows:
            status = await self.get_session_status(session_id)
            if status:
                sessions.append(status)
        return sessions
        
    async def get_metrics(self) -> Dict[str, Any]:
        """Get workflow manager metrics."""
        return {
            **self.metrics,
            "active_sessions": len(self.active_workflows),
            "max_concurrent_sessions": self.max_concurrent_sessions
        }
        
    async def _execute_workflow(self, session_id: str, initial_state: AgentGraphState):
        """Execute the agent workflow."""
        try:
            self.logger.info(f"Executing workflow for session {session_id}")
            graph = self.graph_builder.get_compiled_graph()
            result = await graph.ainvoke(initial_state)
            await self._handle_workflow_result(session_id, result)
        except Exception as e:
            self.logger.error(f"Workflow execution error for session {session_id}: {str(e)}")
            await self._handle_workflow_error(session_id, str(e))
            
    async def _resume_workflow(self, session_id: str):
        """Resume workflow execution after new message."""
        try:
            state = self.state_manager.get_state(session_id)
            if not state:
                return
            if state["current_state"] in [AgentState.WAITING_FOR_INPUT, AgentState.PROCESSING]:
                await self._execute_workflow(session_id, state)
        except Exception as e:
            self.logger.error(f"Workflow resume error for session {session_id}: {str(e)}")
            await self._handle_workflow_error(session_id, str(e))
            
    async def _handle_workflow_result(self, session_id: str, result: AgentGraphState):
        """Handle workflow execution result."""
        try:
            final_response = result["metadata"].get("final_response")
            if final_response:
                await self._send_whatsapp_response(result["user_phone"], final_response)
            if session_id in self.active_workflows:
                workflow = self.active_workflows[session_id]
                if result["current_state"] == AgentState.WAITING_FOR_INPUT:
                    workflow["status"] = WorkflowStatus.WAITING
                elif result["current_state"] == AgentState.ERROR:
                    workflow["status"] = WorkflowStatus.FAILED
                    self.metrics["failed_sessions"] += 1
                else:
                    workflow["status"] = WorkflowStatus.COMPLETED
                    self.metrics["successful_sessions"] += 1
                duration = (datetime.utcnow() - workflow["start_time"]).total_seconds()
                self._update_average_duration(duration)
                for tool_name in result.get("tool_results", {}):
                    self.metrics["tool_usage_count"][tool_name] = (self.metrics["tool_usage_count"].get(tool_name, 0) + 1)
        except Exception as e:
            self.logger.error(f"Error handling workflow result: {str(e)}")
            
    async def _handle_workflow_error(self, session_id: str, error: str):
        """Handle workflow execution error."""
        self.logger.error(f"Workflow error for session {session_id}: {error}")
        self.metrics["error_count"] += 1
        if session_id in self.active_workflows:
            self.active_workflows[session_id]["status"] = WorkflowStatus.FAILED
            self.active_workflows[session_id]["error"] = error
            self.metrics["failed_sessions"] += 1
        try:
            state = self.state_manager.get_state(session_id)
            if state:
                await self._send_whatsapp_response(state["user_phone"], "I'm experiencing technical difficulties. Please try again later.")
        except Exception as e:
            self.logger.error(f"Failed to send error message: {str(e)}")
            
    async def _send_whatsapp_response(self, user_phone: str, message: str):
        """Send response via WhatsApp."""
        try:
            result = await self.mcp_manager.call_tool(
                "whatsapp",
                "send_text_message",
                {
                    "to": user_phone,
                    "message": message
                }
            )
            if not result.get("success", False):
                self.logger.error(f"Failed to send WhatsApp message: {result}")
        except Exception as e:
            self.logger.error(f"WhatsApp send error: {str(e)}")
            
    def _update_average_duration(self, duration: float):
        """Update average session duration metric."""
        total_completed = self.metrics["successful_sessions"] + self.metrics["failed_sessions"]
        if total_completed > 0:
            current_avg = self.metrics["average_session_duration"]
            self.metrics["average_session_duration"] = ((current_avg * (total_completed - 1) + duration) / total_completed)
            
    def _start_cleanup_task(self):
        """Start background cleanup task."""
        async def cleanup_expired_sessions():
            while True:
                try:
                    await asyncio.sleep(300)  # Check every 5 minutes
                    await self._cleanup_expired_sessions()
                except Exception as e:
                    self.logger.error(f"Cleanup task error: {str(e)}")
                    
        self._cleanup_task = asyncio.create_task(cleanup_expired_sessions())
        
    async def _cleanup_expired_sessions(self):
        """Clean up expired sessions."""
        now = datetime.utcnow()
        expired_sessions = []
        for session_id, workflow in self.active_workflows.items():
            if now - workflow["last_activity"] > self.session_timeout:
                expired_sessions.append(session_id)
        for session_id in expired_sessions:
            self.logger.info(f"Cleaning up expired session: {session_id}")
            await self.stop_session(session_id, "timeout")
            
    async def shutdown(self):
        """Shutdown the workflow manager."""
        self.logger.info("Shutting down workflow manager")
        if self._cleanup_task:
            self._cleanup_task.cancel()
        active_sessions = list(self.active_workflows.keys())
        for session_id in active_sessions:
            await self.stop_session(session_id, "shutdown")
        self.executor.shutdown(wait=True)
        self.logger.info("Workflow manager shutdown complete")


class AutonomousAgent:
    """Main autonomous agent class that coordinates all components."""
    
    def __init__(self, mcp_manager: MCPServerManager, openai_api_key: str, settings: Optional[Settings] = None, **kwargs):
        """Initialize autonomous agent."""
        self.logger = logging.getLogger(__name__)
        self.workflow_manager = WorkflowManager(mcp_manager=mcp_manager, openai_api_key=openai_api_key, settings=settings, **kwargs)
        
    async def process_message(self, user_phone: str, message: str, message_type: str = "text", session_id: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> str:
        """Process incoming message from user."""
        try:
            if session_id and session_id in self.workflow_manager.active_workflows:
                success = await self.workflow_manager.send_message(session_id, message, message_type, context)
                if not success:
                    session_id = await self.workflow_manager.start_workflow(user_phone, message, context)
            else:
                session_id = await self.workflow_manager.start_workflow(user_phone, message, context, session_id)
            return session_id
        except Exception as e:
            self.logger.error(f"Message processing error: {str(e)}")
            raise
            
    async def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a session."""
        return await self.workflow_manager.get_session_status(session_id)
        
    async def stop_session(self, session_id: str) -> bool:
        """Stop a session."""
        return await self.workflow_manager.stop_session(session_id)
        
    async def get_metrics(self) -> Dict[str, Any]:
        """Get agent metrics."""
        return await self.workflow_manager.get_metrics()
        
    async def shutdown(self):
        """Shutdown the agent."""
        await self.workflow_manager.shutdown()