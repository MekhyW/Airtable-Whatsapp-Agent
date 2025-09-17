"""
Pydantic models for Airtable records and data structures.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum
from pydantic import BaseModel, Field, validator


class RecordStatus(str, Enum):
    """Status enumeration for records."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class TaskPriority(str, Enum):
    """Priority levels for tasks."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class AirtableRecord(BaseModel):
    """Base model for Airtable records."""
    
    id: Optional[str] = Field(None, description="Airtable record ID")
    created_time: Optional[datetime] = Field(None, description="Record creation timestamp")
    fields: Dict[str, Any] = Field(default_factory=dict, description="Record fields")
    
    class Config:
        """Pydantic configuration."""
        json_encoders = { datetime: lambda v: v.isoformat() if v else None }


class AdminWhitelistRecord(AirtableRecord):
    """Model for administrator whitelist records."""
    
    phone_number: str = Field(..., description="Administrator phone number")
    name: str = Field(..., description="Administrator name")
    email: Optional[str] = Field(None, description="Administrator email")
    role: str = Field(default="admin", description="Administrator role")
    status: RecordStatus = Field(default=RecordStatus.ACTIVE, description="Record status")
    permissions: List[str] = Field(default_factory=list, description="Administrator permissions")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")
    
    @validator('phone_number')
    def validate_phone_number(cls, v):
        """Validate phone number format."""
        digits_only = ''.join(filter(str.isdigit, v)) # Remove any non-digit characters for validation
        if len(digits_only) < 10:
            raise ValueError('Phone number must contain at least 10 digits')
        return v


class ContactRecord(AirtableRecord):
    """Model for contact records."""
    
    phone_number: str = Field(..., description="Contact phone number")
    name: Optional[str] = Field(None, description="Contact name")
    email: Optional[str] = Field(None, description="Contact email")
    company: Optional[str] = Field(None, description="Contact company")
    role: Optional[str] = Field(None, description="Contact role")
    status: RecordStatus = Field(default=RecordStatus.ACTIVE, description="Contact status")
    tags: List[str] = Field(default_factory=list, description="Contact tags")
    notes: Optional[str] = Field(None, description="Contact notes")
    last_contact: Optional[datetime] = Field(None, description="Last contact timestamp")
    
    @validator('phone_number')
    def validate_phone_number(cls, v):
        """Validate phone number format."""
        digits_only = ''.join(filter(str.isdigit, v))
        if len(digits_only) < 10:
            raise ValueError('Phone number must contain at least 10 digits')
        return v


class ConversationRecord(AirtableRecord):
    """Model for conversation records."""
    
    conversation_id: str = Field(..., description="Unique conversation identifier")
    contact_phone: str = Field(..., description="Contact phone number")
    admin_phone: Optional[str] = Field(None, description="Admin phone number")
    status: RecordStatus = Field(default=RecordStatus.ACTIVE, description="Conversation status")
    subject: Optional[str] = Field(None, description="Conversation subject")
    summary: Optional[str] = Field(None, description="Conversation summary")
    started_at: datetime = Field(default_factory=datetime.utcnow, description="Conversation start time")
    last_message_at: Optional[datetime] = Field(None, description="Last message timestamp")
    message_count: int = Field(default=0, description="Number of messages in conversation")
    tags: List[str] = Field(default_factory=list, description="Conversation tags")


class MessageRecord(AirtableRecord):
    """Model for message records."""
    
    message_id: str = Field(..., description="Unique message identifier")
    conversation_id: str = Field(..., description="Associated conversation ID")
    sender_phone: str = Field(..., description="Sender phone number")
    recipient_phone: str = Field(..., description="Recipient phone number")
    message_type: str = Field(..., description="Message type (text, image, document, etc.)")
    content: str = Field(..., description="Message content")
    media_url: Optional[str] = Field(None, description="Media URL if applicable")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Message timestamp")
    status: str = Field(default="sent", description="Message status")
    is_from_admin: bool = Field(default=False, description="Whether message is from admin")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional message metadata")


class TaskRecord(AirtableRecord):
    """Model for task records."""
    
    task_id: str = Field(..., description="Unique task identifier")
    title: str = Field(..., description="Task title")
    description: Optional[str] = Field(None, description="Task description")
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM, description="Task priority")
    status: RecordStatus = Field(default=RecordStatus.PENDING, description="Task status")
    assigned_to: Optional[str] = Field(None, description="Assigned admin phone number")
    created_by: Optional[str] = Field(None, description="Creator admin phone number")
    due_date: Optional[datetime] = Field(None, description="Task due date")
    completed_at: Optional[datetime] = Field(None, description="Task completion timestamp")
    tags: List[str] = Field(default_factory=list, description="Task tags")
    related_conversation: Optional[str] = Field(None, description="Related conversation ID")
    recurring: bool = Field(default=False, description="Whether task is recurring")
    recurring_pattern: Optional[str] = Field(None, description="Recurring pattern (cron-like)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional task metadata")


class AuditLogRecord(AirtableRecord):
    """Model for audit log records."""
    
    log_id: str = Field(..., description="Unique log identifier")
    action: str = Field(..., description="Action performed")
    actor_phone: str = Field(..., description="Phone number of actor")
    actor_type: str = Field(..., description="Type of actor (admin, agent, system)")
    target_type: str = Field(..., description="Type of target (record, conversation, task)")
    target_id: Optional[str] = Field(None, description="Target identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Action timestamp")
    details: Dict[str, Any] = Field(default_factory=dict, description="Action details")
    ip_address: Optional[str] = Field(None, description="IP address of actor")
    user_agent: Optional[str] = Field(None, description="User agent string")
    success: bool = Field(default=True, description="Whether action was successful")
    error_message: Optional[str] = Field(None, description="Error message if action failed")


class ProjectRecord(AirtableRecord):
    """Model for project records."""
    
    project_id: str = Field(..., description="Unique project identifier")
    name: str = Field(..., description="Project name")
    description: Optional[str] = Field(None, description="Project description")
    status: RecordStatus = Field(default=RecordStatus.ACTIVE, description="Project status")
    owner_phone: Optional[str] = Field(None, description="Project owner phone number")
    team_members: List[str] = Field(default_factory=list, description="Team member phone numbers")
    start_date: Optional[datetime] = Field(None, description="Project start date")
    end_date: Optional[datetime] = Field(None, description="Project end date")
    progress: float = Field(default=0.0, ge=0.0, le=100.0, description="Project progress percentage")
    tags: List[str] = Field(default_factory=list, description="Project tags")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional project metadata")


class ScheduledTaskRecord(AirtableRecord):
    """Model for scheduled task records."""
    
    schedule_id: str = Field(..., description="Unique schedule identifier")
    task_name: str = Field(..., description="Scheduled task name")
    description: Optional[str] = Field(None, description="Task description")
    cron_expression: str = Field(..., description="Cron expression for scheduling")
    action_type: str = Field(..., description="Type of action to perform")
    action_config: Dict[str, Any] = Field(default_factory=dict, description="Action configuration")
    status: RecordStatus = Field(default=RecordStatus.ACTIVE, description="Schedule status")
    created_by: str = Field(..., description="Creator admin phone number")
    last_run: Optional[datetime] = Field(None, description="Last execution timestamp")
    next_run: Optional[datetime] = Field(None, description="Next execution timestamp")
    run_count: int = Field(default=0, description="Number of times executed")
    max_runs: Optional[int] = Field(None, description="Maximum number of runs")
    timezone: str = Field(default="UTC", description="Timezone for scheduling")