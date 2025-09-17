"""
Rate limiting and request throttling for external APIs.

This module provides comprehensive rate limiting mechanisms including
token bucket, sliding window, and adaptive rate limiting strategies.
"""

import asyncio
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Optional, Any
from dataclasses import dataclass
from collections import deque
import logging
import redis.asyncio as redis


class RateLimitStrategy(Enum):
    """Rate limiting strategy types."""
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"
    ADAPTIVE = "adaptive"


class RateLimitScope(Enum):
    """Rate limit scope levels."""
    GLOBAL = "global"
    PER_USER = "per_user"
    PER_ENDPOINT = "per_endpoint"
    PER_IP = "per_ip"


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    requests_per_second: float = 10.0
    requests_per_minute: int = 600
    requests_per_hour: int = 36000
    burst_capacity: int = 20
    strategy: RateLimitStrategy = RateLimitStrategy.TOKEN_BUCKET
    scope: RateLimitScope = RateLimitScope.GLOBAL
    adaptive_increase_factor: float = 1.1
    adaptive_decrease_factor: float = 0.9
    adaptive_min_rate: float = 1.0
    adaptive_max_rate: float = 100.0
    backoff_factor: float = 2.0
    max_backoff: float = 300.0  # 5 minutes


@dataclass
class RateLimitResult:
    """Result of rate limit check."""
    allowed: bool
    remaining_requests: int
    reset_time: datetime
    retry_after: Optional[float] = None
    current_rate: Optional[float] = None


class TokenBucket:
    """Token bucket rate limiter implementation."""
    
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.tokens = capacity
        self.refill_rate = refill_rate
        self.last_refill = time.time()
        self._lock = asyncio.Lock()
    
    async def consume(self, tokens: int = 1) -> bool:
        """Attempt to consume tokens from the bucket."""
        async with self._lock:
            now = time.time()
            # Add tokens based on elapsed time
            elapsed = now - self.last_refill
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            self.last_refill = now
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False
    
    async def get_wait_time(self, tokens: int = 1) -> float:
        """Get time to wait before tokens are available."""
        async with self._lock:
            if self.tokens >= tokens:
                return 0.0
            needed_tokens = tokens - self.tokens
            return needed_tokens / self.refill_rate


class SlidingWindowCounter:
    """Sliding window rate limiter implementation."""
    
    def __init__(self, window_size: int, max_requests: int):
        self.window_size = window_size
        self.max_requests = max_requests
        self.requests: deque = deque()
        self._lock = asyncio.Lock()
    
    async def is_allowed(self) -> tuple[bool, int]:
        """Check if request is allowed and return remaining count."""
        async with self._lock:
            now = time.time()
            while self.requests and self.requests[0] <= now - self.window_size:
                self.requests.popleft()
            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return True, self.max_requests - len(self.requests)
            return False, 0
    
    async def get_reset_time(self) -> datetime:
        """Get time when the window resets."""
        async with self._lock:
            if not self.requests:
                return datetime.now()
            oldest_request = self.requests[0]
            reset_time = oldest_request + self.window_size
            return datetime.fromtimestamp(reset_time)


