"""
Main authenticator that coordinates whitelist, sessions, and permissions.
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from .whitelist import WhitelistManager
from .session import SessionManager
from .permissions import PermissionManager
from ..models.auth import UserSession, PermissionType, ResourceType
from ..models.airtable import AdminWhitelistRecord
from ..mcp.manager import MCPServerManager


logger = logging.getLogger(__name__)


class AuthenticationResult:
    """Result of authentication attempt."""
    
    def __init__(
        self,
        success: bool,
        session: Optional[UserSession] = None,
        error_message: Optional[str] = None,
        admin_record: Optional[AdminWhitelistRecord] = None
    ):
        self.success = success
        self.session = session
        self.error_message = error_message
        self.admin_record = admin_record


class Authenticator:
    """Main authenticator coordinating all authentication components."""
    
    def __init__(
        self,
        mcp_manager: MCPServerManager,
        whitelist_table: str = "Admin Whitelist",
        session_timeout: int = 3600,
        cache_ttl: int = 300
    ):
        """Initialize authenticator."""
        self.mcp_manager = mcp_manager
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.whitelist_manager = WhitelistManager(
            mcp_manager=mcp_manager,
            whitelist_table=whitelist_table,
            cache_ttl=cache_ttl
        )
        
        self.session_manager = SessionManager(
            session_timeout=session_timeout
        )
        
        self.permission_manager = PermissionManager()
        
    async def authenticate(
        self,
        phone_number: str,
        context: Optional[Dict] = None
    ) -> AuthenticationResult:
        """Authenticate user by phone number."""
        try:
            # Check if user is in admin whitelist
            if not await self.whitelist_manager.is_admin(phone_number):
                return AuthenticationResult(
                    success=False,
                    error_message="Phone number not authorized"
                )
                
            # Get admin record
            admin_record = await self.whitelist_manager.get_admin_info(phone_number)
            if not admin_record:
                return AuthenticationResult(
                    success=False,
                    error_message="Admin record not found"
                )
                
            # Check if admin is active
            if not admin_record.is_active:
                return AuthenticationResult(
                    success=False,
                    error_message="Admin account is inactive"
                )
                
            # Create or get existing session
            existing_session = await self.session_manager.get_session_by_phone(phone_number)
            
            if existing_session:
                # Extend existing session
                await self.session_manager.extend_session(existing_session.session_id)
                session = existing_session
            else:
                # Create new session
                session = await self.session_manager.create_session(
                    admin_record=admin_record,
                    context=context
                )
                
            self.logger.info(f"Authentication successful for {phone_number}")
            
            return AuthenticationResult(
                success=True,
                session=session,
                admin_record=admin_record
            )
            
        except Exception as e:
            self.logger.error(f"Authentication error for {phone_number}: {e}")
            return AuthenticationResult(
                success=False,
                error_message=f"Authentication failed: {str(e)}"
            )
            
    async def validate_session(self, session_token: str) -> Optional[UserSession]:
        """Validate session token and return session if valid."""
        return await self.session_manager.get_session(session_token)
        
    async def logout(self, session_token: str) -> bool:
        """Logout user by invalidating session."""
        return await self.session_manager.invalidate_session(session_token)
        
    async def logout_user(self, phone_number: str) -> int:
        """Logout all sessions for a user."""
        return await self.session_manager.invalidate_user_sessions(phone_number)
        
    async def check_permission(
        self,
        session_token: str,
        permission: PermissionType,
        resource_type: Optional[ResourceType] = None,
        action: Optional[str] = None
    ) -> bool:
        """Check if user has required permission."""
        try:
            # Validate session
            session = await self.validate_session(session_token)
            if not session:
                return False
                
            # Check specific permission
            if resource_type and action:
                return self.permission_manager.can_access_resource(
                    user_permissions=session.permissions,
                    resource_type=resource_type,
                    action=action
                )
            else:
                return self.permission_manager.has_permission(
                    user_permissions=session.permissions,
                    required_permission=permission
                )
                
        except Exception as e:
            self.logger.error(f"Permission check error: {e}")
            return False
            
    async def check_phone_permission(
        self,
        phone_number: str,
        permission: PermissionType,
        resource_type: Optional[ResourceType] = None,
        action: Optional[str] = None
    ) -> bool:
        """Check permission by phone number (for webhook scenarios)."""
        try:
            # Get active session for phone number
            session = await self.session_manager.get_session_by_phone(phone_number)
            if not session:
                # Try to authenticate if no active session
                auth_result = await self.authenticate(phone_number)
                if not auth_result.success:
                    return False
                session = auth_result.session
                
            # Check permission using session
            return await self.check_permission(
                session_token=session.session_id,
                permission=permission,
                resource_type=resource_type,
                action=action
            )
            
        except Exception as e:
            self.logger.error(f"Phone permission check error for {phone_number}: {e}")
            return False
            
    async def get_user_permissions(self, session_token: str) -> List[PermissionType]:
        """Get user permissions from session."""
        session = await self.validate_session(session_token)
        if session:
            return session.permissions
        return []
        
    async def get_user_info(self, session_token: str) -> Optional[Dict]:
        """Get user information from session."""
        session = await self.validate_session(session_token)
        if not session:
            return None
            
        admin_record = await self.whitelist_manager.get_admin_info(session.phone_number)
        if not admin_record:
            return None
            
        return {
            "phone_number": session.phone_number,
            "name": admin_record.name,
            "role": session.user_role.value,
            "permissions": [p.value for p in session.permissions],
            "session_created": session.created_at.isoformat(),
            "last_activity": session.last_activity.isoformat(),
            "session_expires": session.expires_at.isoformat()
        }
        
    async def update_user_permissions(
        self,
        admin_session_token: str,
        target_phone_number: str,
        new_permissions: List[PermissionType]
    ) -> bool:
        """Update user permissions (admin only)."""
        try:
            # Validate admin session
            admin_session = await self.validate_session(admin_session_token)
            if not admin_session:
                return False
                
            # Check if admin has permission to manage users
            if not self.permission_manager.has_permission(
                admin_session.permissions,
                PermissionType.MANAGE_PERMISSIONS
            ):
                self.logger.warning(f"Admin {admin_session.phone_number} lacks permission to manage permissions")
                return False
                
            # Validate permission grant
            if not self.permission_manager.validate_permission_grant(
                admin_session.permissions,
                new_permissions
            ):
                self.logger.warning(f"Admin {admin_session.phone_number} cannot grant permissions they don't have")
                return False
                
            # Update permissions in whitelist
            success = await self.whitelist_manager.update_admin_permissions(
                phone_number=target_phone_number,
                permissions=new_permissions
            )
            
            if success:
                # Invalidate target user's sessions to force permission refresh
                await self.session_manager.invalidate_user_sessions(target_phone_number)
                self.logger.info(f"Updated permissions for {target_phone_number}")
                
            return success
            
        except Exception as e:
            self.logger.error(f"Error updating permissions for {target_phone_number}: {e}")
            return False
            
    async def add_admin(
        self,
        admin_session_token: str,
        phone_number: str,
        name: str,
        role: str = "admin",
        permissions: Optional[List[str]] = None,
        notes: Optional[str] = None
    ) -> bool:
        """Add new admin (super admin only)."""
        try:
            # Validate admin session
            admin_session = await self.validate_session(admin_session_token)
            if not admin_session:
                return False
                
            # Check if admin has permission to manage users
            if not self.permission_manager.has_permission(
                admin_session.permissions,
                PermissionType.MANAGE_USERS
            ):
                return False
                
            # Convert string permissions to PermissionType
            perm_list = None
            if permissions:
                perm_list = [PermissionType(p) for p in permissions if p in PermissionType.__members__]
                
            # Add admin to whitelist
            return await self.whitelist_manager.add_admin(
                phone_number=phone_number,
                name=name,
                role=role,
                permissions=perm_list,
                notes=notes
            )
            
        except Exception as e:
            self.logger.error(f"Error adding admin {phone_number}: {e}")
            return False
            
    async def remove_admin(
        self,
        admin_session_token: str,
        target_phone_number: str
    ) -> bool:
        """Remove admin (super admin only)."""
        try:
            # Validate admin session
            admin_session = await self.validate_session(admin_session_token)
            if not admin_session:
                return False
                
            # Check if admin has permission to manage users
            if not self.permission_manager.has_permission(
                admin_session.permissions,
                PermissionType.MANAGE_USERS
            ):
                return False
                
            # Get target admin info
            target_admin = await self.whitelist_manager.get_admin_info(target_phone_number)
            if not target_admin:
                return False
                
            # Check role hierarchy
            if not self.permission_manager.can_manage_user(
                admin_session.user_role,
                target_admin.role
            ):
                self.logger.warning(f"Admin {admin_session.phone_number} cannot manage {target_admin.role.value}")
                return False
                
            # Remove admin
            success = await self.whitelist_manager.remove_admin(target_phone_number)
            
            if success:
                # Invalidate target user's sessions
                await self.session_manager.invalidate_user_sessions(target_phone_number)
                
            return success
            
        except Exception as e:
            self.logger.error(f"Error removing admin {target_phone_number}: {e}")
            return False
            
    async def list_admins(self, session_token: str) -> List[Dict]:
        """List all admins (admin only)."""
        try:
            # Validate session
            session = await self.validate_session(session_token)
            if not session:
                return []
                
            # Check permission
            if not self.permission_manager.has_permission(
                session.permissions,
                PermissionType.MANAGE_USERS
            ):
                return []
                
            # Get admin list
            admins = await self.whitelist_manager.list_admins()
            
            # Convert to dict format
            admin_list = []
            for admin in admins:
                admin_list.append({
                    "phone_number": admin.phone_number,
                    "name": admin.name,
                    "role": admin.role.value,
                    "is_active": admin.is_active,
                    "permissions": [p.value for p in admin.permissions],
                    "added_date": admin.added_date,
                    "last_seen": admin.last_seen,
                    "notes": admin.notes
                })
                
            return admin_list
            
        except Exception as e:
            self.logger.error(f"Error listing admins: {e}")
            return []
            
    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions."""
        return await self.session_manager.cleanup_expired_sessions()
        
    async def get_system_stats(self, session_token: str) -> Optional[Dict]:
        """Get system statistics (admin only)."""
        try:
            # Validate session
            session = await self.validate_session(session_token)
            if not session:
                return None
                
            # Check permission
            if not self.permission_manager.has_permission(
                session.permissions,
                PermissionType.VIEW_AUDIT_LOGS
            ):
                return None
                
            # Get stats
            session_stats = await self.session_manager.get_session_stats()
            admin_count = len(await self.whitelist_manager.list_admins())
            
            return {
                "sessions": session_stats,
                "admin_count": admin_count,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting system stats: {e}")
            return None