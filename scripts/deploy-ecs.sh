#!/bin/bash

# AWS ECS Deployment Script for Airtable WhatsApp Agent
# This script deploys the application to AWS ECS using the ECR image

set -e

# Configuration
AWS_REGION="${AWS_REGION:-us-east-1}"
CLUSTER_NAME="${CLUSTER_NAME:-airtable-whatsapp-cluster}"
SERVICE_NAME="${SERVICE_NAME:-airtable-whatsapp-service}"
TASK_DEFINITION_NAME="${TASK_DEFINITION_NAME:-airtable-whatsapp-task}"
ECR_REPOSITORY="${ECR_REPOSITORY:-airtable-whatsapp-agent}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
DESIRED_COUNT="${DESIRED_COUNT:-2}"
SUBNET_IDS="${SUBNET_IDS:-}"
SECURITY_GROUP_IDS="${SECURITY_GROUP_IDS:-}"
TARGET_GROUP_ARN="${TARGET_GROUP_ARN:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if required tools are installed
check_dependencies() {
    log_info "Checking dependencies..."
    
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi
    
    if ! command -v jq &> /dev/null; then
        log_error "jq is not installed. Please install it first."
        exit 1
    fi
    
    log_success "All dependencies are installed"
}

# Get AWS account ID
get_aws_account_id() {
    log_info "Getting AWS account ID..."
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    
    if [ -z "$AWS_ACCOUNT_ID" ]; then
        log_error "Failed to get AWS account ID. Please check your AWS credentials."
        exit 1
    fi
    
    log_success "AWS Account ID: $AWS_ACCOUNT_ID"
}

# Create ECS cluster if it doesn't exist
create_ecs_cluster() {
    log_info "Checking if ECS cluster exists..."
    
    if aws ecs describe-clusters --clusters "$CLUSTER_NAME" --region "$AWS_REGION" --query 'clusters[0].status' --output text 2>/dev/null | grep -q "ACTIVE"; then
        log_success "ECS cluster '$CLUSTER_NAME' already exists"
    else
        log_info "Creating ECS cluster '$CLUSTER_NAME'..."
        aws ecs create-cluster \
            --cluster-name "$CLUSTER_NAME" \
            --capacity-providers FARGATE EC2 \
            --default-capacity-provider-strategy capacityProvider=FARGATE,weight=1 \
            --region "$AWS_REGION" \
            --tags key=Application,value=airtable-whatsapp-agent key=Environment,value=production
        
        log_success "ECS cluster '$CLUSTER_NAME' created successfully"
    fi
}

# Create IAM role for ECS task execution
create_task_execution_role() {
    log_info "Creating ECS task execution role..."
    
    ROLE_NAME="ecsTaskExecutionRole-airtable-whatsapp"
    
    # Check if role exists
    if aws iam get-role --role-name "$ROLE_NAME" --region "$AWS_REGION" &> /dev/null; then
        log_success "Task execution role already exists"
        return
    fi
    
    # Create trust policy
    cat > /tmp/trust-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "ecs-tasks.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}
EOF
    
    # Create role
    aws iam create-role \
        --role-name "$ROLE_NAME" \
        --assume-role-policy-document file:///tmp/trust-policy.json \
        --region "$AWS_REGION"
    
    # Attach policies
    aws iam attach-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy \
        --region "$AWS_REGION"
    
    aws iam attach-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-arn arn:aws:iam::aws:policy/CloudWatchLogsFullAccess \
        --region "$AWS_REGION"
    
    log_success "Task execution role created successfully"
    
    # Clean up
    rm -f /tmp/trust-policy.json
}

# Create CloudWatch log group
create_log_group() {
    log_info "Creating CloudWatch log group..."
    
    LOG_GROUP_NAME="/aws/ecs/$TASK_DEFINITION_NAME"
    
    if aws logs describe-log-groups --log-group-name-prefix "$LOG_GROUP_NAME" --region "$AWS_REGION" --query 'logGroups[0].logGroupName' --output text 2>/dev/null | grep -q "$LOG_GROUP_NAME"; then
        log_success "Log group already exists"
    else
        aws logs create-log-group \
            --log-group-name "$LOG_GROUP_NAME" \
            --region "$AWS_REGION"
        
        # Set retention policy
        aws logs put-retention-policy \
            --log-group-name "$LOG_GROUP_NAME" \
            --retention-in-days 30 \
            --region "$AWS_REGION"
        
        log_success "Log group created successfully"
    fi
}

