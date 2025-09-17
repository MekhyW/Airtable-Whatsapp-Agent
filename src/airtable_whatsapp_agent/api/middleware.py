"""
FastAPI middleware setup and custom middleware.
"""

import time
import logging
from typing import Callable
import uuid

from fastapi import FastAPI, Request, Response
from fastapi.middleware.base import BaseHTTPMiddleware
from starlette.middleware.base import RequestResponseEndpoint


logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging requests and responses."""
    
    async def dispatch(
        self, 
        request: Request, 
        call_next: RequestResponseEndpoint
    ) -> Response:
        """Process request and log details."""
        
        # Generate request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Log request
        start_time = time.time()
        logger.info(
            f"Request {request_id}: {request.method} {request.url.path} "
            f"from {request.client.host if request.client else 'unknown'}"
        )
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate processing time
            process_time = time.time() - start_time
            
            # Log response
            logger.info(
                f"Response {request_id}: {response.status_code} "
                f"in {process_time:.3f}s"
            )
            
            # Add headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = str(process_time)
            
            return response
            
        except Exception as e:
            # Log error
            process_time = time.time() - start_time
            logger.error(
                f"Error {request_id}: {str(e)} in {process_time:.3f}s",
                exc_info=True
            )
            raise


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware for adding security headers."""
    
    async def dispatch(
        self, 
        request: Request, 
        call_next: RequestResponseEndpoint
    ) -> Response:
        """Add security headers to response."""
        
        response = await call_next(request)
        
        # Add security headers
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
        
    async def dispatch(
        self, 
        request: Request, 
        call_next: RequestResponseEndpoint
    ) -> Response:
        """Apply rate limiting."""
        
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"
        
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/", "/docs", "/openapi.json"]:
            return await call_next(request)
        
        current_time = time.time()
        
        # Clean old entries
        if client_ip in self.client_requests:
            self.client_requests[client_ip] = [
                req_time for req_time in self.client_requests[client_ip]
                if current_time - req_time < 60  # Keep last minute
            ]
        else:
            self.client_requests[client_ip] = []
        
        # Check rate limit
        if len(self.client_requests[client_ip]) >= self.calls_per_minute:
            logger.warning(f"Rate limit exceeded for {client_ip}")
            from fastapi import HTTPException
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please try again later."
            )
        
        # Add current request
        self.client_requests[client_ip].append(current_time)
        
        return await call_next(request)


class WhatsAppWebhookMiddleware(BaseHTTPMiddleware):
    """Middleware for WhatsApp webhook validation."""
    
    def __init__(self, app: FastAPI, webhook_verify_token: str):
        super().__init__(app)
        self.webhook_verify_token = webhook_verify_token
        
    async def dispatch(
        self, 
        request: Request, 
        call_next: RequestResponseEndpoint
    ) -> Response:
        """Validate WhatsApp webhook requests."""
        
        # Only apply to webhook endpoints
        if not request.url.path.startswith("/webhooks/whatsapp"):
            return await call_next(request)
        
        # Handle webhook verification (GET request)
        if request.method == "GET":
            verify_token = request.query_params.get("hub.verify_token")
            if verify_token != self.webhook_verify_token:
                logger.warning(f"Invalid webhook verify token: {verify_token}")
                from fastapi import HTTPException
                raise HTTPException(
                    status_code=403,
                    detail="Invalid verify token"
                )
        
        # Handle webhook payload (POST request)
        elif request.method == "POST":
            # Verify signature if needed
            # This would typically involve checking X-Hub-Signature-256 header
            pass
        
        return await call_next(request)


def setup_middleware(app: FastAPI, webhook_verify_token: str = None):
    """Setup all middleware for the FastAPI application."""
    
    # Add custom middleware in reverse order (last added = first executed)
    
    # Security headers (outermost)
    app.add_middleware(SecurityHeadersMiddleware)
    
    # Rate limiting
    app.add_middleware(RateLimitMiddleware, calls_per_minute=120)
    
    # WhatsApp webhook validation
    if webhook_verify_token:
        app.add_middleware(
            WhatsAppWebhookMiddleware, 
            webhook_verify_token=webhook_verify_token
        )
    
    # Request logging (innermost)
    app.add_middleware(RequestLoggingMiddleware)
    
    logger.info("Middleware setup complete")