#!/usr/bin/env node

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ErrorCode,
  ListToolsRequestSchema,
  McpError,
} from '@modelcontextprotocol/sdk/types.js';
import axios from 'axios';
import winston from 'winston';
import dotenv from 'dotenv';

// Load environment variables
dotenv.config();

// Configure logger
const logger = winston.createLogger({
  level: process.env.LOG_LEVEL || 'debug',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.errors({ stack: true }),
    winston.format.json()
  ),
  transports: [
    new winston.transports.Console({
      format: winston.format.combine(
        winston.format.colorize(),
        winston.format.simple()
      )
    })
  ]
});

// WhatsApp Business API configuration
const WHATSAPP_CONFIG = {
  accessToken: process.env.WHATSAPP_ACCESS_TOKEN,
  phoneNumberId: process.env.WHATSAPP_PHONE_NUMBER_ID,
  businessAccountId: process.env.WHATSAPP_BUSINESS_ACCOUNT_ID,
  apiVersion: process.env.WHATSAPP_API_VERSION || 'v22.0',
  baseUrl: 'https://graph.facebook.com'
};

// Validate required environment variables
const requiredEnvVars = ['WHATSAPP_ACCESS_TOKEN', 'WHATSAPP_PHONE_NUMBER_ID'];
for (const envVar of requiredEnvVars) {
  if (!process.env[envVar]) {
    logger.error(`Missing required environment variable: ${envVar}`);
    process.exit(1);
  }
}

class WhatsAppBusinessMCPServer {
  constructor() {
    this.server = new Server(
      {
        name: 'whatsapp-business-mcp-server',
        version: '1.0.0',
      },
      {
        capabilities: {
          tools: {},
        },
      }
    );

    this.setupToolHandlers();
    this.setupErrorHandling();
  }

  setupErrorHandling() {
    this.server.onerror = (error) => {
      logger.error('Server error:', error);
    };

    process.on('SIGINT', async () => {
      logger.info('Shutting down server...');
      await this.server.close();
      process.exit(0);
    });
  }

