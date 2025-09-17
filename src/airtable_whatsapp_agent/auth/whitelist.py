"""
Administrator whitelist management using Airtable.
"""

import logging
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta

from ..models.airtable import AdminWhitelistRecord
from ..models.auth import UserRole, PermissionType
from ..mcp.manager import MCPServerManager


logger = logging.getLogger(__name__)


class WhitelistManager:
    """Manages administrator whitelist stored in Airtable."""
    
    def __init__(
        self,
        mcp_manager: MCPServerManager,
        whitelist_table: str = "Admin Whitelist",
        cache_ttl: int = 300  # 5 minutes
    ):
        """Initialize whitelist manager."""
        self.mcp_manager = mcp_manager
        self.whitelist_table = whitelist_table
        self.cache_ttl = cache_ttl
        self.logger = logging.getLogger(__name__)
        
        # Cache for whitelist data
        self._cache: Dict[str, AdminWhitelistRecord] = {}
        self._cache_timestamp: Optional[datetime] = None
        
    async def is_admin(self, phone_number: str) -> bool:
        """Check if phone number is in admin whitelist."""
        try:
            # Normalize phone number
            normalized_phone = self._normalize_phone_number(phone_number)
            
            # Get whitelist data
            whitelist = await self._get_whitelist()
            
            # Check if phone number exists and is active
            admin_record = whitelist.get(normalized_phone)
            if not admin_record:
                self.logger.warning(f"Phone number {normalized_phone} not in whitelist")
                return False
                
            if not admin_record.is_active:
                self.logger.warning(f"Admin {normalized_phone} is inactive")
                return False
                
            # Update last seen
            await self._update_last_seen(admin_record.record_id, normalized_phone)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking admin status for {phone_number}: {e}")
            return False
            
    async def get_admin_info(self, phone_number: str) -> Optional[AdminWhitelistRecord]:
        """Get admin information from whitelist."""
        try:
            normalized_phone = self._normalize_phone_number(phone_number)
            whitelist = await self._get_whitelist()
            return whitelist.get(normalized_phone)
        except Exception as e:
            self.logger.error(f"Error getting admin info for {phone_number}: {e}")
            return None
            
    async def add_admin(
        self,
        phone_number: str,
        name: str,
        role: UserRole = UserRole.ADMIN,
        permissions: Optional[List[PermissionType]] = None,
        notes: Optional[str] = None
    ) -> bool:
        """Add new admin to whitelist."""
        try:
            normalized_phone = self._normalize_phone_number(phone_number)
            
            # Check if admin already exists
            existing_admin = await self.get_admin_info(normalized_phone)
            if existing_admin:
                self.logger.warning(f"Admin {normalized_phone} already exists")
                return False
                
            # Prepare record data
            record_data = {
                "Phone Number": normalized_phone,
                "Name": name,
                "Role": role.value,
                "Is Active": True,
                "Added Date": datetime.utcnow().isoformat(),
                "Last Seen": None,
                "Notes": notes or ""
            }
            
            # Add permissions if provided
            if permissions:
                record_data["Permissions"] = [p.value for p in permissions]
            else:
                # Default admin permissions
                record_data["Permissions"] = [
                    PermissionType.READ_AIRTABLE.value,
                    PermissionType.WRITE_AIRTABLE.value,
                    PermissionType.SEND_WHATSAPP.value,
                    PermissionType.MANAGE_USERS.value
                ]
                
            # Create record in Airtable
            result = await self.mcp_manager.call_tool(
                "airtable",
                "create_record",
                {
                    "table_name": self.whitelist_table,
                    "fields": record_data
                }
            )
            
            if result:
                self.logger.info(f"Added admin {normalized_phone} to whitelist")
                # Clear cache to force refresh
                self._clear_cache()
                return True
            else:
                self.logger.error(f"Failed to add admin {normalized_phone}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error adding admin {phone_number}: {e}")
            return False
            
    async def remove_admin(self, phone_number: str) -> bool:
        """Remove admin from whitelist (deactivate)."""
        try:
            normalized_phone = self._normalize_phone_number(phone_number)
            
            # Get admin record
            admin_record = await self.get_admin_info(normalized_phone)
            if not admin_record:
                self.logger.warning(f"Admin {normalized_phone} not found")
                return False
                
            # Update record to inactive
            result = await self.mcp_manager.call_tool(
                "airtable",
                "update_record",
                {
                    "table_name": self.whitelist_table,
                    "record_id": admin_record.record_id,
                    "fields": {
                        "Is Active": False,
                        "Deactivated Date": datetime.utcnow().isoformat()
                    }
                }
            )
            
            if result:
                self.logger.info(f"Deactivated admin {normalized_phone}")
                # Clear cache to force refresh
                self._clear_cache()
                return True
            else:
                self.logger.error(f"Failed to deactivate admin {normalized_phone}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error removing admin {phone_number}: {e}")
            return False
            
    async def update_admin_permissions(
        self,
        phone_number: str,
        permissions: List[PermissionType]
    ) -> bool:
        """Update admin permissions."""
        try:
            normalized_phone = self._normalize_phone_number(phone_number)
            
            # Get admin record
            admin_record = await self.get_admin_info(normalized_phone)
            if not admin_record:
                self.logger.warning(f"Admin {normalized_phone} not found")
                return False
                
            # Update permissions
            result = await self.mcp_manager.call_tool(
                "airtable",
                "update_record",
                {
                    "table_name": self.whitelist_table,
                    "record_id": admin_record.record_id,
                    "fields": {
                        "Permissions": [p.value for p in permissions],
                        "Updated Date": datetime.utcnow().isoformat()
                    }
                }
            )
            
            if result:
                self.logger.info(f"Updated permissions for admin {normalized_phone}")
                # Clear cache to force refresh
                self._clear_cache()
                return True
            else:
                self.logger.error(f"Failed to update permissions for admin {normalized_phone}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error updating admin permissions for {phone_number}: {e}")
            return False
            
    async def list_admins(self, active_only: bool = True) -> List[AdminWhitelistRecord]:
        """List all admins in whitelist."""
        try:
            whitelist = await self._get_whitelist()
            admins = list(whitelist.values())
            
            if active_only:
                admins = [admin for admin in admins if admin.is_active]
                
            return sorted(admins, key=lambda x: x.name)
            
        except Exception as e:
            self.logger.error(f"Error listing admins: {e}")
            return []
            
    async def get_admin_permissions(self, phone_number: str) -> List[PermissionType]:
        """Get admin permissions."""
        admin_record = await self.get_admin_info(phone_number)
        if admin_record and admin_record.is_active:
            return admin_record.permissions
        return []
        
    async def has_permission(
        self,
        phone_number: str,
        permission: PermissionType
    ) -> bool:
        """Check if admin has specific permission."""
        permissions = await self.get_admin_permissions(phone_number)
        return permission in permissions
        
    async def _get_whitelist(self) -> Dict[str, AdminWhitelistRecord]:
        """Get whitelist data with caching."""
        # Check cache validity
        if (self._cache_timestamp and 
            datetime.utcnow() - self._cache_timestamp < timedelta(seconds=self.cache_ttl)):
            return self._cache
            
        # Fetch fresh data from Airtable
        try:
            records = await self.mcp_manager.call_tool(
                "airtable",
                "list_records",
                {
                    "table_name": self.whitelist_table,
                    "filter_by_formula": "NOT({Phone Number} = '')"
                }
            )
            
            # Parse records into AdminWhitelistRecord objects
            whitelist = {}
            for record in records.get("records", []):
                try:
                    admin_record = AdminWhitelistRecord(
                        record_id=record["id"],
                        phone_number=record["fields"].get("Phone Number", ""),
                        name=record["fields"].get("Name", ""),
                        role=UserRole(record["fields"].get("Role", "admin")),
                        is_active=record["fields"].get("Is Active", False),
                        permissions=[
                            PermissionType(p) for p in 
                            record["fields"].get("Permissions", [])
                        ],
                        added_date=record["fields"].get("Added Date"),
                        last_seen=record["fields"].get("Last Seen"),
                        notes=record["fields"].get("Notes", "")
                    )
                    
                    # Normalize phone number for consistent lookup
                    normalized_phone = self._normalize_phone_number(admin_record.phone_number)
                    whitelist[normalized_phone] = admin_record
                    
                except Exception as e:
                    self.logger.error(f"Error parsing admin record {record.get('id')}: {e}")
                    continue
                    
            # Update cache
            self._cache = whitelist
            self._cache_timestamp = datetime.utcnow()
            
            self.logger.info(f"Loaded {len(whitelist)} admin records from whitelist")
            return whitelist
            
        except Exception as e:
            self.logger.error(f"Error fetching whitelist from Airtable: {e}")
            # Return cached data if available
            return self._cache
            
    async def _update_last_seen(self, record_id: str, phone_number: str) -> None:
        """Update last seen timestamp for admin."""
        try:
            await self.mcp_manager.call_tool(
                "airtable",
                "update_record",
                {
                    "table_name": self.whitelist_table,
                    "record_id": record_id,
                    "fields": {
                        "Last Seen": datetime.utcnow().isoformat()
                    }
                }
            )
        except Exception as e:
            self.logger.error(f"Error updating last seen for {phone_number}: {e}")
            
    def _normalize_phone_number(self, phone_number: str) -> str:
        """Normalize phone number format."""
        # Remove all non-digit characters
        digits_only = ''.join(filter(str.isdigit, phone_number))
        
        # Add country code if missing (assuming +1 for US/Canada)
        if len(digits_only) == 10:
            digits_only = "1" + digits_only
        elif len(digits_only) == 11 and digits_only.startswith("1"):
            pass  # Already has country code
        
        # Format as +1XXXXXXXXXX
        return f"+{digits_only}"
        
    def _clear_cache(self) -> None:
        """Clear whitelist cache."""
        self._cache.clear()
        self._cache_timestamp = None
        
    async def refresh_cache(self) -> None:
        """Force refresh of whitelist cache."""
        self._clear_cache()
        await self._get_whitelist()