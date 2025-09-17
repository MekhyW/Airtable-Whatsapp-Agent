"""
Admin API endpoints for management and monitoring.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Depends, Query, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from .main import get_app_state
from ..models import AdminUser, AuditLog


logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer()


class AdminLoginRequest(BaseModel):
    """Admin login request model."""
    username: str
    password: str


class AdminLoginResponse(BaseModel):
    """Admin login response model."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600


class WhitelistRequest(BaseModel):
    """Whitelist management request model."""
    phone_number: str
    role: str = "admin"
    name: Optional[str] = None


class SessionInfo(BaseModel):
    """Session information model."""
    session_id: str
    user_phone: str
    created_at: datetime
    last_activity: datetime
    context: Dict[str, Any]


class SystemMetrics(BaseModel):
    """System metrics model."""
    active_sessions: int
    total_messages_processed: int
    total_errors: int
    uptime_seconds: float
    memory_usage_mb: float
    mcp_server_status: Dict[str, str]


class AdminAPI:
    """Admin API functionality."""
    
    def __init__(self):
        self.admin_sessions = {}
        
    async def authenticate_admin(self, credentials: HTTPAuthorizationCredentials) -> AdminUser:
        """Authenticate admin user."""
        try:
            app_state = get_app_state()
            authenticator = app_state.get("authenticator")
            
            if not authenticator:
                raise HTTPException(status_code=500, detail="Authentication service unavailable")
            
            # Verify token (simplified - in production use proper JWT validation)
            token = credentials.credentials
            
            # For demo purposes, accept a simple token
            if token == "admin-token-123":
                return AdminUser(
                    id="admin",
                    username="admin",
                    role="super_admin",
                    permissions=["all"]
                )
            
            raise HTTPException(status_code=401, detail="Invalid credentials")
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Admin authentication error: {str(e)}")
            raise HTTPException(status_code=500, detail="Authentication error")


# Global admin API instance
admin_api = AdminAPI()


async def get_current_admin(credentials: HTTPAuthorizationCredentials = Depends(security)) -> AdminUser:
    """Get current authenticated admin user."""
    return await admin_api.authenticate_admin(credentials)


@router.post("/login", response_model=AdminLoginResponse)
async def admin_login(request: AdminLoginRequest):
    """Admin login endpoint."""
    
    try:
        # Simplified authentication - in production use proper password hashing
        if request.username == "admin" and request.password == "admin123":
            return AdminLoginResponse(
                access_token="admin-token-123",
                token_type="bearer",
                expires_in=3600
            )
        
        raise HTTPException(status_code=401, detail="Invalid credentials")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin login error: {str(e)}")
        raise HTTPException(status_code=500, detail="Login error")


