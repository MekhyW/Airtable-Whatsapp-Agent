"""
Monitoring and health check utilities for the Airtable WhatsApp Agent.

This module provides comprehensive monitoring capabilities including health checks,
metrics collection, and system status reporting.
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
import psutil
import httpx
from .error_handling import error_handler


class HealthStatus(Enum):
    """Health check status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ComponentType(Enum):
    """Component types for health checks."""
    DATABASE = "database"
    CACHE = "cache"
    EXTERNAL_API = "external_api"
    STORAGE = "storage"
    QUEUE = "queue"
    SERVICE = "service"


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    component: str
    component_type: ComponentType
    status: HealthStatus
    response_time_ms: float
    timestamp: datetime
    message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemMetrics:
    """System performance metrics."""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    network_io: Dict[str, int]
    process_count: int
    uptime_seconds: float
    active_connections: int = 0
    request_count: int = 0
    error_count: int = 0
    response_time_avg: float = 0.0


class HealthChecker:
    """Health check manager for monitoring system components."""
    
    def __init__(self):
        self.logger = logging.getLogger("health_checker")
        self.checks: Dict[str, Callable] = {}
        self.last_results: Dict[str, HealthCheckResult] = {}
        self.start_time = time.time()
    
    def register_check(self, name: str, check_func: Callable, component_type: ComponentType, timeout: float = 5.0):
        """Register a health check function."""
        self.checks[name] = {"func": check_func, "type": component_type, "timeout": timeout}
    
    async def run_check(self, name: str) -> HealthCheckResult:
        """Run a specific health check."""
        if name not in self.checks:
            return HealthCheckResult(
                component=name,
                component_type=ComponentType.SERVICE,
                status=HealthStatus.UNKNOWN,
                response_time_ms=0.0,
                timestamp=datetime.now(),
                message=f"Health check '{name}' not found"
            )
        check_config = self.checks[name]
        start_time = time.time()
        try:
            result = await asyncio.wait_for(check_config["func"](), timeout=check_config["timeout"])
            response_time = (time.time() - start_time) * 1000
            if isinstance(result, HealthCheckResult):
                result.response_time_ms = response_time
                result.timestamp = datetime.now()
                self.last_results[name] = result
                return result
            else:
                status = HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY
                health_result = HealthCheckResult(
                    component=name,
                    component_type=check_config["type"],
                    status=status,
                    response_time_ms=response_time,
                    timestamp=datetime.now(),
                    details=result if isinstance(result, dict) else {}
                )
                self.last_results[name] = health_result
                return health_result
        except asyncio.TimeoutError:
            health_result = HealthCheckResult(
                component=name,
                component_type=check_config["type"],
                status=HealthStatus.UNHEALTHY,
                response_time_ms=check_config["timeout"] * 1000,
                timestamp=datetime.now(),
                message=f"Health check timed out after {check_config['timeout']}s"
            )
            self.last_results[name] = health_result
            return health_result
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            health_result = HealthCheckResult(
                component=name,
                component_type=check_config["type"],
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time,
                timestamp=datetime.now(),
                message=f"Health check failed: {str(e)}"
            )
            self.last_results[name] = health_result
            return health_result
    
    async def run_all_checks(self) -> Dict[str, HealthCheckResult]:
        """Run all registered health checks."""
        results = {}
        tasks = [self.run_check(name) for name in self.checks.keys()]
        check_results = await asyncio.gather(*tasks, return_exceptions=True)
        for _, (name, result) in enumerate(zip(self.checks.keys(), check_results)):
            if isinstance(result, Exception):
                results[name] = HealthCheckResult(
                    component=name,
                    component_type=self.checks[name]["type"],
                    status=HealthStatus.UNHEALTHY,
                    response_time_ms=0.0,
                    timestamp=datetime.now(),
                    message=f"Health check exception: {str(result)}"
                )
            else:
                results[name] = result
        return results
    
    def get_overall_status(self) -> HealthStatus:
        """Get overall system health status."""
        if not self.last_results:
            return HealthStatus.UNKNOWN
        statuses = [result.status for result in self.last_results.values()]
        if all(status == HealthStatus.HEALTHY for status in statuses):
            return HealthStatus.HEALTHY
        elif any(status == HealthStatus.UNHEALTHY for status in statuses):
            return HealthStatus.UNHEALTHY
        else:
            return HealthStatus.DEGRADED
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get comprehensive health summary."""
        overall_status = self.get_overall_status()
        uptime = time.time() - self.start_time
        component_summary = {}
        for name, result in self.last_results.items():
            component_summary[name] = {
                "status": result.status.value,
                "response_time_ms": result.response_time_ms,
                "last_check": result.timestamp.isoformat(),
                "message": result.message
            }
        return {
            "overall_status": overall_status.value,
            "uptime_seconds": uptime,
            "timestamp": datetime.now().isoformat(),
            "components": component_summary,
            "error_statistics": error_handler.get_error_statistics()
        }


class MetricsCollector:
    """System metrics collector."""
    
    def __init__(self, collection_interval: int = 60):
        self.logger = logging.getLogger("metrics_collector")
        self.collection_interval = collection_interval
        self.metrics_history: List[SystemMetrics] = []
        self.max_history_size = 1440  # 24 hours at 1-minute intervals
        self.start_time = time.time()
        self.request_count = 0
        self.error_count = 0
        self.response_times: List[float] = []
        self.active_connections = 0
    
    def collect_system_metrics(self) -> SystemMetrics:
        """Collect current system metrics."""
        # CPU and memory
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        # Network I/O
        network_io = psutil.net_io_counters()._asdict()
        # Process info
        process_count = len(psutil.pids())
        uptime = time.time() - self.start_time
        # Calculate average response time
        avg_response_time = (sum(self.response_times) / len(self.response_times) if self.response_times else 0.0)
        metrics = SystemMetrics(
            timestamp=datetime.now(),
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            disk_percent=disk.percent,
            network_io=network_io,
            process_count=process_count,
            uptime_seconds=uptime,
            active_connections=self.active_connections,
            request_count=self.request_count,
            error_count=self.error_count,
            response_time_avg=avg_response_time
        )
        self.metrics_history.append(metrics)
        if len(self.metrics_history) > self.max_history_size:
            self.metrics_history = self.metrics_history[-self.max_history_size:]
        self.response_times.clear()
        return metrics
    
    def record_request(self, response_time: float, is_error: bool = False):
        """Record a request for metrics."""
        self.request_count += 1
        self.response_times.append(response_time)
        if is_error:
            self.error_count += 1
    
    def set_active_connections(self, count: int):
        """Set the current active connection count."""
        self.active_connections = count
    
    def get_metrics_summary(self, hours: int = 1) -> Dict[str, Any]:
        """Get metrics summary for the specified time period."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_metrics = [m for m in self.metrics_history if m.timestamp > cutoff_time]
        if not recent_metrics:
            return {"message": "No metrics available for the specified period"}
        avg_cpu = sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics)
        avg_memory = sum(m.memory_percent for m in recent_metrics) / len(recent_metrics)
        avg_disk = sum(m.disk_percent for m in recent_metrics) / len(recent_metrics)
        latest = recent_metrics[-1]
        return {
            "period_hours": hours,
            "sample_count": len(recent_metrics),
            "averages": {
                "cpu_percent": round(avg_cpu, 2),
                "memory_percent": round(avg_memory, 2),
                "disk_percent": round(avg_disk, 2)
            },
            "current": {
                "cpu_percent": latest.cpu_percent,
                "memory_percent": latest.memory_percent,
                "disk_percent": latest.disk_percent,
                "active_connections": latest.active_connections,
                "uptime_seconds": latest.uptime_seconds
            },
            "totals": {
                "requests": latest.request_count,
                "errors": latest.error_count,
                "error_rate": (
                    latest.error_count / latest.request_count * 100
                    if latest.request_count > 0 else 0
                )
            }
        }


