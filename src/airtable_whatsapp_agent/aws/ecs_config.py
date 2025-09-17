"""
AWS ECS deployment configuration and task definitions.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import boto3
from botocore.exceptions import ClientError, BotoCoreError

from ..config import Settings


logger = logging.getLogger(__name__)


class LaunchType(Enum):
    """ECS launch types."""
    
    EC2 = "EC2"
    FARGATE = "FARGATE"
    EXTERNAL = "EXTERNAL"


class NetworkMode(Enum):
    """ECS network modes."""
    
    BRIDGE = "bridge"
    HOST = "host"
    AWS_VPC = "awsvpc"
    NONE = "none"


class LogDriver(Enum):
    """ECS log drivers."""
    
    JSON_FILE = "json-file"
    SYSLOG = "syslog"
    JOURNALD = "journald"
    GELF = "gelf"
    FLUENTD = "fluentd"
    AWSLOGS = "awslogs"
    SPLUNK = "splunk"
    AWSFIRELENS = "awsfirelens"


@dataclass
class ContainerDefinition:
    """ECS container definition."""
    
    name: str
    image: str
    memory: Optional[int] = None
    memory_reservation: Optional[int] = None
    cpu: Optional[int] = None
    essential: bool = True
    port_mappings: Optional[List[Dict[str, Any]]] = None
    environment: Optional[List[Dict[str, str]]] = None
    secrets: Optional[List[Dict[str, str]]] = None
    log_configuration: Optional[Dict[str, Any]] = None
    health_check: Optional[Dict[str, Any]] = None
    command: Optional[List[str]] = None
    entry_point: Optional[List[str]] = None
    working_directory: Optional[str] = None
    user: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to ECS container definition format."""
        definition = {
            "name": self.name,
            "image": self.image,
            "essential": self.essential
        }
        
        if self.memory:
            definition["memory"] = self.memory
        if self.memory_reservation:
            definition["memoryReservation"] = self.memory_reservation
        if self.cpu:
            definition["cpu"] = self.cpu
        if self.port_mappings:
            definition["portMappings"] = self.port_mappings
        if self.environment:
            definition["environment"] = self.environment
        if self.secrets:
            definition["secrets"] = self.secrets
        if self.log_configuration:
            definition["logConfiguration"] = self.log_configuration
        if self.health_check:
            definition["healthCheck"] = self.health_check
        if self.command:
            definition["command"] = self.command
        if self.entry_point:
            definition["entryPoint"] = self.entry_point
        if self.working_directory:
            definition["workingDirectory"] = self.working_directory
        if self.user:
            definition["user"] = self.user
            
        return definition


@dataclass
class ECSTaskDefinition:
    """ECS task definition configuration."""
    
    family: str
    containers: List[ContainerDefinition]
    task_role_arn: Optional[str] = None
    execution_role_arn: Optional[str] = None
    network_mode: NetworkMode = NetworkMode.AWS_VPC
    requires_compatibilities: List[LaunchType] = None
    cpu: Optional[str] = None
    memory: Optional[str] = None
    tags: Optional[List[Dict[str, str]]] = None
    
    def __post_init__(self):
        """Post-initialization setup."""
        if self.requires_compatibilities is None:
            self.requires_compatibilities = [LaunchType.FARGATE]
            
    def to_dict(self) -> Dict[str, Any]:
        """Convert to ECS task definition format."""
        definition = {
            "family": self.family,
            "containerDefinitions": [container.to_dict() for container in self.containers],
            "networkMode": self.network_mode.value,
            "requiresCompatibilities": [comp.value for comp in self.requires_compatibilities]
        }
        
        if self.task_role_arn:
            definition["taskRoleArn"] = self.task_role_arn
        if self.execution_role_arn:
            definition["executionRoleArn"] = self.execution_role_arn
        if self.cpu:
            definition["cpu"] = self.cpu
        if self.memory:
            definition["memory"] = self.memory
        if self.tags:
            definition["tags"] = self.tags
            
        return definition