  setupToolHandlers() {
    // List available tools
    this.server.setRequestHandler(ListToolsRequestSchema, async () => {
      return {
        tools: [
          {
            name: 'send_message',
            description: 'Send a text message to a WhatsApp number',
            inputSchema: {
              type: 'object',
              properties: {
                to: {
                  type: 'string',
                  description: 'Phone number in international format (e.g., +1234567890)',
                },
                message: {
                  type: 'string',
                  description: 'Text message to send',
                },
              },
              required: ['to', 'message'],
            },
          },
          {
            name: 'send_template_message',
            description: 'Send a template message to a WhatsApp number',
            inputSchema: {
              type: 'object',
              properties: {
                to: {
                  type: 'string',
                  description: 'Phone number in international format',
                },
                template_name: {
                  type: 'string',
                  description: 'Name of the approved template',
                },
                language_code: {
                  type: 'string',
                  description: 'Language code (e.g., en_US)',
                  default: 'en_US',
                },
                parameters: {
                  type: 'array',
                  description: 'Template parameters',
                  items: {
                    type: 'string',
                  },
                },
              },
              required: ['to', 'template_name'],
            },
          },
          {
            name: 'get_message_status',
            description: 'Get the delivery status of a message',
            inputSchema: {
              type: 'object',
              properties: {
                message_id: {
                  type: 'string',
                  description: 'WhatsApp message ID',
                },
              },
              required: ['message_id'],
            },
          },
          {
            name: 'get_business_profile',
            description: 'Get the business profile information',
            inputSchema: {
              type: 'object',
              properties: {},
            },
          },
          {
            name: 'upload_media',
            description: 'Upload media file to WhatsApp',
            inputSchema: {
              type: 'object',
              properties: {
                file_path: {
                  type: 'string',
                  description: 'Path to the media file',
                },
                type: {
                  type: 'string',
                  description: 'Media type (image, document, audio, video)',
                  enum: ['image', 'document', 'audio', 'video'],
                },
              },
              required: ['file_path', 'type'],
            },
          },
        ],
      };
    });

    // Handle tool calls
    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      const { name, arguments: args } = request.params;

      try {
        switch (name) {
          case 'send_message':
            return await this.sendMessage(args);
          case 'send_template_message':
            return await this.sendTemplateMessage(args);
          case 'get_message_status':
            return await this.getMessageStatus(args);
          case 'get_business_profile':
            return await this.getBusinessProfile(args);
          case 'upload_media':
            return await this.uploadMedia(args);
          default:
            throw new McpError(
              ErrorCode.MethodNotFound,
              `Unknown tool: ${name}`
            );
        }
      } catch (error) {
        logger.error(`Error executing tool ${name}:`, error);
        throw new McpError(
          ErrorCode.InternalError,
          `Tool execution failed: ${error.message}`
        );
      }
    });
  }

  async sendMessage(args) {
    const { to, message } = args;
    
    const url = `${WHATSAPP_CONFIG.baseUrl}/${WHATSAPP_CONFIG.apiVersion}/${WHATSAPP_CONFIG.phoneNumberId}/messages`;
    
    const payload = {
      messaging_product: 'whatsapp',
      to: to,
      type: 'text',
      text: {
        body: message,
      },
    };

    try {
      const response = await axios.post(url, payload, {
        headers: {
          'Authorization': `Bearer ${WHATSAPP_CONFIG.accessToken}`,
          'Content-Type': 'application/json',
        },
      });

      logger.info(`Message sent successfully to ${to}`, { messageId: response.data.messages[0].id });

      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify({
              success: true,
              message_id: response.data.messages[0].id,
              status: 'sent',
              to: to,
              message: message,
            }, null, 2),
          },
        ],
      };
    } catch (error) {
      logger.error('Failed to send message:', error.response?.data || error.message);
      throw new Error(`Failed to send message: ${error.response?.data?.error?.message || error.message}`);
    }
  }

  async sendTemplateMessage(args) {
    const { to, template_name, language_code = 'en_US', parameters = [] } = args;
    
    const url = `${WHATSAPP_CONFIG.baseUrl}/${WHATSAPP_CONFIG.apiVersion}/${WHATSAPP_CONFIG.phoneNumberId}/messages`;
    
    const payload = {
      messaging_product: 'whatsapp',
      to: to,
      type: 'template',
      template: {
        name: template_name,
        language: {
          code: language_code,
        },
        components: parameters.length > 0 ? [
          {
            type: 'body',
            parameters: parameters.map(param => ({
              type: 'text',
              text: param,
            })),
          },
        ] : [],
      },
    };

    try {
      const response = await axios.post(url, payload, {
        headers: {
          'Authorization': `Bearer ${WHATSAPP_CONFIG.accessToken}`,
          'Content-Type': 'application/json',
        },
      });

      logger.info(`Template message sent successfully to ${to}`, { messageId: response.data.messages[0].id });

      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify({
              success: true,
              message_id: response.data.messages[0].id,
              status: 'sent',
              to: to,
              template: template_name,
            }, null, 2),
          },
        ],
      };
    } catch (error) {
      logger.error('Failed to send template message:', error.response?.data || error.message);
      throw new Error(`Failed to send template message: ${error.response?.data?.error?.message || error.message}`);
    }
  }

  async getMessageStatus(args) {
    const { message_id } = args;
    
    const url = `${WHATSAPP_CONFIG.baseUrl}/${WHATSAPP_CONFIG.apiVersion}/${message_id}`;

    try {
      const response = await axios.get(url, {
        headers: {
          'Authorization': `Bearer ${WHATSAPP_CONFIG.accessToken}`,
        },
      });

      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(response.data, null, 2),
          },
        ],
      };
    } catch (error) {
      logger.error('Failed to get message status:', error.response?.data || error.message);
      throw new Error(`Failed to get message status: ${error.response?.data?.error?.message || error.message}`);
    }
  }

  async getBusinessProfile(args) {
    const url = `${WHATSAPP_CONFIG.baseUrl}/${WHATSAPP_CONFIG.apiVersion}/${WHATSAPP_CONFIG.phoneNumberId}`;

    try {
      const response = await axios.get(url, {
        headers: {
          'Authorization': `Bearer ${WHATSAPP_CONFIG.accessToken}`,
        },
        params: {
          fields: 'id,display_phone_number,verified_name,quality_rating',
        },
      });

      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(response.data, null, 2),
          },
        ],
      };
    } catch (error) {
      logger.error('Failed to get business profile:', error.response?.data || error.message);
      throw new Error(`Failed to get business profile: ${error.response?.data?.error?.message || error.message}`);
    }
  }

  async uploadMedia(args) {
    const { file_path, type } = args;
    
    // Note: This is a simplified implementation
    // In a real scenario, you'd need to handle file reading and form-data
    const url = `${WHATSAPP_CONFIG.baseUrl}/${WHATSAPP_CONFIG.apiVersion}/${WHATSAPP_CONFIG.phoneNumberId}/media`;

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            error: 'Media upload not implemented in this version. Please use the WhatsApp Business API directly for media uploads.',
            file_path: file_path,
            type: type,
          }, null, 2),
        },
      ],
    };
  }

  async run() {
    const transport = new StdioServerTransport();
    await this.server.connect(transport);
    logger.info('WhatsApp Business MCP Server running on stdio');
  }
}

// Start the server
const server = new WhatsAppBusinessMCPServer();
server.run().catch((error) => {
  logger.error('Failed to start server:', error);
  process.exit(1);
});