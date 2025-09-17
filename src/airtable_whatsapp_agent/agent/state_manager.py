"""
State management for the autonomous agent using LangGraph.
"""

import logging
from typing import Any, Dict, List, Optional, TypedDict
from datetime import datetime
from ..models.agent import (
    AgentState,
    AgentAction,
    AgentDecision,
    ConversationContext,
    TaskStatus
)


logger = logging.getLogger(__name__)


class AgentGraphState(TypedDict):
    """State structure for LangGraph agent."""
    # Core state
    current_state: AgentState
    session_id: str
    user_phone: str
    # Conversation context
    conversation_history: List[Dict[str, Any]]
    current_message: Optional[str]
    message_type: Optional[str]
    # Task management
    current_task: Optional[str]
    task_status: TaskStatus
    task_context: Dict[str, Any]
    # Decision making
    last_decision: Optional[AgentDecision]
    pending_actions: List[AgentAction]
    # Tool usage
    available_tools: List[str]
    tool_results: Dict[str, Any]
    # Error handling
    error_count: int
    last_error: Optional[str]
    # Metadata
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any]


class StateManager:
    """Manages agent state throughout conversation and task execution."""
    
    def __init__(self):
        """Initialize state manager."""
        self.logger = logging.getLogger(__name__)
        self.active_states: Dict[str, AgentGraphState] = {}
        
    def create_initial_state(self, session_id: str, user_phone: str, initial_message: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> AgentGraphState:
        """Create initial agent state."""
        now = datetime.utcnow()
        state = AgentGraphState(
            # Core state
            current_state=AgentState.IDLE,
            session_id=session_id,
            user_phone=user_phone,
            # Conversation context
            conversation_history=[],
            current_message=initial_message,
            message_type="text" if initial_message else None,
            # Task management
            current_task=None,
            task_status=TaskStatus.PENDING,
            task_context={},
            # Decision making
            last_decision=None,
            pending_actions=[],
            # Tool usage
            available_tools=[],
            tool_results={},
            # Error handling
            error_count=0,
            last_error=None,
            # Metadata
            created_at=now,
            updated_at=now,
            metadata=context or {}
        )
        # Store active state
        self.active_states[session_id] = state
        self.logger.info(f"Created initial state for session {session_id}")
        return state
        
    def get_state(self, session_id: str) -> Optional[AgentGraphState]:
        """Get current state for session."""
        return self.active_states.get(session_id)
        
    def update_state(self, session_id: str, updates: Dict[str, Any]) -> Optional[AgentGraphState]:
        """Update agent state."""
        state = self.active_states.get(session_id)
        if not state:
            self.logger.warning(f"No state found for session {session_id}")
            return None
        for key, value in updates.items():
            if key in state:
                state[key] = value
            else:
                self.logger.warning(f"Unknown state key: {key}")
        state["updated_at"] = datetime.utcnow()
        return state
        
    def transition_state(self, session_id: str, new_state: AgentState, context: Optional[Dict[str, Any]] = None) -> bool:
        """Transition agent to new state."""
        state = self.active_states.get(session_id)
        if not state:
            return False
        old_state = state["current_state"]
        if not self._is_valid_transition(old_state, new_state):
            self.logger.warning(f"Invalid state transition: {old_state} -> {new_state}")
            return False
        state["current_state"] = new_state
        state["updated_at"] = datetime.utcnow()
        if context:
            state["metadata"].update(context)
        self.logger.info(f"State transition: {old_state} -> {new_state} for session {session_id}")
        return True
        
    def add_message_to_history(self, session_id: str, message: str, sender: str, message_type: str = "text", metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Add message to conversation history."""
        state = self.active_states.get(session_id)
        if not state:
            return False
        message_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "sender": sender,
            "message": message,
            "type": message_type,
            "metadata": metadata or {}
        }
        state["conversation_history"].append(message_entry)
        state["updated_at"] = datetime.utcnow()
        return True
        
    def set_current_task(self, session_id: str, task_description: str, task_context: Optional[Dict[str, Any]] = None) -> bool:
        """Set current task for agent."""
        state = self.active_states.get(session_id)
        if not state:
            return False
        state["current_task"] = task_description
        state["task_status"] = TaskStatus.IN_PROGRESS
        state["task_context"] = task_context or {}
        state["updated_at"] = datetime.utcnow()
        self.logger.info(f"Set task for session {session_id}: {task_description}")
        return True
        
    def update_task_status(self, session_id: str, status: TaskStatus, result: Optional[Dict[str, Any]] = None) -> bool:
        """Update task status."""
        state = self.active_states.get(session_id)
        if not state:
            return False
        state["task_status"] = status
        state["updated_at"] = datetime.utcnow()
        if result:
            state["task_context"]["result"] = result
        if status == TaskStatus.COMPLETED:
            state["current_task"] = None
            state["task_context"] = {}
        return True
        
    def add_pending_action(self, session_id: str, action: AgentAction) -> bool:
        """Add action to pending actions queue."""
        state = self.active_states.get(session_id)
        if not state:
            return False
        state["pending_actions"].append(action)
        state["updated_at"] = datetime.utcnow()
        return True
        
    def get_next_action(self, session_id: str) -> Optional[AgentAction]:
        """Get next pending action."""
        state = self.active_states.get(session_id)
        if not state or not state["pending_actions"]:
            return None
        return state["pending_actions"].pop(0)
        
    def record_decision(self, session_id: str, decision: AgentDecision) -> bool:
        """Record agent decision."""
        state = self.active_states.get(session_id)
        if not state:
            return False
        state["last_decision"] = decision
        state["updated_at"] = datetime.utcnow()
        return True
        
    def record_tool_result(self, session_id: str, tool_name: str, result: Any, success: bool = True) -> bool:
        """Record tool execution result."""
        state = self.active_states.get(session_id)
        if not state:
            return False
        state["tool_results"][tool_name] = {"result": result, "success": success, "timestamp": datetime.utcnow().isoformat()}
        state["updated_at"] = datetime.utcnow()
        return True
        
    def record_error(self, session_id: str, error_message: str, error_context: Optional[Dict[str, Any]] = None) -> bool:
        """Record error in state."""
        state = self.active_states.get(session_id)
        if not state:
            return False
        state["error_count"] += 1
        state["last_error"] = error_message
        state["updated_at"] = datetime.utcnow()
        if error_context:
            state["metadata"]["last_error_context"] = error_context
        self.logger.error(f"Error recorded for session {session_id}: {error_message}")
        return True
        
    def clear_errors(self, session_id: str) -> bool:
        """Clear error state."""
        state = self.active_states.get(session_id)
        if not state:
            return False
        state["error_count"] = 0
        state["last_error"] = None
        state["updated_at"] = datetime.utcnow()
        if "last_error_context" in state["metadata"]:
            del state["metadata"]["last_error_context"]
        return True
        
    def get_conversation_context(self, session_id: str) -> Optional[ConversationContext]:
        """Get conversation context for LLM."""
        state = self.active_states.get(session_id)
        if not state:
            return None
        recent_history = state["conversation_history"][-10:]
        return ConversationContext(
            session_id=session_id,
            user_phone=state["user_phone"],
            current_state=state["current_state"],
            conversation_history=recent_history,
            current_task=state["current_task"],
            task_context=state["task_context"],
            available_tools=state["available_tools"],
            metadata=state["metadata"]
        )
        
    def cleanup_session(self, session_id: str) -> bool:
        """Clean up session state."""
        if session_id in self.active_states:
            del self.active_states[session_id]
            self.logger.info(f"Cleaned up session {session_id}")
            return True
        return False
        
    def get_active_sessions(self) -> List[str]:
        """Get list of active session IDs."""
        return list(self.active_states.keys())
        
    def get_session_summary(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get summary of session state."""
        state = self.active_states.get(session_id)
        if not state:
            return None
        return {
            "session_id": session_id,
            "user_phone": state["user_phone"],
            "current_state": state["current_state"].value,
            "message_count": len(state["conversation_history"]),
            "current_task": state["current_task"],
            "task_status": state["task_status"].value,
            "pending_actions": len(state["pending_actions"]),
            "error_count": state["error_count"],
            "created_at": state["created_at"].isoformat(),
            "updated_at": state["updated_at"].isoformat()
        }
        
    def _is_valid_transition(self, from_state: AgentState, to_state: AgentState) -> bool:
        """Validate state transition."""
        valid_transitions = {
            AgentState.IDLE: [
                AgentState.PROCESSING,
                AgentState.AUTHENTICATING,
                AgentState.ERROR
            ],
            AgentState.AUTHENTICATING: [
                AgentState.PROCESSING,
                AgentState.IDLE,
                AgentState.ERROR
            ],
            AgentState.PROCESSING: [
                AgentState.EXECUTING_TASK,
                AgentState.WAITING_FOR_INPUT,
                AgentState.IDLE,
                AgentState.ERROR
            ],
            AgentState.EXECUTING_TASK: [
                AgentState.PROCESSING,
                AgentState.WAITING_FOR_INPUT,
                AgentState.IDLE,
                AgentState.ERROR
            ],
            AgentState.WAITING_FOR_INPUT: [
                AgentState.PROCESSING,
                AgentState.IDLE,
                AgentState.ERROR
            ],
            AgentState.ERROR: [
                AgentState.IDLE,
                AgentState.PROCESSING
            ]
        }
        allowed_states = valid_transitions.get(from_state, [])
        return to_state in allowed_states