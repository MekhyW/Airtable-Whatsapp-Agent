"""
Data models for the Airtable WhatsApp Agent.
"""

from .airtable import (
    AirtableRecord,
    AdminWhitelistRecord,
    ContactRecord,
    ConversationRecord,
    MessageRecord,
    TaskRecord,
    AuditLogRecord,
)
from .whatsapp import (
    WhatsAppMessage,
    WhatsAppWebhook,
    WhatsAppContact,
    WhatsAppMessageStatus,
    WhatsAppMediaMessage,
    WhatsAppTextMessage,
    WhatsAppInteractiveMessage,
)
from .agent import (
    AgentState,
    AgentAction,
    AgentResponse,
    AgentMemory,
    AgentTask,
    AgentDecision,
)
from .auth import (
    User,
    AdminUser,
    AuthToken,
    Permission,
)

__all__ = [
    # Airtable models
    "AirtableRecord",
    "AdminWhitelistRecord",
    "ContactRecord",
    "ConversationRecord",
    "MessageRecord",
    "TaskRecord",
    "AuditLogRecord",
    # WhatsApp models
    "WhatsAppMessage",
    "WhatsAppWebhook",
    "WhatsAppContact",
    "WhatsAppMessageStatus",
    "WhatsAppMediaMessage",
    "WhatsAppTextMessage",
    "WhatsAppInteractiveMessage",
    # Agent models
    "AgentState",
    "AgentAction",
    "AgentResponse",
    "AgentMemory",
    "AgentTask",
    "AgentDecision",
    # Auth models
    "User",
    "AdminUser",
    "AuthToken",
    "Permission",
]