class AdaptiveRateLimiter:
    """Adaptive rate limiter that adjusts based on success/failure rates."""
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.current_rate = config.requests_per_second
        self.success_count = 0
        self.failure_count = 0
        self.last_adjustment = time.time()
        self.adjustment_window = 60.0  # 1 minute
        self._lock = asyncio.Lock()
        self.token_bucket = TokenBucket(capacity=int(config.burst_capacity), refill_rate=self.current_rate)
    
    async def is_allowed(self) -> RateLimitResult:
        """Check if request is allowed with adaptive rate adjustment."""
        async with self._lock:
            await self._adjust_rate()
            self.token_bucket.refill_rate = self.current_rate
            allowed = await self.token_bucket.consume()
            if allowed:
                remaining = int(self.token_bucket.tokens)
                reset_time = datetime.now() + timedelta(seconds=1/self.current_rate)
                return RateLimitResult(allowed=True, remaining_requests=remaining, reset_time=reset_time, current_rate=self.current_rate)
            else:
                wait_time = await self.token_bucket.get_wait_time()
                return RateLimitResult(allowed=False, remaining_requests=0, reset_time=datetime.now() + timedelta(seconds=wait_time), retry_after=wait_time, current_rate=self.current_rate)
    
    async def record_success(self):
        """Record a successful request."""
        async with self._lock:
            self.success_count += 1
    
    async def record_failure(self):
        """Record a failed request."""
        async with self._lock:
            self.failure_count += 1
    
    async def _adjust_rate(self):
        """Adjust rate based on success/failure ratio."""
        now = time.time()
        if now - self.last_adjustment < self.adjustment_window:
            return
        total_requests = self.success_count + self.failure_count
        if total_requests == 0:
            return
        success_rate = self.success_count / total_requests
        if success_rate > 0.95:  # High success rate, increase rate
            self.current_rate = min(self.config.adaptive_max_rate, self.current_rate * self.config.adaptive_increase_factor)
        elif success_rate < 0.8:  # Low success rate, decrease rate
            self.current_rate = max(self.config.adaptive_min_rate, self.current_rate * self.config.adaptive_decrease_factor)
        self.success_count = 0
        self.failure_count = 0
        self.last_adjustment = now


