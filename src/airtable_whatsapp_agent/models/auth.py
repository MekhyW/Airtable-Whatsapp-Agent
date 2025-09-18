"""
Pydantic models for authentication and authorization.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from enum import Enum
from pydantic import BaseModel, Field, validator


class UserRole(str, Enum):
    """User roles in the system."""
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    MANAGER = "manager"
    USER = "user"
    READONLY = "readonly"
    GUEST = "guest"


class PermissionType(str, Enum):
    """Permission types."""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXECUTE = "execute"
    ADMIN = "admin"


class ResourceType(str, Enum):
    """Resource types for permissions."""
    AIRTABLE_RECORDS = "airtable_records"
    WHATSAPP_MESSAGES = "whatsapp_messages"
    CONVERSATIONS = "conversations"
    TASKS = "tasks"
    SCHEDULES = "schedules"
    USERS = "users"
    SYSTEM_CONFIG = "system_config"
    AUDIT_LOGS = "audit_logs"
    AGENT_ACTIONS = "agent_actions"


class AuthTokenType(str, Enum):
    """Authentication token types."""
    ACCESS = "access"
    REFRESH = "refresh"
    API_KEY = "api_key"
    WEBHOOK = "webhook"
    TEMPORARY = "temporary"


class Permission(BaseModel):
    """Permission model."""
    resource: ResourceType = Field(..., description="Resource type")
    action: PermissionType = Field(..., description="Permission type")
    conditions: Optional[Dict[str, Any]] = Field(None, description="Permission conditions")
    granted_at: datetime = Field(default_factory=datetime.utcnow, description="Permission grant timestamp")
    granted_by: Optional[str] = Field(None, description="Who granted the permission")
    expires_at: Optional[datetime] = Field(None, description="Permission expiration")
    
    def __str__(self) -> str:
        """String representation of permission."""
        return f"{self.action.value}:{self.resource.value}"
    
    def is_expired(self) -> bool:
        """Check if permission is expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at


class User(BaseModel):
    """Base user model."""
    user_id: str = Field(..., description="Unique user identifier")
    phone_number: str = Field(..., description="User phone number")
    name: Optional[str] = Field(None, description="User name")
    email: Optional[str] = Field(None, description="User email")
    role: UserRole = Field(default=UserRole.USER, description="User role")
    permissions: List[Permission] = Field(default_factory=list, description="User permissions")
    is_active: bool = Field(default=True, description="Whether user is active")
    is_verified: bool = Field(default=False, description="Whether user is verified")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="User creation timestamp")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")
    login_count: int = Field(default=0, description="Number of logins")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional user metadata")
    
    @validator('phone_number')
    def validate_phone_number(cls, v):
        """Validate phone number format."""
        digits_only = ''.join(filter(str.isdigit, v))
        if len(digits_only) < 10:
            raise ValueError('Phone number must contain at least 10 digits')
        return v
    
    def has_permission(self, resource: ResourceType, action: PermissionType) -> bool:
        """Check if user has specific permission."""
        for permission in self.permissions:
            if permission.resource == resource and permission.action == action:
                if not permission.is_expired():
                    return True
        return False
    
    def get_permissions_for_resource(self, resource: ResourceType) -> List[Permission]:
        """Get all permissions for a specific resource."""
        return [p for p in self.permissions if p.resource == resource and not p.is_expired()]


class AdminUser(User):
    """Administrator user model with additional privileges."""
    role: UserRole = Field(default=UserRole.ADMIN, description="Admin role")
    admin_level: int = Field(default=1, ge=1, le=10, description="Admin level (1-10)")
    can_manage_users: bool = Field(default=True, description="Can manage other users")
    can_access_audit_logs: bool = Field(default=True, description="Can access audit logs")
    can_modify_system_config: bool = Field(default=False, description="Can modify system configuration")
    emergency_contact: Optional[str] = Field(None, description="Emergency contact information")
    backup_phone: Optional[str] = Field(None, description="Backup phone number")
    
    def can_manage_user(self, target_user: User) -> bool:
        """Check if admin can manage target user."""
        if not self.can_manage_users:
            return False
        if self.role == UserRole.SUPER_ADMIN:
            return True
        if target_user.role == UserRole.SUPER_ADMIN:
            return False
        role_hierarchy = {
            UserRole.GUEST: 1,
            UserRole.READONLY: 2,
            UserRole.USER: 3,
            UserRole.MANAGER: 4,
            UserRole.ADMIN: 5,
            UserRole.SUPER_ADMIN: 6,
        }
        return role_hierarchy.get(self.role, 0) >= role_hierarchy.get(target_user.role, 0)


