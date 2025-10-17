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
from .app_state import get_app_state
from ..models import WhatsAppMessage, WhatsAppWebhook

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
        logger.info("🔄 Started webhook event processing loop")
        while self.is_processing:
            try:
                event = await asyncio.wait_for(self.processing_queue.get(), timeout=1.0)
                logger.debug("🔍 Processing webhook event from queue")
                await self._handle_event(event)
                logger.debug("✅ Webhook event processed successfully")
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error processing webhook event: {str(e)}", exc_info=True)
        logger.info("🛑 Webhook event processing loop stopped")
                
    async def _handle_event(self, event: WhatsAppWebhook):
        """Handle a single webhook event."""
        try:
            app_state = get_app_state()
            agent = app_state.get("agent")
            if not agent:
                logger.error("Agent not available")
                return
            message = self._extract_message(event)
            if not message:
                logger.warning("No message found in webhook event")
                return
            logger.info(f"📥 RECEIVED WhatsApp message from {message.from_number}: {message.text or f'[{message.type} message]'}")
            logger.debug(f"Message details: ID={message.id}, Type={message.type}, Timestamp={message.timestamp}")
            session_id = await agent.process_message(
                user_phone=message.from_number,
                message=message.text or f"[{message.type} message]",
                message_type=message.type,
                context={
                    "message_id": message.id,
                    "timestamp": message.timestamp,
                    "media_url": message.media_url,
                    "context": message.context,
                    "metadata": message.metadata
                }
            )
            logger.info(f"✅ Message processed successfully. Session ID: {session_id}")
        except Exception as e:
            logger.error(f"Error handling webhook event: {str(e)}", exc_info=True)
            
    def _extract_message(self, event: WhatsAppWebhook) -> Optional[WhatsAppMessage]:
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
        
    async def queue_event(self, event: WhatsAppWebhook):
        """Queue webhook event for processing."""
        try:
            await self.processing_queue.put(event)
            logger.info(f"Queued webhook event for processing")
        except Exception as e:
            logger.error(f"Error queuing webhook event: {str(e)}")


webhook_handler = WhatsAppWebhookHandler()


@router.get("/whatsapp")
async def verify_webhook(request: Request, hub_mode: str = Query(alias="hub.mode"), hub_challenge: str = Query(alias="hub.challenge"), hub_verify_token: str = Query(alias="hub.verify_token")):
    """Verify WhatsApp webhook."""
    client_ip = request.client.host if request.client else "unknown"
    logger.info(f"🔍 WEBHOOK VERIFICATION: {request.method} {request.url.path} from {client_ip}")
    logger.info(f"🔍 Verification params - mode: {hub_mode}, challenge: {hub_challenge}, token: {'***' if hub_verify_token else 'None'}")
    logger.debug(f"🔍 Full query params: {dict(request.query_params)}")
    logger.debug(f"🔍 Headers: {dict(request.headers)}")
    try:
        app_state = get_app_state()
        settings = app_state.get("settings")
        if not settings:
            logger.error("🔍 VERIFICATION FAILED: Settings not available")
            raise HTTPException(status_code=500, detail="Server configuration error")
        expected_token = settings.whatsapp_webhook_verify_token
        logger.debug(f"🔍 Expected token configured: {'Yes' if expected_token else 'No'}")
        if hub_verify_token != expected_token:
            logger.warning(f"🔍 VERIFICATION FAILED: Invalid verify token received")
            logger.debug(f"🔍 Token comparison - received: '{hub_verify_token}', expected: '{expected_token}'")
            raise HTTPException(status_code=403, detail="Invalid verify token")
        if hub_mode != "subscribe":
            logger.warning(f"🔍 VERIFICATION FAILED: Invalid mode: {hub_mode}")
            raise HTTPException(status_code=400, detail="Invalid mode")
        logger.info(f"🔍 VERIFICATION SUCCESS: Returning challenge: {hub_challenge}")
        return PlainTextResponse(hub_challenge)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"🔍 VERIFICATION ERROR: Unexpected error during webhook verification: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/whatsapp")
async def handle_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handle WhatsApp webhook events."""
    client_ip = request.client.host if request.client else "unknown"
    logger.info(f"📨 WEBHOOK POST: {request.method} {request.url.path} from {client_ip}")
    logger.debug(f"📨 Request headers: {dict(request.headers)}")
    logger.debug(f"📨 Request URL: {request.url}")
    try:
        body = await request.body()
        body_str = body.decode('utf-8', errors='replace') if body else ""
        logger.info(f"📨 Received webhook body ({len(body)} bytes)")
        logger.debug(f"📨 Raw body: {body_str}")
        try:
            data = json.loads(body)
            logger.info(f"📨 Successfully parsed JSON payload")
            logger.debug(f"📨 Parsed payload: {json.dumps(data, indent=2)}")
        except json.JSONDecodeError as e:
            logger.error(f"📨 WEBHOOK ERROR: Invalid JSON in payload: {str(e)}")
            logger.error(f"📨 Raw body that failed to parse: {body_str}")
            raise HTTPException(status_code=400, detail="Invalid JSON")
        try:
            event = WhatsAppWebhook(**data)
            logger.info(f"📨 Webhook event validated successfully")
            logger.debug(f"📨 Event object: {event.object}, entries: {len(event.entry)}")
        except Exception as e:
            logger.error(f"📨 WEBHOOK ERROR: Invalid webhook structure: {str(e)}")
            logger.error(f"📨 Data that failed validation: {json.dumps(data, indent=2)}")
            raise HTTPException(status_code=400, detail=f"Invalid webhook structure: {str(e)}")
        logger.info(f"📨 Starting webhook processing and queuing event")
        await webhook_handler.start_processing()
        background_tasks.add_task(webhook_handler.queue_event, event)
        logger.info(f"📨 ✅ WEBHOOK SUCCESS: Event accepted and queued for processing")
        return {"status": "success", "message": "Webhook event queued for processing"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"📨 WEBHOOK ERROR: Unexpected error handling webhook: {str(e)}", exc_info=True)
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
        event = WhatsAppWebhook(**test_data)
        await webhook_handler.start_processing()
        await webhook_handler.queue_event(event)
        return { "status": "success", "message": "Test event queued for processing" }
    except Exception as e:
        logger.error(f"Error testing webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))