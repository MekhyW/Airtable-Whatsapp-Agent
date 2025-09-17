"""
Permission management and authorization system.
"""

import logging
from typing import Dict, List, Optional, Set
from enum import Enum

from ..models.auth import PermissionType, UserRole, ResourceType


logger = logging.getLogger(__name__)


class PermissionManager:
    """Manages permissions and authorization for users."""
    
    def __init__(self):
        """Initialize permission manager."""
        self.logger = logging.getLogger(__name__)
        
        # Define role-based default permissions
        self.role_permissions = {
            UserRole.SUPER_ADMIN: [
                PermissionType.READ_AIRTABLE,
                PermissionType.WRITE_AIRTABLE,
                PermissionType.DELETE_AIRTABLE,
                PermissionType.SEND_WHATSAPP,
                PermissionType.RECEIVE_WHATSAPP,
                PermissionType.MANAGE_USERS,
                PermissionType.MANAGE_PERMISSIONS,
                PermissionType.VIEW_AUDIT_LOGS,
                PermissionType.MANAGE_SYSTEM,
                PermissionType.SCHEDULE_TASKS,
                PermissionType.MANAGE_INTEGRATIONS
            ],
            UserRole.ADMIN: [
                PermissionType.READ_AIRTABLE,
                PermissionType.WRITE_AIRTABLE,
                PermissionType.SEND_WHATSAPP,
                PermissionType.RECEIVE_WHATSAPP,
                PermissionType.MANAGE_USERS,
                PermissionType.VIEW_AUDIT_LOGS,
                PermissionType.SCHEDULE_TASKS
            ],
            UserRole.MODERATOR: [
                PermissionType.READ_AIRTABLE,
                PermissionType.WRITE_AIRTABLE,
                PermissionType.SEND_WHATSAPP,
                PermissionType.RECEIVE_WHATSAPP,
                PermissionType.VIEW_AUDIT_LOGS
            ],
            UserRole.USER: [
                PermissionType.READ_AIRTABLE,
                PermissionType.SEND_WHATSAPP,
                PermissionType.RECEIVE_WHATSAPP
            ]
        }
        
        # Define resource-specific permission requirements
        self.resource_permissions = {
            ResourceType.AIRTABLE_RECORD: {
                "read": [PermissionType.READ_AIRTABLE],
                "create": [PermissionType.WRITE_AIRTABLE],
                "update": [PermissionType.WRITE_AIRTABLE],
                "delete": [PermissionType.DELETE_AIRTABLE]
            },
            ResourceType.WHATSAPP_MESSAGE: {
                "send": [PermissionType.SEND_WHATSAPP],
                "receive": [PermissionType.RECEIVE_WHATSAPP],
                "read": [PermissionType.RECEIVE_WHATSAPP]
            },
            ResourceType.USER_ACCOUNT: {
                "read": [PermissionType.MANAGE_USERS],
                "create": [PermissionType.MANAGE_USERS],
                "update": [PermissionType.MANAGE_USERS],
                "delete": [PermissionType.MANAGE_USERS]
            },
            ResourceType.SYSTEM_CONFIG: {
                "read": [PermissionType.MANAGE_SYSTEM],
                "update": [PermissionType.MANAGE_SYSTEM]
            },
            ResourceType.AUDIT_LOG: {
                "read": [PermissionType.VIEW_AUDIT_LOGS]
            },
            ResourceType.SCHEDULED_TASK: {
                "create": [PermissionType.SCHEDULE_TASKS],
                "read": [PermissionType.SCHEDULE_TASKS],
                "update": [PermissionType.SCHEDULE_TASKS],
                "delete": [PermissionType.SCHEDULE_TASKS]
            }
        }
        
    def get_role_permissions(self, role: UserRole) -> List[PermissionType]:
        """Get default permissions for a role."""
        return self.role_permissions.get(role, [])
        
    def has_permission(
        self,
        user_permissions: List[PermissionType],
        required_permission: PermissionType
    ) -> bool:
        """Check if user has required permission."""
        return required_permission in user_permissions
        
    def has_any_permission(
        self,
        user_permissions: List[PermissionType],
        required_permissions: List[PermissionType]
    ) -> bool:
        """Check if user has any of the required permissions."""
        return any(perm in user_permissions for perm in required_permissions)
        
    def has_all_permissions(
        self,
        user_permissions: List[PermissionType],
        required_permissions: List[PermissionType]
    ) -> bool:
        """Check if user has all required permissions."""
        return all(perm in user_permissions for perm in required_permissions)
        
    def can_access_resource(
        self,
        user_permissions: List[PermissionType],
        resource_type: ResourceType,
        action: str
    ) -> bool:
        """Check if user can perform action on resource type."""
        resource_perms = self.resource_permissions.get(resource_type, {})
        required_perms = resource_perms.get(action, [])
        
        if not required_perms:
            self.logger.warning(f"No permissions defined for {resource_type.value}:{action}")
            return False
            
        return self.has_any_permission(user_permissions, required_perms)
        
    def get_accessible_resources(
        self,
        user_permissions: List[PermissionType]
    ) -> Dict[ResourceType, List[str]]:
        """Get all resources and actions user can access."""
        accessible = {}
        
        for resource_type, actions in self.resource_permissions.items():
            accessible_actions = []
            
            for action, required_perms in actions.items():
                if self.has_any_permission(user_permissions, required_perms):
                    accessible_actions.append(action)
                    
            if accessible_actions:
                accessible[resource_type] = accessible_actions
                
        return accessible
        
    def validate_permission_grant(
        self,
        granter_permissions: List[PermissionType],
        permissions_to_grant: List[PermissionType]
    ) -> bool:
        """Validate if user can grant specified permissions."""
        # Super admins can grant any permission
        if PermissionType.MANAGE_PERMISSIONS in granter_permissions:
            return True
            
        # Users can only grant permissions they have
        return self.has_all_permissions(granter_permissions, permissions_to_grant)
        
    def get_permission_hierarchy(self) -> Dict[UserRole, int]:
        """Get role hierarchy for permission comparison."""
        return {
            UserRole.USER: 1,
            UserRole.MODERATOR: 2,
            UserRole.ADMIN: 3,
            UserRole.SUPER_ADMIN: 4
        }
        
    def can_manage_user(
        self,
        manager_role: UserRole,
        target_role: UserRole
    ) -> bool:
        """Check if manager can manage target user based on role hierarchy."""
        hierarchy = self.get_permission_hierarchy()
        manager_level = hierarchy.get(manager_role, 0)
        target_level = hierarchy.get(target_role, 0)
        
        # Can manage users with lower or equal role level
        return manager_level >= target_level
        
    def get_effective_permissions(
        self,
        role: UserRole,
        custom_permissions: Optional[List[PermissionType]] = None
    ) -> List[PermissionType]:
        """Get effective permissions combining role and custom permissions."""
        role_perms = set(self.get_role_permissions(role))
        
        if custom_permissions:
            # Union of role permissions and custom permissions
            effective_perms = role_perms.union(set(custom_permissions))
        else:
            effective_perms = role_perms
            
        return list(effective_perms)
        
    def validate_permissions(
        self,
        permissions: List[PermissionType]
    ) -> List[PermissionType]:
        """Validate and filter valid permissions."""
        valid_permissions = []
        
        for perm in permissions:
            if isinstance(perm, PermissionType):
                valid_permissions.append(perm)
            else:
                self.logger.warning(f"Invalid permission type: {perm}")
                
        return valid_permissions
        
    def get_permission_description(self, permission: PermissionType) -> str:
        """Get human-readable description of permission."""
        descriptions = {
            PermissionType.READ_AIRTABLE: "Read data from Airtable tables",
            PermissionType.WRITE_AIRTABLE: "Create and update Airtable records",
            PermissionType.DELETE_AIRTABLE: "Delete Airtable records",
            PermissionType.SEND_WHATSAPP: "Send WhatsApp messages",
            PermissionType.RECEIVE_WHATSAPP: "Receive and read WhatsApp messages",
            PermissionType.MANAGE_USERS: "Manage user accounts and permissions",
            PermissionType.MANAGE_PERMISSIONS: "Grant and revoke permissions",
            PermissionType.VIEW_AUDIT_LOGS: "View system audit logs",
            PermissionType.MANAGE_SYSTEM: "Manage system configuration",
            PermissionType.SCHEDULE_TASKS: "Create and manage scheduled tasks",
            PermissionType.MANAGE_INTEGRATIONS: "Manage external integrations"
        }
        
        return descriptions.get(permission, f"Unknown permission: {permission.value}")
        
    def get_role_description(self, role: UserRole) -> str:
        """Get human-readable description of role."""
        descriptions = {
            UserRole.SUPER_ADMIN: "Full system access with all permissions",
            UserRole.ADMIN: "Administrative access with user management",
            UserRole.MODERATOR: "Content management and moderation access",
            UserRole.USER: "Basic user access for reading and messaging"
        }
        
        return descriptions.get(role, f"Unknown role: {role.value}")
        
    def audit_permission_check(
        self,
        user_id: str,
        permission: PermissionType,
        resource_type: Optional[ResourceType] = None,
        action: Optional[str] = None,
        granted: bool = False
    ) -> Dict:
        """Create audit log entry for permission check."""
        audit_entry = {
            "timestamp": logging.Formatter().formatTime(logging.LogRecord(
                name="", level=0, pathname="", lineno=0, msg="", args=(), exc_info=None
            )),
            "user_id": user_id,
            "permission": permission.value,
            "granted": granted,
            "action": "permission_check"
        }
        
        if resource_type:
            audit_entry["resource_type"] = resource_type.value
        if action:
            audit_entry["resource_action"] = action
            
        return audit_entry