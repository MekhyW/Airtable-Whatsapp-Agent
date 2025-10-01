#!/usr/bin/env python3
"""
Test script to demonstrate WhatsApp message handling flow.
This script simulates the complete message processing pipeline.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any

# Configure logging to see the message flow
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('whatsapp_test.log')
    ]
)

logger = logging.getLogger(__name__)

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
    
    # Create test payload
    webhook_payload = create_test_webhook_payload()
    logger.info("📋 Created test webhook payload")
    
    # Log the payload (similar to what the webhook endpoint does)
    logger.info("🌐 Simulating webhook receipt")
    logger.debug(f"Webhook payload: {json.dumps(webhook_payload, indent=2)}")
    
    # Extract message info (similar to _extract_message)
    entry = webhook_payload["entry"][0]
    change = entry["changes"][0]
    value = change["value"]
    message_data = value["messages"][0]
    
    user_phone = message_data["from"]
    message_text = message_data["text"]["body"]
    message_id = message_data["id"]
    
    logger.info(f"📥 RECEIVED WhatsApp message from {user_phone}: {message_text}")
    logger.debug(f"Message details: ID={message_id}, Type=text")
    
    # Simulate agent processing
    logger.info(f"🚀 Starting new workflow session for user {user_phone}")
    logger.info(f"💬 Processing message: {message_text}")
    
    # Simulate response generation
    response_text = f"Thank you for your message: '{message_text}'. I'm here to help you with your project!"
    
    logger.info(f"📤 SENDING WhatsApp response to {user_phone}: {response_text}")
    logger.info(f"✅ WhatsApp message sent successfully to {user_phone}")
    
    # Simulate metrics update
    logger.info("📊 Updated message metrics")
    
    logger.info("🎉 Message flow simulation completed successfully!")

def main():
    """Main function to run the test."""
    print("WhatsApp Message Flow Test")
    print("=" * 50)
    print("This script demonstrates the complete message processing pipeline.")
    print("Check the logs to see the message flow with emojis and detailed tracking.")
    print()
    
    # Run the simulation
    asyncio.run(simulate_message_flow())
    
    print()
    print("✅ Test completed! Check 'whatsapp_test.log' for detailed logs.")

if __name__ == "__main__":
    main()