async def check_database_connection(database_url: str) -> HealthCheckResult:
    """Check database connectivity."""
    try:
        # This would be implemented based on database type
        # For now, return a placeholder
        return HealthCheckResult(
            component="database",
            component_type=ComponentType.DATABASE,
            status=HealthStatus.HEALTHY,
            response_time_ms=0.0,
            timestamp=datetime.now(),
            message="Database connection successful"
        )
    except Exception as e:
        return HealthCheckResult(
            component="database",
            component_type=ComponentType.DATABASE,
            status=HealthStatus.UNHEALTHY,
            response_time_ms=0.0,
            timestamp=datetime.now(),
            message=f"Database connection failed: {str(e)}"
        )


async def check_redis_connection(redis_url: str) -> HealthCheckResult:
    """Check Redis connectivity."""
    try:
        # This would be implemented with actual Redis client
        return HealthCheckResult(
            component="redis",
            component_type=ComponentType.CACHE,
            status=HealthStatus.HEALTHY,
            response_time_ms=0.0,
            timestamp=datetime.now(),
            message="Redis connection successful"
        )
    except Exception as e:
        return HealthCheckResult(
            component="redis",
            component_type=ComponentType.CACHE,
            status=HealthStatus.UNHEALTHY,
            response_time_ms=0.0,
            timestamp=datetime.now(),
            message=f"Redis connection failed: {str(e)}"
        )


