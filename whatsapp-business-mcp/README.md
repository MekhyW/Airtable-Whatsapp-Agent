# WhatsApp Business API MCP Server

A Model Context Protocol (MCP) server that provides integration with the official WhatsApp Business API. This server replaces the `wweb-mcp` solution and uses the official Meta WhatsApp Business API instead of browser automation.

## Features

- **Official API Integration**: Uses Meta's WhatsApp Business API
- **No Browser Automation**: No need for device linking or QR code scanning
- **Production Ready**: Designed for production environments
- **MCP Compatible**: Follows the Model Context Protocol specification
- **Comprehensive Tools**: Send messages, templates, check status, and more

## Available Tools

### `send_message`
Send a text message to a WhatsApp number.

**Parameters:**
- `to` (string): Phone number in international format (e.g., +1234567890)
- `message` (string): Text message to send

### `send_template_message`
Send a pre-approved template message.

**Parameters:**
- `to` (string): Phone number in international format
- `template_name` (string): Name of the approved template
- `language_code` (string, optional): Language code (default: en_US)
- `parameters` (array, optional): Template parameters

### `get_message_status`
Get the delivery status of a sent message.

**Parameters:**
- `message_id` (string): WhatsApp message ID

### `get_business_profile`
Get the business profile information.

**Parameters:** None

### `upload_media`
Upload media files (placeholder - not fully implemented).

**Parameters:**
- `file_path` (string): Path to the media file
- `type` (string): Media type (image, document, audio, video)

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Required
WHATSAPP_ACCESS_TOKEN=your_access_token_here
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id_here
WHATSAPP_BUSINESS_ACCOUNT_ID=your_business_account_id_here

# Optional
WHATSAPP_API_VERSION=v22.0
LOG_LEVEL=debug
```

### Getting WhatsApp Business API Credentials

1. **Create a Meta Business Account**: Visit [business.facebook.com](https://business.facebook.com)
2. **Set up WhatsApp Business API**: Follow the [official documentation](https://developers.facebook.com/docs/whatsapp/cloud-api/get-started)
3. **Get your credentials**:
   - Access Token: From your app's dashboard
   - Phone Number ID: From your WhatsApp Business Account
   - Business Account ID: From your WhatsApp Business Account

## Installation

### Using Docker (Recommended)

```bash
# Build the image
docker build -t whatsapp-business-mcp .

# Run the container
docker run -d \
  --name whatsapp-business-mcp \
  -e WHATSAPP_ACCESS_TOKEN=your_token \
  -e WHATSAPP_PHONE_NUMBER_ID=your_phone_id \
  -e WHATSAPP_BUSINESS_ACCOUNT_ID=your_business_id \
  whatsapp-business-mcp
```

### Using Node.js

```bash
# Install dependencies
npm install

# Start the server
npm start

# For development with auto-reload
npm run dev
```

## Integration with Main Application

This MCP server is designed to replace the `wweb-mcp` server in the main application. The main application will communicate with this server through the MCP protocol.

### Advantages over wweb-mcp

1. **No Device Linking**: Uses official API, no QR code scanning required
2. **Production Ready**: Stable and reliable for production environments
3. **Official Support**: Uses Meta's official API with proper authentication
4. **Better Rate Limits**: Official API has better rate limiting and reliability
5. **No Browser Dependencies**: No need for Puppeteer or browser automation

## API Rate Limits

The WhatsApp Business API has the following rate limits:
- **Messages**: 1000 messages per second per phone number
- **API Calls**: 4000 API calls per hour per app

## Error Handling

The server includes comprehensive error handling:
- API errors are properly caught and logged
- Rate limiting is respected
- Network errors are handled gracefully
- All errors include detailed error messages

## Logging

The server uses Winston for logging with configurable log levels:
- `error`: Error messages only
- `warn`: Warning and error messages
- `info`: Informational, warning, and error messages (default)
- `debug`: All messages including debug information

## Security

- Uses official Meta API with proper authentication
- No sensitive data is logged
- Environment variables are used for configuration
- Runs as non-root user in Docker

## Support

For issues related to:
- **WhatsApp Business API**: Check [Meta's documentation](https://developers.facebook.com/docs/whatsapp)
- **MCP Protocol**: Check [MCP documentation](https://modelcontextprotocol.io/)
- **This Server**: Create an issue in the repository