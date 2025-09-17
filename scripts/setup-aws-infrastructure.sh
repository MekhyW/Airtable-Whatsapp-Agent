#!/bin/bash

# AWS Infrastructure Setup Script for Airtable WhatsApp Agent
# This script sets up the complete AWS infrastructure using CloudFormation

set -e

# Configuration
AWS_REGION="${AWS_REGION:-us-east-1}"
STACK_NAME="${STACK_NAME:-airtable-whatsapp-infrastructure}"
ENVIRONMENT="${ENVIRONMENT:-production}"
APP_NAME="${APP_NAME:-airtable-whatsapp-agent}"

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
    
    log_success "All dependencies are installed"
}

# Create CloudFormation template
create_cloudformation_template() {
    log_info "Creating CloudFormation template..."
    
    cat > /tmp/infrastructure.yaml << 'EOF'
AWSTemplateFormatVersion: '2010-09-09'
Description: 'Infrastructure for Airtable WhatsApp Agent'

Parameters:
  Environment:
    Type: String
    Default: production
    AllowedValues: [development, staging, production]
    Description: Environment name
  
  AppName:
    Type: String
    Default: airtable-whatsapp-agent
    Description: Application name

Resources:
  # VPC
  VPC:
    Type: AWS::EC2::VPC
    Properties:
      CidrBlock: 10.0.0.0/16
      EnableDnsHostnames: true
      EnableDnsSupport: true
      Tags:
        - Key: Name
          Value: !Sub '${AppName}-vpc'
        - Key: Environment
          Value: !Ref Environment

  # Internet Gateway
  InternetGateway:
    Type: AWS::EC2::InternetGateway
    Properties:
      Tags:
        - Key: Name
          Value: !Sub '${AppName}-igw'
        - Key: Environment
          Value: !Ref Environment

  InternetGatewayAttachment:
    Type: AWS::EC2::VPCGatewayAttachment
    Properties:
      InternetGatewayId: !Ref InternetGateway
      VpcId: !Ref VPC

  # Public Subnets
  PublicSubnet1:
    Type: AWS::EC2::Subnet
    Properties:
      VpcId: !Ref VPC
      AvailabilityZone: !Select [0, !GetAZs '']
      CidrBlock: 10.0.1.0/24
      MapPublicIpOnLaunch: true
      Tags:
        - Key: Name
          Value: !Sub '${AppName}-public-subnet-1'
        - Key: Environment
          Value: !Ref Environment

  PublicSubnet2:
    Type: AWS::EC2::Subnet
    Properties:
      VpcId: !Ref VPC
      AvailabilityZone: !Select [1, !GetAZs '']
      CidrBlock: 10.0.2.0/24
      MapPublicIpOnLaunch: true
      Tags:
        - Key: Name
          Value: !Sub '${AppName}-public-subnet-2'
        - Key: Environment
          Value: !Ref Environment

  # Private Subnets
  PrivateSubnet1:
    Type: AWS::EC2::Subnet
    Properties:
      VpcId: !Ref VPC
      AvailabilityZone: !Select [0, !GetAZs '']
      CidrBlock: 10.0.3.0/24
      Tags:
        - Key: Name
          Value: !Sub '${AppName}-private-subnet-1'
        - Key: Environment
          Value: !Ref Environment

  PrivateSubnet2:
    Type: AWS::EC2::Subnet
    Properties:
      VpcId: !Ref VPC
      AvailabilityZone: !Select [1, !GetAZs '']
      CidrBlock: 10.0.4.0/24
      Tags:
        - Key: Name
          Value: !Sub '${AppName}-private-subnet-2'
        - Key: Environment
          Value: !Ref Environment

  # NAT Gateways
  NatGateway1EIP:
    Type: AWS::EC2::EIP
    DependsOn: InternetGatewayAttachment
    Properties:
      Domain: vpc
      Tags:
        - Key: Name
          Value: !Sub '${AppName}-nat-eip-1'

  NatGateway2EIP:
    Type: AWS::EC2::EIP
    DependsOn: InternetGatewayAttachment
    Properties:
      Domain: vpc
      Tags:
        - Key: Name
          Value: !Sub '${AppName}-nat-eip-2'

  NatGateway1:
    Type: AWS::EC2::NatGateway
    Properties:
      AllocationId: !GetAtt NatGateway1EIP.AllocationId
      SubnetId: !Ref PublicSubnet1
      Tags:
        - Key: Name
          Value: !Sub '${AppName}-nat-1'

  NatGateway2:
    Type: AWS::EC2::NatGateway
    Properties:
      AllocationId: !GetAtt NatGateway2EIP.AllocationId
      SubnetId: !Ref PublicSubnet2
      Tags:
        - Key: Name
          Value: !Sub '${AppName}-nat-2'

  # Route Tables
  PublicRouteTable:
    Type: AWS::EC2::RouteTable
    Properties:
      VpcId: !Ref VPC
      Tags:
        - Key: Name
          Value: !Sub '${AppName}-public-routes'
        - Key: Environment
          Value: !Ref Environment

  DefaultPublicRoute:
    Type: AWS::EC2::Route
    DependsOn: InternetGatewayAttachment
    Properties:
      RouteTableId: !Ref PublicRouteTable
      DestinationCidrBlock: 0.0.0.0/0
      GatewayId: !Ref InternetGateway

  PublicSubnet1RouteTableAssociation:
    Type: AWS::EC2::SubnetRouteTableAssociation
    Properties:
      RouteTableId: !Ref PublicRouteTable
      SubnetId: !Ref PublicSubnet1

  PublicSubnet2RouteTableAssociation:
    Type: AWS::EC2::SubnetRouteTableAssociation
    Properties:
      RouteTableId: !Ref PublicRouteTable
      SubnetId: !Ref PublicSubnet2

  PrivateRouteTable1:
    Type: AWS::EC2::RouteTable
    Properties:
      VpcId: !Ref VPC
      Tags:
        - Key: Name
          Value: !Sub '${AppName}-private-routes-1'
        - Key: Environment
          Value: !Ref Environment

  DefaultPrivateRoute1:
    Type: AWS::EC2::Route
    Properties:
      RouteTableId: !Ref PrivateRouteTable1
      DestinationCidrBlock: 0.0.0.0/0
      NatGatewayId: !Ref NatGateway1

  PrivateSubnet1RouteTableAssociation:
    Type: AWS::EC2::SubnetRouteTableAssociation
    Properties:
      RouteTableId: !Ref PrivateRouteTable1
      SubnetId: !Ref PrivateSubnet1

  PrivateRouteTable2:
    Type: AWS::EC2::RouteTable
    Properties:
      VpcId: !Ref VPC
      Tags:
        - Key: Name
          Value: !Sub '${AppName}-private-routes-2'
        - Key: Environment
          Value: !Ref Environment

  DefaultPrivateRoute2:
    Type: AWS::EC2::Route
    Properties:
      RouteTableId: !Ref PrivateRouteTable2
      DestinationCidrBlock: 0.0.0.0/0
      NatGatewayId: !Ref NatGateway2

  PrivateSubnet2RouteTableAssociation:
    Type: AWS::EC2::SubnetRouteTableAssociation
    Properties:
      RouteTableId: !Ref PrivateRouteTable2
      SubnetId: !Ref PrivateSubnet2

  # Security Groups
  ALBSecurityGroup:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupName: !Sub '${AppName}-alb-sg'
      GroupDescription: Security group for Application Load Balancer
      VpcId: !Ref VPC
      SecurityGroupIngress:
        - IpProtocol: tcp
          FromPort: 80
          ToPort: 80
          CidrIp: 0.0.0.0/0
        - IpProtocol: tcp
          FromPort: 443
          ToPort: 443
          CidrIp: 0.0.0.0/0
      Tags:
        - Key: Name
          Value: !Sub '${AppName}-alb-sg'
        - Key: Environment
          Value: !Ref Environment

  ECSSecurityGroup:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupName: !Sub '${AppName}-ecs-sg'
      GroupDescription: Security group for ECS tasks
      VpcId: !Ref VPC
      SecurityGroupIngress:
        - IpProtocol: tcp
          FromPort: 8000
          ToPort: 8000
          SourceSecurityGroupId: !Ref ALBSecurityGroup
      Tags:
        - Key: Name
          Value: !Sub '${AppName}-ecs-sg'
        - Key: Environment
          Value: !Ref Environment

  # Application Load Balancer
  ApplicationLoadBalancer:
    Type: AWS::ElasticLoadBalancingV2::LoadBalancer
    Properties:
      Name: !Sub '${AppName}-alb'
      Scheme: internet-facing
      Type: application
      Subnets:
        - !Ref PublicSubnet1
        - !Ref PublicSubnet2
      SecurityGroups:
        - !Ref ALBSecurityGroup
      Tags:
        - Key: Name
          Value: !Sub '${AppName}-alb'
        - Key: Environment
          Value: !Ref Environment

  # Target Group
  TargetGroup:
    Type: AWS::ElasticLoadBalancingV2::TargetGroup
    Properties:
      Name: !Sub '${AppName}-tg'
      Port: 8000
      Protocol: HTTP
      VpcId: !Ref VPC
      TargetType: ip
      HealthCheckPath: /health
      HealthCheckProtocol: HTTP
      HealthCheckIntervalSeconds: 30
      HealthCheckTimeoutSeconds: 5
      HealthyThresholdCount: 2
      UnhealthyThresholdCount: 3
      Tags:
        - Key: Name
          Value: !Sub '${AppName}-tg'
        - Key: Environment
          Value: !Ref Environment

  # ALB Listener
  ALBListener:
    Type: AWS::ElasticLoadBalancingV2::Listener
    Properties:
      DefaultActions:
        - Type: forward
          TargetGroupArn: !Ref TargetGroup
      LoadBalancerArn: !Ref ApplicationLoadBalancer
      Port: 80
      Protocol: HTTP

  # ECS Cluster
  ECSCluster:
    Type: AWS::ECS::Cluster
    Properties:
      ClusterName: !Sub '${AppName}-cluster'
      CapacityProviders:
        - FARGATE
        - FARGATE_SPOT
      DefaultCapacityProviderStrategy:
        - CapacityProvider: FARGATE
          Weight: 1
      ClusterSettings:
        - Name: containerInsights
          Value: enabled
      Tags:
        - Key: Name
          Value: !Sub '${AppName}-cluster'
        - Key: Environment
          Value: !Ref Environment

  # ECR Repository
  ECRRepository:
    Type: AWS::ECR::Repository
    Properties:
      RepositoryName: !Ref AppName
      ImageScanningConfiguration:
        ScanOnPush: true
      EncryptionConfiguration:
        EncryptionType: AES256
      LifecyclePolicy:
        LifecyclePolicyText: |
          {
            "rules": [
              {
                "rulePriority": 1,
                "description": "Keep last 10 images",
                "selection": {
                  "tagStatus": "tagged",
                  "countType": "imageCountMoreThan",
                  "countNumber": 10
                },
                "action": {
                  "type": "expire"
                }
              }
            ]
          }
      Tags:
        - Key: Name
          Value: !Sub '${AppName}-ecr'
        - Key: Environment
          Value: !Ref Environment

  # IAM Role for ECS Task Execution
  ECSTaskExecutionRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: !Sub '${AppName}-ecs-execution-role'
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: ecs-tasks.amazonaws.com
            Action: sts:AssumeRole
      ManagedPolicyArns:
        - arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
        - arn:aws:iam::aws:policy/CloudWatchLogsFullAccess
      Policies:
        - PolicyName: SSMParameterAccess
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - ssm:GetParameter
                  - ssm:GetParameters
                  - ssm:GetParametersByPath
                Resource: !Sub 'arn:aws:ssm:${AWS::Region}:${AWS::AccountId}:parameter/${AppName}/*'
      Tags:
        - Key: Name
          Value: !Sub '${AppName}-ecs-execution-role'
        - Key: Environment
          Value: !Ref Environment

  # IAM Role for ECS Task
  ECSTaskRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: !Sub '${AppName}-ecs-task-role'
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: ecs-tasks.amazonaws.com
            Action: sts:AssumeRole
      Policies:
        - PolicyName: ApplicationPermissions
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - logs:CreateLogGroup
                  - logs:CreateLogStream
                  - logs:PutLogEvents
                  - cloudwatch:PutMetricData
                  - events:PutEvents
                  - ssm:GetParameter
                  - ssm:GetParameters
                  - ssm:PutParameter
                Resource: '*'
      Tags:
        - Key: Name
          Value: !Sub '${AppName}-ecs-task-role'
        - Key: Environment
          Value: !Ref Environment

  # CloudWatch Log Group
  CloudWatchLogGroup:
    Type: AWS::Logs::LogGroup
    Properties:
      LogGroupName: !Sub '/aws/ecs/${AppName}'
      RetentionInDays: 30

  # EventBridge Rule for scheduled tasks
  ScheduledTaskRule:
    Type: AWS::Events::Rule
    Properties:
      Name: !Sub '${AppName}-scheduled-tasks'
      Description: 'Scheduled tasks for Airtable WhatsApp Agent'
      ScheduleExpression: 'rate(1 hour)'
      State: ENABLED
      Targets:
        - Arn: !GetAtt ECSCluster.Arn
          Id: 'ScheduledTaskTarget'
          RoleArn: !GetAtt EventBridgeRole.Arn
          EcsParameters:
            TaskDefinitionArn: !Sub 'arn:aws:ecs:${AWS::Region}:${AWS::AccountId}:task-definition/${AppName}-scheduled:1'
            LaunchType: FARGATE
            NetworkConfiguration:
              AwsVpcConfiguration:
                Subnets:
                  - !Ref PrivateSubnet1
                  - !Ref PrivateSubnet2
                SecurityGroups:
                  - !Ref ECSSecurityGroup
                AssignPublicIp: DISABLED

  # IAM Role for EventBridge
  EventBridgeRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: !Sub '${AppName}-eventbridge-role'
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: events.amazonaws.com
            Action: sts:AssumeRole
      Policies:
        - PolicyName: ECSTaskExecution
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - ecs:RunTask
                Resource: !Sub 'arn:aws:ecs:${AWS::Region}:${AWS::AccountId}:task-definition/${AppName}-scheduled:*'
              - Effect: Allow
                Action:
                  - iam:PassRole
                Resource:
                  - !GetAtt ECSTaskExecutionRole.Arn
                  - !GetAtt ECSTaskRole.Arn

Outputs:
  VPCId:
    Description: VPC ID
    Value: !Ref VPC
    Export:
      Name: !Sub '${AWS::StackName}-VPC-ID'

  PublicSubnets:
    Description: Public subnet IDs
    Value: !Join [',', [!Ref PublicSubnet1, !Ref PublicSubnet2]]
    Export:
      Name: !Sub '${AWS::StackName}-PUBLIC-SUBNETS'

  PrivateSubnets:
    Description: Private subnet IDs
    Value: !Join [',', [!Ref PrivateSubnet1, !Ref PrivateSubnet2]]
    Export:
      Name: !Sub '${AWS::StackName}-PRIVATE-SUBNETS'

  ECSSecurityGroup:
    Description: ECS Security Group ID
    Value: !Ref ECSSecurityGroup
    Export:
      Name: !Sub '${AWS::StackName}-ECS-SG'

  ALBSecurityGroup:
    Description: ALB Security Group ID
    Value: !Ref ALBSecurityGroup
    Export:
      Name: !Sub '${AWS::StackName}-ALB-SG'

  LoadBalancerDNS:
    Description: Load Balancer DNS Name
    Value: !GetAtt ApplicationLoadBalancer.DNSName
    Export:
      Name: !Sub '${AWS::StackName}-ALB-DNS'

  TargetGroupArn:
    Description: Target Group ARN
    Value: !Ref TargetGroup
    Export:
      Name: !Sub '${AWS::StackName}-TG-ARN'

  ECSClusterName:
    Description: ECS Cluster Name
    Value: !Ref ECSCluster
    Export:
      Name: !Sub '${AWS::StackName}-ECS-CLUSTER'

  ECRRepositoryURI:
    Description: ECR Repository URI
    Value: !Sub '${AWS::AccountId}.dkr.ecr.${AWS::Region}.amazonaws.com/${ECRRepository}'
    Export:
      Name: !Sub '${AWS::StackName}-ECR-URI'

  TaskExecutionRoleArn:
    Description: ECS Task Execution Role ARN
    Value: !GetAtt ECSTaskExecutionRole.Arn
    Export:
      Name: !Sub '${AWS::StackName}-TASK-EXECUTION-ROLE'

  TaskRoleArn:
    Description: ECS Task Role ARN
    Value: !GetAtt ECSTaskRole.Arn
    Export:
      Name: !Sub '${AWS::StackName}-TASK-ROLE'
EOF

    log_success "CloudFormation template created"
}