class ECSDeploymentConfig:
    """ECS deployment configuration and management."""
    
    def __init__(self, settings: Settings):
        """Initialize ECS deployment configuration."""
        self.settings = settings
        self.region = settings.aws_region
        self.account_id = settings.aws_account_id
        
        # Initialize AWS clients
        self.ecs_client = boto3.client(
            'ecs',
            region_name=self.region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key
        )
        
        self.ec2_client = boto3.client(
            'ec2',
            region_name=self.region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key
        )
        
        self.logs_client = boto3.client(
            'logs',
            region_name=self.region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key
        )
        
        # Configuration
        self.cluster_name = f"{settings.app_name}-cluster"
        self.service_name = f"{settings.app_name}-service"
        self.task_family = f"{settings.app_name}-task"
        
    def create_main_task_definition(self) -> ECSTaskDefinition:
        """Create the main application task definition."""
        # Main application container
        main_container = ContainerDefinition(
            name="main-app",
            image=f"{self.account_id}.dkr.ecr.{self.region}.amazonaws.com/{self.settings.app_name}:latest",
            memory=1024,
            cpu=512,
            essential=True,
            port_mappings=[
                {
                    "containerPort": 8000,
                    "protocol": "tcp"
                }
            ],
            environment=[
                {"name": "ENVIRONMENT", "value": self.settings.environment},
                {"name": "AWS_REGION", "value": self.region},
                {"name": "LOG_LEVEL", "value": "INFO"}
            ],
            secrets=[
                {
                    "name": "OPENAI_API_KEY",
                    "valueFrom": f"arn:aws:secretsmanager:{self.region}:{self.account_id}:secret:openai-api-key"
                },
                {
                    "name": "WHATSAPP_ACCESS_TOKEN",
                    "valueFrom": f"arn:aws:secretsmanager:{self.region}:{self.account_id}:secret:whatsapp-access-token"
                },
                {
                    "name": "AIRTABLE_API_KEY",
                    "valueFrom": f"arn:aws:secretsmanager:{self.region}:{self.account_id}:secret:airtable-api-key"
                }
            ],
            log_configuration={
                "logDriver": LogDriver.AWSLOGS.value,
                "options": {
                    "awslogs-group": f"/ecs/{self.settings.app_name}",
                    "awslogs-region": self.region,
                    "awslogs-stream-prefix": "ecs"
                }
            },
            health_check={
                "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
                "interval": 30,
                "timeout": 5,
                "retries": 3,
                "startPeriod": 60
            }
        )
        
        # Sidecar container for monitoring
        monitoring_container = ContainerDefinition(
            name="monitoring",
            image="amazon/cloudwatch-agent:latest",
            memory=256,
            cpu=128,
            essential=False,
            environment=[
                {"name": "CW_CONFIG_CONTENT", "value": json.dumps(self._get_cloudwatch_config())}
            ],
            log_configuration={
                "logDriver": LogDriver.AWSLOGS.value,
                "options": {
                    "awslogs-group": f"/ecs/{self.settings.app_name}-monitoring",
                    "awslogs-region": self.region,
                    "awslogs-stream-prefix": "monitoring"
                }
            }
        )
        
        return ECSTaskDefinition(
            family=self.task_family,
            containers=[main_container, monitoring_container],
            task_role_arn=f"arn:aws:iam::{self.account_id}:role/{self.settings.app_name}-task-role",
            execution_role_arn=f"arn:aws:iam::{self.account_id}:role/{self.settings.app_name}-execution-role",
            network_mode=NetworkMode.AWS_VPC,
            requires_compatibilities=[LaunchType.FARGATE],
            cpu="1024",
            memory="2048",
            tags=[
                {"key": "Application", "value": self.settings.app_name},
                {"key": "Environment", "value": self.settings.environment},
                {"key": "Component", "value": "MainApp"}
            ]
        )
        
    def create_worker_task_definition(self) -> ECSTaskDefinition:
        """Create worker task definition for background jobs."""
        worker_container = ContainerDefinition(
            name="worker",
            image=f"{self.account_id}.dkr.ecr.{self.region}.amazonaws.com/{self.settings.app_name}-worker:latest",
            memory=512,
            cpu=256,
            essential=True,
            environment=[
                {"name": "ENVIRONMENT", "value": self.settings.environment},
                {"name": "AWS_REGION", "value": self.region},
                {"name": "WORKER_TYPE", "value": "background"},
                {"name": "LOG_LEVEL", "value": "INFO"}
            ],
            secrets=[
                {
                    "name": "OPENAI_API_KEY",
                    "valueFrom": f"arn:aws:secretsmanager:{self.region}:{self.account_id}:secret:openai-api-key"
                },
                {
                    "name": "AIRTABLE_API_KEY",
                    "valueFrom": f"arn:aws:secretsmanager:{self.region}:{self.account_id}:secret:airtable-api-key"
                }
            ],
            log_configuration={
                "logDriver": LogDriver.AWSLOGS.value,
                "options": {
                    "awslogs-group": f"/ecs/{self.settings.app_name}-worker",
                    "awslogs-region": self.region,
                    "awslogs-stream-prefix": "worker"
                }
            },
            command=["python", "-m", "airtable_whatsapp_agent.worker"]
        )
        
        return ECSTaskDefinition(
            family=f"{self.task_family}-worker",
            containers=[worker_container],
            task_role_arn=f"arn:aws:iam::{self.account_id}:role/{self.settings.app_name}-task-role",
            execution_role_arn=f"arn:aws:iam::{self.account_id}:role/{self.settings.app_name}-execution-role",
            network_mode=NetworkMode.AWS_VPC,
            requires_compatibilities=[LaunchType.FARGATE],
            cpu="512",
            memory="1024",
            tags=[
                {"key": "Application", "value": self.settings.app_name},
                {"key": "Environment", "value": self.settings.environment},
                {"key": "Component", "value": "Worker"}
            ]
        )
        
    def _get_cloudwatch_config(self) -> Dict[str, Any]:
        """Get CloudWatch agent configuration."""
        return {
            "metrics": {
                "namespace": f"{self.settings.app_name}/ECS",
                "metrics_collected": {
                    "cpu": {
                        "measurement": ["cpu_usage_idle", "cpu_usage_iowait", "cpu_usage_user", "cpu_usage_system"],
                        "metrics_collection_interval": 60
                    },
                    "disk": {
                        "measurement": ["used_percent"],
                        "metrics_collection_interval": 60,
                        "resources": ["*"]
                    },
                    "diskio": {
                        "measurement": ["io_time"],
                        "metrics_collection_interval": 60,
                        "resources": ["*"]
                    },
                    "mem": {
                        "measurement": ["mem_used_percent"],
                        "metrics_collection_interval": 60
                    },
                    "netstat": {
                        "measurement": ["tcp_established", "tcp_time_wait"],
                        "metrics_collection_interval": 60
                    }
                }
            },
            "logs": {
                "logs_collected": {
                    "files": {
                        "collect_list": [
                            {
                                "file_path": "/var/log/app/*.log",
                                "log_group_name": f"/ecs/{self.settings.app_name}/application",
                                "log_stream_name": "{instance_id}"
                            }
                        ]
                    }
                }
            }
        }
        
    async def register_task_definition(self, task_definition: ECSTaskDefinition) -> Optional[str]:
        """Register a task definition with ECS."""
        try:
            response = self.ecs_client.register_task_definition(**task_definition.to_dict())
            
            task_def_arn = response['taskDefinition']['taskDefinitionArn']
            logger.info(f"Registered task definition: {task_def_arn}")
            
            return task_def_arn
            
        except (ClientError, BotoCoreError) as e:
            logger.error(f"Error registering task definition: {str(e)}")
            return None
            
    async def create_cluster(self) -> Optional[str]:
        """Create ECS cluster."""
        try:
            response = self.ecs_client.create_cluster(
                clusterName=self.cluster_name,
                tags=[
                    {"key": "Application", "value": self.settings.app_name},
                    {"key": "Environment", "value": self.settings.environment}
                ],
                capacityProviders=["FARGATE"],
                defaultCapacityProviderStrategy=[
                    {
                        "capacityProvider": "FARGATE",
                        "weight": 1
                    }
                ]
            )
            
            cluster_arn = response['cluster']['clusterArn']
            logger.info(f"Created ECS cluster: {cluster_arn}")
            
            return cluster_arn
            
        except (ClientError, BotoCoreError) as e:
            logger.error(f"Error creating ECS cluster: {str(e)}")
            return None
            
    async def create_service(
        self,
        task_definition_arn: str,
        desired_count: int = 2,
        subnet_ids: List[str] = None,
        security_group_ids: List[str] = None
    ) -> Optional[str]:
        """Create ECS service."""
        try:
            # Get default VPC and subnets if not provided
            if not subnet_ids:
                subnet_ids = await self._get_default_subnets()
            if not security_group_ids:
                security_group_ids = await self._get_default_security_groups()
                
            service_config = {
                "cluster": self.cluster_name,
                "serviceName": self.service_name,
                "taskDefinition": task_definition_arn,
                "desiredCount": desired_count,
                "launchType": "FARGATE",
                "networkConfiguration": {
                    "awsvpcConfiguration": {
                        "subnets": subnet_ids,
                        "securityGroups": security_group_ids,
                        "assignPublicIp": "ENABLED"
                    }
                },
                "loadBalancers": [
                    {
                        "targetGroupArn": f"arn:aws:elasticloadbalancing:{self.region}:{self.account_id}:targetgroup/{self.settings.app_name}-tg",
                        "containerName": "main-app",
                        "containerPort": 8000
                    }
                ],
                "serviceRegistries": [
                    {
                        "registryArn": f"arn:aws:servicediscovery:{self.region}:{self.account_id}:service/{self.settings.app_name}-service"
                    }
                ],
                "tags": [
                    {"key": "Application", "value": self.settings.app_name},
                    {"key": "Environment", "value": self.settings.environment}
                ]
            }
            
            response = self.ecs_client.create_service(**service_config)
            
            service_arn = response['service']['serviceArn']
            logger.info(f"Created ECS service: {service_arn}")
            
            return service_arn
            
        except (ClientError, BotoCoreError) as e:
            logger.error(f"Error creating ECS service: {str(e)}")
            return None
            
    async def _get_default_subnets(self) -> List[str]:
        """Get default VPC subnets."""
        try:
            response = self.ec2_client.describe_subnets(
                Filters=[
                    {"Name": "default-for-az", "Values": ["true"]}
                ]
            )
            
            return [subnet['SubnetId'] for subnet in response['Subnets']]
            
        except (ClientError, BotoCoreError) as e:
            logger.error(f"Error getting default subnets: {str(e)}")
            return []
            
    async def _get_default_security_groups(self) -> List[str]:
        """Get default security groups."""
        try:
            response = self.ec2_client.describe_security_groups(
                Filters=[
                    {"Name": "group-name", "Values": ["default"]}
                ]
            )
            
            return [sg['GroupId'] for sg in response['SecurityGroups']]
            
        except (ClientError, BotoCoreError) as e:
            logger.error(f"Error getting default security groups: {str(e)}")
            return []
            
    async def create_log_groups(self):
        """Create CloudWatch log groups."""
        log_groups = [
            f"/ecs/{self.settings.app_name}",
            f"/ecs/{self.settings.app_name}-worker",
            f"/ecs/{self.settings.app_name}-monitoring"
        ]
        
        for log_group in log_groups:
            try:
                self.logs_client.create_log_group(
                    logGroupName=log_group,
                    tags={
                        "Application": self.settings.app_name,
                        "Environment": self.settings.environment
                    }
                )
                logger.info(f"Created log group: {log_group}")
                
            except ClientError as e:
                if e.response['Error']['Code'] != 'ResourceAlreadyExistsException':
                    logger.error(f"Error creating log group {log_group}: {str(e)}")
                    
    async def deploy_full_stack(self) -> Dict[str, Any]:
        """Deploy the complete ECS stack."""
        results = {}
        
        try:
            # Create log groups
            await self.create_log_groups()
            results["log_groups"] = "created"
            
            # Create cluster
            cluster_arn = await self.create_cluster()
            results["cluster"] = cluster_arn
            
            # Register main task definition
            main_task_def = self.create_main_task_definition()
            main_task_arn = await self.register_task_definition(main_task_def)
            results["main_task_definition"] = main_task_arn
            
            # Register worker task definition
            worker_task_def = self.create_worker_task_definition()
            worker_task_arn = await self.register_task_definition(worker_task_def)
            results["worker_task_definition"] = worker_task_arn
            
            # Create main service
            if main_task_arn:
                service_arn = await self.create_service(main_task_arn)
                results["service"] = service_arn
                
            return results
            
        except Exception as e:
            logger.error(f"Error deploying ECS stack: {str(e)}")
            results["error"] = str(e)
            return results
            
    def generate_deployment_template(self) -> Dict[str, Any]:
        """Generate CloudFormation template for deployment."""
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Description": f"ECS deployment for {self.settings.app_name}",
            "Parameters": {
                "Environment": {
                    "Type": "String",
                    "Default": self.settings.environment,
                    "Description": "Environment name"
                },
                "DesiredCount": {
                    "Type": "Number",
                    "Default": 2,
                    "Description": "Desired number of tasks"
                }
            },
            "Resources": {
                "ECSCluster": {
                    "Type": "AWS::ECS::Cluster",
                    "Properties": {
                        "ClusterName": self.cluster_name,
                        "CapacityProviders": ["FARGATE"],
                        "DefaultCapacityProviderStrategy": [
                            {
                                "CapacityProvider": "FARGATE",
                                "Weight": 1
                            }
                        ]
                    }
                },
                "TaskDefinition": {
                    "Type": "AWS::ECS::TaskDefinition",
                    "Properties": self.create_main_task_definition().to_dict()
                },
                "ECSService": {
                    "Type": "AWS::ECS::Service",
                    "Properties": {
                        "Cluster": {"Ref": "ECSCluster"},
                        "TaskDefinition": {"Ref": "TaskDefinition"},
                        "DesiredCount": {"Ref": "DesiredCount"},
                        "LaunchType": "FARGATE"
                    }
                }
            },
            "Outputs": {
                "ClusterName": {
                    "Description": "ECS Cluster Name",
                    "Value": {"Ref": "ECSCluster"}
                },
                "ServiceName": {
                    "Description": "ECS Service Name",
                    "Value": {"Ref": "ECSService"}
                }
            }
        }
        
        return template