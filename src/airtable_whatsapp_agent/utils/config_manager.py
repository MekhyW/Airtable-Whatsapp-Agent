"""
Configuration management for the Airtable WhatsApp Agent.

This module provides centralized configuration management with environment variable
support, validation, and type conversion.
"""

import os
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import yaml


class Environment(Enum):
    """Application environments."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class LogLevel(Enum):
    """Logging levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class DatabaseConfig:
    """Database configuration."""
    url: str = ""
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600
    echo: bool = False


@dataclass
class RedisConfig:
    """Redis configuration."""
    url: str = "redis://localhost:6379/0"
    max_connections: int = 10
    socket_timeout: int = 5
    socket_connect_timeout: int = 5
    retry_on_timeout: bool = True
    health_check_interval: int = 30


@dataclass
class WhatsAppConfig:
    """WhatsApp API configuration."""
    access_token: str = ""
    phone_number_id: str = ""
    business_account_id: str = ""
    webhook_verify_token: str = ""
    api_version: str = "v18.0"
    base_url: str = "https://graph.facebook.com"
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    rate_limit_requests: int = 1000
    rate_limit_window: int = 3600


@dataclass
class AirtableConfig:
    """Airtable API configuration."""
    api_key: str = ""
    base_id: str = ""
    table_name: str = ""
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    rate_limit_requests: int = 5
    rate_limit_window: int = 1


@dataclass
class SecurityConfig:
    """Security configuration."""
    secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    password_min_length: int = 8
    max_login_attempts: int = 5
    lockout_duration_minutes: int = 15
    cors_origins: List[str] = field(default_factory=lambda: ["*"])
    allowed_hosts: List[str] = field(default_factory=lambda: ["*"])


@dataclass
class MonitoringConfig:
    """Monitoring and observability configuration."""
    enable_metrics: bool = True
    metrics_port: int = 9090
    health_check_interval: int = 60
    log_level: LogLevel = LogLevel.INFO
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_file: Optional[str] = None
    max_log_file_size: int = 10 * 1024 * 1024  # 10MB
    log_backup_count: int = 5
    enable_tracing: bool = False
    jaeger_endpoint: Optional[str] = None


@dataclass
class ServerConfig:
    """Server configuration."""
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    worker_class: str = "uvicorn.workers.UvicornWorker"
    max_requests: int = 1000
    max_requests_jitter: int = 100
    timeout: int = 30
    keepalive: int = 2
    reload: bool = False
    debug: bool = False


