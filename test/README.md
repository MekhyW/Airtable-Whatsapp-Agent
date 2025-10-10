Cloud Testing for Airtable-Whatsapp-Agent
========================================

Overview
- Tests in this folder can target the deployed service.
- Default base URL is `https://airwppa.linkschooltech.com`.

Environment Variables
- `AGENT_BASE_URL`: Base URL of the deployed agent (optional; defaults to the domain above).
- `WHATSAPP_WEBHOOK_VERIFY_TOKEN`: Verify token used for WhatsApp webhook verification (required for valid verification test).

How to Run
- Health, admin, and webhook endpoint tests:
  `python test/test_cloud_endpoints.py`
- Flow simulations (optionally post to cloud):
  `python test/test_whatsapp_flow.py`
  `python test/test_whatsapp_flow_windows.py`

Endpoints Used
- Health: `<BASE_URL>/health`
- Admin config: `<BASE_URL>/api/v1/admin/config`
- Webhook verification: `<BASE_URL>/api/v1/webhooks/whatsapp?hub.mode=subscribe&hub.challenge=...&hub.verify_token=...`
- Webhook POST: `<BASE_URL>/api/v1/webhooks/whatsapp`
- Webhook status: `<BASE_URL>/api/v1/webhooks/whatsapp/status`
- Webhook test: `<BASE_URL>/api/v1/webhooks/whatsapp/test`

Notes
- Nginx applies rate limiting to `/api/` and `/api/v1/webhooks/`; keep test runs modest.
- Ensure the deployed instance has correct environment and MCP servers initialized.