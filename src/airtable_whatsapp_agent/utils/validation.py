"""
Validation utilities for the Airtable WhatsApp Agent.

This module provides validation functions for various data types, formats,
and business logic validation.
"""

import re
import json
from typing import Any, Dict, List, Optional, Union, Callable
from datetime import datetime
from urllib.parse import urlparse
from enum import Enum
import phonenumbers
from phonenumbers import NumberParseException


class ValidationError(Exception):
    """Custom validation error."""
    
    def __init__(self, message: str, field: str = None, value: Any = None):
        self.message = message
        self.field = field
        self.value = value
        super().__init__(message)


class ValidationSeverity(Enum):
    """Validation severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ValidationResult:
    """Result of a validation operation."""
    
    def __init__(self, is_valid: bool = True, errors: List[str] = None, warnings: List[str] = None):
        self.is_valid = is_valid
        self.errors = errors or []
        self.warnings = warnings or []
    
    def add_error(self, message: str):
        """Add an error message."""
        self.errors.append(message)
        self.is_valid = False
    
    def add_warning(self, message: str):
        """Add a warning message."""
        self.warnings.append(message)
    
    def merge(self, other: 'ValidationResult'):
        """Merge another validation result."""
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        if not other.is_valid:
            self.is_valid = False


class Validator:
    """Base validator class."""
    
    def __init__(self, required: bool = True, allow_none: bool = False):
        self.required = required
        self.allow_none = allow_none
    
    def validate(self, value: Any, field_name: str = None) -> ValidationResult:
        """Validate a value."""
        result = ValidationResult()
        
        # Check if value is None
        if value is None:
            if self.required and not self.allow_none:
                result.add_error(f"Field '{field_name or 'value'}' is required")
            return result
        
        # Perform specific validation
        return self._validate_value(value, field_name)
    
    def _validate_value(self, value: Any, field_name: str = None) -> ValidationResult:
        """Override this method in subclasses."""
        return ValidationResult()


class StringValidator(Validator):
    """String validation."""
    
    def __init__(self, min_length: int = None, max_length: int = None, 
                 pattern: str = None, **kwargs):
        super().__init__(**kwargs)
        self.min_length = min_length
        self.max_length = max_length
        self.pattern = re.compile(pattern) if pattern else None
    
    def _validate_value(self, value: Any, field_name: str = None) -> ValidationResult:
        result = ValidationResult()
        
        if not isinstance(value, str):
            result.add_error(f"Field '{field_name or 'value'}' must be a string")
            return result
        
        # Length validation
        if self.min_length is not None and len(value) < self.min_length:
            result.add_error(f"Field '{field_name or 'value'}' must be at least {self.min_length} characters")
        
        if self.max_length is not None and len(value) > self.max_length:
            result.add_error(f"Field '{field_name or 'value'}' must be at most {self.max_length} characters")
        
        # Pattern validation
        if self.pattern and not self.pattern.match(value):
            result.add_error(f"Field '{field_name or 'value'}' does not match required pattern")
        
        return result


class EmailValidator(StringValidator):
    """Email validation."""
    
    EMAIL_PATTERN = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    def __init__(self, **kwargs):
        super().__init__(pattern=self.EMAIL_PATTERN, **kwargs)
    
    def _validate_value(self, value: Any, field_name: str = None) -> ValidationResult:
        result = super()._validate_value(value, field_name)
        
        if result.is_valid and isinstance(value, str):
            # Additional email validation
            if '@' not in value:
                result.add_error(f"Field '{field_name or 'value'}' must contain '@' symbol")
            elif value.count('@') > 1:
                result.add_error(f"Field '{field_name or 'value'}' must contain only one '@' symbol")
        
        return result


class PhoneValidator(Validator):
    """Phone number validation."""
    
    def __init__(self, region: str = None, **kwargs):
        super().__init__(**kwargs)
        self.region = region
    
    def _validate_value(self, value: Any, field_name: str = None) -> ValidationResult:
        result = ValidationResult()
        
        if not isinstance(value, str):
            result.add_error(f"Field '{field_name or 'value'}' must be a string")
            return result
        
        try:
            parsed = phonenumbers.parse(value, self.region)
            if not phonenumbers.is_valid_number(parsed):
                result.add_error(f"Field '{field_name or 'value'}' is not a valid phone number")
        except NumberParseException as e:
            result.add_error(f"Field '{field_name or 'value'}' is not a valid phone number: {e}")
        
        return result


class URLValidator(StringValidator):
    """URL validation."""
    
    def __init__(self, schemes: List[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.schemes = schemes or ['http', 'https']
    
    def _validate_value(self, value: Any, field_name: str = None) -> ValidationResult:
        result = super()._validate_value(value, field_name)
        
        if result.is_valid and isinstance(value, str):
            try:
                parsed = urlparse(value)
                if not parsed.scheme:
                    result.add_error(f"Field '{field_name or 'value'}' must include a scheme (http/https)")
                elif parsed.scheme not in self.schemes:
                    result.add_error(f"Field '{field_name or 'value'}' scheme must be one of: {', '.join(self.schemes)}")
                elif not parsed.netloc:
                    result.add_error(f"Field '{field_name or 'value'}' must include a domain")
            except Exception as e:
                result.add_error(f"Field '{field_name or 'value'}' is not a valid URL: {e}")
        
        return result


class NumberValidator(Validator):
    """Number validation."""
    
    def __init__(self, min_value: Union[int, float] = None, 
                 max_value: Union[int, float] = None, **kwargs):
        super().__init__(**kwargs)
        self.min_value = min_value
        self.max_value = max_value
    
    def _validate_value(self, value: Any, field_name: str = None) -> ValidationResult:
        result = ValidationResult()
        
        if not isinstance(value, (int, float)):
            result.add_error(f"Field '{field_name or 'value'}' must be a number")
            return result
        
        if self.min_value is not None and value < self.min_value:
            result.add_error(f"Field '{field_name or 'value'}' must be at least {self.min_value}")
        
        if self.max_value is not None and value > self.max_value:
            result.add_error(f"Field '{field_name or 'value'}' must be at most {self.max_value}")
        
        return result


class ListValidator(Validator):
    """List validation."""
    
    def __init__(self, item_validator: Validator = None, min_items: int = None, 
                 max_items: int = None, **kwargs):
        super().__init__(**kwargs)
        self.item_validator = item_validator
        self.min_items = min_items
        self.max_items = max_items
    
    def _validate_value(self, value: Any, field_name: str = None) -> ValidationResult:
        result = ValidationResult()
        
        if not isinstance(value, list):
            result.add_error(f"Field '{field_name or 'value'}' must be a list")
            return result
        
        # Length validation
        if self.min_items is not None and len(value) < self.min_items:
            result.add_error(f"Field '{field_name or 'value'}' must have at least {self.min_items} items")
        
        if self.max_items is not None and len(value) > self.max_items:
            result.add_error(f"Field '{field_name or 'value'}' must have at most {self.max_items} items")
        
        # Item validation
        if self.item_validator:
            for i, item in enumerate(value):
                item_result = self.item_validator.validate(item, f"{field_name or 'value'}[{i}]")
                result.merge(item_result)
        
        return result


class DictValidator(Validator):
    """Dictionary validation."""
    
    def __init__(self, schema: Dict[str, Validator] = None, **kwargs):
        super().__init__(**kwargs)
        self.schema = schema or {}
    
    def _validate_value(self, value: Any, field_name: str = None) -> ValidationResult:
        result = ValidationResult()
        
        if not isinstance(value, dict):
            result.add_error(f"Field '{field_name or 'value'}' must be a dictionary")
            return result
        
        # Validate each field in schema
        for field, validator in self.schema.items():
            field_value = value.get(field)
            field_result = validator.validate(field_value, f"{field_name or 'value'}.{field}")
            result.merge(field_result)
        
        return result


class JSONValidator(StringValidator):
    """JSON validation."""
    
    def _validate_value(self, value: Any, field_name: str = None) -> ValidationResult:
        result = super()._validate_value(value, field_name)
        
        if result.is_valid and isinstance(value, str):
            try:
                json.loads(value)
            except json.JSONDecodeError as e:
                result.add_error(f"Field '{field_name or 'value'}' is not valid JSON: {e}")
        
        return result


class DateTimeValidator(Validator):
    """DateTime validation."""
    
    def __init__(self, format_string: str = None, **kwargs):
        super().__init__(**kwargs)
        self.format_string = format_string
    
    def _validate_value(self, value: Any, field_name: str = None) -> ValidationResult:
        result = ValidationResult()
        
        if isinstance(value, datetime):
            return result
        
        if isinstance(value, str):
            if self.format_string:
                try:
                    datetime.strptime(value, self.format_string)
                except ValueError as e:
                    result.add_error(f"Field '{field_name or 'value'}' does not match format '{self.format_string}': {e}")
            else:
                try:
                    datetime.fromisoformat(value.replace('Z', '+00:00'))
                except ValueError as e:
                    result.add_error(f"Field '{field_name or 'value'}' is not a valid ISO datetime: {e}")
        else:
            result.add_error(f"Field '{field_name or 'value'}' must be a datetime or string")
        
        return result


# Convenience functions
def validate_email(email: str) -> bool:
    """Validate email address."""
    validator = EmailValidator()
    result = validator.validate(email)
    return result.is_valid

def validate_phone(phone: str, region: str = None) -> bool:
    """Validate phone number."""
    validator = PhoneValidator(region=region)
    result = validator.validate(phone)
    return result.is_valid

def validate_url(url: str, schemes: List[str] = None) -> bool:
    """Validate URL."""
    validator = URLValidator(schemes=schemes)
    result = validator.validate(url)
    return result.is_valid

def validate_json(json_str: str) -> bool:
    """Validate JSON string."""
    validator = JSONValidator()
    result = validator.validate(json_str)
    return result.is_valid

def sanitize_string(value: str, max_length: int = None, strip_html: bool = False) -> str:
    """Sanitize string input."""
    if not isinstance(value, str):
        return str(value)
    
    # Strip whitespace
    value = value.strip()
    
    # Strip HTML if requested
    if strip_html:
        value = re.sub(r'<[^>]+>', '', value)
    
    # Truncate if needed
    if max_length and len(value) > max_length:
        value = value[:max_length]
    
    return value

def sanitize_phone(phone: str) -> str:
    """Sanitize phone number."""
    if not isinstance(phone, str):
        return str(phone)
    
    # Remove all non-digit characters except +
    return re.sub(r'[^\d+]', '', phone)

def validate_whatsapp_number(phone: str) -> bool:
    """Validate WhatsApp phone number format."""
    # WhatsApp numbers should be in international format without +
    pattern = r'^\d{10,15}$'
    return bool(re.match(pattern, phone))

def validate_airtable_record_id(record_id: str) -> bool:
    """Validate Airtable record ID format."""
    # Airtable record IDs start with 'rec' followed by 14 alphanumeric characters
    pattern = r'^rec[a-zA-Z0-9]{14}$'
    return bool(re.match(pattern, record_id))

def validate_airtable_base_id(base_id: str) -> bool:
    """Validate Airtable base ID format."""
    # Airtable base IDs start with 'app' followed by 14 alphanumeric characters
    pattern = r'^app[a-zA-Z0-9]{14}$'
    return bool(re.match(pattern, base_id))