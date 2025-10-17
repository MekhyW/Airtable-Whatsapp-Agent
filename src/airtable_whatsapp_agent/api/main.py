"""
Main FastAPI application setup.
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import JSONResponse
import uvicorn
from .webhooks import router as webhooks_router
from .admin import router as admin_router
from .middleware import setup_middleware
from .app_state import get_app_state, set_app_state
from ..agent import AutonomousAgent
from ..mcp import MCPServerManager
from ..config import Settings
from ..utils.logging import configure_logging


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    settings = Settings()
    configure_logging(level="DEBUG", format_type="colored" if settings.is_development else "structured", log_file=None)
    logger.info("Starting up application...")
    try:
        set_app_state("settings", settings)
        mcp_manager = MCPServerManager(settings)
        await mcp_manager.initialize()
        set_app_state("mcp_manager", mcp_manager)
        agent = AutonomousAgent(
            mcp_manager=mcp_manager, 
            openai_api_key=settings.openai_api_key,
            settings=settings,
            max_concurrent_sessions=settings.max_concurrent_sessions
        )
        set_app_state("agent", agent)
        logger.info("Application startup complete")
        yield
    except Exception as e:
        logger.error(f"Startup error: {str(e)}")
        raise
    logger.info("Shutting down application...")
    try:
        current_state = get_app_state()
        if current_state["agent"]:
            await current_state["agent"].shutdown()
        if current_state["mcp_manager"]:
            await current_state["mcp_manager"].shutdown()
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
    local_settings = Settings()
    setup_middleware(
        app,
        webhook_verify_token=local_settings.whatsapp_webhook_verify_token,
        rate_limit_per_minute=local_settings.rate_limit_per_minute,
        webhook_url=local_settings.whatsapp_webhook_url,
    )
    app.include_router(webhooks_router, prefix=f"{local_settings.api_v1_str}/webhooks", tags=["webhooks"])
    app.include_router(admin_router, prefix=f"{local_settings.api_v1_str}/admin", tags=["admin"])

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        try:
            current_state = get_app_state()
            mcp_health = await current_state["mcp_manager"].health_check() if current_state["mcp_manager"] else False
            agent_metrics = await current_state["agent"].get_metrics() if current_state["agent"] else {}
            return {
                "status": "healthy" if mcp_health else "degraded",
                "timestamp": datetime.now().isoformat(),
                "services": {
                    "mcp_manager": "healthy" if mcp_health else "unhealthy",
                    "agent": "healthy" if current_state["agent"] else "unhealthy"
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

    @app.exception_handler(StarletteHTTPException)
    async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException):
        """Starlette HTTP exception handler."""
        return JSONResponse(status_code=exc.status_code, content={"error": exc.detail, "status_code": exc.status_code})

    return app


def run_server(host: str = "0.0.0.0", port: int = 8000, reload: bool = False, log_level: str = "debug"):
    """Run the FastAPI server."""
    uvicorn.run(
        "airtable_whatsapp_agent.api.main:create_app",
        factory=True,
        host=host,
        port=port,
        reload=reload,
        log_level=log_level
    )