"""
WhatsApp webhook handlers.
"""

import logging
from typing import Dict, Any, Optional
import asyncio
import json

from fastapi import APIRouter, Request, HTTPException, Query, BackgroundTasks
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from .main import get_app_state
from ..models import WhatsAppMessage, WhatsAppWebhookEvent


logger = logging.getLogger(__name__)

router = APIRouter()


class WebhookVerification(BaseModel):
    """WhatsApp webhook verification model."""
    challenge: str = Field(..., alias="hub.challenge")
    verify_token: str = Field(..., alias="hub.verify_token")
    mode: str = Field(..., alias="hub.mode")


class WhatsAppWebhookHandler:
    """Handler for WhatsApp webhook events."""
    
    def __init__(self):
        self.processing_queue = asyncio.Queue()
        self.is_processing = False
        
    async def start_processing(self):
        """Start background processing of webhook events."""
        if not self.is_processing:
            self.is_processing = True
            asyncio.create_task(self._process_events())
            
    async def stop_processing(self):
        """Stop background processing."""
        self.is_processing = False
        
    async def _process_events(self):
        """Background task to process webhook events."""
        while self.is_processing:
            try:
                # Get event from queue with timeout
                event = await asyncio.wait_for(
                    self.processing_queue.get(), 
                    timeout=1.0
                )
                
                await self._handle_event(event)
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error processing webhook event: {str(e)}", exc_info=True)
                
    async def _handle_event(self, event: WhatsAppWebhookEvent):
        """Handle a single webhook event."""
        try:
            app_state = get_app_state()
            agent = app_state.get("agent")
            
            if not agent:
                logger.error("Agent not available")
                return
                
            # Extract message from event
            message = self._extract_message(event)
            if not message:
                logger.warning("No message found in webhook event")
                return
                
            # Process message with agent
            await agent.process_message(message)
            
        except Exception as e:
            logger.error(f"Error handling webhook event: {str(e)}", exc_info=True)
            
    def _extract_message(self, event: WhatsAppWebhookEvent) -> Optional[WhatsAppMessage]:
        """Extract WhatsApp message from webhook event."""
        try:
            if not event.entry:
                return None
                
            for entry in event.entry:
                if not entry.get("changes"):
                    continue
                    
                for change in entry["changes"]:
                    if change.get("field") != "messages":
                        continue
                        
                    value = change.get("value", {})
                    messages = value.get("messages", [])
                    
                    if not messages:
                        continue
                        
                    # Process first message
                    msg_data = messages[0]
                    
                    return WhatsAppMessage(
                        id=msg_data.get("id"),
                        from_number=msg_data.get("from"),
                        to_number=value.get("metadata", {}).get("phone_number_id"),
                        timestamp=msg_data.get("timestamp"),
                        type=msg_data.get("type"),
                        text=msg_data.get("text", {}).get("body") if msg_data.get("type") == "text" else None,
                        media_url=self._extract_media_url(msg_data),
                        context=msg_data.get("context"),
                        metadata=value.get("metadata", {})
                    )
                    
            return None
            
        except Exception as e:
            logger.error(f"Error extracting message: {str(e)}")
            return None
            
    def _extract_media_url(self, msg_data: Dict[str, Any]) -> Optional[str]:
        """Extract media URL from message data."""
        msg_type = msg_data.get("type")
        
        if msg_type in ["image", "audio", "video", "document"]:
            media_data = msg_data.get(msg_type, {})
            return media_data.get("id")  # This is the media ID, not URL
            
        return None
        
    async def queue_event(self, event: WhatsAppWebhookEvent):
        """Queue webhook event for processing."""
        try:
            await self.processing_queue.put(event)
            logger.info(f"Queued webhook event for processing")
            
        except Exception as e:
            logger.error(f"Error queuing webhook event: {str(e)}")


# Global webhook handler instance
webhook_handler = WhatsAppWebhookHandler()


@router.get("/whatsapp")
async def verify_webhook(
    request: Request,
    hub_mode: str = Query(alias="hub.mode"),
    hub_challenge: str = Query(alias="hub.challenge"),
    hub_verify_token: str = Query(alias="hub.verify_token")
):
    """Verify WhatsApp webhook."""
    
    logger.info(f"Webhook verification request: mode={hub_mode}, token={hub_verify_token}")
    
    # Get settings from app state
    app_state = get_app_state()
    settings = app_state.get("settings")
    
    if not settings:
        logger.error("Settings not available")
        raise HTTPException(status_code=500, detail="Server configuration error")
    
    # Verify token
    if hub_verify_token != settings.whatsapp_webhook_verify_token:
        logger.warning(f"Invalid verify token: {hub_verify_token}")
        raise HTTPException(status_code=403, detail="Invalid verify token")
    
    # Verify mode
    if hub_mode != "subscribe":
        logger.warning(f"Invalid mode: {hub_mode}")
        raise HTTPException(status_code=400, detail="Invalid mode")
    
    logger.info("Webhook verification successful")
    return PlainTextResponse(hub_challenge)


@router.post("/whatsapp")
async def handle_webhook(
    request: Request,
    background_tasks: BackgroundTasks
):
    """Handle WhatsApp webhook events."""
    
    try:
        # Parse request body
        body = await request.body()
        data = json.loads(body)
        
        logger.info(f"Received webhook event: {json.dumps(data, indent=2)}")
        
        # Create webhook event
        event = WhatsAppWebhookEvent(**data)
        
        # Start processing if not already started
        await webhook_handler.start_processing()
        
        # Queue event for background processing
        background_tasks.add_task(webhook_handler.queue_event, event)
        
        # Return success immediately
        return {"status": "success"}
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in webhook payload: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid JSON")
        
    except Exception as e:
        logger.error(f"Error handling webhook: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/whatsapp/status")
async def webhook_status():
    """Get webhook processing status."""
    
    try:
        queue_size = webhook_handler.processing_queue.qsize()
        
        return {
            "status": "active" if webhook_handler.is_processing else "inactive",
            "queue_size": queue_size,
            "processing": webhook_handler.is_processing
        }
        
    except Exception as e:
        logger.error(f"Error getting webhook status: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/whatsapp/test")
async def test_webhook(test_data: Dict[str, Any]):
    """Test webhook processing with sample data."""
    
    try:
        # Create test event
        event = WhatsAppWebhookEvent(**test_data)
        
        # Start processing if not already started
        await webhook_handler.start_processing()
        
        # Queue event
        await webhook_handler.queue_event(event)
        
        return {
            "status": "success",
            "message": "Test event queued for processing"
        }
        
    except Exception as e:
        logger.error(f"Error testing webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))