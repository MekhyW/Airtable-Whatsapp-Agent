"""
FastAPI middleware setup and custom middleware.
"""

import time
import logging
import uuid
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint


logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging requests and responses."""
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process request and log details."""
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        start_time = time.time()
        logger.info(
            f"Request {request_id}: {request.method} {request.url.path} "
            f"from {request.client.host if request.client else 'unknown'}"
        )
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            logger.info(
                f"Response {request_id}: {response.status_code} "
                f"in {process_time:.3f}s"
            )
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = str(process_time)
            return response
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(f"Error {request_id}: {str(e)} in {process_time:.3f}s", exc_info=True)
            raise


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware for adding security headers."""
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Add security headers to response."""
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple rate limiting middleware."""
    def __init__(self, app: FastAPI, calls_per_minute: int = 60):
        super().__init__(app)
        self.calls_per_minute = calls_per_minute
        self.client_requests = {}
        
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Apply rate limiting."""
        client_ip = request.client.host if request.client else "unknown"
        if request.url.path in ["/health", "/", "/docs", "/openapi.json"]:
            return await call_next(request)
        current_time = time.time()
        if client_ip in self.client_requests:
            self.client_requests[client_ip] = [
                req_time for req_time in self.client_requests[client_ip]
                if current_time - req_time < 60  # Keep last minute
            ]
        else:
            self.client_requests[client_ip] = []
        if len(self.client_requests[client_ip]) >= self.calls_per_minute:
            logger.warning(f"Rate limit exceeded for {client_ip}")
            from fastapi import HTTPException
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Please try again later.")
        self.client_requests[client_ip].append(current_time)
        return await call_next(request)


class WhatsAppWebhookMiddleware(BaseHTTPMiddleware):
    """Middleware for WhatsApp webhook validation."""
    def __init__(self, app: FastAPI, webhook_verify_token: str, webhook_url: str = None):
        super().__init__(app)
        self.webhook_verify_token = webhook_verify_token
        self.expected_path_prefix = None
        logger.info(f"🔧 Initializing WhatsApp webhook middleware with verify_token: {'***' if webhook_verify_token else 'None'}")
        try:
            if webhook_url:
                from urllib.parse import urlparse
                parsed = urlparse(webhook_url)
                path = parsed.path or ""
                self.expected_path_prefix = path.rstrip("/")
                logger.info(f"🔧 Webhook URL path prefix set to: {self.expected_path_prefix}")
        except Exception as e:
            logger.warning(f"🔧 Failed to parse webhook URL: {e}")
            self.expected_path_prefix = None

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Validate WhatsApp webhook requests."""
        try:
            if "/webhooks/whatsapp" in request.url.path:
                logger.info(f"🌐 Webhook middleware processing: {request.method} {request.url.path}")
                logger.debug(f"Query params: {dict(request.query_params)}")
            expected_prefixes = ["/webhooks/whatsapp", "/api/v1/webhooks/whatsapp"]
            if self.expected_path_prefix:
                expected_prefixes.append(self.expected_path_prefix)
            if not any(request.url.path.startswith(p) for p in expected_prefixes):
                return await call_next(request)
            if request.method == "GET":
                logger.info(f"📋 Webhook verification request - passing to route handler")
                return await call_next(request)
            elif request.method == "POST":
                logger.info(f"📨 Webhook POST request - processing")
                # Verify signature if needed
                # This would typically involve checking X-Hub-Signature-256 header
                pass
            return await call_next(request)
        except Exception as e:
            logger.error(f"❌ Error in webhook middleware: {str(e)}", exc_info=True)
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=500, content={"error": "Internal server error", "message": "Webhook middleware error"})


def setup_middleware(app: FastAPI, webhook_verify_token: str = None, rate_limit_per_minute: int = 60, webhook_url: str = None):
    """Setup all middleware for the FastAPI application."""
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware, calls_per_minute=rate_limit_per_minute)
    if webhook_verify_token:
        app.add_middleware(WhatsAppWebhookMiddleware, webhook_verify_token=webhook_verify_token, webhook_url=webhook_url)
    app.add_middleware(RequestLoggingMiddleware)
    logger.info("Middleware setup complete")