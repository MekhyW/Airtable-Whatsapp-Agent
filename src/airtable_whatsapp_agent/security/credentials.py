"""
Credential management system for secure storage and retrieval of API keys and secrets.
"""

import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from pathlib import Path

from .encryption import EncryptionService


logger = logging.getLogger(__name__)


class CredentialStore:
    """Secure credential storage backend."""
    
    def __init__(self, storage_path: str, encryption_service: EncryptionService):
        """Initialize credential store."""
        self.storage_path = Path(storage_path)
        self.encryption_service = encryption_service
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
    def store(self, key: str, value: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Store encrypted credential."""
        try:
            credentials = self._load_credentials()
            encrypted_value = self.encryption_service.encrypt(value)
            credentials[key] = {
                "value": encrypted_value,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
                "metadata": metadata or {}
            }
            return self._save_credentials(credentials)
        except Exception as e:
            logger.error(f"Error storing credential {key}: {str(e)}")
            return False
            
    def retrieve(self, key: str) -> Optional[str]:
        """Retrieve and decrypt credential."""
        try:
            credentials = self._load_credentials()
            if key not in credentials:
                return None
            encrypted_value = credentials[key]["value"]
            return self.encryption_service.decrypt(encrypted_value)
        except Exception as e:
            logger.error(f"Error retrieving credential {key}: {str(e)}")
            return None
            
    def delete(self, key: str) -> bool:
        """Delete credential."""
        try:
            credentials = self._load_credentials()
            if key in credentials:
                del credentials[key]
                return self._save_credentials(credentials)
            return False
        except Exception as e:
            logger.error(f"Error deleting credential {key}: {str(e)}")
            return False
            
    def list_keys(self) -> List[str]:
        """List all credential keys."""
        try:
            credentials = self._load_credentials()
            return list(credentials.keys())
        except Exception as e:
            logger.error(f"Error listing credential keys: {str(e)}")
            return []
            
    def get_metadata(self, key: str) -> Optional[Dict[str, Any]]:
        """Get credential metadata."""
        try:
            credentials = self._load_credentials()
            if key not in credentials:
                return None
            return credentials[key].get("metadata", {})
        except Exception as e:
            logger.error(f"Error getting metadata for {key}: {str(e)}")
            return None
            
    def update_metadata(self, key: str, metadata: Dict[str, Any]) -> bool:
        """Update credential metadata."""
        try:
            credentials = self._load_credentials()
            if key not in credentials:
                return False
            credentials[key]["metadata"] = metadata
            credentials[key]["updated_at"] = datetime.utcnow().isoformat()
            return self._save_credentials(credentials)
        except Exception as e:
            logger.error(f"Error updating metadata for {key}: {str(e)}")
            return False
            
    def _load_credentials(self) -> Dict[str, Any]:
        """Load credentials from storage."""
        if not self.storage_path.exists():
            return {}
        try:
            with open(self.storage_path, 'r') as f:
                encrypted_data = f.read()
            if not encrypted_data.strip():
                return {}
            decrypted_data = self.encryption_service.decrypt(encrypted_data) # Decrypt the entire credential store
            return json.loads(decrypted_data)
            
        except Exception as e:
            logger.error(f"Error loading credentials: {str(e)}")
            return {}
            
    def _save_credentials(self, credentials: Dict[str, Any]) -> bool:
        """Save credentials to storage."""
        try:
            json_data = json.dumps(credentials, indent=2)
            encrypted_data = self.encryption_service.encrypt(json_data) # Encrypt the entire credential store
            temp_path = self.storage_path.with_suffix('.tmp')
            with open(temp_path, 'w') as f:
                f.write(encrypted_data)
            temp_path.replace(self.storage_path)
            return True
        except Exception as e:
            logger.error(f"Error saving credentials: {str(e)}")
            return False


class CredentialManager:
    """High-level credential management interface."""
    
    def __init__(self, storage_path: str = "credentials.enc", master_key: Optional[str] = None):
        """Initialize credential manager."""
        self.encryption_service = EncryptionService(master_key)
        self.store = CredentialStore(storage_path, self.encryption_service)
        self._cache = {}
        self._cache_ttl = {}
        
    def set_credential(self, key: str, value: str, description: str = "", expires_in_days: Optional[int] = None) -> bool:
        """Set a credential with optional expiration."""
        metadata = {"description": description, "key_fingerprint": self.encryption_service.get_key_fingerprint()}
        if expires_in_days:
            expiry_date = datetime.utcnow() + timedelta(days=expires_in_days)
            metadata["expires_at"] = expiry_date.isoformat()
        success = self.store.store(key, value, metadata)
        if success:
            self._cache.pop(key, None)
            self._cache_ttl.pop(key, None)
        return success
        
    def get_credential(self, key: str, use_cache: bool = True) -> Optional[str]:
        """Get a credential with optional caching."""
        if use_cache and key in self._cache:
            if key in self._cache_ttl and datetime.utcnow() < self._cache_ttl[key]:
                return self._cache[key]
            else:
                self._cache.pop(key, None)
                self._cache_ttl.pop(key, None)
        metadata = self.store.get_metadata(key)
        if metadata and "expires_at" in metadata:
            expiry_date = datetime.fromisoformat(metadata["expires_at"])
            if datetime.utcnow() > expiry_date:
                logger.warning(f"Credential {key} has expired")
                return None
        value = self.store.retrieve(key)
        if value and use_cache:
            self._cache[key] = value
            self._cache_ttl[key] = datetime.utcnow() + timedelta(minutes=5) # Cache for 5 minutes
        return value
        
    def delete_credential(self, key: str) -> bool:
        """Delete a credential."""
        success = self.store.delete(key)
        if success:
            self._cache.pop(key, None)
            self._cache_ttl.pop(key, None)
        return success
        
    def list_credentials(self) -> List[Dict[str, Any]]:
        """List all credentials with metadata."""
        credentials = []
        for key in self.store.list_keys():
            metadata = self.store.get_metadata(key)
            credential_info = {
                "key": key,
                "description": metadata.get("description", "") if metadata else "",
                "created_at": metadata.get("created_at") if metadata else None,
                "updated_at": metadata.get("updated_at") if metadata else None,
                "expires_at": metadata.get("expires_at") if metadata else None,
                "is_expired": False
            }
            if credential_info["expires_at"]:
                expiry_date = datetime.fromisoformat(credential_info["expires_at"])
                credential_info["is_expired"] = datetime.utcnow() > expiry_date
            credentials.append(credential_info)
        return credentials
        
    def rotate_credential(self, key: str, new_value: str) -> bool:
        """Rotate a credential while preserving metadata."""
        metadata = self.store.get_metadata(key)
        if not metadata:
            return False
        metadata["rotated_at"] = datetime.utcnow().isoformat()
        metadata["rotation_count"] = metadata.get("rotation_count", 0) + 1
        return self.store.store(key, new_value, metadata)
        
    def cleanup_expired(self) -> int:
        """Remove expired credentials."""
        removed_count = 0
        for credential in self.list_credentials():
            if credential["is_expired"]:
                if self.delete_credential(credential["key"]):
                    removed_count += 1     
        return removed_count
        
    def export_credentials(self, keys: Optional[List[str]] = None) -> Dict[str, str]:
        """Export credentials (for backup/migration)."""
        exported = {}
        keys_to_export = keys or self.store.list_keys()
        for key in keys_to_export:
            value = self.get_credential(key, use_cache=False)
            if value:
                exported[key] = value 
        return exported
        
    def import_credentials(self, credentials: Dict[str, str], overwrite: bool = False) -> Dict[str, bool]:
        """Import credentials from export."""
        results = {}
        for key, value in credentials.items():
            if not overwrite and key in self.store.list_keys():
                results[key] = False
                continue
            results[key] = self.set_credential(key, value, description=f"Imported on {datetime.utcnow().isoformat()}")
        return results
        
    def get_stats(self) -> Dict[str, Any]:
        """Get credential store statistics."""
        credentials = self.list_credentials()
        return {
            "total_credentials": len(credentials),
            "expired_credentials": sum(1 for c in credentials if c["is_expired"]),
            "cache_size": len(self._cache),
            "key_fingerprint": self.encryption_service.get_key_fingerprint(),
            "storage_path": str(self.store.storage_path)
        }