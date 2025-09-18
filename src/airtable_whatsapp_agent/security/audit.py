"""
Audit logging system for tracking security events and user actions.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from enum import Enum
from pathlib import Path
import asyncio
from dataclasses import dataclass, asdict
from .encryption import EncryptionService


logger = logging.getLogger(__name__)


class AuditEventType(Enum):
    """Types of audit events."""
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    SESSION_EXPIRED = "session_expired"
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    PERMISSION_CHANGED = "permission_changed"
    DATA_READ = "data_read"
    DATA_WRITE = "data_write"
    DATA_DELETE = "data_delete"
    DATA_EXPORT = "data_export"
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"
    CONFIG_CHANGE = "config_change"
    ERROR_OCCURRED = "error_occurred"
    MESSAGE_RECEIVED = "message_received"
    MESSAGE_SENT = "message_sent"
    WEBHOOK_RECEIVED = "webhook_received"
    ADMIN_ACTION = "admin_action"
    WHITELIST_MODIFIED = "whitelist_modified"
    CREDENTIAL_ACCESSED = "credential_accessed"
    CREDENTIAL_MODIFIED = "credential_modified"


class AuditSeverity(Enum):
    """Severity levels for audit events."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Audit event data structure."""
    
    event_id: str
    event_type: AuditEventType
    severity: AuditSeverity
    timestamp: datetime
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    source_ip: Optional[str] = None
    user_agent: Optional[str] = None
    resource: Optional[str] = None
    action: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    success: bool = True
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data["event_type"] = self.event_type.value
        data["severity"] = self.severity.value
        data["timestamp"] = self.timestamp.isoformat()
        return data
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AuditEvent':
        """Create from dictionary."""
        data["event_type"] = AuditEventType(data["event_type"])
        data["severity"] = AuditSeverity(data["severity"])
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


class AuditStorage:
    """Storage backend for audit logs."""
    
    def __init__(self, storage_path: str, encryption_service: Optional[EncryptionService] = None):
        """Initialize audit storage."""
        self.storage_path = Path(storage_path)
        self.encryption_service = encryption_service
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
    async def store_event(self, event: AuditEvent) -> bool:
        """Store audit event."""
        try:
            log_entry = {"timestamp": datetime.utcnow().isoformat(), "event": event.to_dict()}
            json_data = json.dumps(log_entry, separators=(',', ':'))
            if self.encryption_service:
                json_data = self.encryption_service.encrypt(json_data)
            with open(self.storage_path, 'a', encoding='utf-8') as f:
                f.write(json_data + '\n')
            return True
        except Exception as e:
            logger.error(f"Error storing audit event: {str(e)}")
            return False
            
    async def retrieve_events(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_types: Optional[List[AuditEventType]] = None,
        user_id: Optional[str] = None,
        severity: Optional[AuditSeverity] = None,
        limit: int = 1000
    ) -> List[AuditEvent]:
        """Retrieve audit events with filtering."""
        events = []
        try:
            if not self.storage_path.exists():
                return events
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        if self.encryption_service:
                            line = self.encryption_service.decrypt(line)
                        log_entry = json.loads(line)
                        event = AuditEvent.from_dict(log_entry["event"])
                        if start_time and event.timestamp < start_time:
                            continue
                        if end_time and event.timestamp > end_time:
                            continue
                        if event_types and event.event_type not in event_types:
                            continue
                        if user_id and event.user_id != user_id:
                            continue
                        if severity and event.severity != severity:
                            continue
                        events.append(event)
                        if len(events) >= limit:
                            break
                    except Exception as e:
                        logger.warning(f"Error parsing audit log line: {str(e)}")
                        continue 
        except Exception as e:
            logger.error(f"Error retrieving audit events: {str(e)}")
        return events
        
    async def cleanup_old_events(self, days_to_keep: int = 90) -> int:
        """Remove old audit events."""
        if not self.storage_path.exists():
            return 0
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        kept_events = []
        removed_count = 0
        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        if self.encryption_service:
                            decrypted_line = self.encryption_service.decrypt(line)
                        else:
                            decrypted_line = line
                        log_entry = json.loads(decrypted_line)
                        event_time = datetime.fromisoformat(log_entry["event"]["timestamp"])
                        if event_time >= cutoff_date:
                            kept_events.append(line)
                        else:
                            removed_count += 1
                    except Exception as e:
                        logger.warning(f"Error processing audit log line during cleanup: {str(e)}")
                        kept_events.append(line) # Keep the line if we can't parse it
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                for line in kept_events:
                    f.write(line + '\n')
        except Exception as e:
            logger.error(f"Error during audit log cleanup: {str(e)}")
            return 0
        return removed_count


