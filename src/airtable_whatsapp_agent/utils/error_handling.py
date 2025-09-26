"""
Error handling and retry mechanisms for external API calls.

This module provides comprehensive error handling, retry logic, and circuit breaker
patterns for robust external API interactions.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type
from dataclasses import dataclass, field
from functools import wraps
import random
import httpx


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RetryStrategy(Enum):
    """Retry strategy types."""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    FIXED_DELAY = "fixed_delay"
    LINEAR_BACKOFF = "linear_backoff"
    RANDOM_JITTER = "random_jitter"


@dataclass
class RetryConfig:
    """Configuration for retry mechanisms."""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    retryable_exceptions: List[Type[Exception]] = field(default_factory=lambda: [
        httpx.TimeoutException,
        httpx.ConnectTimeout,
        httpx.ReadTimeout,
        httpx.NetworkError,
        ConnectionError,
        TimeoutError
    ])
    retryable_status_codes: List[int] = field(default_factory=lambda: [
        429,  # Too Many Requests
        500,  # Internal Server Error
        502,  # Bad Gateway
        503,  # Service Unavailable
        504,  # Gateway Timeout
    ])


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker pattern."""
    failure_threshold: int = 5
    recovery_timeout: int = 60
    expected_exception: Type[Exception] = Exception
    name: str = "default"


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class ErrorContext:
    """Context information for errors."""
    timestamp: datetime
    function_name: str
    args: tuple
    kwargs: dict
    attempt_number: int
    exception: Exception
    severity: ErrorSeverity
    metadata: Dict[str, Any] = field(default_factory=dict)


