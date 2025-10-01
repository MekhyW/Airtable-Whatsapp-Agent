#!/usr/bin/env python3
"""
Test script for WhatsApp Business API MCP Server
This script tests the connection and basic functionality of the new WhatsApp Business API implementation.
"""

import os
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def check_environment_variables():
    """Check if all required environment variables are set."""
    required_vars = [
        'WHATSAPP_ACCESS_TOKEN',
        'WHATSAPP_PHONE_NUMBER_ID',
        'WHATSAPP_BUSINESS_ACCOUNT_ID'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        return False
    
    print("✅ All required environment variables are set")
    return True

def test_whatsapp_api_direct():
    """Test direct connection to WhatsApp Business API."""
    import requests
    
    access_token = os.getenv('WHATSAPP_ACCESS_TOKEN')
    business_account_id = os.getenv('WHATSAPP_BUSINESS_ACCOUNT_ID')
    api_version = os.getenv('WHATSAPP_API_VERSION', 'v18.0')
    
    # Test business profile endpoint
    url = f"https://graph.facebook.com/{api_version}/{business_account_id}"
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ WhatsApp Business API connection successful")
            print(f"   Business Account ID: {data.get('id', 'N/A')}")
            print(f"   Name: {data.get('name', 'N/A')}")
            return True
        else:
            print(f"❌ WhatsApp Business API connection failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error connecting to WhatsApp Business API: {e}")
        return False

def test_mcp_server_build():
    """Test if the MCP server can be built and started."""
    mcp_dir = Path("whatsapp-business-mcp")
    
    if not mcp_dir.exists():
        print(f"❌ MCP server directory not found: {mcp_dir}")
        return False
    
    # Check if package.json exists
    package_json = mcp_dir / "package.json"
    if not package_json.exists():
        print(f"❌ package.json not found in {mcp_dir}")
        return False
    
    print("✅ MCP server files found")
    
    # Test npm install
    try:
        result = subprocess.run(
            ["npm", "install"],
            cwd=mcp_dir,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            print("✅ npm install successful")
            return True
        else:
            print(f"❌ npm install failed: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("❌ npm install timed out")
        return False
    except Exception as e:
        print(f"❌ Error running npm install: {e}")
        return False

def test_docker_build():
    """Test if the Docker image can be built."""
    try:
        print("🔨 Testing Docker build (this may take a few minutes)...")
        result = subprocess.run(
            ["docker", "build", "-t", "test-whatsapp-agent", "."],
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes timeout
        )
        
        if result.returncode == 0:
            print("✅ Docker build successful")
            return True
        else:
            print(f"❌ Docker build failed: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("❌ Docker build timed out")
        return False
    except Exception as e:
        print(f"❌ Error running Docker build: {e}")
        return False

def main():
    """Run all tests."""
    print("🧪 Testing WhatsApp Business API MCP Server Implementation")
    print("=" * 60)
    
    tests = [
        ("Environment Variables", check_environment_variables),
        ("WhatsApp Business API Connection", test_whatsapp_api_direct),
        ("MCP Server Build", test_mcp_server_build),
        ("Docker Build", test_docker_build)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n📋 Running test: {test_name}")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Results Summary:")
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n🎯 Tests passed: {passed}/{len(results)}")
    
    if passed == len(results):
        print("🎉 All tests passed! The WhatsApp Business API implementation is ready.")
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
    
    return passed == len(results)

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)