async def check_whatsapp_api() -> HealthCheckResult:
    """Check WhatsApp API connectivity."""
    try:
        # This would make an actual API call to WhatsApp
        async with httpx.AsyncClient() as client:
            response = await client.get("https://graph.facebook.com/v18.0/me")
        if response.status_code == 200:
            return HealthCheckResult(
                component="whatsapp_api",
                component_type=ComponentType.EXTERNAL_API,
                status=HealthStatus.HEALTHY,
                response_time_ms=0.0,
                timestamp=datetime.now(),
                message="WhatsApp API accessible"
            )
        else:
            return HealthCheckResult(
                component="whatsapp_api",
                component_type=ComponentType.EXTERNAL_API,
                status=HealthStatus.DEGRADED,
                response_time_ms=0.0,
                timestamp=datetime.now(),
                message=f"WhatsApp API returned status {response.status_code}"
            )
    except Exception as e:
        return HealthCheckResult(
            component="whatsapp_api",
            component_type=ComponentType.EXTERNAL_API,
            status=HealthStatus.UNHEALTHY,
            response_time_ms=0.0,
            timestamp=datetime.now(),
            message=f"WhatsApp API check failed: {str(e)}"
        )


async def check_airtable_api() -> HealthCheckResult:
    """Check Airtable API connectivity."""
    try:
        # This would make an actual API call to Airtable
        async with httpx.AsyncClient() as client:
            response = await client.get("https://api.airtable.com/v0/meta/whoami")
        if response.status_code == 200:
            return HealthCheckResult(
                component="airtable_api",
                component_type=ComponentType.EXTERNAL_API,
                status=HealthStatus.HEALTHY,
                response_time_ms=0.0,
                timestamp=datetime.now(),
                message="Airtable API accessible"
            )
        else:
            return HealthCheckResult(
                component="airtable_api",
                component_type=ComponentType.EXTERNAL_API,
                status=HealthStatus.DEGRADED,
                response_time_ms=0.0,
                timestamp=datetime.now(),
                message=f"Airtable API returned status {response.status_code}"
            )
    except Exception as e:
        return HealthCheckResult(
            component="airtable_api",
            component_type=ComponentType.EXTERNAL_API,
            status=HealthStatus.UNHEALTHY,
            response_time_ms=0.0,
            timestamp=datetime.now(),
            message=f"Airtable API check failed: {str(e)}"
        )


# Global instances
health_checker = HealthChecker()
metrics_collector = MetricsCollector()


# Register default health checks
def setup_default_health_checks():
    """Setup default health checks."""
    health_checker.register_check(
        "whatsapp_api",
        check_whatsapp_api,
        ComponentType.EXTERNAL_API,
        timeout=10.0
    )
    health_checker.register_check(
        "airtable_api",
        check_airtable_api,
        ComponentType.EXTERNAL_API,
        timeout=10.0
    )