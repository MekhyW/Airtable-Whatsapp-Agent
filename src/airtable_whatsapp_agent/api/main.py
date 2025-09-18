"""
Main FastAPI application setup.
"""

import logging
from contextlib import asynccontextmanager
from typing import Dict, Any
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from .webhooks import router as webhooks_router
from .admin import router as admin_router
from .middleware import setup_middleware
from ..agent import AutonomousAgent
from ..auth import Authenticator
from ..mcp import MCPServerManager
from ..config import Settings


logger = logging.getLogger(__name__)


app_state = {
    "agent": None,
    "authenticator": None,
    "mcp_manager": None,
    "settings": None
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting up application...")
    try:
        settings = Settings()
        app_state["settings"] = settings
        mcp_manager = MCPServerManager()
        await mcp_manager.initialize()
        app_state["mcp_manager"] = mcp_manager
        authenticator = Authenticator(airtable_api_key=settings.airtable.api_key, airtable_base_id=settings.airtable.base_id)
        app_state["authenticator"] = authenticator
        agent = AutonomousAgent(
            mcp_manager=mcp_manager,
            authenticator=authenticator,
            openai_api_key=settings.openai_api_key,
            max_concurrent_sessions=settings.max_concurrent_sessions,
            session_timeout_minutes=settings.session_timeout_minutes
        )
        app_state["agent"] = agent
        logger.info("Application startup complete")
        yield
    except Exception as e:
        logger.error(f"Startup error: {str(e)}")
        raise
    logger.info("Shutting down application...")
    try:
        if app_state["agent"]:
            await app_state["agent"].shutdown()
        if app_state["mcp_manager"]:
            await app_state["mcp_manager"].shutdown()
        logger.info("Application shutdown complete")
    except Exception as e:
        logger.error(f"Shutdown error: {str(e)}")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="Airtable WhatsApp Agent",
        description="Autonomous AI agent for WhatsApp and Airtable integration",
        lifespan=lifespan
    )
    settings = app_state.get("settings")
    webhook_verify_token = settings.whatsapp_webhook_verify_token if settings else None
    setup_middleware(app, webhook_verify_token)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(
        webhooks_router,
        prefix="/webhooks",
        tags=["webhooks"]
    )
    app.include_router(
        admin_router,
        prefix="/admin",
        tags=["admin"]
    )

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        try:
            mcp_health = await app_state["mcp_manager"].health_check() if app_state["mcp_manager"] else False
            agent_metrics = await app_state["agent"].get_metrics() if app_state["agent"] else {}
            return {
                "status": "healthy" if mcp_health else "degraded",
                "timestamp": datetime.now().isoformat(),
                "services": {
                    "mcp_manager": "healthy" if mcp_health else "unhealthy",
                    "agent": "healthy" if app_state["agent"] else "unhealthy",
                    "authenticator": "healthy" if app_state["authenticator"] else "unhealthy"
                },
                "metrics": agent_metrics
            }
        except Exception as e:
            logger.error(f"Health check error: {str(e)}")
            return JSONResponse(status_code=503, content={"status": "unhealthy", "error": str(e)})

    @app.get("/")
    async def root():
        """Root endpoint."""
        return {
            "message": "Airtable WhatsApp Agent API",
            "docs": "/docs",
            "health": "/health"
        }
    
    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Global exception handler."""
        logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": "Internal server error", "message": "An unexpected error occurred"})

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """HTTP exception handler."""
        return JSONResponse(status_code=exc.status_code, content={"error": exc.detail, "status_code": exc.status_code})

    return app


def get_app_state() -> Dict[str, Any]:
    """Get application state."""
    return app_state


def run_server(
    host: str = "0.0.0.0",
    port: int = 8000,
    reload: bool = False,
    log_level: str = "info"
):
    """Run the FastAPI server."""
    uvicorn.run(
        "airtable_whatsapp_agent.api.main:create_app",
        factory=True,
        host=host,
        port=port,
        reload=reload,
        log_level=log_level
    )