# Deploy CloudFormation stack
deploy_stack() {
    log_info "Deploying CloudFormation stack..."
    
    # Check if stack exists
    if aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$AWS_REGION" &> /dev/null; then
        log_info "Stack exists, updating..."
        
        aws cloudformation update-stack \
            --stack-name "$STACK_NAME" \
            --template-body file:///tmp/infrastructure.yaml \
            --parameters ParameterKey=Environment,ParameterValue="$ENVIRONMENT" \
                        ParameterKey=AppName,ParameterValue="$APP_NAME" \
            --capabilities CAPABILITY_NAMED_IAM \
            --region "$AWS_REGION"
        
        log_info "Waiting for stack update to complete..."
        aws cloudformation wait stack-update-complete \
            --stack-name "$STACK_NAME" \
            --region "$AWS_REGION"
    else
        log_info "Creating new stack..."
        
        aws cloudformation create-stack \
            --stack-name "$STACK_NAME" \
            --template-body file:///tmp/infrastructure.yaml \
            --parameters ParameterKey=Environment,ParameterValue="$ENVIRONMENT" \
                        ParameterKey=AppName,ParameterValue="$APP_NAME" \
            --capabilities CAPABILITY_NAMED_IAM \
            --region "$AWS_REGION" \
            --tags Key=Environment,Value="$ENVIRONMENT" \
                   Key=Application,Value="$APP_NAME"
        
        log_info "Waiting for stack creation to complete..."
        aws cloudformation wait stack-create-complete \
            --stack-name "$STACK_NAME" \
            --region "$AWS_REGION"
    fi
    
    log_success "CloudFormation stack deployed successfully"
}

