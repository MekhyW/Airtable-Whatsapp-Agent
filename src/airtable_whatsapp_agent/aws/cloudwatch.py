"""
AWS CloudWatch integration for logging and metrics collection.
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from enum import Enum
import asyncio
import boto3
from botocore.exceptions import ClientError, BotoCoreError
from ..config import Settings


logger = logging.getLogger(__name__)


class MetricUnit(Enum):
    """CloudWatch metric units."""
    
    SECONDS = "Seconds"
    MICROSECONDS = "Microseconds"
    MILLISECONDS = "Milliseconds"
    BYTES = "Bytes"
    KILOBYTES = "Kilobytes"
    MEGABYTES = "Megabytes"
    GIGABYTES = "Gigabytes"
    TERABYTES = "Terabytes"
    BITS = "Bits"
    KILOBITS = "Kilobits"
    MEGABITS = "Megabits"
    GIGABITS = "Gigabits"
    TERABITS = "Terabits"
    PERCENT = "Percent"
    COUNT = "Count"
    BYTES_PER_SECOND = "Bytes/Second"
    KILOBYTES_PER_SECOND = "Kilobytes/Second"
    MEGABYTES_PER_SECOND = "Megabytes/Second"
    GIGABYTES_PER_SECOND = "Gigabytes/Second"
    TERABYTES_PER_SECOND = "Terabytes/Second"
    BITS_PER_SECOND = "Bits/Second"
    KILOBITS_PER_SECOND = "Kilobits/Second"
    MEGABITS_PER_SECOND = "Megabits/Second"
    GIGABITS_PER_SECOND = "Gigabits/Second"
    TERABITS_PER_SECOND = "Terabits/Second"
    COUNT_PER_SECOND = "Count/Second"
    NONE = "None"


class CloudWatchLogger:
    """CloudWatch logging integration."""
    
    def __init__(self, settings: Settings):
        """Initialize CloudWatch logger."""
        self.settings = settings
        self.region = settings.aws_region
        self.logs_client = boto3.client(
            'logs',
            region_name=self.region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key
        )
        self.log_group_name = f"/aws/lambda/{settings.app_name}"
        self.log_stream_name = f"{settings.environment}-{datetime.utcnow().strftime('%Y-%m-%d')}"
        asyncio.create_task(self._ensure_log_group())
        
    async def _ensure_log_group(self):
        """Ensure log group exists."""
        try:
            self.logs_client.create_log_group(
                logGroupName=self.log_group_name,
                tags={
                    'Application': self.settings.app_name,
                    'Environment': self.settings.environment
                }
            )
            logger.info(f"Created CloudWatch log group: {self.log_group_name}")
        except ClientError as e:
            if e.response['Error']['Code'] != 'ResourceAlreadyExistsException':
                logger.error(f"Error creating log group: {str(e)}")
                
    async def _ensure_log_stream(self):
        """Ensure log stream exists."""
        try:
            self.logs_client.create_log_stream(
                logGroupName=self.log_group_name,
                logStreamName=self.log_stream_name
            )
        except ClientError as e:
            if e.response['Error']['Code'] != 'ResourceAlreadyExistsException':
                logger.error(f"Error creating log stream: {str(e)}")
                
    async def send_log_events(self, events: List[Dict[str, Any]]):
        """Send log events to CloudWatch."""
        try:
            await self._ensure_log_stream()
            try:
                response = self.logs_client.describe_log_streams(
                    logGroupName=self.log_group_name,
                    logStreamNamePrefix=self.log_stream_name
                )
                streams = response.get('logStreams', [])
                sequence_token = None
                for stream in streams:
                    if stream['logStreamName'] == self.log_stream_name:
                        sequence_token = stream.get('uploadSequenceToken')
                        break  
            except ClientError:
                sequence_token = None
            log_events = []
            for event in events:
                log_events.append({
                    'timestamp': int(event.get('timestamp', datetime.utcnow().timestamp() * 1000)),
                    'message': json.dumps(event) if isinstance(event.get('message'), dict) else str(event.get('message', ''))
                })
            log_events.sort(key=lambda x: x['timestamp'])
            put_events_kwargs = {
                'logGroupName': self.log_group_name,
                'logStreamName': self.log_stream_name,
                'logEvents': log_events
            }
            if sequence_token:
                put_events_kwargs['sequenceToken'] = sequence_token
            self.logs_client.put_log_events(**put_events_kwargs)
        except (ClientError, BotoCoreError) as e:
            logger.error(f"Error sending log events to CloudWatch: {str(e)}")
            
    async def log_application_event(self, level: str, message: str, component: str = None, user_id: str = None, session_id: str = None, extra_data: Dict[str, Any] = None):
        """Log application event."""
        event = {
            'timestamp': datetime.utcnow().timestamp() * 1000,
            'level': level,
            'message': message,
            'application': self.settings.app_name,
            'environment': self.settings.environment,
            'component': component,
            'user_id': user_id,
            'session_id': session_id
        }
        if extra_data:
            event.update(extra_data)
        await self.send_log_events([event])
        
    async def log_api_request(self, method: str, path: str, status_code: int, response_time_ms: float, user_id: str = None, ip_address: str = None, user_agent: str = None):
        """Log API request."""
        event = {
            'timestamp': datetime.utcnow().timestamp() * 1000,
            'event_type': 'api_request',
            'method': method,
            'path': path,
            'status_code': status_code,
            'response_time_ms': response_time_ms,
            'user_id': user_id,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'application': self.settings.app_name,
            'environment': self.settings.environment
        }
        await self.send_log_events([event])
        
    async def log_whatsapp_event(self, event_type: str, phone_number: str, message_id: str = None, message_type: str = None, status: str = None, error_message: str = None):
        """Log WhatsApp event."""
        event = {
            'timestamp': datetime.utcnow().timestamp() * 1000,
            'event_type': 'whatsapp_event',
            'whatsapp_event_type': event_type,
            'phone_number': phone_number,
            'message_id': message_id,
            'message_type': message_type,
            'status': status,
            'error_message': error_message,
            'application': self.settings.app_name,
            'environment': self.settings.environment
        }
        await self.send_log_events([event])
        
    async def log_airtable_operation(self, operation: str, table_name: str, record_id: str = None, success: bool = True, error_message: str = None, duration_ms: float = None):
        """Log Airtable operation."""
        event = {
            'timestamp': datetime.utcnow().timestamp() * 1000,
            'event_type': 'airtable_operation',
            'operation': operation,
            'table_name': table_name,
            'record_id': record_id,
            'success': success,
            'error_message': error_message,
            'duration_ms': duration_ms,
            'application': self.settings.app_name,
            'environment': self.settings.environment
        }
        await self.send_log_events([event])


class MetricsCollector:
    """CloudWatch metrics collection."""
    
    def __init__(self, settings: Settings):
        """Initialize metrics collector."""
        self.settings = settings
        self.region = settings.aws_region
        self.cloudwatch_client = boto3.client(
            'cloudwatch',
            region_name=self.region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key
        )
        self.namespace = f"{settings.app_name}/Application"
        self._metrics_buffer = []
        self._buffer_size = 20  # CloudWatch limit
        
    async def put_metric(self,metric_name: str, value: Union[int, float], unit: MetricUnit = MetricUnit.COUNT, dimensions: Optional[Dict[str, str]] = None, timestamp: Optional[datetime] = None):
        """Put a single metric."""
        metric_data = {
            'MetricName': metric_name,
            'Value': value,
            'Unit': unit.value,
            'Timestamp': timestamp or datetime.utcnow()
        }
        if dimensions:
            metric_data['Dimensions'] = [{'Name': k, 'Value': v} for k, v in dimensions.items()]
        self._metrics_buffer.append(metric_data)
        if len(self._metrics_buffer) >= self._buffer_size:
            await self.flush_metrics()
            
    async def put_metrics(self, metrics: List[Dict[str, Any]]):
        """Put multiple metrics."""
        for metric in metrics:
            await self.put_metric(**metric)
            
    async def flush_metrics(self):
        """Flush metrics buffer to CloudWatch."""
        if not self._metrics_buffer:
            return
        try:
            for i in range(0, len(self._metrics_buffer), self._buffer_size):
                batch = self._metrics_buffer[i:i + self._buffer_size]
                self.cloudwatch_client.put_metric_data(Namespace=self.namespace, MetricData=batch)
            self._metrics_buffer.clear()
        except (ClientError, BotoCoreError) as e:
            logger.error(f"Error sending metrics to CloudWatch: {str(e)}")
            
    async def record_api_metrics(self, endpoint: str, method: str, status_code: int, response_time_ms: float, request_size_bytes: int = None, response_size_bytes: int = None):
        """Record API-related metrics."""
        dimensions = {
            'Endpoint': endpoint,
            'Method': method,
            'Environment': self.settings.environment
        }
        await self.put_metric('APIResponseTime', response_time_ms, MetricUnit.MILLISECONDS, dimensions)
        await self.put_metric('APIRequestCount', 1, MetricUnit.COUNT, dimensions)
        if status_code >= 400:
            await self.put_metric('APIErrorCount', 1, MetricUnit.COUNT, {**dimensions, 'StatusCode': str(status_code)})   
        if request_size_bytes:
            await self.put_metric('APIRequestSize', request_size_bytes, MetricUnit.BYTES, dimensions)
        if response_size_bytes:
            await self.put_metric('APIResponseSize', response_size_bytes, MetricUnit.BYTES, dimensions)
            
    async def record_whatsapp_metrics(self, event_type: str, success: bool = True, processing_time_ms: float = None):
        """Record WhatsApp-related metrics."""
        dimensions = {
            'EventType': event_type,
            'Environment': self.settings.environment
        }
        await self.put_metric('WhatsAppEventCount', 1, MetricUnit.COUNT, dimensions)
        status_dimensions = {**dimensions, 'Status': 'Success' if success else 'Failure'}
        await self.put_metric('WhatsAppEventStatus', 1, MetricUnit.COUNT, status_dimensions)
        if processing_time_ms:
            await self.put_metric('WhatsAppProcessingTime', processing_time_ms, MetricUnit.MILLISECONDS, dimensions)
            
    async def record_airtable_metrics(self, operation: str, table_name: str, success: bool = True, duration_ms: float = None, record_count: int = None):
        """Record Airtable-related metrics."""
        dimensions = {
            'Operation': operation,
            'Table': table_name,
            'Environment': self.settings.environment
        }
        await self.put_metric('AirtableOperationCount', 1, MetricUnit.COUNT, dimensions)
        status_dimensions = {**dimensions, 'Status': 'Success' if success else 'Failure'}
        await self.put_metric('AirtableOperationStatus', 1, MetricUnit.COUNT, status_dimensions)
        if duration_ms:
            await self.put_metric('AirtableOperationDuration', duration_ms, MetricUnit.MILLISECONDS, dimensions)
        if record_count:
            await self.put_metric('AirtableRecordCount', record_count, MetricUnit.COUNT, dimensions)
            
    async def record_agent_metrics(self, action: str, success: bool = True, processing_time_ms: float = None, tokens_used: int = None, cost_usd: float = None):
        """Record AI agent-related metrics."""
        dimensions = {
            'Action': action,
            'Environment': self.settings.environment
        }
        await self.put_metric('AgentActionCount', 1, MetricUnit.COUNT, dimensions)
        status_dimensions = {**dimensions, 'Status': 'Success' if success else 'Failure'}
        await self.put_metric('AgentActionStatus', 1, MetricUnit.COUNT, status_dimensions)
        if processing_time_ms:
            await self.put_metric('AgentProcessingTime', processing_time_ms, MetricUnit.MILLISECONDS, dimensions)
        if tokens_used:
            await self.put_metric('AgentTokensUsed', tokens_used, MetricUnit.COUNT, dimensions)
        if cost_usd:
            await self.put_metric('AgentCostUSD', cost_usd, MetricUnit.NONE, dimensions)
            
    async def record_system_metrics(self, cpu_usage_percent: float = None, memory_usage_percent: float = None, disk_usage_percent: float = None, active_connections: int = None):
        """Record system-related metrics."""
        dimensions = {
            'Environment': self.settings.environment,
            'Instance': 'main'
        }
        if cpu_usage_percent is not None:
            await self.put_metric('SystemCPUUsage', cpu_usage_percent, MetricUnit.PERCENT, dimensions)
        if memory_usage_percent is not None:
            await self.put_metric('SystemMemoryUsage', memory_usage_percent, MetricUnit.PERCENT, dimensions)
        if disk_usage_percent is not None:
            await self.put_metric('SystemDiskUsage', disk_usage_percent, MetricUnit.PERCENT, dimensions)
        if active_connections is not None:
            await self.put_metric('SystemActiveConnections', active_connections, MetricUnit.COUNT, dimensions)
            
    async def create_dashboard(self) -> Optional[str]:
        """Create CloudWatch dashboard."""
        dashboard_body = {
            "widgets": [
                {
                    "type": "metric",
                    "x": 0,
                    "y": 0,
                    "width": 12,
                    "height": 6,
                    "properties": {
                        "metrics": [
                            [self.namespace, "APIRequestCount", "Environment", self.settings.environment],
                            [".", "APIErrorCount", ".", "."],
                            [".", "WhatsAppEventCount", ".", "."],
                            [".", "AirtableOperationCount", ".", "."]
                        ],
                        "period": 300,
                        "stat": "Sum",
                        "region": self.region,
                        "title": "Request Counts"
                    }
                },
                {
                    "type": "metric",
                    "x": 12,
                    "y": 0,
                    "width": 12,
                    "height": 6,
                    "properties": {
                        "metrics": [
                            [self.namespace, "APIResponseTime", "Environment", self.settings.environment],
                            [".", "WhatsAppProcessingTime", ".", "."],
                            [".", "AirtableOperationDuration", ".", "."],
                            [".", "AgentProcessingTime", ".", "."]
                        ],
                        "period": 300,
                        "stat": "Average",
                        "region": self.region,
                        "title": "Response Times"
                    }
                },
                {
                    "type": "metric",
                    "x": 0,
                    "y": 6,
                    "width": 24,
                    "height": 6,
                    "properties": {
                        "metrics": [
                            [self.namespace, "SystemCPUUsage", "Environment", self.settings.environment],
                            [".", "SystemMemoryUsage", ".", "."],
                            [".", "SystemDiskUsage", ".", "."]
                        ],
                        "period": 300,
                        "stat": "Average",
                        "region": self.region,
                        "title": "System Metrics"
                    }
                }
            ]
        }
        try:
            dashboard_name = f"{self.settings.app_name}-{self.settings.environment}"
            self.cloudwatch_client.put_dashboard(DashboardName=dashboard_name, DashboardBody=json.dumps(dashboard_body))
            logger.info(f"Created CloudWatch dashboard: {dashboard_name}")
            return dashboard_name
        except (ClientError, BotoCoreError) as e:
            logger.error(f"Error creating CloudWatch dashboard: {str(e)}")
            return None
            
    async def create_alarms(self) -> List[str]:
        """Create CloudWatch alarms."""
        alarms = []
        alarm_configs = [
            {
                'AlarmName': f"{self.settings.app_name}-HighErrorRate",
                'ComparisonOperator': 'GreaterThanThreshold',
                'EvaluationPeriods': 2,
                'MetricName': 'APIErrorCount',
                'Namespace': self.namespace,
                'Period': 300,
                'Statistic': 'Sum',
                'Threshold': 10.0,
                'ActionsEnabled': True,
                'AlarmDescription': 'High API error rate detected',
                'Dimensions': [
                    {'Name': 'Environment', 'Value': self.settings.environment}
                ],
                'Unit': 'Count'
            },
            {
                'AlarmName': f"{self.settings.app_name}-HighResponseTime",
                'ComparisonOperator': 'GreaterThanThreshold',
                'EvaluationPeriods': 3,
                'MetricName': 'APIResponseTime',
                'Namespace': self.namespace,
                'Period': 300,
                'Statistic': 'Average',
                'Threshold': 5000.0,
                'ActionsEnabled': True,
                'AlarmDescription': 'High API response time detected',
                'Dimensions': [
                    {'Name': 'Environment', 'Value': self.settings.environment}
                ],
                'Unit': 'Milliseconds'
            },
            {
                'AlarmName': f"{self.settings.app_name}-HighCPUUsage",
                'ComparisonOperator': 'GreaterThanThreshold',
                'EvaluationPeriods': 3,
                'MetricName': 'SystemCPUUsage',
                'Namespace': self.namespace,
                'Period': 300,
                'Statistic': 'Average',
                'Threshold': 80.0,
                'ActionsEnabled': True,
                'AlarmDescription': 'High CPU usage detected',
                'Dimensions': [
                    {'Name': 'Environment', 'Value': self.settings.environment}
                ],
                'Unit': 'Percent'
            }
        ]
        for alarm_config in alarm_configs:
            try:
                self.cloudwatch_client.put_metric_alarm(**alarm_config)
                alarms.append(alarm_config['AlarmName'])
                logger.info(f"Created CloudWatch alarm: {alarm_config['AlarmName']}")
            except (ClientError, BotoCoreError) as e:
                logger.error(f"Error creating alarm {alarm_config['AlarmName']}: {str(e)}")
        return alarms