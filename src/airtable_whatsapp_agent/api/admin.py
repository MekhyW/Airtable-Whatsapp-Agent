"""
Simplified admin API endpoints for monitoring.
"""

import logging
from typing import Dict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .app_state import get_app_state

logger = logging.getLogger(__name__)
router = APIRouter()

class SystemMetrics(BaseModel):
    """System metrics response model."""
    active_sessions: int
    total_messages_processed: int
    total_errors: int
    uptime_seconds: float
    memory_usage_mb: float
    mcp_server_status: Dict[str, str]


@router.get("/metrics", response_model=SystemMetrics)
async def get_system_metrics():
    """Get system metrics and status."""
    try:
        app_state = get_app_state()
        agent = app_state.get("agent")
        mcp_manager = app_state.get("mcp_manager")
        if not agent or not mcp_manager:
            raise HTTPException(status_code=500, detail="Services unavailable")
        agent_metrics = await agent.get_metrics()
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


@router.get("/config")
async def get_config():
    """Get non-sensitive configuration information."""
    try:
        app_state = get_app_state()
        settings = app_state.get("settings")
        if not settings:
            raise HTTPException(status_code=500, detail="Configuration unavailable")
        return {
            "environment": getattr(settings, "environment", "development"),
            "debug": getattr(settings, "debug", False),
            "max_concurrent_sessions": getattr(settings, "max_concurrent_sessions", 10),
            "session_timeout_minutes": getattr(settings, "session_timeout_minutes", 30),
            "mcp_servers": {
                "airtable_url": getattr(settings.mcp, "airtable_server_url", None),
                "whatsapp_url": getattr(settings.mcp, "whatsapp_server_url", None),
                "timeout": getattr(settings.mcp, "timeout", 30)
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting configuration: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving configuration")