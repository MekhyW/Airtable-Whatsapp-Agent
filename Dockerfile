# Multi-stage build for production optimization
FROM python:3.11-slim as builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create and activate virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Node.js stage for MCP servers
FROM node:18-alpine as node-builder

# Install Airtable MCP server globally
RUN npm install -g airtable-mcp-server

# Build WhatsApp Business MCP server
WORKDIR /whatsapp-business-mcp
COPY whatsapp-business-mcp/package*.json ./
RUN npm ci --only=production
COPY whatsapp-business-mcp/src ./src

# Production stage
FROM python:3.11-slim as production

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    NODE_VERSION=18.19.0

# Install runtime dependencies including Node.js and supervisor
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy Node.js global packages from node-builder
COPY --from=node-builder /usr/local/lib/node_modules /usr/local/lib/node_modules
COPY --from=node-builder /usr/local/bin /usr/local/bin

# Copy WhatsApp Business MCP server
COPY --from=node-builder /whatsapp-business-mcp /app/whatsapp-business-mcp

# Create application directory
WORKDIR /app

# Copy application code
COPY src/ ./src/
COPY pyproject.toml ./
COPY README.md ./
COPY LICENSE ./

# Copy supervisord configuration
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Install the application in development mode
RUN pip install -e .

# Create user and supervisor log directory
RUN groupadd -r appuser && useradd -r -g appuser appuser && \
    mkdir -p /app/logs /app/data /var/log/supervisor && \
    chown -R appuser:appuser /app /var/log/supervisor && \
    mkdir -p /home/appuser/.npm && \
    chown -R appuser:appuser /home/appuser

# Expose ports
EXPOSE 8000 8001 8002

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Switch to root for supervisord
USER root

# Run supervisord to manage all processes
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]