# Airtable WhatsApp Agent

Agent for monitoring business processes via Airtable, capable of sending messages to employees on WhatsApp, using AWS EventBridge for internal task scheduling.

![architecture](docs/architecture.png)

![flow](docs/flow.png)

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- Docker and Docker Compose
- AWS CLI (for cloud deployment)
- WhatsApp Business API access
- Airtable account and API key

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/Airtable-Whatsapp-Agent.git
   cd Airtable-Whatsapp-Agent
   ```

2. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your actual credentials
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run with Docker Compose**
   ```bash
   docker-compose up -d
   ```

The application will be available at `http://localhost:8000`

## 📋 Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure the required environment variables.

### Configuration File

Alternatively, use a YAML configuration file:

```bash
cp config.example.yaml config.yaml
# Edit config.yaml with your settings
```

## 🔌 MCP (Model Context Protocol) Architecture

This application uses external MCP servers for enhanced modularity and maintainability:

### External MCP Servers

- **WhatsApp MCP Server**: Handles WhatsApp Business API integration
  - Uses public `whatsapp-mcp` server
  - Supports message sending, receiving, and status tracking
  - Configured via `MCP_WHATSAPP_SERVER_URL`

- **Airtable MCP Server**: Manages Airtable database operations
  - Uses public `@domdomegg/airtable-mcp-server`
  - Handles table operations, record management, and queries
  - Configured via `MCP_AIRTABLE_SERVER_URL`

### MCP Configuration

```env
# MCP Server URLs
MCP_AIRTABLE_SERVER_URL=http://airtable-mcp:8000
MCP_WHATSAPP_SERVER_URL=http://whatsapp-mcp:8001
MCP_TIMEOUT_SECONDS=30
MCP_MAX_RETRIES=3
MCP_RETRY_DELAY=1.0
```

### Benefits

- **Modularity**: Each service handles specific functionality
- **Scalability**: MCP servers can be scaled independently
- **Maintainability**: Updates to MCP servers don't require application changes
- **Reliability**: Built-in retry logic and error handling

## 🐳 Docker Deployment

### Local Development

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Production Deployment

```bash
# Use production configuration
docker-compose -f docker-compose.prod.yml up -d
```

## ☁️ AWS Cloud Deployment

#### 1. Create ECR Repository

```bash
aws ecr create-repository --repository-name airtable-whatsapp-agent
```

#### 2. Build and Push Docker Image

```bash
# Get login token
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Build image
docker build -t airtable-whatsapp-agent .

# Tag image
docker tag airtable-whatsapp-agent:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/airtable-whatsapp-agent:latest

# Push image
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/airtable-whatsapp-agent:latest
```

#### 3. Create ECS Cluster

```bash
aws ecs create-cluster --cluster-name airtable-whatsapp-cluster
```

#### 4. Create Task Definition

```bash
aws ecs register-task-definition --cli-input-json file://task-definition.json
```

#### 5. Create ECS Service

```bash
aws ecs create-service \
  --cluster airtable-whatsapp-cluster \
  --service-name airtable-whatsapp-service \
  --task-definition airtable-whatsapp-agent:1 \
  --desired-count 1
```

## 📊 Monitoring

### Health Checks

- **Application Health**: `GET /health`
- **Detailed Health**: `GET /health/detailed`
- **Metrics**: `GET /metrics` (Prometheus format)

### Logging

Logs are structured and include:
- Request/response tracking
- Error details with context
- Performance metrics
- Security events

### Monitoring Endpoints

```bash
# Check application health
curl http://localhost:8000/health

# Get detailed component status
curl http://localhost:8000/health/detailed

# View metrics (Prometheus format)
curl http://localhost:8000/metrics
```

### Logs and Debugging

```bash
# View application logs
docker-compose logs -f app

# View all service logs
docker-compose logs -f

# Debug mode (local development)
AIRTABLE_WHATSAPP_DEBUG=true python -m uvicorn src.airtable_whatsapp_agent.api.main:app --reload
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔄 Updates and Maintenance

### Updating Dependencies

```bash
# Update Python packages
pip install --upgrade -r requirements.txt

# Update Docker images
docker-compose pull
docker-compose up -d
```

### Backup and Recovery

```bash
# Backup database (if using PostgreSQL)
docker-compose exec db pg_dump -U username dbname > backup.sql

# Restore database
docker-compose exec -T db psql -U username dbname < backup.sql
```