#!/usr/bin/env python3
"""
Cloud endpoint tests for the deployed Airtable-Whatsapp-Agent.
Targets https://airwppa.linkschooltech.com by default, configurable via AGENT_BASE_URL.
"""

import json
from datetime import datetime
import requests
from cloud_test_utils import get_base_url, get_admin_url, get_webhooks_url, get_verify_token, http_get


def create_sample_webhook_payload() -> dict:
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
                                "phone_number_id": "987654321",
                            },
                            "contacts": [
                                {
                                    "profile": {"name": "Cloud Test User"},
                                    "wa_id": "15559876543",
                                }
                            ],
                            "messages": [
                                {
                                    "from": "15559876543",
                                    "id": "wamid.cloudtest123",
                                    "timestamp": str(int(datetime.now().timestamp())),
                                    "text": {"body": "Hello from cloud test!"},
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


def test_health() -> bool:
    resp = http_get("/health")
    ok = resp.status_code == 200
    try:
        data = resp.json()
    except Exception:
        data = {"parse_error": resp.text}
    print(f"GET {get_base_url()}/health -> {resp.status_code} {data}")
    return ok


def test_admin_config() -> bool:
    url = f"{get_admin_url()}/config"
    resp = requests.get(url, timeout=10)
    ok = resp.status_code == 200
    try:
        data = resp.json()
    except Exception:
        data = {"parse_error": resp.text}
    print(f"GET {url} -> {resp.status_code} {json.dumps(data, indent=2)}")
    return ok and "environment" in data


def test_webhook_verification_valid() -> bool:
    token = get_verify_token()
    if not token:
        print("WHATSAPP_WEBHOOK_VERIFY_TOKEN not set; skipping valid verification test.")
        return True  # don't fail when token missing
    params = {
        "hub.mode": "subscribe",
        "hub.challenge": "cloud-test-challenge",
        "hub.verify_token": token,
    }
    url = f"{get_webhooks_url()}/whatsapp"
    resp = requests.get(url, params=params, timeout=10)
    ok = resp.status_code == 200 and resp.text == "cloud-test-challenge"
    print(f"GET {url} (valid token) -> {resp.status_code} body='{resp.text}'")
    return ok


def test_webhook_verification_invalid() -> bool:
    params = {
        "hub.mode": "subscribe",
        "hub.challenge": "cloud-test-challenge",
        "hub.verify_token": "invalid-token",
    }
    url = f"{get_webhooks_url()}/whatsapp"
    resp = requests.get(url, params=params, timeout=10)
    ok = resp.status_code == 403
    print(f"GET {url} (invalid token) -> {resp.status_code} body='{resp.text}'")
    return ok


def test_webhook_post() -> bool:
    url = f"{get_webhooks_url()}/whatsapp"
    payload = create_sample_webhook_payload()
    resp = requests.post(url, json=payload, timeout=10)
    ok = resp.status_code == 200
    try:
        data = resp.json()
    except Exception:
        data = {"parse_error": resp.text}
    print(f"POST {url} -> {resp.status_code} {json.dumps(data, indent=2)}")
    return ok and data.get("status") == "success"


def test_webhook_status() -> bool:
    url = f"{get_webhooks_url()}/whatsapp/status"
    resp = requests.get(url, timeout=10)
    ok = resp.status_code == 200
    try:
        data = resp.json()
    except Exception:
        data = {"parse_error": resp.text}
    print(f"GET {url} -> {resp.status_code} {json.dumps(data, indent=2)}")
    return ok and "status" in data and "queue_size" in data


def main() -> bool:
    print("\n🧪 Cloud Endpoint Tests for Airtable-Whatsapp-Agent")
    print("===============================================")
    print(f"Target base URL: {get_base_url()}\n")

    tests = [
        ("Health", test_health),
        ("Admin Config", test_admin_config),
        ("Webhook Verify (valid)", test_webhook_verification_valid),
        ("Webhook Verify (invalid)", test_webhook_verification_invalid),
        ("Webhook POST", test_webhook_post),
        ("Webhook Status", test_webhook_status),
    ]

    results = []
    for name, fn in tests:
        try:
            print(f"\n📋 Running: {name}")
            res = fn()
            print("✅ PASS" if res else "❌ FAIL")
            results.append((name, res))
        except Exception as e:
            print(f"❌ Exception in {name}: {e}")
            results.append((name, False))

    passed = sum(1 for _, r in results if r)
    total = len(results)
    print("\n📊 Summary:")
    for name, r in results:
        print(f" - {name}: {'PASS' if r else 'FAIL'}")
    print(f"\n🎯 Passed {passed}/{total} tests")
    return passed == total


if __name__ == "__main__":
    ok = main()
    raise SystemExit(0 if ok else 1)