class AuditLogger:
    """High-level audit logging interface."""
    
    def __init__(self, storage_path: str = "audit.log", encryption_service: Optional[EncryptionService] = None, enable_console_logging: bool = True):
        """Initialize audit logger."""
        self.storage = AuditStorage(storage_path, encryption_service)
        self.enable_console_logging = enable_console_logging
        self._event_queue = asyncio.Queue()
        self._processing_task = None
        self._is_running = False
        
    async def start(self):
        """Start audit logger background processing."""
        if not self._is_running:
            self._is_running = True
            self._processing_task = asyncio.create_task(self._process_events())
            
    async def stop(self):
        """Stop audit logger background processing."""
        self._is_running = False
        if self._processing_task:
            await self._processing_task
            
    async def _process_events(self):
        """Background task to process audit events."""
        while self._is_running:
            try:
                event = await asyncio.wait_for(self._event_queue.get(), timeout=1.0)
                await self.storage.store_event(event)
                if self.enable_console_logging:
                    self._log_to_console(event)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error processing audit event: {str(e)}")
                
    def _log_to_console(self, event: AuditEvent):
        """Log event to console."""
        log_level = {
            AuditSeverity.LOW: logging.INFO,
            AuditSeverity.MEDIUM: logging.WARNING,
            AuditSeverity.HIGH: logging.ERROR,
            AuditSeverity.CRITICAL: logging.CRITICAL
        }.get(event.severity, logging.INFO)
        message = f"AUDIT: {event.event_type.value} - {event.action or 'N/A'}"
        if event.user_id:
            message += f" (User: {event.user_id})"
        if event.resource:
            message += f" (Resource: {event.resource})"
        if not event.success and event.error_message:
            message += f" (Error: {event.error_message})"
        logger.log(log_level, message)
        
    async def log_event(
        self,
        event_type: AuditEventType,
        severity: AuditSeverity = AuditSeverity.LOW,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        source_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        resource: Optional[str] = None,
        action: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ):
        """Log an audit event."""
        import uuid
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            severity=severity,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            session_id=session_id,
            source_ip=source_ip,
            user_agent=user_agent,
            resource=resource,
            action=action,
            details=details,
            success=success,
            error_message=error_message
        )
        try:
            await self._event_queue.put(event)
        except Exception as e:
            logger.error(f"Error queuing audit event: {str(e)}")

    async def log_login(self, user_id: str, success: bool, source_ip: str = None, error_message: str = None):
        """Log login attempt."""
        await self.log_event(
            event_type=AuditEventType.LOGIN_SUCCESS if success else AuditEventType.LOGIN_FAILURE,
            severity=AuditSeverity.MEDIUM if not success else AuditSeverity.LOW,
            user_id=user_id,
            source_ip=source_ip,
            action="login",
            success=success,
            error_message=error_message
        )
        
    async def log_access(self, user_id: str, resource: str, action: str, success: bool, error_message: str = None):
        """Log resource access."""
        await self.log_event(
            event_type=AuditEventType.ACCESS_GRANTED if success else AuditEventType.ACCESS_DENIED,
            severity=AuditSeverity.MEDIUM if not success else AuditSeverity.LOW,
            user_id=user_id,
            resource=resource,
            action=action,
            success=success,
            error_message=error_message
        )
        
    async def log_data_operation(self, user_id: str, operation: str, resource: str, details: Dict[str, Any] = None):
        """Log data operation."""
        event_type_map = {
            "read": AuditEventType.DATA_READ,
            "write": AuditEventType.DATA_WRITE,
            "delete": AuditEventType.DATA_DELETE,
            "export": AuditEventType.DATA_EXPORT
        }
        
        await self.log_event(
            event_type=event_type_map.get(operation, AuditEventType.DATA_READ),
            severity=AuditSeverity.MEDIUM if operation in ["delete", "export"] else AuditSeverity.LOW,
            user_id=user_id,
            resource=resource,
            action=operation,
            details=details
        )
        
    async def log_admin_action(self, admin_id: str, action: str, target: str = None, details: Dict[str, Any] = None):
        """Log admin action."""
        await self.log_event(
            event_type=AuditEventType.ADMIN_ACTION,
            severity=AuditSeverity.HIGH,
            user_id=admin_id,
            resource=target,
            action=action,
            details=details
        )
        
    async def log_error(self, error_message: str, user_id: str = None, details: Dict[str, Any] = None):
        """Log system error."""
        await self.log_event(
            event_type=AuditEventType.ERROR_OCCURRED,
            severity=AuditSeverity.HIGH,
            user_id=user_id,
            action="system_error",
            error_message=error_message,
            details=details,
            success=False
        )
        
    async def get_events(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_types: Optional[List[AuditEventType]] = None,
        user_id: Optional[str] = None,
        severity: Optional[AuditSeverity] = None,
        limit: int = 1000
    ) -> List[AuditEvent]:
        """Retrieve audit events."""
        return await self.storage.retrieve_events(
            start_time=start_time,
            end_time=end_time,
            event_types=event_types,
            user_id=user_id,
            severity=severity,
            limit=limit
        )
        
    async def cleanup_old_events(self, days_to_keep: int = 90) -> int:
        """Clean up old audit events."""
        return await self.storage.cleanup_old_events(days_to_keep)
        
    async def get_statistics(self) -> Dict[str, Any]:
        """Get audit log statistics."""
        start_time = datetime.utcnow() - timedelta(days=30) # Get events from last 30 days
        events = await self.get_events(start_time=start_time, limit=10000)
        stats = {
            "total_events_30_days": len(events),
            "events_by_type": {},
            "events_by_severity": {},
            "unique_users": set(),
            "failed_events": 0
        }
        for event in events:
            event_type = event.event_type.value
            stats["events_by_type"][event_type] = stats["events_by_type"].get(event_type, 0) + 1
            severity = event.severity.value
            stats["events_by_severity"][severity] = stats["events_by_severity"].get(severity, 0) + 1
            if event.user_id:
                stats["unique_users"].add(event.user_id)
            if not event.success:
                stats["failed_events"] += 1
        stats["unique_users"] = len(stats["unique_users"])
        return stats