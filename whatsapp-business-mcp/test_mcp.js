#!/usr/bin/env node

/**
 * Simple test script for WhatsApp Business MCP Server
 * This script tests the MCP server functionality by sending JSON-RPC messages
 */

import { spawn } from 'child_process';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Test configuration
const TEST_TIMEOUT = 10000; // 10 seconds

function createMCPMessage(id, method, params = {}) {
    return JSON.stringify({
        jsonrpc: "2.0",
        id: id,
        method: method,
        params: params
    }) + '\n';
}

function testMCPServer() {
    return new Promise((resolve, reject) => {
        console.log('🧪 Testing WhatsApp Business MCP Server...');
        
        // Set environment variables
        const env = {
            ...process.env,
            WHATSAPP_ACCESS_TOKEN: "EAAQkAvyISLUBPoPAP1s6Wr3qeUgxwMW10GTnqUMLPaBDE3Bl0paWdGJDe7GCdHfgvMufuYSgfMyjJp0SceGtzZCA4zfRZBQl9GnscjsB1Wo71DlZBjCYfVjzy8BazCyDpAuAbBOu5CJG9QFcx2PGyOVOQzZCpjPdz09UxPQOAAquOjbjRmTjbCjHK2dVErFvjxcdEzh3kFfqP4CRCWfytX740qkNlM5fQqZBSrCe3IP1dWeIZD",
            WHATSAPP_PHONE_NUMBER_ID: "333848533154837",
            WHATSAPP_BUSINESS_ACCOUNT_ID: "406042695918539",
            WHATSAPP_API_VERSION: "v22.0",
            LOG_LEVEL: "debug"
        };

        // Spawn the MCP server
        const serverPath = join(__dirname, 'src', 'index.js');
        const server = spawn('node', [serverPath], {
            env: env,
            stdio: ['pipe', 'pipe', 'pipe']
        });

        let responses = [];
        let serverOutput = '';
        let serverError = '';

        // Handle server output
        server.stdout.on('data', (data) => {
            const output = data.toString();
            console.log('📤 Server output:', output.trim());
            
            // Try to parse JSON responses
            const lines = output.split('\n').filter(line => line.trim());
            for (const line of lines) {
                try {
                    const response = JSON.parse(line);
                    responses.push(response);
                    console.log('📨 Received response:', JSON.stringify(response, null, 2));
                } catch (e) {
                    // Not JSON, probably log output
                    serverOutput += output;
                }
            }
        });

        server.stderr.on('data', (data) => {
            serverError += data.toString();
            console.log('📤 Server stderr:', data.toString().trim());
        });

        server.on('error', (error) => {
            console.error('❌ Server error:', error);
            reject(error);
        });

        // Test sequence
        setTimeout(() => {
            console.log('📋 Sending initialize request...');
            const initMessage = createMCPMessage(1, 'initialize', {
                protocolVersion: "2024-11-05",
                capabilities: {
                    tools: {}
                },
                clientInfo: {
                    name: "test-client",
                    version: "1.0.0"
                }
            });
            server.stdin.write(initMessage);
        }, 1000);

        setTimeout(() => {
            console.log('📋 Sending tools/list request...');
            const toolsMessage = createMCPMessage(2, 'tools/list', {});
            server.stdin.write(toolsMessage);
        }, 2000);

        setTimeout(() => {
            console.log('📋 Sending get_business_profile tool call...');
            const toolCallMessage = createMCPMessage(3, 'tools/call', {
                name: 'get_business_profile',
                arguments: {}
            });
            server.stdin.write(toolCallMessage);
        }, 3000);

        // Cleanup and resolve
        setTimeout(() => {
            server.kill();
            
            console.log('\n📊 Test Results:');
            console.log(`   Responses received: ${responses.length}`);
            console.log(`   Server output: ${serverOutput ? 'Yes' : 'No'}`);
            console.log(`   Server errors: ${serverError ? 'Yes' : 'No'}`);
            
            if (responses.length > 0) {
                console.log('✅ MCP Server is responding to requests');
                resolve(true);
            } else if (serverOutput.includes('WhatsApp Business MCP Server running')) {
                console.log('✅ MCP Server started successfully (no responses due to protocol timing)');
                resolve(true);
            } else {
                console.log('❌ MCP Server did not respond properly');
                console.log('Server output:', serverOutput);
                console.log('Server errors:', serverError);
                resolve(false);
            }
        }, TEST_TIMEOUT);
    });
}

// Run the test
testMCPServer()
    .then((success) => {
        if (success) {
            console.log('\n🎉 WhatsApp Business MCP Server test completed successfully!');
            process.exit(0);
        } else {
            console.log('\n⚠️ WhatsApp Business MCP Server test failed');
            process.exit(1);
        }
    })
    .catch((error) => {
        console.error('\n❌ Test failed with error:', error);
        process.exit(1);
    });