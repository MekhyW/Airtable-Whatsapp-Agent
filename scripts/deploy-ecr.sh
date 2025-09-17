#!/bin/bash

# AWS ECR Deployment Script for Airtable WhatsApp Agent
# This script builds, tags, and pushes the Docker image to AWS ECR

set -e

# Configuration
AWS_REGION="${AWS_REGION:-us-east-1}"
ECR_REPOSITORY="${ECR_REPOSITORY:-airtable-whatsapp-agent}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
DOCKERFILE="${DOCKERFILE:-Dockerfile}"

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
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install it first."
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

# Create ECR repository if it doesn't exist
create_ecr_repository() {
    log_info "Checking if ECR repository exists..."
    
    if aws ecr describe-repositories --repository-names "$ECR_REPOSITORY" --region "$AWS_REGION" &> /dev/null; then
        log_success "ECR repository '$ECR_REPOSITORY' already exists"
    else
        log_info "Creating ECR repository '$ECR_REPOSITORY'..."
        aws ecr create-repository \
            --repository-name "$ECR_REPOSITORY" \
            --region "$AWS_REGION" \
            --image-scanning-configuration scanOnPush=true \
            --encryption-configuration encryptionType=AES256
        
        log_success "ECR repository '$ECR_REPOSITORY' created successfully"
    fi
}

# Login to ECR
ecr_login() {
    log_info "Logging in to ECR..."
    aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"
    log_success "Successfully logged in to ECR"
}

# Build Docker image
build_image() {
    log_info "Building Docker image..."
    
    # Build with build args for optimization
    docker build \
        --file "$DOCKERFILE" \
        --tag "$ECR_REPOSITORY:$IMAGE_TAG" \
        --tag "$ECR_REPOSITORY:latest" \
        --build-arg BUILDKIT_INLINE_CACHE=1 \
        --cache-from "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY:latest" \
        .
    
    log_success "Docker image built successfully"
}

# Tag image for ECR
tag_image() {
    log_info "Tagging image for ECR..."
    
    ECR_URI="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY"
    
    docker tag "$ECR_REPOSITORY:$IMAGE_TAG" "$ECR_URI:$IMAGE_TAG"
    docker tag "$ECR_REPOSITORY:latest" "$ECR_URI:latest"
    
    # Add timestamp tag
    TIMESTAMP=$(date +%Y%m%d-%H%M%S)
    docker tag "$ECR_REPOSITORY:$IMAGE_TAG" "$ECR_URI:$TIMESTAMP"
    
    log_success "Image tagged for ECR"
}

# Push image to ECR
push_image() {
    log_info "Pushing image to ECR..."
    
    ECR_URI="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY"
    
    docker push "$ECR_URI:$IMAGE_TAG"
    docker push "$ECR_URI:latest"
    docker push "$ECR_URI:$TIMESTAMP"
    
    log_success "Image pushed to ECR successfully"
    log_info "Image URI: $ECR_URI:$IMAGE_TAG"
}

# Clean up local images (optional)
cleanup() {
    if [ "$CLEANUP" = "true" ]; then
        log_info "Cleaning up local images..."
        
        docker rmi "$ECR_REPOSITORY:$IMAGE_TAG" || true
        docker rmi "$ECR_REPOSITORY:latest" || true
        docker rmi "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY:$IMAGE_TAG" || true
        docker rmi "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY:latest" || true
        docker rmi "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY:$TIMESTAMP" || true
        
        log_success "Local images cleaned up"
    fi
}

# Scan image for vulnerabilities
scan_image() {
    if [ "$SCAN_IMAGE" = "true" ]; then
        log_info "Starting image vulnerability scan..."
        
        aws ecr start-image-scan \
            --repository-name "$ECR_REPOSITORY" \
            --image-id imageTag="$IMAGE_TAG" \
            --region "$AWS_REGION" || true
        
        log_info "Vulnerability scan initiated. Check ECR console for results."
    fi
}

# Main deployment function
main() {
    log_info "Starting ECR deployment process..."
    log_info "Repository: $ECR_REPOSITORY"
    log_info "Tag: $IMAGE_TAG"
    log_info "Region: $AWS_REGION"
    
    check_dependencies
    get_aws_account_id
    create_ecr_repository
    ecr_login
    build_image
    tag_image
    push_image
    scan_image
    cleanup
    
    log_success "ECR deployment completed successfully!"
    log_info "Image URI: $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY:$IMAGE_TAG"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --region)
            AWS_REGION="$2"
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
        --dockerfile)
            DOCKERFILE="$2"
            shift 2
            ;;
        --cleanup)
            CLEANUP="true"
            shift
            ;;
        --scan)
            SCAN_IMAGE="true"
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --region REGION        AWS region (default: us-east-1)"
            echo "  --repository REPO      ECR repository name (default: airtable-whatsapp-agent)"
            echo "  --tag TAG              Image tag (default: latest)"
            echo "  --dockerfile FILE      Dockerfile path (default: Dockerfile)"
            echo "  --cleanup              Clean up local images after push"
            echo "  --scan                 Start vulnerability scan after push"
            echo "  --help                 Show this help message"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Run main function
main