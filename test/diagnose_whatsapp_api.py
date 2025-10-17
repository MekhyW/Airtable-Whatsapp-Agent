#!/usr/bin/env python3
"""
WhatsApp Business API Diagnostic Tool
This script tests the WhatsApp Business API configuration and MCP server connectivity.
"""

import os
import asyncio
import httpx
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class WhatsAppAPIDiagnostic:
    def __init__(self):
        self.access_token = os.getenv('WHATSAPP_ACCESS_TOKEN')
        self.phone_number_id = os.getenv('WHATSAPP_PHONE_NUMBER_ID')
        self.business_account_id = os.getenv('WHATSAPP_BUSINESS_ACCOUNT_ID')
        self.api_version = os.getenv('WHATSAPP_API_VERSION')
        self.mcp_whatsapp_url = "http://localhost:8000"
        self.test_phone = "+5511976132143"  # Recipient
        self.base_url = f"https://graph.facebook.com/{self.api_version}"
        
    def print_header(self, title):
        print(f"\n{'='*60}")
        print(f"🔍 {title}")
        print(f"{'='*60}")
        
    def print_section(self, title):
        print(f"\n📋 {title}")
        print("-" * 40)
        
    def check_environment_variables(self):
        """Check if all required environment variables are set."""
        self.print_section("Environment Variables Check")
        required_vars = {
            'WHATSAPP_ACCESS_TOKEN': self.access_token,
            'WHATSAPP_PHONE_NUMBER_ID': self.phone_number_id,
            'WHATSAPP_BUSINESS_ACCOUNT_ID': self.business_account_id,
            'MCP_WHATSAPP_SERVER_URL': self.mcp_whatsapp_url
        }
        all_set = True
        for var_name, var_value in required_vars.items():
            if var_value:
                print(f"   ✅ {var_name}: {'*' * 20}...{var_value[-4:] if len(var_value) > 4 else '****'}")
            else:
                print(f"   ❌ {var_name}: Not set")
                all_set = False
        print(f"   📊 API Version: {self.api_version}")
        print(f"   📱 Test Phone: {self.test_phone}")
        return all_set
        
    async def test_whatsapp_api_direct(self):
        """Test direct WhatsApp Business API connectivity."""
        self.print_section("WhatsApp Business API Direct Test")
        if not self.access_token or not self.phone_number_id:
            print("   ❌ Missing WhatsApp credentials")
            return False
        try:
            async with httpx.AsyncClient() as client:
                # Test 1: Get Business Profile
                print("   🔍 Testing business profile retrieval...")
                profile_url = f"{self.base_url}/{self.phone_number_id}"
                headers = {
                    'Authorization': f'Bearer {self.access_token}',
                    'Content-Type': 'application/json'
                }
                response = await client.get(profile_url, headers=headers)
                if response.status_code == 200:
                    profile_data = response.json()
                    print(f"   ✅ Business profile retrieved successfully")
                    print(f"      Display Name: {profile_data.get('display_phone_number', 'N/A')}")
                    print(f"      Status: {profile_data.get('verified_name', 'N/A')}")
                else:
                    print(f"   ❌ Failed to get business profile: {response.status_code}")
                    print(f"      Error: {response.text}")
                    return False
                    
                # Test 2: Send a test message
                print("   📤 Testing message sending...")
                message_url = f"{self.base_url}/{self.phone_number_id}/messages"
                message_data = {
                    "messaging_product": "whatsapp",
                    "to": self.test_phone,
                    "type": "text",
                    "text": {
                        "body": f"🧪 Test message from WhatsApp Bot - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    }
                }
                response = await client.post(message_url, headers=headers, json=message_data)
                if response.status_code == 200:
                    result = response.json()
                    message_id = result.get('messages', [{}])[0].get('id', 'Unknown')
                    print(f"   ✅ Test message sent successfully!")
                    print(f"      Message ID: {message_id}")
                    print(f"      Recipient: {self.test_phone}")
                    return True
                else:
                    print(f"   ❌ Failed to send test message: {response.status_code}")
                    print(f"      Error: {response.text}")
                    return False 
        except Exception as e:
            print(f"   ❌ WhatsApp API test failed: {str(e)}")
            return False
            
    async def test_mcp_server_connectivity(self):
        """Test MCP server connectivity."""
        self.print_section("MCP Server Connectivity Test")
        try:
            async with httpx.AsyncClient() as client:
                print(f"   🔍 Testing MCP server at {self.mcp_whatsapp_url}...")
                health_url = f"{self.mcp_whatsapp_url}/health"
                try:
                    response = await client.get(health_url, timeout=10)
                    if response.status_code == 200:
                        print(f"   ✅ MCP server is responding")
                        print(f"      Health check: {response.json()}")
                        return True
                    else:
                        print(f"   ⚠️ MCP server responded with status: {response.status_code}")
                except httpx.ConnectError:
                    print(f"   ❌ Cannot connect to MCP server at {self.mcp_whatsapp_url}")
                    print(f"      This is expected if running in ECS (internal communication)")
                    return False
                except Exception as e:
                    print(f"   ❌ MCP server test failed: {str(e)}")
                    return False
        except Exception as e:
            print(f"   ❌ MCP connectivity test failed: {str(e)}")
            return False
            
    async def test_webhook_message_simulation(self):
        """Simulate a webhook message to test the full pipeline."""
        self.print_section("Webhook Message Simulation")
        webhook_url = os.getenv("WHATSAPP_WEBHOOK_URL")
        webhook_payload = {
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
                                    "phone_number_id": self.phone_number_id,
                                },
                                "contacts": [
                                    {
                                        "profile": {"name": "Felipe Test User"},
                                        "wa_id": "551196132143",
                                    }
                                ],
                                "messages": [
                                    {
                                        "from": "551196132143",
                                        "id": f"wamid.diagnostic{int(datetime.now().timestamp())}",
                                        "timestamp": str(int(datetime.now().timestamp())),
                                        "text": {"body": "Hello, this is a diagnostic test message!"},
                                        "type": "text",
                                    }
                                ],
                            },
                            "field": "messages",
                        }
                    ],
                }
            ],
        }
        try:
            async with httpx.AsyncClient() as client:
                print(f"   📤 Sending test webhook to {webhook_url}...")
                response = await client.post(webhook_url, json=webhook_payload, timeout=10.0)
                if response.status_code == 200:
                    print(f"   ✅ Webhook accepted successfully")
                    print(f"      Response: {response.json()}")
                    print(f"   ⏳ Check your phone for a response message...")
                    return True
                else:
                    print(f"   ❌ Webhook failed: {response.status_code}")
                    print(f"      Error: {response.text}")
                    return False   
        except Exception as e:
            print(f"   ❌ Webhook simulation failed: {str(e)}")
            return False
            
    def generate_recommendations(self, results):
        """Generate recommendations based on test results."""
        self.print_section("Recommendations")
        if not results['env_vars']:
            print("   🔧 Set missing environment variables in your ECS task definition:")
            print("      - WHATSAPP_ACCESS_TOKEN")
            print("      - WHATSAPP_PHONE_NUMBER_ID") 
            print("      - WHATSAPP_BUSINESS_ACCOUNT_ID")
        if not results['whatsapp_api']:
            print("   🔧 WhatsApp API issues:")
            print("      - Verify your access token is valid and not expired")
            print("      - Check if your phone number is verified in Meta Business")
            print("      - Ensure your WhatsApp Business Account is active")
        if not results['mcp_server']:
            print("   🔧 MCP Server issues:")
            print("      - In ECS, MCP servers run internally (this is normal)")
            print("      - Check ECS task logs for MCP server startup errors")
            print("      - Verify MCP_WHATSAPP_SERVER_URL points to localhost:8001")
        if results['whatsapp_api'] and not results['webhook_sim']:
            print("   🔧 Webhook processing issues:")
            print("      - Check CloudWatch logs for message processing errors")
            print("      - Verify agent is properly initialized")
            print("      - Check MCP server communication within the container")
            
    async def run_diagnostics(self):
        """Run all diagnostic tests."""
        self.print_header("WhatsApp Business API Diagnostic Tool")
        results = {
            'env_vars': self.check_environment_variables(),
            'whatsapp_api': False,
            'mcp_server': False,
            'webhook_sim': False
        }
        if results['env_vars']:
            results['whatsapp_api'] = await self.test_whatsapp_api_direct()
            results['mcp_server'] = await self.test_mcp_server_connectivity()
            results['webhook_sim'] = await self.test_webhook_message_simulation()
        self.print_header("Diagnostic Summary")
        passed = sum(results.values())
        total = len(results)
        for test_name, result in results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"   {test_name.replace('_', ' ').title()}: {status}")  
        print(f"\n🎯 Tests passed: {passed}/{total}")
        self.generate_recommendations(results)
        return results

async def main():
    """Main function."""
    diagnostic = WhatsAppAPIDiagnostic()
    await diagnostic.run_diagnostics()

if __name__ == "__main__":
    asyncio.run(main())