# Get stack outputs
get_stack_outputs() {
    log_info "Getting stack outputs..."
    
    OUTPUTS=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$AWS_REGION" \
        --query 'Stacks[0].Outputs')
    
    echo "$OUTPUTS" | jq -r '.[] | "\(.OutputKey): \(.OutputValue)"'
    
    # Save outputs to file
    echo "$OUTPUTS" > /tmp/stack-outputs.json
    log_success "Stack outputs saved to /tmp/stack-outputs.json"
}

# Create SSM parameters for secrets
create_ssm_parameters() {
    log_info "Creating SSM parameters for secrets..."
    
    PARAMETERS=(
        "openai-api-key:OPENAI_API_KEY:SecureString"
        "airtable-api-key:AIRTABLE_API_KEY:SecureString"
        "whatsapp-access-token:WHATSAPP_ACCESS_TOKEN:SecureString"
        "webhook-verify-token:WEBHOOK_VERIFY_TOKEN:SecureString"
        "jwt-secret-key:JWT_SECRET_KEY:SecureString"
        "encryption-key:ENCRYPTION_KEY:SecureString"
    )
    
    for param in "${PARAMETERS[@]}"; do
        IFS=':' read -r param_name env_var param_type <<< "$param"
        
        # Check if parameter exists
        if aws ssm get-parameter --name "/$APP_NAME/$param_name" --region "$AWS_REGION" &> /dev/null; then
            log_warning "Parameter /$APP_NAME/$param_name already exists"
        else
            # Generate a placeholder value
            placeholder_value="CHANGE_ME_$(openssl rand -hex 16)"
            
            aws ssm put-parameter \
                --name "/$APP_NAME/$param_name" \
                --value "$placeholder_value" \
                --type "$param_type" \
                --description "Secret for $APP_NAME - $env_var" \
                --region "$AWS_REGION" \
                --tags Key=Application,Value="$APP_NAME" Key=Environment,Value="$ENVIRONMENT"
            
            log_warning "Created parameter /$APP_NAME/$param_name with placeholder value. Please update with actual value."
        fi
    done
    
    log_success "SSM parameters created"
}

# Main function
main() {
    log_info "Starting AWS infrastructure setup..."
    log_info "Stack Name: $STACK_NAME"
    log_info "Environment: $ENVIRONMENT"
    log_info "App Name: $APP_NAME"
    log_info "Region: $AWS_REGION"
    
    check_dependencies
    create_cloudformation_template
    deploy_stack
    get_stack_outputs
    create_ssm_parameters
    
    log_success "AWS infrastructure setup completed successfully!"
    log_info "Next steps:"
    log_info "1. Update SSM parameters with actual secret values"
    log_info "2. Build and push Docker image to ECR"
    log_info "3. Deploy ECS service"
    
    # Clean up
    rm -f /tmp/infrastructure.yaml
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --region)
            AWS_REGION="$2"
            shift 2
            ;;
        --stack-name)
            STACK_NAME="$2"
            shift 2
            ;;
        --environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --app-name)
            APP_NAME="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --region REGION        AWS region (default: us-east-1)"
            echo "  --stack-name NAME      CloudFormation stack name (default: airtable-whatsapp-infrastructure)"
            echo "  --environment ENV      Environment name (default: production)"
            echo "  --app-name NAME        Application name (default: airtable-whatsapp-agent)"
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