#!/usr/bin/env python3
import os
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import requests

load_dotenv()

def get_base_url() -> str:
    base = os.getenv("AGENT_BASE_URL", "https://airwppa.linkschooltech.com")
    return base.rstrip("/")

def get_admin_url() -> str:
    return f"{get_base_url()}/api/v1/admin"

def get_webhooks_url() -> str:
    return f"{get_base_url()}/api/v1/webhooks"

def get_verify_token() -> Optional[str]:
    return os.getenv("WHATSAPP_WEBHOOK_VERIFY_TOKEN")

def http_get(path: str, params: Optional[Dict[str, Any]] = None, timeout: float = 10.0) -> requests.Response:
    url = f"{get_base_url()}{path}"
    return requests.get(url, params=params, timeout=timeout)

def http_post(path: str, json_body: Dict[str, Any], timeout: float = 10.0) -> requests.Response:
    url = f"{get_base_url()}{path}"
    headers = {"Content-Type": "application/json"}
    return requests.post(url, json=json_body, headers=headers, timeout=timeout)