class RateLimiter:
    """Main rate limiter with multiple strategies and Redis support."""
    
    def __init__(self, config: RateLimitConfig, redis_client: Optional[redis.Redis] = None):
        self.config = config
        self.redis_client = redis_client
        self.logger = logging.getLogger("rate_limiter")
        self.local_limiters: Dict[str, Any] = {}
        if config.strategy == RateLimitStrategy.TOKEN_BUCKET:
            self.token_bucket = TokenBucket(capacity=config.burst_capacity, refill_rate=config.requests_per_second)
        elif config.strategy == RateLimitStrategy.SLIDING_WINDOW:
            self.sliding_window = SlidingWindowCounter(window_size=60, max_requests=config.requests_per_minute)
        elif config.strategy == RateLimitStrategy.ADAPTIVE:
            self.adaptive_limiter = AdaptiveRateLimiter(config)
    
    async def is_allowed(self, key: str = "default") -> RateLimitResult:
        """Check if request is allowed for the given key."""
        if self.redis_client:
            return await self._check_redis_rate_limit(key)
        else:
            return await self._check_local_rate_limit(key)
    
    async def _check_local_rate_limit(self, key: str) -> RateLimitResult:
        """Check rate limit using local storage."""
        if self.config.strategy == RateLimitStrategy.TOKEN_BUCKET:
            allowed = await self.token_bucket.consume()
            if allowed:
                return RateLimitResult(allowed=True, remaining_requests=int(self.token_bucket.tokens), reset_time=datetime.now() + timedelta(seconds=1/self.config.requests_per_second))
            else:
                wait_time = await self.token_bucket.get_wait_time()
                return RateLimitResult(allowed=False, remaining_requests=0, reset_time=datetime.now() + timedelta(seconds=wait_time), retry_after=wait_time)
        elif self.config.strategy == RateLimitStrategy.SLIDING_WINDOW:
            allowed, remaining = await self.sliding_window.is_allowed()
            reset_time = await self.sliding_window.get_reset_time()
            if allowed:
                return RateLimitResult(allowed=True, remaining_requests=remaining, reset_time=reset_time)
            else:
                retry_after = (reset_time - datetime.now()).total_seconds()
                return RateLimitResult(allowed=False, remaining_requests=0, reset_time=reset_time, retry_after=max(0, retry_after))
        elif self.config.strategy == RateLimitStrategy.ADAPTIVE:
            return await self.adaptive_limiter.is_allowed()
        else:
            # Default to allowing request
            return RateLimitResult(allowed=True, remaining_requests=self.config.requests_per_minute, reset_time=datetime.now() + timedelta(minutes=1))
    
    async def _check_redis_rate_limit(self, key: str) -> RateLimitResult:
        """Check rate limit using Redis for distributed rate limiting."""
        if not self.redis_client:
            return await self._check_local_rate_limit(key)
        try:
            now = time.time()
            window_start = now - 60  # 1 minute window
            pipe = self.redis_client.pipeline()
            pipe.zremrangebyscore(f"rate_limit:{key}", 0, window_start)
            pipe.zcard(f"rate_limit:{key}")
            pipe.zadd(f"rate_limit:{key}", {str(now): now})
            pipe.expire(f"rate_limit:{key}", 60)
            results = await pipe.execute()
            current_count = results[1]
            if current_count < self.config.requests_per_minute:
                remaining = self.config.requests_per_minute - current_count - 1
                return RateLimitResult(allowed=True, remaining_requests=remaining, reset_time=datetime.now() + timedelta(minutes=1))
            else:
                oldest_entries = await self.redis_client.zrange(f"rate_limit:{key}", 0, 0, withscores=True)
                if oldest_entries:
                    oldest_time = oldest_entries[0][1]
                    reset_time = datetime.fromtimestamp(oldest_time + 60)
                    retry_after = (reset_time - datetime.now()).total_seconds()
                else:
                    reset_time = datetime.now() + timedelta(minutes=1)
                    retry_after = 60
                return RateLimitResult(allowed=False, remaining_requests=0, reset_time=reset_time, retry_after=max(0, retry_after))
        except Exception as e:
            self.logger.error(f"Redis rate limit check failed: {e}")
            # Fallback to local rate limiting
            return await self._check_local_rate_limit(key)
    
    async def record_success(self, key: str = "default"):
        """Record a successful request for adaptive rate limiting."""
        if self.config.strategy == RateLimitStrategy.ADAPTIVE:
            await self.adaptive_limiter.record_success()
    
    async def record_failure(self, key: str = "default"):
        """Record a failed request for adaptive rate limiting."""
        if self.config.strategy == RateLimitStrategy.ADAPTIVE:
            await self.adaptive_limiter.record_failure()
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics."""
        stats = {
            "strategy": self.config.strategy.value,
            "scope": self.config.scope.value,
            "requests_per_second": self.config.requests_per_second,
            "requests_per_minute": self.config.requests_per_minute,
            "burst_capacity": self.config.burst_capacity
        }
        if self.config.strategy == RateLimitStrategy.ADAPTIVE:
            stats["current_rate"] = self.adaptive_limiter.current_rate
            stats["success_count"] = self.adaptive_limiter.success_count
            stats["failure_count"] = self.adaptive_limiter.failure_count
        return stats


WHATSAPP_RATE_LIMIT = RateLimitConfig(
    requests_per_second=10.0,
    requests_per_minute=600,
    requests_per_hour=36000,
    burst_capacity=20,
    strategy=RateLimitStrategy.TOKEN_BUCKET,
    scope=RateLimitScope.GLOBAL
)

AIRTABLE_RATE_LIMIT = RateLimitConfig(
    requests_per_second=5.0,
    requests_per_minute=300,
    requests_per_hour=18000,
    burst_capacity=10,
    strategy=RateLimitStrategy.SLIDING_WINDOW,
    scope=RateLimitScope.GLOBAL
)

OPENAI_RATE_LIMIT = RateLimitConfig(
    requests_per_second=3.0,
    requests_per_minute=180,
    requests_per_hour=10800,
    burst_capacity=5,
    strategy=RateLimitStrategy.ADAPTIVE,
    scope=RateLimitScope.GLOBAL
)


class RateLimitMiddleware:
    """Middleware for applying rate limiting to API calls."""
    
    def __init__(self, rate_limiter: RateLimiter):
        self.rate_limiter = rate_limiter
        self.logger = logging.getLogger("rate_limit_middleware")
    
    async def __call__(self, request_func, *args, **kwargs):
        """Apply rate limiting to a request function."""
        key = kwargs.get('rate_limit_key', 'default')
        result = await self.rate_limiter.is_allowed(key)
        if not result.allowed:
            self.logger.warning(f"Rate limit exceeded for key: {key}")
            if result.retry_after:
                await asyncio.sleep(result.retry_after)
                result = await self.rate_limiter.is_allowed(key)
                if not result.allowed:
                    raise Exception(f"Rate limit exceeded. Retry after {result.retry_after} seconds")
        try:
            response = await request_func(*args, **kwargs)
            await self.rate_limiter.record_success(key)
            return response
        except Exception as e:
            await self.rate_limiter.record_failure(key)
            raise e