@dataclass
class AppConfig:
    """Main application configuration."""
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False
    testing: bool = False
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    whatsapp: WhatsAppConfig = field(default_factory=WhatsAppConfig)
    airtable: AirtableConfig = field(default_factory=AirtableConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    timezone: str = "UTC"
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    temp_dir: str = "/tmp"
    data_dir: str = "./data"


class ConfigManager:
    """Configuration manager with environment variable support."""
    
    def __init__(self, config_file: Optional[str] = None):
        self.logger = logging.getLogger("config_manager")
        self.config_file = config_file
        self._config: Optional[AppConfig] = None
        self._env_prefix = "AIRTABLE_WHATSAPP_"
    
    def load_config(self) -> AppConfig:
        """Load configuration from file and environment variables."""
        if self._config is not None:
            return self._config
        config_dict = {}
        if self.config_file and os.path.exists(self.config_file):
            config_dict = self._load_config_file(self.config_file)
        env_config = self._load_from_env()
        config_dict = self._deep_merge(config_dict, env_config)
        self._config = self._dict_to_config(config_dict)
        self._validate_config(self._config)
        return self._config
    
    def _load_config_file(self, file_path: str) -> Dict[str, Any]:
        """Load configuration from file."""
        file_path = Path(file_path)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                if file_path.suffix.lower() in ['.yml', '.yaml']:
                    return yaml.safe_load(f) or {}
                elif file_path.suffix.lower() == '.json':
                    return json.load(f)
                else:
                    raise ValueError(f"Unsupported config file format: {file_path.suffix}")
        except Exception as e:
            self.logger.error(f"Failed to load config file {file_path}: {e}")
            return {}
    
    def _load_from_env(self) -> Dict[str, Any]:
        """Load configuration from environment variables."""
        config = {}
        if env_val := os.getenv(f"{self._env_prefix}ENVIRONMENT"):
            config["environment"] = env_val
        if env_val := os.getenv(f"{self._env_prefix}DEBUG"):
            config["debug"] = env_val.lower() in ("true", "1", "yes", "on")
        database_config = {}
        if env_val := os.getenv(f"{self._env_prefix}DATABASE_URL"):
            database_config["url"] = env_val
        if env_val := os.getenv(f"{self._env_prefix}DATABASE_POOL_SIZE"):
            database_config["pool_size"] = int(env_val)
        if database_config:
            config["database"] = database_config
        # Redis
        redis_config = {}
        if env_val := os.getenv(f"{self._env_prefix}REDIS_URL"):
            redis_config["url"] = env_val
        if env_val := os.getenv(f"{self._env_prefix}REDIS_MAX_CONNECTIONS"):
            redis_config["max_connections"] = int(env_val)
        if redis_config:
            config["redis"] = redis_config
        # WhatsApp
        whatsapp_config = {}
        if env_val := os.getenv(f"{self._env_prefix}WHATSAPP_ACCESS_TOKEN"):
            whatsapp_config["access_token"] = env_val
        if env_val := os.getenv(f"{self._env_prefix}WHATSAPP_PHONE_NUMBER_ID"):
            whatsapp_config["phone_number_id"] = env_val
        if env_val := os.getenv(f"{self._env_prefix}WHATSAPP_BUSINESS_ACCOUNT_ID"):
            whatsapp_config["business_account_id"] = env_val
        if env_val := os.getenv(f"{self._env_prefix}WHATSAPP_WEBHOOK_VERIFY_TOKEN"):
            whatsapp_config["webhook_verify_token"] = env_val
        if whatsapp_config:
            config["whatsapp"] = whatsapp_config
        # Airtable
        airtable_config = {}
        if env_val := os.getenv(f"{self._env_prefix}AIRTABLE_API_KEY"):
            airtable_config["api_key"] = env_val
        if env_val := os.getenv(f"{self._env_prefix}AIRTABLE_BASE_ID"):
            airtable_config["base_id"] = env_val
        if env_val := os.getenv(f"{self._env_prefix}AIRTABLE_TABLE_NAME"):
            airtable_config["table_name"] = env_val
        if airtable_config:
            config["airtable"] = airtable_config
        # Security
        security_config = {}
        if env_val := os.getenv(f"{self._env_prefix}SECRET_KEY"):
            security_config["secret_key"] = env_val
        if env_val := os.getenv(f"{self._env_prefix}JWT_ALGORITHM"):
            security_config["jwt_algorithm"] = env_val
        if security_config:
            config["security"] = security_config
        # Server
        server_config = {}
        if env_val := os.getenv(f"{self._env_prefix}SERVER_HOST"):
            server_config["host"] = env_val
        if env_val := os.getenv(f"{self._env_prefix}SERVER_PORT"):
            server_config["port"] = int(env_val)
        if env_val := os.getenv(f"{self._env_prefix}SERVER_WORKERS"):
            server_config["workers"] = int(env_val)
        if server_config:
            config["server"] = server_config
        # Monitoring
        monitoring_config = {}
        if env_val := os.getenv(f"{self._env_prefix}LOG_LEVEL"):
            monitoring_config["log_level"] = LogLevel(env_val.upper())
        if env_val := os.getenv(f"{self._env_prefix}LOG_FILE"):
            monitoring_config["log_file"] = env_val
        if env_val := os.getenv(f"{self._env_prefix}ENABLE_METRICS"):
            monitoring_config["enable_metrics"] = env_val.lower() in ("true", "1", "yes", "on")
        if monitoring_config:
            config["monitoring"] = monitoring_config
        return config
    
    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result
    
    def _dict_to_config(self, config_dict: Dict[str, Any]) -> AppConfig:
        """Convert dictionary to AppConfig object."""
        # Handle environment enum
        if "environment" in config_dict:
            if isinstance(config_dict["environment"], str):
                config_dict["environment"] = Environment(config_dict["environment"])
        # Handle log level enum
        if "monitoring" in config_dict and "log_level" in config_dict["monitoring"]:
            if isinstance(config_dict["monitoring"]["log_level"], str):
                config_dict["monitoring"]["log_level"] = LogLevel(config_dict["monitoring"]["log_level"].upper())
        # Create nested config objects
        if "database" in config_dict:
            config_dict["database"] = DatabaseConfig(**config_dict["database"])
        if "redis" in config_dict:
            config_dict["redis"] = RedisConfig(**config_dict["redis"])
        if "whatsapp" in config_dict:
            config_dict["whatsapp"] = WhatsAppConfig(**config_dict["whatsapp"])
        if "airtable" in config_dict:
            config_dict["airtable"] = AirtableConfig(**config_dict["airtable"])
        if "security" in config_dict:
            config_dict["security"] = SecurityConfig(**config_dict["security"])
        if "monitoring" in config_dict:
            config_dict["monitoring"] = MonitoringConfig(**config_dict["monitoring"])
        if "server" in config_dict:
            config_dict["server"] = ServerConfig(**config_dict["server"])
        return AppConfig(**config_dict)
    
    def _validate_config(self, config: AppConfig):
        """Validate configuration."""
        errors = []
        if config.environment == Environment.PRODUCTION:
            if not config.whatsapp.access_token:
                errors.append("WhatsApp access token is required in production")
            if not config.airtable.api_key:
                errors.append("Airtable API key is required in production")
            if not config.security.secret_key:
                errors.append("Secret key is required in production")
            if config.debug:
                errors.append("Debug mode should be disabled in production")
        if not (1 <= config.server.port <= 65535):
            errors.append(f"Invalid server port: {config.server.port}")
        if not (1 <= config.monitoring.metrics_port <= 65535):
            errors.append(f"Invalid metrics port: {config.monitoring.metrics_port}")
        if config.server.workers < 1:
            errors.append("Server workers must be at least 1")
        if config.whatsapp.timeout <= 0:
            errors.append("WhatsApp timeout must be positive")
        if config.airtable.timeout <= 0:
            errors.append("Airtable timeout must be positive")
        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(f"- {error}" for error in errors)
            raise ValueError(error_msg)
    
    def get_config(self) -> AppConfig:
        """Get the current configuration."""
        if self._config is None:
            return self.load_config()
        return self._config
    
    def reload_config(self) -> AppConfig:
        """Reload configuration from sources."""
        self._config = None
        return self.load_config()
    
    def save_config(self, file_path: str, format: str = "yaml"):
        """Save current configuration to file."""
        if self._config is None:
            raise ValueError("No configuration loaded")
        config_dict = self._config_to_dict(self._config)
        with open(file_path, 'w', encoding='utf-8') as f:
            if format.lower() in ['yml', 'yaml']:
                yaml.dump(config_dict, f, default_flow_style=False, indent=2)
            elif format.lower() == 'json':
                json.dump(config_dict, f, indent=2, default=str)
            else:
                raise ValueError(f"Unsupported format: {format}")
    
    def _config_to_dict(self, config: AppConfig) -> Dict[str, Any]:
        """Convert AppConfig to dictionary."""
        result = {}
        result["environment"] = config.environment.value
        result["debug"] = config.debug
        result["testing"] = config.testing
        result["timezone"] = config.timezone
        result["max_file_size"] = config.max_file_size
        result["temp_dir"] = config.temp_dir
        result["data_dir"] = config.data_dir
        result["database"] = {
            "url": config.database.url,
            "pool_size": config.database.pool_size,
            "max_overflow": config.database.max_overflow,
            "pool_timeout": config.database.pool_timeout,
            "pool_recycle": config.database.pool_recycle,
            "echo": config.database.echo
        }
        result["redis"] = {
            "url": config.redis.url,
            "max_connections": config.redis.max_connections,
            "socket_timeout": config.redis.socket_timeout,
            "socket_connect_timeout": config.redis.socket_connect_timeout,
            "retry_on_timeout": config.redis.retry_on_timeout,
            "health_check_interval": config.redis.health_check_interval
        }
        result["whatsapp"] = {
            "access_token": config.whatsapp.access_token,
            "phone_number_id": config.whatsapp.phone_number_id,
            "business_account_id": config.whatsapp.business_account_id,
            "webhook_verify_token": config.whatsapp.webhook_verify_token,
            "api_version": config.whatsapp.api_version,
            "base_url": config.whatsapp.base_url,
            "timeout": config.whatsapp.timeout,
            "max_retries": config.whatsapp.max_retries,
            "retry_delay": config.whatsapp.retry_delay,
            "rate_limit_requests": config.whatsapp.rate_limit_requests,
            "rate_limit_window": config.whatsapp.rate_limit_window
        }
        result["airtable"] = {
            "api_key": config.airtable.api_key,
            "base_id": config.airtable.base_id,
            "table_name": config.airtable.table_name,
            "timeout": config.airtable.timeout,
            "max_retries": config.airtable.max_retries,
            "retry_delay": config.airtable.retry_delay,
            "rate_limit_requests": config.airtable.rate_limit_requests,
            "rate_limit_window": config.airtable.rate_limit_window
        }
        result["security"] = {
            "secret_key": config.security.secret_key,
            "jwt_algorithm": config.security.jwt_algorithm,
            "jwt_expiration_hours": config.security.jwt_expiration_hours,
            "password_min_length": config.security.password_min_length,
            "max_login_attempts": config.security.max_login_attempts,
            "lockout_duration_minutes": config.security.lockout_duration_minutes,
            "cors_origins": config.security.cors_origins,
            "allowed_hosts": config.security.allowed_hosts
        }
        result["monitoring"] = {
            "enable_metrics": config.monitoring.enable_metrics,
            "metrics_port": config.monitoring.metrics_port,
            "health_check_interval": config.monitoring.health_check_interval,
            "log_level": config.monitoring.log_level.value,
            "log_format": config.monitoring.log_format,
            "log_file": config.monitoring.log_file,
            "max_log_file_size": config.monitoring.max_log_file_size,
            "log_backup_count": config.monitoring.log_backup_count,
            "enable_tracing": config.monitoring.enable_tracing,
            "jaeger_endpoint": config.monitoring.jaeger_endpoint
        }
        result["server"] = {
            "host": config.server.host,
            "port": config.server.port,
            "workers": config.server.workers,
            "worker_class": config.server.worker_class,
            "max_requests": config.server.max_requests,
            "max_requests_jitter": config.server.max_requests_jitter,
            "timeout": config.server.timeout,
            "keepalive": config.server.keepalive,
            "reload": config.server.reload,
            "debug": config.server.debug
        }
        return result


config_manager = ConfigManager() # Global config manager instance


def get_config() -> AppConfig:
    """Get the application configuration."""
    return config_manager.get_config()


def load_config(config_file: Optional[str] = None) -> AppConfig:
    """Load configuration from file and environment."""
    global config_manager
    config_manager = ConfigManager(config_file)
    return config_manager.load_config()