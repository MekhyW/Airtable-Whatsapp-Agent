"""
Pydantic models for AI agent state, actions, and decision-making.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum
from pydantic import BaseModel, Field


class AgentActionType(str, Enum):
    """Types of actions the agent can perform."""
    READ_AIRTABLE = "read_airtable"
    WRITE_AIRTABLE = "write_airtable"
    SEND_WHATSAPP = "send_whatsapp"
    SCHEDULE_TASK = "schedule_task"
    ANALYZE_MESSAGE = "analyze_message"
    MAKE_DECISION = "make_decision"
    DELEGATE_TASK = "delegate_task"
    UPDATE_STATUS = "update_status"
    GENERATE_RESPONSE = "generate_response"
    SEARCH_RECORDS = "search_records"
    CREATE_REMINDER = "create_reminder"
    ESCALATE_ISSUE = "escalate_issue"


class AgentDecisionType(str, Enum):
    """Types of decisions the agent can make."""
    APPROVE = "approve"
    REJECT = "reject"
    ESCALATE = "escalate"
    DELEGATE = "delegate"
    SCHEDULE = "schedule"
    IMMEDIATE = "immediate"
    REQUIRE_CONFIRMATION = "require_confirmation"


class TaskStatus(str, Enum):
    """Status of agent tasks."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    WAITING_APPROVAL = "waiting_approval"


class ConfidenceLevel(str, Enum):
    """Confidence levels for agent decisions."""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class AgentMemoryItem(BaseModel):
    """Individual memory item for the agent."""
    key: str = Field(..., description="Memory key")
    value: Any = Field(..., description="Memory value")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Memory timestamp")
    ttl: Optional[int] = Field(None, description="Time to live in seconds")
    tags: List[str] = Field(default_factory=list, description="Memory tags")
    importance: float = Field(default=1.0, ge=0.0, le=10.0, description="Memory importance score")


class AgentMemory(BaseModel):
    """Agent memory system for maintaining context and state."""
    conversation_id: str = Field(..., description="Associated conversation ID")
    short_term: Dict[str, AgentMemoryItem] = Field(default_factory=dict, description="Short-term memory")
    long_term: Dict[str, AgentMemoryItem] = Field(default_factory=dict, description="Long-term memory")
    working_memory: Dict[str, Any] = Field(default_factory=dict, description="Working memory for current task")
    context_window: List[Dict[str, Any]] = Field(default_factory=list, description="Recent conversation context")
    max_context_size: int = Field(default=50, description="Maximum context window size")
    
    def add_to_context(self, item: Dict[str, Any]) -> None:
        """Add item to context window."""
        self.context_window.append(item)
        if len(self.context_window) > self.max_context_size:
            self.context_window.pop(0)
    
    def store_memory(self, key: str, value: Any, memory_type: str = "short_term", **kwargs) -> None:
        """Store item in memory."""
        memory_item = AgentMemoryItem(key=key, value=value, **kwargs)
        if memory_type == "short_term":
            self.short_term[key] = memory_item
        elif memory_type == "long_term":
            self.long_term[key] = memory_item


class AgentAction(BaseModel):
    """Action that the agent can perform."""
    action_id: str = Field(..., description="Unique action identifier")
    action_type: AgentActionType = Field(..., description="Type of action")
    description: str = Field(..., description="Action description")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Action parameters")
    prerequisites: List[str] = Field(default_factory=list, description="Required prerequisites")
    expected_outcome: Optional[str] = Field(None, description="Expected outcome")
    confidence: ConfidenceLevel = Field(default=ConfidenceLevel.MEDIUM, description="Confidence level")
    estimated_duration: Optional[int] = Field(None, description="Estimated duration in seconds")
    priority: int = Field(default=5, ge=1, le=10, description="Action priority (1-10)")
    requires_approval: bool = Field(default=False, description="Whether action requires approval")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Action creation time")


class AgentDecision(BaseModel):
    """Decision made by the agent."""
    decision_id: str = Field(..., description="Unique decision identifier")
    decision_type: AgentDecisionType = Field(..., description="Type of decision")
    context: str = Field(..., description="Decision context")
    reasoning: str = Field(..., description="Decision reasoning")
    confidence: ConfidenceLevel = Field(..., description="Decision confidence")
    alternatives_considered: List[str] = Field(default_factory=list, description="Alternative options considered")
    risk_assessment: Dict[str, Any] = Field(default_factory=dict, description="Risk assessment")
    impact_analysis: Dict[str, Any] = Field(default_factory=dict, description="Impact analysis")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Decision timestamp")
    expires_at: Optional[datetime] = Field(None, description="Decision expiration time")


class AgentTask(BaseModel):
    """Task assigned to or created by the agent."""
    task_id: str = Field(..., description="Unique task identifier")
    title: str = Field(..., description="Task title")
    description: str = Field(..., description="Task description")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="Task status")
    actions: List[AgentAction] = Field(default_factory=list, description="Actions to perform")
    dependencies: List[str] = Field(default_factory=list, description="Task dependencies")
    assigned_to: Optional[str] = Field(None, description="Assigned agent or user")
    created_by: str = Field(..., description="Task creator")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Task creation time")
    started_at: Optional[datetime] = Field(None, description="Task start time")
    completed_at: Optional[datetime] = Field(None, description="Task completion time")
    due_date: Optional[datetime] = Field(None, description="Task due date")
    priority: int = Field(default=5, ge=1, le=10, description="Task priority")
    progress: float = Field(default=0.0, ge=0.0, le=100.0, description="Task progress percentage")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional task metadata")
    conversation_id: Optional[str] = Field(None, description="Associated conversation ID")