@router.get("/metrics", response_model=SystemMetrics)
async def get_system_metrics(admin: AdminUser = Depends(get_current_admin)):
    """Get system metrics and status."""
    
    try:
        app_state = get_app_state()
        agent = app_state.get("agent")
        mcp_manager = app_state.get("mcp_manager")
        
        if not agent or not mcp_manager:
            raise HTTPException(status_code=500, detail="Services unavailable")
        
        # Get agent metrics
        agent_metrics = await agent.get_metrics()
        
        # Get MCP server status
        mcp_health = await mcp_manager.health_check()
        mcp_status = {
            "airtable": "healthy" if mcp_health else "unhealthy",
            "whatsapp": "healthy" if mcp_health else "unhealthy"
        }
        
        return SystemMetrics(
            active_sessions=agent_metrics.get("active_sessions", 0),
            total_messages_processed=agent_metrics.get("total_messages", 0),
            total_errors=agent_metrics.get("total_errors", 0),
            uptime_seconds=agent_metrics.get("uptime_seconds", 0),
            memory_usage_mb=agent_metrics.get("memory_usage_mb", 0),
            mcp_server_status=mcp_status
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting system metrics: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving metrics")


@router.get("/sessions", response_model=List[SessionInfo])
async def get_active_sessions(
    admin: AdminUser = Depends(get_current_admin),
    limit: int = Query(50, ge=1, le=100)
):
    """Get active user sessions."""
    
    try:
        app_state = get_app_state()
        agent = app_state.get("agent")
        
        if not agent:
            raise HTTPException(status_code=500, detail="Agent service unavailable")
        
        # Get active sessions from agent
        sessions = await agent.get_active_sessions(limit=limit)
        
        return [
            SessionInfo(
                session_id=session["session_id"],
                user_phone=session["user_phone"],
                created_at=session["created_at"],
                last_activity=session["last_activity"],
                context=session.get("context", {})
            )
            for session in sessions
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting active sessions: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving sessions")


@router.delete("/sessions/{session_id}")
async def terminate_session(
    session_id: str,
    admin: AdminUser = Depends(get_current_admin)
):
    """Terminate a user session."""
    
    try:
        app_state = get_app_state()
        agent = app_state.get("agent")
        
        if not agent:
            raise HTTPException(status_code=500, detail="Agent service unavailable")
        
        # Terminate session
        success = await agent.terminate_session(session_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {"status": "success", "message": f"Session {session_id} terminated"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error terminating session: {str(e)}")
        raise HTTPException(status_code=500, detail="Error terminating session")


@router.get("/whitelist")
async def get_whitelist(admin: AdminUser = Depends(get_current_admin)):
    """Get admin whitelist."""
    
    try:
        app_state = get_app_state()
        authenticator = app_state.get("authenticator")
        
        if not authenticator:
            raise HTTPException(status_code=500, detail="Authentication service unavailable")
        
        # Get whitelist from authenticator
        whitelist = await authenticator.whitelist_manager.get_all_admins()
        
        return {"whitelist": whitelist}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting whitelist: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving whitelist")


@router.post("/whitelist")
async def add_to_whitelist(
    request: WhitelistRequest,
    admin: AdminUser = Depends(get_current_admin)
):
    """Add phone number to admin whitelist."""
    
    try:
        app_state = get_app_state()
        authenticator = app_state.get("authenticator")
        
        if not authenticator:
            raise HTTPException(status_code=500, detail="Authentication service unavailable")
        
        # Add to whitelist
        success = await authenticator.whitelist_manager.add_admin(
            phone_number=request.phone_number,
            role=request.role,
            name=request.name
        )
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to add to whitelist")
        
        return {
            "status": "success",
            "message": f"Added {request.phone_number} to whitelist"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding to whitelist: {str(e)}")
        raise HTTPException(status_code=500, detail="Error adding to whitelist")


@router.delete("/whitelist/{phone_number}")
async def remove_from_whitelist(
    phone_number: str,
    admin: AdminUser = Depends(get_current_admin)
):
    """Remove phone number from admin whitelist."""
    
    try:
        app_state = get_app_state()
        authenticator = app_state.get("authenticator")
        
        if not authenticator:
            raise HTTPException(status_code=500, detail="Authentication service unavailable")
        
        # Remove from whitelist
        success = await authenticator.whitelist_manager.remove_admin(phone_number)
        
        if not success:
            raise HTTPException(status_code=404, detail="Phone number not found in whitelist")
        
        return {
            "status": "success",
            "message": f"Removed {phone_number} from whitelist"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing from whitelist: {str(e)}")
        raise HTTPException(status_code=500, detail="Error removing from whitelist")


@router.get("/audit-logs")
async def get_audit_logs(
    admin: AdminUser = Depends(get_current_admin),
    limit: int = Query(100, ge=1, le=1000),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    action_type: Optional[str] = Query(None)
):
    """Get audit logs."""
    
    try:
        app_state = get_app_state()
        authenticator = app_state.get("authenticator")
        
        if not authenticator:
            raise HTTPException(status_code=500, detail="Authentication service unavailable")
        
        # Get audit logs (simplified - in production implement proper filtering)
        logs = []  # Would fetch from audit log storage
        
        return {
            "logs": logs,
            "total": len(logs),
            "limit": limit
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting audit logs: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving audit logs")


@router.post("/broadcast")
async def broadcast_message(
    message: str = Body(..., embed=True),
    admin: AdminUser = Depends(get_current_admin)
):
    """Broadcast message to all active sessions."""
    
    try:
        app_state = get_app_state()
        agent = app_state.get("agent")
        
        if not agent:
            raise HTTPException(status_code=500, detail="Agent service unavailable")
        
        # Broadcast message
        result = await agent.broadcast_message(message)
        
        return {
            "status": "success",
            "message": "Broadcast sent",
            "recipients": result.get("recipients", 0)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error broadcasting message: {str(e)}")
        raise HTTPException(status_code=500, detail="Error broadcasting message")


@router.post("/maintenance")
async def toggle_maintenance_mode(
    enabled: bool = Body(..., embed=True),
    admin: AdminUser = Depends(get_current_admin)
):
    """Toggle maintenance mode."""
    
    try:
        app_state = get_app_state()
        agent = app_state.get("agent")
        
        if not agent:
            raise HTTPException(status_code=500, detail="Agent service unavailable")
        
        # Toggle maintenance mode
        await agent.set_maintenance_mode(enabled)
        
        return {
            "status": "success",
            "maintenance_mode": enabled,
            "message": f"Maintenance mode {'enabled' if enabled else 'disabled'}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling maintenance mode: {str(e)}")
        raise HTTPException(status_code=500, detail="Error toggling maintenance mode")