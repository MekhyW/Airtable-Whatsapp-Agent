"""
Pydantic models for WhatsApp Business API data structures.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum
from pydantic import BaseModel, Field, validator


class MessageType(str, Enum):
    """WhatsApp message types."""
    TEXT = "text"
    IMAGE = "image"
    DOCUMENT = "document"
    AUDIO = "audio"
    VIDEO = "video"
    STICKER = "sticker"
    LOCATION = "location"
    CONTACTS = "contacts"
    INTERACTIVE = "interactive"
    TEMPLATE = "template"
    SYSTEM = "system"
    UNKNOWN = "unknown"


class MessageStatus(str, Enum):
    """WhatsApp message status."""
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    PENDING = "pending"


class InteractiveType(str, Enum):
    """Interactive message types."""
    BUTTON = "button"
    LIST = "list"
    PRODUCT = "product"
    PRODUCT_LIST = "product_list"


class WhatsAppContact(BaseModel):
    """WhatsApp contact information."""
    wa_id: str = Field(..., description="WhatsApp ID (phone number)")
    profile: Optional[Dict[str, Any]] = Field(None, description="Contact profile information")
    @validator('wa_id')
    def validate_wa_id(cls, v):
        """Validate WhatsApp ID format."""
        digits_only = ''.join(filter(str.isdigit, v)) # Remove any non-digit characters for validation
        if len(digits_only) < 10:
            raise ValueError('WhatsApp ID must contain at least 10 digits')
        return v


class WhatsAppMedia(BaseModel):
    """WhatsApp media information."""
    id: Optional[str] = Field(None, description="Media ID")
    mime_type: Optional[str] = Field(None, description="Media MIME type")
    sha256: Optional[str] = Field(None, description="Media SHA256 hash")
    filename: Optional[str] = Field(None, description="Media filename")
    caption: Optional[str] = Field(None, description="Media caption")
    url: Optional[str] = Field(None, description="Media URL")


class WhatsAppLocation(BaseModel):
    """WhatsApp location information."""
    latitude: float = Field(..., description="Location latitude")
    longitude: float = Field(..., description="Location longitude")
    name: Optional[str] = Field(None, description="Location name")
    address: Optional[str] = Field(None, description="Location address")


class WhatsAppButton(BaseModel):
    """WhatsApp interactive button."""
    type: str = Field(..., description="Button type")
    reply: Dict[str, str] = Field(..., description="Button reply configuration")


class WhatsAppListSection(BaseModel):
    """WhatsApp list section."""
    title: Optional[str] = Field(None, description="Section title")
    rows: List[Dict[str, str]] = Field(..., description="Section rows")


class WhatsAppInteractive(BaseModel):
    """WhatsApp interactive message content."""
    type: InteractiveType = Field(..., description="Interactive type")
    header: Optional[Dict[str, Any]] = Field(None, description="Interactive header")
    body: Optional[Dict[str, str]] = Field(None, description="Interactive body")
    footer: Optional[Dict[str, str]] = Field(None, description="Interactive footer")
    action: Optional[Dict[str, Any]] = Field(None, description="Interactive action")


class WhatsAppMessage(BaseModel):
    """Base WhatsApp message model."""
    id: str = Field(..., description="Message ID")
    from_: str = Field(..., alias="from", description="Sender phone number")
    to: Optional[str] = Field(None, description="Recipient phone number")
    timestamp: datetime = Field(..., description="Message timestamp")
    type: MessageType = Field(..., description="Message type")
    context: Optional[Dict[str, Any]] = Field(None, description="Message context")
    class Config:
        """Pydantic configuration."""
        allow_population_by_field_name = True
        json_encoders = { datetime: lambda v: v.isoformat() if v else None }


class WhatsAppTextMessage(WhatsAppMessage):
    """WhatsApp text message."""
    text: Dict[str, str] = Field(..., description="Text content")
    type: MessageType = Field(default=MessageType.TEXT, description="Message type")


class WhatsAppMediaMessage(WhatsAppMessage):
    """WhatsApp media message."""
    media: WhatsAppMedia = Field(..., description="Media information")
    caption: Optional[str] = Field(None, description="Media caption")


class WhatsAppLocationMessage(WhatsAppMessage):
    """WhatsApp location message."""
    
    location: WhatsAppLocation = Field(..., description="Location information")
    type: MessageType = Field(default=MessageType.LOCATION, description="Message type")


class WhatsAppInteractiveMessage(WhatsAppMessage):
    """WhatsApp interactive message."""
    interactive: WhatsAppInteractive = Field(..., description="Interactive content")
    type: MessageType = Field(default=MessageType.INTERACTIVE, description="Message type")


class WhatsAppContactMessage(WhatsAppMessage):
    """WhatsApp contact message."""
    contacts: List[Dict[str, Any]] = Field(..., description="Contact information")
    type: MessageType = Field(default=MessageType.CONTACTS, description="Message type")


class WhatsAppMessageStatus(BaseModel):
    """WhatsApp message status update."""
    id: str = Field(..., description="Message ID")
    status: MessageStatus = Field(..., description="Message status")
    timestamp: datetime = Field(..., description="Status timestamp")
    recipient_id: str = Field(..., description="Recipient phone number")
    conversation: Optional[Dict[str, Any]] = Field(None, description="Conversation information")
    pricing: Optional[Dict[str, Any]] = Field(None, description="Pricing information")
    class Config:
        """Pydantic configuration."""
        json_encoders = { datetime: lambda v: v.isoformat() if v else None }


class WhatsAppError(BaseModel):
    """WhatsApp API error."""
    code: int = Field(..., description="Error code")
    title: str = Field(..., description="Error title")
    message: str = Field(..., description="Error message")
    error_data: Optional[Dict[str, Any]] = Field(None, description="Additional error data")


class WhatsAppWebhookEntry(BaseModel):
    """WhatsApp webhook entry."""
    id: str = Field(..., description="Entry ID")
    changes: List[Dict[str, Any]] = Field(..., description="Changes in the entry")


class WhatsAppWebhook(BaseModel):
    """WhatsApp webhook payload."""
    object: str = Field(..., description="Webhook object type")
    entry: List[WhatsAppWebhookEntry] = Field(..., description="Webhook entries")


class WhatsAppMessageRequest(BaseModel):
    """Request model for sending WhatsApp messages."""
    messaging_product: str = Field(default="whatsapp", description="Messaging product")
    recipient_type: str = Field(default="individual", description="Recipient type")
    to: str = Field(..., description="Recipient phone number")
    type: MessageType = Field(..., description="Message type")
    text: Optional[Dict[str, str]] = Field(None, description="Text content")
    media: Optional[WhatsAppMedia] = Field(None, description="Media content")
    location: Optional[WhatsAppLocation] = Field(None, description="Location content")
    interactive: Optional[WhatsAppInteractive] = Field(None, description="Interactive content")
    template: Optional[Dict[str, Any]] = Field(None, description="Template content")
    context: Optional[Dict[str, Any]] = Field(None, description="Message context")
    @validator('to')
    def validate_recipient(cls, v):
        """Validate recipient phone number."""
        digits_only = ''.join(filter(str.isdigit, v))
        if len(digits_only) < 10:
            raise ValueError('Recipient phone number must contain at least 10 digits')
        return v


class WhatsAppMessageResponse(BaseModel):
    """Response model for WhatsApp message sending."""
    messaging_product: str = Field(..., description="Messaging product")
    contacts: List[WhatsAppContact] = Field(..., description="Contact information")
    messages: List[Dict[str, str]] = Field(..., description="Message information")


class WhatsAppTemplate(BaseModel):
    """WhatsApp message template."""
    name: str = Field(..., description="Template name")
    language: Dict[str, str] = Field(..., description="Template language")
    components: Optional[List[Dict[str, Any]]] = Field(None, description="Template components")


class WhatsAppBusinessProfile(BaseModel):
    """WhatsApp Business profile information."""
    about: Optional[str] = Field(None, description="Business description")
    address: Optional[str] = Field(None, description="Business address")
    description: Optional[str] = Field(None, description="Business description")
    email: Optional[str] = Field(None, description="Business email")
    profile_picture_url: Optional[str] = Field(None, description="Profile picture URL")
    websites: Optional[List[str]] = Field(None, description="Business websites")
    vertical: Optional[str] = Field(None, description="Business vertical")


class WhatsAppPhoneNumber(BaseModel):
    """WhatsApp phone number information."""
    verified_name: str = Field(..., description="Verified business name")
    display_phone_number: str = Field(..., description="Display phone number")
    id: str = Field(..., description="Phone number ID")
    quality_rating: Optional[str] = Field(None, description="Quality rating")