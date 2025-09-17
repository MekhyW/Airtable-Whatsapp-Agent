"""
Encryption service for secure credential storage and data protection.
"""

import base64
import hashlib
import secrets
from typing import Optional, Dict, Any
import logging
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


logger = logging.getLogger(__name__)


class EncryptionService:
    """Service for encrypting and decrypting sensitive data."""
    
    def __init__(self, master_key: Optional[str] = None):
        """Initialize encryption service with master key."""
        self.master_key = master_key or self._generate_master_key()
        self._fernet = self._create_fernet(self.master_key)
        
    def _generate_master_key(self) -> str:
        """Generate a new master key."""
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
        
    def _create_fernet(self, master_key: str) -> Fernet:
        """Create Fernet instance from master key."""
        try:
            key_bytes = base64.urlsafe_b64decode(master_key.encode())
            if len(key_bytes) == 32:
                return Fernet(master_key.encode())
        except Exception:
            pass
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'airtable_whatsapp_agent_salt',  # Use a fixed salt for consistency
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(master_key.encode()))
        return Fernet(key)
        
    def encrypt(self, data: str) -> str:
        """Encrypt string data."""
        try:
            encrypted_data = self._fernet.encrypt(data.encode())
            return base64.urlsafe_b64encode(encrypted_data).decode()
        except Exception as e:
            logger.error(f"Encryption error: {str(e)}")
            raise
            
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt string data."""
        try:
            decoded_data = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted_data = self._fernet.decrypt(decoded_data)
            return decrypted_data.decode()
        except Exception as e:
            logger.error(f"Decryption error: {str(e)}")
            raise
            
    def encrypt_dict(self, data: Dict[str, Any]) -> str:
        """Encrypt dictionary data."""
        import json
        json_data = json.dumps(data, sort_keys=True)
        return self.encrypt(json_data)
        
    def decrypt_dict(self, encrypted_data: str) -> Dict[str, Any]:
        """Decrypt dictionary data."""
        import json
        json_data = self.decrypt(encrypted_data)
        return json.loads(json_data)
        
    def hash_password(self, password: str, salt: Optional[str] = None) -> tuple[str, str]:
        """Hash password with salt."""
        if salt is None:
            salt = secrets.token_hex(32)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt.encode(),
            iterations=100000,
        )
        password_hash = base64.urlsafe_b64encode(kdf.derive(password.encode())).decode()
        return password_hash, salt
        
    def verify_password(self, password: str, password_hash: str, salt: str) -> bool:
        """Verify password against hash."""
        try:
            computed_hash, _ = self.hash_password(password, salt)
            return secrets.compare_digest(computed_hash, password_hash)
        except Exception as e:
            logger.error(f"Password verification error: {str(e)}")
            return False
            
    def generate_token(self, length: int = 32) -> str:
        """Generate secure random token."""
        return secrets.token_urlsafe(length)
        
    def hash_data(self, data: str) -> str:
        """Create SHA-256 hash of data."""
        return hashlib.sha256(data.encode()).hexdigest()
        
    def create_signature(self, data: str, secret: str) -> str:
        """Create HMAC signature for data."""
        import hmac
        signature = hmac.new(secret.encode(), data.encode(), hashlib.sha256).hexdigest()
        return signature
        
    def verify_signature(self, data: str, signature: str, secret: str) -> bool:
        """Verify HMAC signature."""
        try:
            expected_signature = self.create_signature(data, secret)
            return secrets.compare_digest(signature, expected_signature)
        except Exception as e:
            logger.error(f"Signature verification error: {str(e)}")
            return False
            
    def encrypt_file_content(self, content: bytes) -> bytes:
        """Encrypt file content."""
        try:
            return self._fernet.encrypt(content)
        except Exception as e:
            logger.error(f"File encryption error: {str(e)}")
            raise
            
    def decrypt_file_content(self, encrypted_content: bytes) -> bytes:
        """Decrypt file content."""
        try:
            return self._fernet.decrypt(encrypted_content)
        except Exception as e:
            logger.error(f"File decryption error: {str(e)}")
            raise
            
    def rotate_key(self, new_master_key: str) -> 'EncryptionService':
        """Create new encryption service with rotated key."""
        return EncryptionService(new_master_key)
        
    def get_key_fingerprint(self) -> str:
        """Get fingerprint of current encryption key."""
        return self.hash_data(self.master_key)[:16]