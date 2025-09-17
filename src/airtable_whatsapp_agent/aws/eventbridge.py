"""
AWS EventBridge integration for scheduled tasks and event-driven workflows.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable, Union
from enum import Enum
from dataclasses import dataclass, asdict
import asyncio
import boto3
from botocore.exceptions import ClientError, BotoCoreError

from ..config import Settings


logger = logging.getLogger(__name__)


class ScheduleType(Enum):
    """Types of schedule expressions."""
    
    RATE = "rate"
    CRON = "cron"
    ONE_TIME = "one_time"


class TaskStatus(Enum):
    """Status of scheduled tasks."""
    
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class ScheduledTask:
    """Scheduled task configuration."""
    
    name: str
    description: str
    schedule_expression: str
    schedule_type: ScheduleType
    target_function: str
    payload: Optional[Dict[str, Any]] = None
    enabled: bool = True
    retry_attempts: int = 3
    timeout_minutes: int = 15
    tags: Optional[Dict[str, str]] = None
    
    def to_eventbridge_rule(self) -> Dict[str, Any]:
        """Convert to EventBridge rule configuration."""
        rule_config = {
            "Name": self.name,
            "Description": self.description,
            "ScheduleExpression": self.schedule_expression,
            "State": "ENABLED" if self.enabled else "DISABLED"
        }
        
        if self.tags:
            rule_config["Tags"] = [
                {"Key": k, "Value": v} for k, v in self.tags.items()
            ]
            
        return rule_config
        
    def to_target_config(self, target_arn: str) -> Dict[str, Any]:
        """Convert to EventBridge target configuration."""
        target_config = {
            "Id": f"{self.name}-target",
            "Arn": target_arn,
            "Input": json.dumps({
                "task_name": self.name,
                "function": self.target_function,
                "payload": self.payload or {},
                "retry_attempts": self.retry_attempts,
                "timeout_minutes": self.timeout_minutes
            })
        }
        
        return target_config


class EventBridgeScheduler:
    """AWS EventBridge scheduler for managing scheduled tasks."""
    
    def __init__(self, settings: Settings):
        """Initialize EventBridge scheduler."""
        self.settings = settings
        self.region = settings.aws_region
        self.account_id = settings.aws_account_id
        
        # Initialize AWS clients
        self.eventbridge_client = boto3.client(
            'events',
            region_name=self.region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key
        )
        
        self.lambda_client = boto3.client(
            'lambda',
            region_name=self.region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key
        )
        
        # Task registry
        self.tasks: Dict[str, ScheduledTask] = {}
        self.task_handlers: Dict[str, Callable] = {}
        
        # Default scheduled tasks
        self._register_default_tasks()
        
    def _register_default_tasks(self):
        """Register default scheduled tasks."""
        default_tasks = [
            ScheduledTask(
                name="cleanup-old-audit-logs",
                description="Clean up old audit log entries",
                schedule_expression="rate(1 day)",
                schedule_type=ScheduleType.RATE,
                target_function="cleanup_audit_logs",
                payload={"days_to_keep": 90},
                tags={"Type": "Maintenance", "Component": "Security"}
            ),
            ScheduledTask(
                name="sync-airtable-data",
                description="Sync data with Airtable",
                schedule_expression="rate(30 minutes)",
                schedule_type=ScheduleType.RATE,
                target_function="sync_airtable_data",
                tags={"Type": "DataSync", "Component": "Airtable"}
            ),
            ScheduledTask(
                name="health-check-services",
                description="Perform health checks on external services",
                schedule_expression="rate(5 minutes)",
                schedule_type=ScheduleType.RATE,
                target_function="health_check_services",
                tags={"Type": "Monitoring", "Component": "HealthCheck"}
            ),
            ScheduledTask(
                name="rotate-credentials",
                description="Rotate API credentials and tokens",
                schedule_expression="cron(0 2 * * ? *)",  # Daily at 2 AM
                schedule_type=ScheduleType.CRON,
                target_function="rotate_credentials",
                tags={"Type": "Security", "Component": "Credentials"}
            ),
            ScheduledTask(
                name="generate-daily-report",
                description="Generate daily activity report",
                schedule_expression="cron(0 8 * * ? *)",  # Daily at 8 AM
                schedule_type=ScheduleType.CRON,
                target_function="generate_daily_report",
                tags={"Type": "Reporting", "Component": "Analytics"}
            )
        ]
        
        for task in default_tasks:
            self.register_task(task)
            
    def register_task(self, task: ScheduledTask):
        """Register a scheduled task."""
        self.tasks[task.name] = task
        logger.info(f"Registered scheduled task: {task.name}")
        
    def register_handler(self, function_name: str, handler: Callable):
        """Register a task handler function."""
        self.task_handlers[function_name] = handler
        logger.info(f"Registered task handler: {function_name}")
        
    async def create_schedule(self, task_name: str) -> bool:
        """Create EventBridge schedule for a task."""
        if task_name not in self.tasks:
            logger.error(f"Task not found: {task_name}")
            return False
            
        task = self.tasks[task_name]
        
        try:
            # Create EventBridge rule
            rule_config = task.to_eventbridge_rule()
            
            response = self.eventbridge_client.put_rule(**rule_config)
            rule_arn = response['RuleArn']
            
            logger.info(f"Created EventBridge rule: {rule_arn}")
            
            # Create Lambda function if it doesn't exist
            lambda_arn = await self._ensure_lambda_function()
            
            # Add target to rule
            target_config = task.to_target_config(lambda_arn)
            
            self.eventbridge_client.put_targets(
                Rule=task.name,
                Targets=[target_config]
            )
            
            # Add permission for EventBridge to invoke Lambda
            await self._add_lambda_permission(task.name, rule_arn)
            
            logger.info(f"Successfully created schedule for task: {task_name}")
            return True
            
        except (ClientError, BotoCoreError) as e:
            logger.error(f"Error creating schedule for {task_name}: {str(e)}")
            return False
            
    async def _ensure_lambda_function(self) -> str:
        """Ensure Lambda function exists for task execution."""
        function_name = f"{self.settings.app_name}-scheduler"
        
        try:
            # Check if function exists
            response = self.lambda_client.get_function(FunctionName=function_name)
            return response['Configuration']['FunctionArn']
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                # Function doesn't exist, create it
                return await self._create_lambda_function(function_name)
            else:
                raise
                
    async def _create_lambda_function(self, function_name: str) -> str:
        """Create Lambda function for task execution."""
        # Lambda function code
        lambda_code = '''
import json
import boto3
import logging
from typing import Dict, Any

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """Handle scheduled task execution."""
    try:
        task_name = event.get('task_name')
        function = event.get('function')
        payload = event.get('payload', {})
        
        logger.info(f"Executing scheduled task: {task_name}")
        
        # Here you would implement the actual task execution logic
        # This could involve calling your application's API endpoints
        # or executing specific functions
        
        result = {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Successfully executed task: {task_name}',
                'function': function,
                'payload': payload
            })
        }
        
        logger.info(f"Task {task_name} completed successfully")
        return result
        
    except Exception as e:
        logger.error(f"Error executing task: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'task_name': event.get('task_name', 'unknown')
            })
        }
'''
        
        try:
            response = self.lambda_client.create_function(
                FunctionName=function_name,
                Runtime='python3.9',
                Role=f"arn:aws:iam::{self.account_id}:role/lambda-execution-role",
                Handler='index.lambda_handler',
                Code={'ZipFile': lambda_code.encode()},
                Description='Scheduled task executor for Airtable WhatsApp Agent',
                Timeout=900,  # 15 minutes
                MemorySize=256,
                Tags={
                    'Application': self.settings.app_name,
                    'Component': 'Scheduler',
                    'Environment': self.settings.environment
                }
            )
            
            return response['FunctionArn']
            
        except (ClientError, BotoCoreError) as e:
            logger.error(f"Error creating Lambda function: {str(e)}")
            raise
            
    async def _add_lambda_permission(self, rule_name: str, rule_arn: str):
        """Add permission for EventBridge to invoke Lambda."""
        function_name = f"{self.settings.app_name}-scheduler"
        
        try:
            self.lambda_client.add_permission(
                FunctionName=function_name,
                StatementId=f"allow-eventbridge-{rule_name}",
                Action='lambda:InvokeFunction',
                Principal='events.amazonaws.com',
                SourceArn=rule_arn
            )
        except ClientError as e:
            if e.response['Error']['Code'] != 'ResourceConflictException':
                # Ignore if permission already exists
                raise
                
    async def update_schedule(self, task_name: str, **updates) -> bool:
        """Update an existing schedule."""
        if task_name not in self.tasks:
            logger.error(f"Task not found: {task_name}")
            return False
            
        # Update task configuration
        task = self.tasks[task_name]
        for key, value in updates.items():
            if hasattr(task, key):
                setattr(task, key, value)
                
        # Recreate the schedule
        await self.delete_schedule(task_name)
        return await self.create_schedule(task_name)
        
    async def delete_schedule(self, task_name: str) -> bool:
        """Delete a schedule."""
        try:
            # Remove targets first
            self.eventbridge_client.remove_targets(
                Rule=task_name,
                Ids=[f"{task_name}-target"]
            )
            
            # Delete rule
            self.eventbridge_client.delete_rule(Name=task_name)
            
            logger.info(f"Deleted schedule for task: {task_name}")
            return True
            
        except (ClientError, BotoCoreError) as e:
            logger.error(f"Error deleting schedule for {task_name}: {str(e)}")
            return False
            
    async def enable_schedule(self, task_name: str) -> bool:
        """Enable a schedule."""
        return await self.update_schedule(task_name, enabled=True)
        
    async def disable_schedule(self, task_name: str) -> bool:
        """Disable a schedule."""
        return await self.update_schedule(task_name, enabled=False)
        
    async def list_schedules(self) -> List[Dict[str, Any]]:
        """List all schedules."""
        try:
            response = self.eventbridge_client.list_rules()
            rules = response.get('Rules', [])
            
            schedules = []
            for rule in rules:
                if rule['Name'] in self.tasks:
                    task = self.tasks[rule['Name']]
                    schedules.append({
                        'name': rule['Name'],
                        'description': rule.get('Description', ''),
                        'schedule_expression': rule.get('ScheduleExpression', ''),
                        'state': rule.get('State', ''),
                        'task_config': asdict(task)
                    })
                    
            return schedules
            
        except (ClientError, BotoCoreError) as e:
            logger.error(f"Error listing schedules: {str(e)}")
            return []
            
    async def get_schedule_status(self, task_name: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific schedule."""
        try:
            response = self.eventbridge_client.describe_rule(Name=task_name)
            
            return {
                'name': response['Name'],
                'description': response.get('Description', ''),
                'schedule_expression': response.get('ScheduleExpression', ''),
                'state': response.get('State', ''),
                'arn': response['Arn'],
                'created_by': response.get('CreatedBy', ''),
                'event_bus_name': response.get('EventBusName', 'default')
            }
            
        except (ClientError, BotoCoreError) as e:
            logger.error(f"Error getting schedule status for {task_name}: {str(e)}")
            return None
            
    async def trigger_task_now(self, task_name: str) -> bool:
        """Manually trigger a task immediately."""
        if task_name not in self.tasks:
            logger.error(f"Task not found: {task_name}")
            return False
            
        task = self.tasks[task_name]
        
        try:
            # Create a one-time event
            event_detail = {
                'task_name': task.name,
                'function': task.target_function,
                'payload': task.payload or {},
                'triggered_manually': True,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            response = self.eventbridge_client.put_events(
                Entries=[
                    {
                        'Source': f'{self.settings.app_name}.scheduler',
                        'DetailType': 'Manual Task Trigger',
                        'Detail': json.dumps(event_detail),
                        'EventBusName': 'default'
                    }
                ]
            )
            
            logger.info(f"Manually triggered task: {task_name}")
            return True
            
        except (ClientError, BotoCoreError) as e:
            logger.error(f"Error triggering task {task_name}: {str(e)}")
            return False
            
    async def execute_task_locally(self, task_name: str) -> Dict[str, Any]:
        """Execute a task locally (for testing)."""
        if task_name not in self.tasks:
            return {"error": f"Task not found: {task_name}"}
            
        task = self.tasks[task_name]
        
        if task.target_function not in self.task_handlers:
            return {"error": f"Handler not found for function: {task.target_function}"}
            
        try:
            handler = self.task_handlers[task.target_function]
            result = await handler(task.payload or {})
            
            return {
                "success": True,
                "task_name": task_name,
                "function": task.target_function,
                "result": result
            }
            
        except Exception as e:
            logger.error(f"Error executing task {task_name} locally: {str(e)}")
            return {
                "success": False,
                "task_name": task_name,
                "error": str(e)
            }
            
    async def setup_all_schedules(self) -> Dict[str, bool]:
        """Set up all registered schedules."""
        results = {}
        
        for task_name in self.tasks:
            results[task_name] = await self.create_schedule(task_name)
            
        return results
        
    async def cleanup_all_schedules(self) -> Dict[str, bool]:
        """Clean up all schedules."""
        results = {}
        
        for task_name in self.tasks:
            results[task_name] = await self.delete_schedule(task_name)
            
        return results