# Register task definition
register_task_definition() {
    log_info "Registering ECS task definition..."
    
    ECR_URI="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY:$IMAGE_TAG"
    EXECUTION_ROLE_ARN="arn:aws:iam::$AWS_ACCOUNT_ID:role/ecsTaskExecutionRole-airtable-whatsapp"
    
    # Create task definition JSON
    cat > /tmp/task-definition.json << EOF
{
    "family": "$TASK_DEFINITION_NAME",
    "networkMode": "awsvpc",
    "requiresCompatibilities": ["FARGATE"],
    "cpu": "1024",
    "memory": "2048",
    "executionRoleArn": "$EXECUTION_ROLE_ARN",
    "taskRoleArn": "$EXECUTION_ROLE_ARN",
    "containerDefinitions": [
        {
            "name": "airtable-whatsapp-agent",
            "image": "$ECR_URI",
            "essential": true,
            "portMappings": [
                {
                    "containerPort": 8000,
                    "protocol": "tcp"
                }
            ],
            "environment": [
                {
                    "name": "ENVIRONMENT",
                    "value": "production"
                },
                {
                    "name": "LOG_LEVEL",
                    "value": "INFO"
                },
                {
                    "name": "AWS_DEFAULT_REGION",
                    "value": "$AWS_REGION"
                }
            ],
            "secrets": [
                {
                    "name": "OPENAI_API_KEY",
                    "valueFrom": "arn:aws:ssm:$AWS_REGION:$AWS_ACCOUNT_ID:parameter/airtable-whatsapp/openai-api-key"
                },
                {
                    "name": "AIRTABLE_API_KEY",
                    "valueFrom": "arn:aws:ssm:$AWS_REGION:$AWS_ACCOUNT_ID:parameter/airtable-whatsapp/airtable-api-key"
                },
                {
                    "name": "WHATSAPP_ACCESS_TOKEN",
                    "valueFrom": "arn:aws:ssm:$AWS_REGION:$AWS_ACCOUNT_ID:parameter/airtable-whatsapp/whatsapp-access-token"
                },
                {
                    "name": "WEBHOOK_VERIFY_TOKEN",
                    "valueFrom": "arn:aws:ssm:$AWS_REGION:$AWS_ACCOUNT_ID:parameter/airtable-whatsapp/webhook-verify-token"
                }
            ],
            "logConfiguration": {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-group": "/aws/ecs/$TASK_DEFINITION_NAME",
                    "awslogs-region": "$AWS_REGION",
                    "awslogs-stream-prefix": "ecs"
                }
            },
            "healthCheck": {
                "command": [
                    "CMD-SHELL",
                    "curl -f http://localhost:8000/health || exit 1"
                ],
                "interval": 30,
                "timeout": 5,
                "retries": 3,
                "startPeriod": 60
            }
        }
    ]
}
EOF
    
    # Register the task definition
    TASK_DEFINITION_ARN=$(aws ecs register-task-definition \
        --cli-input-json file:///tmp/task-definition.json \
        --region "$AWS_REGION" \
        --query 'taskDefinition.taskDefinitionArn' \
        --output text)
    
    log_success "Task definition registered: $TASK_DEFINITION_ARN"
    
    # Clean up
    rm -f /tmp/task-definition.json
}

# Create or update ECS service
create_or_update_service() {
    log_info "Creating or updating ECS service..."
    
    # Check if service exists
    if aws ecs describe-services --cluster "$CLUSTER_NAME" --services "$SERVICE_NAME" --region "$AWS_REGION" --query 'services[0].status' --output text 2>/dev/null | grep -q "ACTIVE"; then
        log_info "Service exists, updating..."
        
        aws ecs update-service \
            --cluster "$CLUSTER_NAME" \
            --service "$SERVICE_NAME" \
            --task-definition "$TASK_DEFINITION_ARN" \
            --desired-count "$DESIRED_COUNT" \
            --region "$AWS_REGION" \
            --force-new-deployment
        
        log_success "Service updated successfully"
    else
        log_info "Creating new service..."
        
        # Build service configuration
        SERVICE_CONFIG="{
            \"serviceName\": \"$SERVICE_NAME\",
            \"cluster\": \"$CLUSTER_NAME\",
            \"taskDefinition\": \"$TASK_DEFINITION_ARN\",
            \"desiredCount\": $DESIRED_COUNT,
            \"launchType\": \"FARGATE\",
            \"networkConfiguration\": {
                \"awsvpcConfiguration\": {
                    \"subnets\": [$(echo $SUBNET_IDS | sed 's/,/","/g' | sed 's/^/"/' | sed 's/$/"/')],
                    \"securityGroups\": [$(echo $SECURITY_GROUP_IDS | sed 's/,/","/g' | sed 's/^/"/' | sed 's/$/"/')],
                    \"assignPublicIp\": \"ENABLED\"
                }
            },
            \"deploymentConfiguration\": {
                \"maximumPercent\": 200,
                \"minimumHealthyPercent\": 50
            },
            \"enableExecuteCommand\": true
        }"
        
        # Add load balancer configuration if target group is provided
        if [ -n "$TARGET_GROUP_ARN" ]; then
            SERVICE_CONFIG=$(echo "$SERVICE_CONFIG" | jq ". + {
                \"loadBalancers\": [
                    {
                        \"targetGroupArn\": \"$TARGET_GROUP_ARN\",
                        \"containerName\": \"airtable-whatsapp-agent\",
                        \"containerPort\": 8000
                    }
                ],
                \"healthCheckGracePeriodSeconds\": 300
            }")
        fi
        
        # Create service
        echo "$SERVICE_CONFIG" > /tmp/service-config.json
        
        aws ecs create-service \
            --cli-input-json file:///tmp/service-config.json \
            --region "$AWS_REGION"
        
        log_success "Service created successfully"
        
        # Clean up
        rm -f /tmp/service-config.json
    fi
}

