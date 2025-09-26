#!/usr/bin/env python3
"""
Comprehensive test script to check for import and structural issues.
This script systematically imports all modules to identify missing dependencies.
"""

import sys
import os
import importlib
import traceback
from pathlib import Path

# Add src to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

def test_import(module_name, description=""):
    """Test importing a module and report results."""
    try:
        importlib.import_module(module_name)
        print(f"✅ {module_name} - {description}")
        return True
    except ImportError as e:
        print(f"❌ {module_name} - {description}")
        print(f"   ImportError: {e}")
        return False
    except Exception as e:
        print(f"⚠️  {module_name} - {description}")
        print(f"   Error: {e}")
        return False

def main():
    """Run comprehensive import tests."""
    print("🔍 Testing imports and structural integrity...\n")
    
    failed_imports = []
    
    # Test core modules
    print("📦 Core Modules:")
    modules_to_test = [
        ("airtable_whatsapp_agent", "Main package"),
        ("airtable_whatsapp_agent.config", "Configuration module"),
        ("airtable_whatsapp_agent.cli", "CLI module"),
    ]
    
    for module, desc in modules_to_test:
        if not test_import(module, desc):
            failed_imports.append(module)
    
    print("\n📊 Models:")
    model_modules = [
        ("airtable_whatsapp_agent.models", "Models package"),
        ("airtable_whatsapp_agent.models.airtable", "Airtable models"),
        ("airtable_whatsapp_agent.models.whatsapp", "WhatsApp models"),
        ("airtable_whatsapp_agent.models.agent", "Agent models"),
    ]
    
    for module, desc in model_modules:
        if not test_import(module, desc):
            failed_imports.append(module)
    
    print("\n🌐 API Modules:")
    api_modules = [
        ("airtable_whatsapp_agent.api", "API package"),
        ("airtable_whatsapp_agent.api.main", "Main API module"),
        ("airtable_whatsapp_agent.api.webhooks", "Webhooks API"),
        ("airtable_whatsapp_agent.api.admin", "Admin API"),
        ("airtable_whatsapp_agent.api.middleware", "Middleware"),
        ("airtable_whatsapp_agent.api.app_state", "App state management"),
    ]
    
    for module, desc in api_modules:
        if not test_import(module, desc):
            failed_imports.append(module)
    
    print("\n🤖 Agent Modules:")
    agent_modules = [
        ("airtable_whatsapp_agent.agent", "Agent package"),
        ("airtable_whatsapp_agent.agent.state_manager", "State manager"),
        ("airtable_whatsapp_agent.agent.tool_registry", "Tool registry"),
        ("airtable_whatsapp_agent.agent.graph_builder", "Graph builder"),
    ]
    
    for module, desc in agent_modules:
        if not test_import(module, desc):
            failed_imports.append(module)
    
    print("\n🔧 Utility Modules:")
    util_modules = [
        ("airtable_whatsapp_agent.utils", "Utils package"),
        ("airtable_whatsapp_agent.utils.error_handling", "Error handling"),
        ("airtable_whatsapp_agent.utils.rate_limiter", "Rate limiter"),
        ("airtable_whatsapp_agent.utils.logging", "Logging utilities"),
        ("airtable_whatsapp_agent.utils.validation", "Validation utilities"),
    ]
    
    for module, desc in util_modules:
        if not test_import(module, desc):
            failed_imports.append(module)
    
    print("\n🔌 MCP Modules:")
    mcp_modules = [
        ("airtable_whatsapp_agent.mcp", "MCP package"),
        ("airtable_whatsapp_agent.mcp.external_client", "External MCP client"),
    ]
    
    for module, desc in mcp_modules:
        if not test_import(module, desc):
            failed_imports.append(module)
    
    print("\n☁️ AWS Modules:")
    aws_modules = [
        ("airtable_whatsapp_agent.aws", "AWS package"),
    ]
    
    for module, desc in aws_modules:
        if not test_import(module, desc):
            failed_imports.append(module)
    
    # Test specific imports that have caused issues
    print("\n🎯 Specific Import Tests:")
    specific_tests = [
        ("airtable_whatsapp_agent.models.agent.ConversationContext", "ConversationContext model"),
        ("airtable_whatsapp_agent.models.agent.ToolExecutionResult", "ToolExecutionResult model"),
        ("airtable_whatsapp_agent.utils.error_handling.EXTERNAL_MCP_RETRY_CONFIG", "External MCP retry config"),
        ("airtable_whatsapp_agent.models.whatsapp.WhatsAppWebhook", "WhatsApp webhook model"),
    ]
    
    for import_path, desc in specific_tests:
        try:
            module_name, attr_name = import_path.rsplit('.', 1)
            module = importlib.import_module(module_name)
            getattr(module, attr_name)
            print(f"✅ {import_path} - {desc}")
        except (ImportError, AttributeError) as e:
            print(f"❌ {import_path} - {desc}")
            print(f"   Error: {e}")
            failed_imports.append(import_path)
    
    # Test configuration-related functionality
    print("\n⚙️ Configuration Tests:")
    
    # Test CircuitBreaker with dictionary configuration
    try:
        from airtable_whatsapp_agent.utils.error_handling import CircuitBreaker, CircuitBreakerConfig
        config_obj = CircuitBreakerConfig(name="test_circuit_breaker", failure_threshold=3)
        _ = CircuitBreaker(config_obj)
        print("✅ CircuitBreaker with CircuitBreakerConfig object")
        config_dict = {"name": "test_dict_circuit_breaker", "failure_threshold": 5, "recovery_timeout": 30}
        _ = CircuitBreaker(config_dict)
        print("✅ CircuitBreaker with dictionary configuration")
        from airtable_whatsapp_agent.utils.error_handling import error_handler
        _ = error_handler.register_circuit_breaker("test_registration", config_dict)
        print("✅ Error handler circuit breaker registration with dictionary")
        from airtable_whatsapp_agent.utils.error_handling import circuit_breaker
        _ = circuit_breaker("test_convenience", config_dict)
        print("✅ Circuit breaker convenience function with dictionary")
    except Exception as e:
        print(f"❌ CircuitBreaker configuration tests")
        print(f"   Error: {e}")
        failed_imports.append("CircuitBreaker configuration tests")
    
    # Test ExternalMCPClient initialization
    try:
        from airtable_whatsapp_agent.mcp.external_client import ExternalMCPClient, ExternalMCPServerConfig
        _ = ExternalMCPServerConfig(name="test_server", url="http://localhost:8080", timeout=30) # Don't actually initialize the client (would require network), just test config creation
        print("✅ ExternalMCPServerConfig creation")
        
    except Exception as e:
        print(f"❌ ExternalMCPClient configuration test")
        print(f"   Error: {e}")
        failed_imports.append("ExternalMCPClient configuration test")
    
    # Test configuration manager functionality
    try:
        from airtable_whatsapp_agent.utils.config_manager import ConfigManager, AppConfig
        _ = ConfigManager()
        print("✅ ConfigManager creation")
    except Exception as e:
        print(f"❌ ConfigManager test")
        print(f"   Error: {e}")
        failed_imports.append("ConfigManager test")
    
    # Summary
    print(f"\n📋 Summary:")
    print(f"Total modules tested: {len(modules_to_test) + len(model_modules) + len(api_modules) + len(agent_modules) + len(util_modules) + len(mcp_modules) + len(aws_modules) + len(specific_tests)}")
    print(f"Failed imports: {len(failed_imports)}")
    
    if failed_imports:
        print(f"\n❌ Failed imports:")
        for module in failed_imports:
            print(f"   - {module}")
        return False
    else:
        print(f"\n🎉 All imports successful!")
        return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)