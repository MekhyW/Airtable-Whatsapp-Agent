"""
Utility modules for the Airtable WhatsApp Agent.

This package provides common utilities including error handling, rate limiting,
monitoring, configuration management, and other shared functionality.
"""

from .error_handling import (
    ErrorHandler,
    ErrorSeverity,
    RetryStrategy,
    RetryConfig,
    CircuitBreakerConfig,
    CircuitBreaker,
    error_handler,
    retry_on_failure,
    circuit_breaker,
    AIRTABLE_RETRY_CONFIG,
    WHATSAPP_RETRY_CONFIG,
    OPENAI_RETRY_CONFIG
)

from .rate_limiter import (
    RateLimiter,
    RateLimitStrategy,
    RateLimitScope,
    RateLimitConfig,
    RateLimitResult,
    RateLimitMiddleware,
    TokenBucket,
    SlidingWindowCounter,
    AdaptiveRateLimiter,
    WHATSAPP_RATE_LIMIT,
    AIRTABLE_RATE_LIMIT,
    OPENAI_RATE_LIMIT
)

from .monitoring import (
    HealthChecker,
    MetricsCollector,
    HealthStatus,
    ComponentType,
    HealthCheckResult,
    SystemMetrics,
    health_checker,
    metrics_collector,
    setup_default_health_checks,
    check_whatsapp_api,
    check_airtable_api,
    check_database_connection,
    check_redis_connection,
)

from .config_manager import (
    ConfigManager,
    AppConfig,
    DatabaseConfig,
    RedisConfig,
    WhatsAppConfig,
    AirtableConfig,
    SecurityConfig,
    MonitoringConfig,
    ServerConfig,
    Environment,
    LogLevel,
    config_manager,
    get_config,
    load_config,
)

__all__ = [
    # Error handling
    "ErrorHandler",
    "ErrorSeverity",
    "RetryStrategy",
    "RetryConfig",
    "CircuitBreakerConfig",
    "CircuitBreaker",
    "error_handler",
    "retry_on_failure",
    "circuit_breaker",
    "AIRTABLE_RETRY_CONFIG",
    "WHATSAPP_RETRY_CONFIG",
    "OPENAI_RETRY_CONFIG",
    
    # Rate limiting
    "RateLimiter",
    "RateLimitStrategy",
    "RateLimitScope",
    "RateLimitConfig",
    "RateLimitResult",
    "RateLimitMiddleware",
    "TokenBucket",
    "SlidingWindowCounter",
    "AdaptiveRateLimiter",
    "WHATSAPP_RATE_LIMIT",
    "AIRTABLE_RATE_LIMIT",
    "OPENAI_RATE_LIMIT",
    
    # Monitoring
    "HealthChecker",
    "MetricsCollector",
    "HealthStatus",
    "ComponentType",
    "HealthCheckResult",
    "SystemMetrics",
    "health_checker",
    "metrics_collector",
    "setup_default_health_checks",
    "check_whatsapp_api",
    "check_airtable_api",
    "check_database_connection",
    "check_redis_connection",
    
    # Configuration
    "ConfigManager",
    "AppConfig",
    "DatabaseConfig",
    "RedisConfig",
    "WhatsAppConfig",
    "AirtableConfig",
    "SecurityConfig",
    "MonitoringConfig",
    "ServerConfig",
    "Environment",
    "LogLevel",
    "config_manager",
    "get_config",
    "load_config",
]