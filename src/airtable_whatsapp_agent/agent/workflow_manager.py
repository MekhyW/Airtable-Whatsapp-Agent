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
from ..models.agent import AgentState
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
        self.logger.info(f"🚀 Starting new workflow session {session_id} for user {user_phone}")
        if initial_message:
            self.logger.debug(f"Initial message: {initial_message}")
        if len(self.active_workflows) >= self.max_concurrent_sessions:
            raise Exception("Maximum concurrent sessions reached")
        initial_state = self.state_manager.create_initial_state(session_id=session_id, user_phone=user_phone, initial_message=initial_message, context=context)
        self.active_workflows[session_id] = {
            "user_phone": user_phone,
            "start_time": datetime.utcnow(),
            "status": "running",
            "message_count": 0,
            "last_activity": datetime.utcnow()
        }
        self.metrics["total_sessions"] += 1
        asyncio.create_task(self._execute_workflow(session_id, initial_state))
        self.logger.info(f"✅ Workflow session {session_id} started successfully")
        return session_id
        
    async def send_message(self, session_id: str, message: str, message_type: str = "text", metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Send a message to an active workflow session."""
        if session_id not in self.active_workflows:
            self.logger.warning(f"⚠️ Session {session_id} not found")
            return False
        workflow = self.active_workflows[session_id]
        user_phone = workflow["user_phone"]
        self.logger.info(f"💬 Processing message in session {session_id} from {user_phone}: {message}")
        workflow["last_activity"] = datetime.utcnow()
        workflow["message_count"] += 1
        state = self.state_manager.get_state(session_id)
        if not state:
            self.logger.error(f"❌ State not found for session {session_id}")
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
        self.logger.debug(f"Message queued for processing in session {session_id}")
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
        self.active_workflows[session_id]["status"] = "stopped"
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
            workflow = self.active_workflows.get(session_id)
            if not workflow:
                return
            workflow["last_activity"] = datetime.utcnow()
            user_phone = workflow["user_phone"]
            self.state_manager.update_state(session_id, {"current_state": result["current_state"], "updated_at": datetime.utcnow()})
            response_text = result.get("response") or result["metadata"].get("final_response")
            if not response_text:
                response_text = "I've processed your message. How can I help you further?"
            self.logger.info(f"📤 SENDING WhatsApp response to {user_phone}: {response_text}")
            await self._send_whatsapp_response(user_phone, response_text)
            if result["current_state"] == AgentState.WAITING_FOR_INPUT:
                workflow["status"] = "waiting"
            elif result["current_state"] == AgentState.ERROR:
                workflow["status"] = "failed"
                self.metrics["failed_sessions"] += 1
            else:
                workflow["status"] = "completed"
                self.metrics["successful_sessions"] += 1
            duration = (datetime.utcnow() - workflow["start_time"]).total_seconds()
            self._update_average_duration(duration)
            for tool_name in result.get("tool_results", {}):
                self.metrics["tool_usage_count"][tool_name] = (self.metrics["tool_usage_count"].get(tool_name, 0) + 1)
        except Exception as e:
            self.logger.error(f"❌ Error handling workflow result: {str(e)}")
            await self._handle_workflow_error(session_id, str(e))
            
    async def _handle_workflow_error(self, session_id: str, error: str):
        """Handle workflow execution error."""
        self.logger.error(f"Workflow error for session {session_id}: {error}")
        self.metrics["error_count"] += 1
        if session_id in self.active_workflows:
            workflow = self.active_workflows[session_id]
            workflow["status"] = "failed"
            workflow["error"] = error
            user_phone = workflow["user_phone"]
            self.logger.error(f"❌ Workflow error for session {session_id} (user: {user_phone}): {error}")
            error_message = "I encountered an error processing your request. Please try again or contact support if the issue persists."
            self.logger.info(f"📤 SENDING error response to {user_phone}")
            self.metrics["failed_sessions"] += 1
        try:
            state = self.state_manager.get_state(session_id)
            if state:
                await self._send_whatsapp_response(state["user_phone"], error_message if session_id in self.active_workflows else "I'm experiencing technical difficulties. Please try again later.")
        except Exception as e:
            self.logger.error(f"❌ Failed to send error message: {str(e)}")
            
    async def _send_whatsapp_response(self, user_phone: str, message: str):
        """Send WhatsApp response to user."""
        try:
            self.logger.debug(f"Attempting to send WhatsApp message to {user_phone}")
            result = await self.mcp_manager.call_tool(
                "whatsapp-mcp",
                "send_message",
                {
                    "to": user_phone,
                    "message": message
                }
            )
            if result.get("success", False):
                self.logger.info(f"✅ WhatsApp message sent successfully to {user_phone}")
                self.logger.debug(f"Message content: {message}")
                self.metrics["messages_sent"] = self.metrics.get("messages_sent", 0) + 1
            else:
                self.logger.error(f"❌ Failed to send WhatsApp message to {user_phone}: {result}")
                self.metrics["failed_messages"] = self.metrics.get("failed_messages", 0) + 1
        except Exception as e:
            self.logger.error(f"❌ WhatsApp send error to {user_phone}: {str(e)}")
            self.metrics["failed_messages"] = self.metrics.get("failed_messages", 0) + 1
            
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