# Wait for deployment to complete
wait_for_deployment() {
    log_info "Waiting for deployment to complete..."
    
    aws ecs wait services-stable \
        --cluster "$CLUSTER_NAME" \
        --services "$SERVICE_NAME" \
        --region "$AWS_REGION"
    
    log_success "Deployment completed successfully"
}

# Get service status
get_service_status() {
    log_info "Getting service status..."
    
    SERVICE_INFO=$(aws ecs describe-services \
        --cluster "$CLUSTER_NAME" \
        --services "$SERVICE_NAME" \
        --region "$AWS_REGION" \
        --query 'services[0]')
    
    RUNNING_COUNT=$(echo "$SERVICE_INFO" | jq -r '.runningCount')
    DESIRED_COUNT=$(echo "$SERVICE_INFO" | jq -r '.desiredCount')
    PENDING_COUNT=$(echo "$SERVICE_INFO" | jq -r '.pendingCount')
    
    log_info "Service Status:"
    log_info "  Running: $RUNNING_COUNT"
    log_info "  Desired: $DESIRED_COUNT"
    log_info "  Pending: $PENDING_COUNT"
    
    if [ "$RUNNING_COUNT" -eq "$DESIRED_COUNT" ] && [ "$PENDING_COUNT" -eq 0 ]; then
        log_success "Service is healthy and running"
    else
        log_warning "Service is not fully healthy yet"
    fi
}

# Main deployment function
main() {
    log_info "Starting ECS deployment process..."
    log_info "Cluster: $CLUSTER_NAME"
    log_info "Service: $SERVICE_NAME"
    log_info "Task Definition: $TASK_DEFINITION_NAME"
    log_info "Image Tag: $IMAGE_TAG"
    log_info "Desired Count: $DESIRED_COUNT"
    
    check_dependencies
    get_aws_account_id
    create_ecs_cluster
    create_task_execution_role
    create_log_group
    register_task_definition
    create_or_update_service
    wait_for_deployment
    get_service_status
    
    log_success "ECS deployment completed successfully!"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --region)
            AWS_REGION="$2"
            shift 2
            ;;
        --cluster)
            CLUSTER_NAME="$2"
            shift 2
            ;;
        --service)
            SERVICE_NAME="$2"
            shift 2
            ;;
        --task-definition)
            TASK_DEFINITION_NAME="$2"
            shift 2
            ;;
        --repository)
            ECR_REPOSITORY="$2"
            shift 2
            ;;
        --tag)
            IMAGE_TAG="$2"
            shift 2
            ;;
        --desired-count)
            DESIRED_COUNT="$2"
            shift 2
            ;;
        --subnets)
            SUBNET_IDS="$2"
            shift 2
            ;;
        --security-groups)
            SECURITY_GROUP_IDS="$2"
            shift 2
            ;;
        --target-group)
            TARGET_GROUP_ARN="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --region REGION              AWS region (default: us-east-1)"
            echo "  --cluster CLUSTER            ECS cluster name (default: airtable-whatsapp-cluster)"
            echo "  --service SERVICE            ECS service name (default: airtable-whatsapp-service)"
            echo "  --task-definition TASK       Task definition name (default: airtable-whatsapp-task)"
            echo "  --repository REPO            ECR repository name (default: airtable-whatsapp-agent)"
            echo "  --tag TAG                    Image tag (default: latest)"
            echo "  --desired-count COUNT        Desired task count (default: 2)"
            echo "  --subnets SUBNET_IDS         Comma-separated subnet IDs (required)"
            echo "  --security-groups SG_IDS     Comma-separated security group IDs (required)"
            echo "  --target-group ARN           Target group ARN for load balancer (optional)"
            echo "  --help                       Show this help message"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate required parameters
if [ -z "$SUBNET_IDS" ]; then
    log_error "Subnet IDs are required. Use --subnets option."
    exit 1
fi

if [ -z "$SECURITY_GROUP_IDS" ]; then
    log_error "Security group IDs are required. Use --security-groups option."
    exit 1
fi

# Run main function
main