class CircuitBreaker:
    """Circuit breaker implementation for fault tolerance."""
    
    def __init__(self, config: CircuitBreakerConfig):
        if isinstance(config, dict):
            self.config = CircuitBreakerConfig(**config)
        else:
            self.config = config
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = CircuitBreakerState.CLOSED
        self.logger = logging.getLogger(f"circuit_breaker.{self.config.name}")
    
    def __call__(self, func: Callable) -> Callable:
        """Decorator to apply circuit breaker to a function."""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if self.state == CircuitBreakerState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitBreakerState.HALF_OPEN
                    self.logger.info(f"Circuit breaker {self.config.name} moved to HALF_OPEN")
                else:
                    raise Exception(f"Circuit breaker {self.config.name} is OPEN")
            try:
                result = await func(*args, **kwargs)
                self._on_success()
                return result
            except self.config.expected_exception as e:
                self._on_failure()
                raise e
        return wrapper
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt to reset."""
        if self.last_failure_time is None:
            return True
        return (datetime.now() - self.last_failure_time).total_seconds() > self.config.recovery_timeout
    
    def _on_success(self):
        """Handle successful call."""
        self.failure_count = 0
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.CLOSED
            self.logger.info(f"Circuit breaker {self.config.name} moved to CLOSED")
    
    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        if self.failure_count >= self.config.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            self.logger.warning(f"Circuit breaker {self.config.name} moved to OPEN")


class ErrorHandler:
    """Comprehensive error handling with retry mechanisms."""
    
    def __init__(self):
        self.logger = logging.getLogger("error_handler")
        self.error_history: List[ErrorContext] = []
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
    
    def register_circuit_breaker(self, name: str, config: CircuitBreakerConfig) -> CircuitBreaker:
        """Register a circuit breaker."""
        if isinstance(config, dict):
            config = CircuitBreakerConfig(**config)
        circuit_breaker = CircuitBreaker(config)
        self.circuit_breakers[name] = circuit_breaker
        return circuit_breaker
    
    def get_circuit_breaker(self, name: str) -> Optional[CircuitBreaker]:
        """Get a registered circuit breaker."""
        return self.circuit_breakers.get(name)
    
    def retry_with_backoff(self, config: RetryConfig = None):
        """Decorator for retry with configurable backoff strategy."""
        if config is None:
            config = RetryConfig()
        
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args, **kwargs):
                last_exception = None
                for attempt in range(config.max_attempts):
                    try:
                        result = await func(*args, **kwargs)
                        if attempt > 0:
                            self.logger.info(f"Function {func.__name__} succeeded on attempt {attempt + 1}")
                        return result
                    except Exception as e:
                        last_exception = e
                        if not self._is_retryable_exception(e, config):
                            self.logger.error(f"Non-retryable exception in {func.__name__}: {e}")
                            raise e
                        error_context = ErrorContext(timestamp=datetime.now(), function_name=func.__name__, args=args, kwargs=kwargs, attempt_number=attempt + 1, exception=e, severity=self._determine_severity(e))
                        self.error_history.append(error_context)
                        if attempt < config.max_attempts - 1:
                            delay = self._calculate_delay(attempt, config)
                            self.logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {e}. " f"Retrying in {delay:.2f} seconds...")
                            await asyncio.sleep(delay)
                        else:
                            self.logger.error(f"All {config.max_attempts} attempts failed for {func.__name__}")
                raise last_exception
            return wrapper
        return decorator
    
    def _is_retryable_exception(self, exception: Exception, config: RetryConfig) -> bool:
        """Check if an exception is retryable."""
        if any(isinstance(exception, exc_type) for exc_type in config.retryable_exceptions):
            return True
        if isinstance(exception, httpx.HTTPStatusError):
            return exception.response.status_code in config.retryable_status_codes
        return False
    
    def _calculate_delay(self, attempt: int, config: RetryConfig) -> float:
        """Calculate delay based on retry strategy."""
        if config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = config.base_delay * (config.exponential_base ** attempt)
        elif config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = config.base_delay * (attempt + 1)
        elif config.strategy == RetryStrategy.FIXED_DELAY:
            delay = config.base_delay
        elif config.strategy == RetryStrategy.RANDOM_JITTER:
            delay = config.base_delay + random.uniform(0, config.base_delay)
        else:
            delay = config.base_delay
        if config.jitter and config.strategy != RetryStrategy.RANDOM_JITTER:
            jitter = random.uniform(0.1, 0.3) * delay
            delay += jitter
        return min(delay, config.max_delay)
    
    def _determine_severity(self, exception: Exception) -> ErrorSeverity:
        """Determine error severity based on exception type."""
        if isinstance(exception, (TimeoutError, httpx.TimeoutException)):
            return ErrorSeverity.MEDIUM
        elif isinstance(exception, (ConnectionError, httpx.NetworkError)):
            return ErrorSeverity.HIGH
        elif isinstance(exception, httpx.HTTPStatusError):
            if exception.response.status_code >= 500:
                return ErrorSeverity.HIGH
            elif exception.response.status_code == 429:
                return ErrorSeverity.MEDIUM
            else:
                return ErrorSeverity.LOW
        else:
            return ErrorSeverity.MEDIUM
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics from history."""
        if not self.error_history:
            return {"total_errors": 0}
        total_errors = len(self.error_history)
        severity_counts = {}
        function_counts = {}
        for error in self.error_history:
            severity = error.severity.value
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
            func_name = error.function_name
            function_counts[func_name] = function_counts.get(func_name, 0) + 1
        recent_errors = [error for error in self.error_history if error.timestamp > datetime.now() - timedelta(hours=1)]
        return {
            "total_errors": total_errors,
            "severity_breakdown": severity_counts,
            "function_breakdown": function_counts,
            "recent_errors_1h": len(recent_errors),
            "circuit_breaker_states": { name: cb.state.value for name, cb in self.circuit_breakers.items() }
        }
    
    def clear_error_history(self, older_than_hours: int = 24):
        """Clear old error history."""
        cutoff_time = datetime.now() - timedelta(hours=older_than_hours)
        self.error_history = [
            error for error in self.error_history
            if error.timestamp > cutoff_time
        ]


error_handler = ErrorHandler() # Global error handler instance

# Convenience decorators
def retry_on_failure(config: RetryConfig = None):
    """Convenience decorator for retry with default config."""
    return error_handler.retry_with_backoff(config)

def circuit_breaker(name: str, config: CircuitBreakerConfig = None):
    """Convenience decorator for circuit breaker."""
    if config is None:
        config = CircuitBreakerConfig(name=name)
    elif isinstance(config, dict):
        config = CircuitBreakerConfig(**config)
    cb = error_handler.register_circuit_breaker(name, config)
    return cb


AIRTABLE_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=30.0,
    strategy=RetryStrategy.EXPONENTIAL_BACKOFF
)

WHATSAPP_RETRY_CONFIG = RetryConfig(
    max_attempts=5,
    base_delay=2.0,
    max_delay=60.0,
    strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
    retryable_status_codes=[429, 500, 502, 503, 504]
)

OPENAI_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=45.0,
    strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
    retryable_status_codes=[429, 500, 502, 503, 504]
)

EXTERNAL_MCP_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=30.0,
    strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
    retryable_status_codes=[429, 500, 502, 503, 504]
)