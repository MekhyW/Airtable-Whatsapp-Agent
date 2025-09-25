"""
Configuration management for the Airtable WhatsApp Agent.
"""

from typing import List, Optional
from pydantic import Field, validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings."""
    
    # Application Settings
    environment: str = Field(default="development", env="ENVIRONMENT")
    debug: bool = Field(default=False, env="DEBUG")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    api_v1_str: str = Field(default="/api/v1", env="API_V1_STR")
    
    # Database Configuration
    database_url: str = Field(..., env="DATABASE_URL")
    redis_url: str = Field(..., env="REDIS_URL")
    
    # OpenAI Configuration
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4-turbo-preview", env="OPENAI_MODEL")
    openai_max_tokens: int = Field(default=4096, env="OPENAI_MAX_TOKENS")
    openai_temperature: float = Field(default=0.1, env="OPENAI_TEMPERATURE")
    
    # WhatsApp Business API Configuration
    whatsapp_access_token: str = Field(..., env="WHATSAPP_ACCESS_TOKEN")
    whatsapp_phone_number_id: str = Field(..., env="WHATSAPP_PHONE_NUMBER_ID")
    whatsapp_business_account_id: str = Field(..., env="WHATSAPP_BUSINESS_ACCOUNT_ID")
    whatsapp_webhook_verify_token: str = Field(..., env="WHATSAPP_WEBHOOK_VERIFY_TOKEN")
    whatsapp_webhook_url: str = Field(..., env="WHATSAPP_WEBHOOK_URL")
    whatsapp_api_version: str = Field(default="v18.0", env="WHATSAPP_API_VERSION")
    
    # Airtable Configuration
    airtable_api_key: str = Field(..., env="AIRTABLE_API_KEY")
    airtable_base_id: str = Field(..., env="AIRTABLE_BASE_ID")
    
    # AWS Configuration
    aws_region: str = Field(default="us-east-1", env="AWS_REGION")
    aws_access_key_id: Optional[str] = Field(default=None, env="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: Optional[str] = Field(default=None, env="AWS_SECRET_ACCESS_KEY")
    aws_eventbridge_bus_name: str = Field(default="airtable-whatsapp-agent-events", env="AWS_EVENTBRIDGE_BUS_NAME")
    aws_ecs_cluster_name: str = Field(default="airtable-whatsapp-agent-cluster", env="AWS_ECS_CLUSTER_NAME")
    aws_ecr_repository_uri: Optional[str] = Field(default=None, env="AWS_ECR_REPOSITORY_URI")
    
    # Security
    rate_limit_per_minute: int = Field(default=60, env="RATE_LIMIT_PER_MINUTE")
    cors_origins: List[str] = Field(default=["http://localhost:3000"], env="CORS_ORIGINS")
    
    # Agent Configuration
    agent_name: str = Field(default="AirtableWhatsAppAgent", env="AGENT_NAME")
    agent_description: str = Field(
        default="Autonomous AI agent for Airtable and WhatsApp integration",
        env="AGENT_DESCRIPTION"
    )
    agent_max_iterations: int = Field(default=10, env="AGENT_MAX_ITERATIONS")
    agent_timeout_seconds: int = Field(default=300, env="AGENT_TIMEOUT_SECONDS")
    agent_memory_size: int = Field(default=1000, env="AGENT_MEMORY_SIZE")
    
    # MCP Server Configuration
    mcp_airtable_server_url: str = Field(default="http://localhost:8001", env="MCP_AIRTABLE_SERVER_URL")
    mcp_whatsapp_server_url: str = Field(default="http://localhost:8002", env="MCP_WHATSAPP_SERVER_URL")
    mcp_timeout_seconds: int = Field(default=30, env="MCP_TIMEOUT_SECONDS")
    mcp_max_retries: int = Field(default=3, env="MCP_MAX_RETRIES")
    mcp_retry_delay: float = Field(default=1.0, env="MCP_RETRY_DELAY")
    mcp_airtable_api_key: Optional[str] = Field(default=None, env="MCP_AIRTABLE_API_KEY")
    mcp_whatsapp_access_token: Optional[str] = Field(default=None, env="MCP_WHATSAPP_ACCESS_TOKEN")
    
    # Monitoring and Observability
    prometheus_multiproc_dir: str = Field(default="/tmp/prometheus_multiproc_dir", env="PROMETHEUS_MULTIPROC_DIR")
    jaeger_agent_host: str = Field(default="localhost", env="JAEGER_AGENT_HOST")
    jaeger_agent_port: int = Field(default=6831, env="JAEGER_AGENT_PORT")
    
    # Development Settings
    reload: bool = Field(default=False, env="RELOAD")
    workers: int = Field(default=1, env="WORKERS")
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    
    @validator("cors_origins", pre=True)
    def assemble_cors_origins(cls, v):
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, list):
            return v
        raise ValueError("CORS origins must be a string or list")
    
    @validator("log_level")
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v.upper()
    
    @property
    def whatsapp_api_base_url(self) -> str:
        """Get WhatsApp API base URL."""
        return f"https://graph.facebook.com/{self.whatsapp_api_version}"
    
    @property
    def airtable_api_base_url(self) -> str:
        """Get Airtable API base URL."""
        return f"https://api.airtable.com/v0/{self.airtable_base_id}"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment.lower() == "development"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment.lower() == "production"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()