class AuthToken(BaseModel):
    """Authentication token model."""
    token_id: str = Field(..., description="Unique token identifier")
    token_type: AuthTokenType = Field(..., description="Token type")
    user_id: str = Field(..., description="Associated user ID")
    token_hash: str = Field(..., description="Hashed token value")
    scopes: List[str] = Field(default_factory=list, description="Token scopes")
    is_active: bool = Field(default=True, description="Whether token is active")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Token creation timestamp")
    expires_at: Optional[datetime] = Field(None, description="Token expiration timestamp")
    last_used: Optional[datetime] = Field(None, description="Last usage timestamp")
    usage_count: int = Field(default=0, description="Number of times used")
    max_uses: Optional[int] = Field(None, description="Maximum number of uses")
    ip_restrictions: List[str] = Field(default_factory=list, description="IP address restrictions")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional token metadata")
    
    def is_expired(self) -> bool:
        """Check if token is expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    def is_usage_exceeded(self) -> bool:
        """Check if token usage limit is exceeded."""
        if self.max_uses is None:
            return False
        return self.usage_count >= self.max_uses
    
    def is_valid(self) -> bool:
        """Check if token is valid for use."""
        return (self.is_active and not self.is_expired() and not self.is_usage_exceeded())


class AuthSession(BaseModel):
    """User authentication session."""
    session_id: str = Field(..., description="Unique session identifier")
    user_id: str = Field(..., description="Associated user ID")
    conversation_id: Optional[str] = Field(None, description="Associated conversation ID")
    is_active: bool = Field(default=True, description="Whether session is active")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Session creation timestamp")
    last_activity: datetime = Field(default_factory=datetime.utcnow, description="Last activity timestamp")
    expires_at: datetime = Field(..., description="Session expiration timestamp")
    ip_address: Optional[str] = Field(None, description="Client IP address")
    user_agent: Optional[str] = Field(None, description="Client user agent")
    device_info: Optional[Dict[str, Any]] = Field(None, description="Device information")
    location: Optional[Dict[str, Any]] = Field(None, description="Session location")
    
    @classmethod
    def create_session(cls, user_id: str, duration_hours: int = 24, **kwargs) -> 'AuthSession':
        """Create a new authentication session."""
        import uuid
        session_id = str(uuid.uuid4())
        expires_at = datetime.utcnow() + timedelta(hours=duration_hours)
        return cls(session_id=session_id, user_id=user_id, expires_at=expires_at, **kwargs)
    
    def is_expired(self) -> bool:
        """Check if session is expired."""
        return datetime.utcnow() > self.expires_at
    
    def extend_session(self, hours: int = 24) -> None:
        """Extend session expiration."""
        self.expires_at = datetime.utcnow() + timedelta(hours=hours)
        self.last_activity = datetime.utcnow()
    
    def is_valid(self) -> bool:
        """Check if session is valid."""
        return self.is_active and not self.is_expired()


class AuthenticationRequest(BaseModel):
    """Authentication request model."""
    phone_number: str = Field(..., description="User phone number")
    verification_code: Optional[str] = Field(None, description="Verification code")
    device_info: Optional[Dict[str, Any]] = Field(None, description="Device information")
    ip_address: Optional[str] = Field(None, description="Client IP address")
    user_agent: Optional[str] = Field(None, description="Client user agent")
    
    @validator('phone_number')
    def validate_phone_number(cls, v):
        """Validate phone number format."""
        digits_only = ''.join(filter(str.isdigit, v))
        if len(digits_only) < 10:
            raise ValueError('Phone number must contain at least 10 digits')
        return v


class AuthenticationResponse(BaseModel):
    """Authentication response model."""
    success: bool = Field(..., description="Whether authentication was successful")
    user: Optional[User] = Field(None, description="Authenticated user")
    session: Optional[AuthSession] = Field(None, description="Created session")
    access_token: Optional[str] = Field(None, description="Access token")
    refresh_token: Optional[str] = Field(None, description="Refresh token")
    expires_in: Optional[int] = Field(None, description="Token expiration in seconds")
    error_message: Optional[str] = Field(None, description="Error message if authentication failed")
    requires_verification: bool = Field(default=False, description="Whether verification is required")


class PermissionCheck(BaseModel):
    """Permission check request."""
    user_id: str = Field(..., description="User ID to check")
    resource: ResourceType = Field(..., description="Resource to access")
    action: PermissionType = Field(..., description="Action to perform")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")


class PermissionCheckResult(BaseModel):
    """Permission check result."""
    allowed: bool = Field(..., description="Whether action is allowed")
    reason: Optional[str] = Field(None, description="Reason for denial")
    conditions: Optional[Dict[str, Any]] = Field(None, description="Conditional permissions")
    expires_at: Optional[datetime] = Field(None, description="Permission expiration")


class AuditEvent(BaseModel):
    """Audit event for security logging."""
    event_id: str = Field(..., description="Unique event identifier")
    event_type: str = Field(..., description="Type of event")
    user_id: Optional[str] = Field(None, description="User who performed the action")
    resource: Optional[str] = Field(None, description="Resource affected")
    action: str = Field(..., description="Action performed")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp")
    ip_address: Optional[str] = Field(None, description="Client IP address")
    user_agent: Optional[str] = Field(None, description="Client user agent")
    success: bool = Field(..., description="Whether action was successful")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional event details")
    risk_score: Optional[float] = Field(None, description="Risk score for the event")
    class Config:
        """Pydantic configuration."""
        json_encoders = { datetime: lambda v: v.isoformat() if v else None }