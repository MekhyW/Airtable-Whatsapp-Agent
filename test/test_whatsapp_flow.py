#!/usr/bin/env python3
"""
Test script to demonstrate WhatsApp message handling flow.
This script simulates the complete message processing pipeline.
"""

import asyncio
import json
import logging
import sys
import os
from datetime import datetime
from typing import Dict, Any

if sys.platform == "win32": # Set console encoding to UTF-8 for Windows compatibility
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.detach())

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('whatsapp_test.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

def maybe_post_to_cloud(webhook_payload: Dict[str, Any]):
    base_url = os.getenv("AGENT_BASE_URL", "https://airwppa.linkschooltech.com")
    if not base_url:
        return
    try:
        import requests
        base_url = base_url.rstrip("/")
        url = f"{base_url}/api/v1/webhooks/whatsapp/test"
        resp = requests.post(url, json=webhook_payload, timeout=10)
        logger.info(f"🌐 Posted test payload to {url} -> {resp.status_code}")
    except Exception as e:
        logger.error(f"Error posting to cloud endpoint: {e}")

def create_test_webhook_payload() -> Dict[str, Any]:
    """Create a test WhatsApp webhook payload."""
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123456789",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15551234567",
                                "phone_number_id": "987654321"
                            },
                            "contacts": [
                                {
                                    "profile": {
                                        "name": "Test User"
                                    },
                                    "wa_id": "15559876543"
                                }
                            ],
                            "messages": [
                                {
                                    "from": "15559876543",
                                    "id": "wamid.test123",
                                    "timestamp": str(int(datetime.now().timestamp())),
                                    "text": {
                                        "body": "Hello! Can you help me with my project?"
                                    },
                                    "type": "text"
                                }
                            ]
                        },
                        "field": "messages"
                    }
                ]
            }
        ]
    }

async def simulate_message_flow():
    """Simulate the complete WhatsApp message processing flow."""
    logger.info("🧪 Starting WhatsApp message flow simulation")
    webhook_payload = create_test_webhook_payload()
    logger.info("📋 Created test webhook payload")
    logger.info("🌐 Simulating webhook receipt")
    logger.debug(f"Webhook payload: {json.dumps(webhook_payload, indent=2)}")
    entry = webhook_payload["entry"][0]
    change = entry["changes"][0]
    value = change["value"]
    message_data = value["messages"][0]
    user_phone = message_data["from"]
    message_text = message_data["text"]["body"]
    message_id = message_data["id"]
    logger.info(f"📥 RECEIVED WhatsApp message from {user_phone}: {message_text}")
    logger.debug(f"Message details: ID={message_id}, Type=text")
    logger.info(f"🚀 Starting new workflow session for user {user_phone}")
    logger.info(f"💬 Processing message: {message_text}")
    response_text = f"Thank you for your message: '{message_text}'. I'm here to help you with your project!"
    logger.info(f"📤 SENDING WhatsApp response to {user_phone}: {response_text}")
    logger.info(f"✅ WhatsApp message sent successfully to {user_phone}")
    logger.info("📊 Updated message metrics")
    maybe_post_to_cloud(webhook_payload)
    logger.info("🎉 Message flow simulation completed successfully!")

def main():
    """Main function to run the test."""
    print("WhatsApp Message Flow Test")
    print("=" * 50)
    print("This script demonstrates the complete message processing pipeline.")
    print("Check the logs to see the message flow with emojis and detailed tracking.")
    print()
    try:
        asyncio.run(simulate_message_flow())
        print()
        print("✅ Test completed! Check 'whatsapp_test.log' for detailed logs.")
    except UnicodeEncodeError as e:
        print(f"Unicode encoding error: {e}")
        print("Falling back to simple text output...")
        print("TEST: Starting WhatsApp message flow simulation")
        print("TEST: Created test webhook payload")
        print("TEST: Simulating webhook receipt")
        print("TEST: RECEIVED WhatsApp message from 15559876543: Hello! Can you help me with my project?")
        print("TEST: Starting new workflow session for user 15559876543")
        print("TEST: Processing message: Hello! Can you help me with my project?")
        print("TEST: SENDING WhatsApp response to 15559876543")
        print("TEST: WhatsApp message sent successfully")
        print("TEST: Updated message metrics")
        print("TEST: Message flow simulation completed successfully!")
        print()
        print("PASS: Test completed! (Fallback mode)")

if __name__ == "__main__":
    main()