class AgentResponse(BaseModel):
    """Response generated by the agent."""
    response_id: str = Field(..., description="Unique response identifier")
    content: str = Field(..., description="Response content")
    response_type: str = Field(..., description="Type of response")
    confidence: ConfidenceLevel = Field(..., description="Response confidence")
    reasoning: Optional[str] = Field(None, description="Response reasoning")
    suggested_actions: List[AgentAction] = Field(default_factory=list, description="Suggested follow-up actions")
    requires_human_review: bool = Field(default=False, description="Whether response needs human review")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional response metadata")
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="Response generation time")


class AgentState(BaseModel):
    """Current state of the agent."""
    agent_id: str = Field(..., description="Unique agent identifier")
    conversation_id: Optional[str] = Field(None, description="Current conversation ID")
    current_task: Optional[AgentTask] = Field(None, description="Current active task")
    memory: AgentMemory = Field(default_factory=AgentMemory, description="Agent memory")
    active_actions: List[AgentAction] = Field(default_factory=list, description="Currently executing actions")
    pending_decisions: List[AgentDecision] = Field(default_factory=list, description="Pending decisions")
    capabilities: List[str] = Field(default_factory=list, description="Agent capabilities")
    permissions: List[str] = Field(default_factory=list, description="Agent permissions")
    status: str = Field(default="idle", description="Agent status")
    last_activity: datetime = Field(default_factory=datetime.utcnow, description="Last activity timestamp")
    session_start: datetime = Field(default_factory=datetime.utcnow, description="Session start time")
    total_actions_performed: int = Field(default=0, description="Total actions performed")
    total_decisions_made: int = Field(default=0, description="Total decisions made")
    error_count: int = Field(default=0, description="Number of errors encountered")
    success_rate: float = Field(default=100.0, ge=0.0, le=100.0, description="Success rate percentage")
    class Config:
        """Pydantic configuration."""
        json_encoders = { datetime: lambda v: v.isoformat() if v else None }


class ConversationContext(BaseModel):
    """Context for ongoing conversations."""
    session_id: str = Field(..., description="Session identifier")
    user_phone: str = Field(..., description="User phone number")
    current_state: str = Field(..., description="Current conversation state")
    conversation_history: List[Dict[str, Any]] = Field(default_factory=list, description="Recent conversation history")
    current_task: Optional[str] = Field(None, description="Current task being processed")
    task_context: Dict[str, Any] = Field(default_factory=dict, description="Task-specific context")
    available_tools: List[str] = Field(default_factory=list, description="Available tools for this conversation")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    class Config:
        """Pydantic configuration."""
        json_encoders = { datetime: lambda v: v.isoformat() if v else None }


class AgentCapability(BaseModel):
    """Agent capability definition."""
    name: str = Field(..., description="Capability name")
    description: str = Field(..., description="Capability description")
    version: str = Field(..., description="Capability version")
    enabled: bool = Field(default=True, description="Whether capability is enabled")
    configuration: Dict[str, Any] = Field(default_factory=dict, description="Capability configuration")
    dependencies: List[str] = Field(default_factory=list, description="Required dependencies")
    permissions_required: List[str] = Field(default_factory=list, description="Required permissions")


class AgentWorkflow(BaseModel):
    """Agent workflow definition."""
    workflow_id: str = Field(..., description="Unique workflow identifier")
    name: str = Field(..., description="Workflow name")
    description: str = Field(..., description="Workflow description")
    steps: List[Dict[str, Any]] = Field(..., description="Workflow steps")
    triggers: List[str] = Field(default_factory=list, description="Workflow triggers")
    conditions: Dict[str, Any] = Field(default_factory=dict, description="Workflow conditions")
    timeout: Optional[int] = Field(None, description="Workflow timeout in seconds")
    retry_policy: Dict[str, Any] = Field(default_factory=dict, description="Retry policy")
    error_handling: Dict[str, Any] = Field(default_factory=dict, description="Error handling configuration")


class AgentMetrics(BaseModel):
    """Agent performance metrics."""
    agent_id: str = Field(..., description="Agent identifier")
    period_start: datetime = Field(..., description="Metrics period start")
    period_end: datetime = Field(..., description="Metrics period end")
    total_conversations: int = Field(default=0, description="Total conversations handled")
    total_messages_processed: int = Field(default=0, description="Total messages processed")
    total_actions_executed: int = Field(default=0, description="Total actions executed")
    successful_actions: int = Field(default=0, description="Successful actions")
    failed_actions: int = Field(default=0, description="Failed actions")
    average_response_time: float = Field(default=0.0, description="Average response time in seconds")
    user_satisfaction_score: Optional[float] = Field(None, description="User satisfaction score")
    uptime_percentage: float = Field(default=100.0, description="Uptime percentage")
    error_rate: float = Field(default=0.0, description="Error rate percentage")
    throughput: float = Field(default=0.0, description="Messages per minute")
    class Config:
        """Pydantic configuration."""
        json_encoders = { datetime: lambda v: v.isoformat() if v else None }