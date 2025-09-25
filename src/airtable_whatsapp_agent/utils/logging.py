"""
Logging utilities and configuration for the Airtable WhatsApp Agent.

This module provides structured logging, log formatting, and logging configuration
for different environments and components.
"""

import logging
import logging.handlers
import sys
import json
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path
import traceback
from enum import Enum


class LogLevel(Enum):
    """Log level enumeration."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class StructuredFormatter(logging.Formatter):
    """Structured JSON formatter for logs."""
    
    def __init__(self, include_extra: bool = True):
        super().__init__()
        self.include_extra = include_extra
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception information if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info)
            }
        
        # Add extra fields if enabled
        if self.include_extra:
            for key, value in record.__dict__.items():
                if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 
                              'pathname', 'filename', 'module', 'lineno', 
                              'funcName', 'created', 'msecs', 'relativeCreated', 
                              'thread', 'threadName', 'processName', 'process',
                              'getMessage', 'exc_info', 'exc_text', 'stack_info']:
                    log_data[key] = value
        
        return json.dumps(log_data, default=str)


class ColoredFormatter(logging.Formatter):
    """Colored formatter for console output."""
    
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors."""
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        
        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
        
        # Format the message
        formatted = f"{color}[{timestamp}] {record.levelname:8} {record.name}: {record.getMessage()}{reset}"
        
        # Add exception information if present
        if record.exc_info:
            formatted += f"\n{self.formatException(record.exc_info)}"
        
        return formatted


class LoggerManager:
    """Centralized logger management."""
    
    def __init__(self):
        self._loggers: Dict[str, logging.Logger] = {}
        self._configured = False
    
    def configure_logging(
        self,
        level: str = "INFO",
        format_type: str = "structured",
        log_file: Optional[str] = None,
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5
    ):
        """Configure global logging settings."""
        # Set root logger level
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, level.upper()))
        
        # Clear existing handlers
        root_logger.handlers.clear()
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        if format_type == "structured":
            console_handler.setFormatter(StructuredFormatter())
        else:
            console_handler.setFormatter(ColoredFormatter())
        root_logger.addHandler(console_handler)
        
        # File handler if specified
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=max_file_size,
                backupCount=backup_count
            )
            file_handler.setFormatter(StructuredFormatter())
            root_logger.addHandler(file_handler)
        
        self._configured = True
    
    def get_logger(self, name: str) -> logging.Logger:
        """Get or create a logger with the given name."""
        if name not in self._loggers:
            logger = logging.getLogger(name)
            self._loggers[name] = logger
        return self._loggers[name]
    
    def log_function_call(self, func_name: str, args: tuple, kwargs: dict, logger_name: str = None):
        """Log function call details."""
        logger = self.get_logger(logger_name or "function_calls")
        logger.debug(
            f"Function call: {func_name}",
            extra={
                "function": func_name,
                "args": args,
                "kwargs": kwargs,
                "call_type": "function_entry"
            }
        )
    
    def log_function_result(self, func_name: str, result: Any, execution_time: float, logger_name: str = None):
        """Log function result and execution time."""
        logger = self.get_logger(logger_name or "function_calls")
        logger.debug(
            f"Function result: {func_name}",
            extra={
                "function": func_name,
                "result": str(result)[:1000],  # Truncate long results
                "execution_time": execution_time,
                "call_type": "function_exit"
            }
        )
    
    def log_api_request(self, method: str, url: str, headers: dict, body: Any, logger_name: str = None):
        """Log API request details."""
        logger = self.get_logger(logger_name or "api_requests")
        logger.info(
            f"API Request: {method} {url}",
            extra={
                "method": method,
                "url": url,
                "headers": {k: v for k, v in headers.items() if k.lower() not in ['authorization', 'x-api-key']},
                "body_size": len(str(body)) if body else 0,
                "request_type": "outbound"
            }
        )
    
    def log_api_response(self, method: str, url: str, status_code: int, response_time: float, logger_name: str = None):
        """Log API response details."""
        logger = self.get_logger(logger_name or "api_requests")
        logger.info(
            f"API Response: {method} {url} - {status_code}",
            extra={
                "method": method,
                "url": url,
                "status_code": status_code,
                "response_time": response_time,
                "request_type": "outbound"
            }
        )


# Global logger manager instance
logger_manager = LoggerManager()

# Convenience functions
def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logger_manager.get_logger(name)

def configure_logging(**kwargs):
    """Configure global logging settings."""
    return logger_manager.configure_logging(**kwargs)

def log_function_call(func_name: str, args: tuple, kwargs: dict, logger_name: str = None):
    """Log function call details."""
    return logger_manager.log_function_call(func_name, args, kwargs, logger_name)

def log_function_result(func_name: str, result: Any, execution_time: float, logger_name: str = None):
    """Log function result and execution time."""
    return logger_manager.log_function_result(func_name, result, execution_time, logger_name)

def log_api_request(method: str, url: str, headers: dict, body: Any, logger_name: str = None):
    """Log API request details."""
    return logger_manager.log_api_request(method, url, headers, body, logger_name)

def log_api_response(method: str, url: str, status_code: int, response_time: float, logger_name: str = None):
    """Log API response details."""
    return logger_manager.log_api_response(method, url, status_code, response_time, logger_name)