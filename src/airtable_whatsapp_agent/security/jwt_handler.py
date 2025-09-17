"""
JWT token handling for authentication and authorization.
"""

import jwt
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass
from .encryption import EncryptionService


logger = logging.getLogger(__name__)


class TokenType(Enum):
    """Types of JWT tokens."""
    ACCESS = "access"
    REFRESH = "refresh"
    API_KEY = "api_key"
    WEBHOOK = "webhook"
    ADMIN = "admin"


class TokenScope(Enum):
    """Token permission scopes."""
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"
    WEBHOOK = "webhook"
    API = "api"


@dataclass
class TokenClaims:
    """JWT token claims structure."""
    
    user_id: str
    token_type: TokenType
    scopes: List[TokenScope]
    issued_at: datetime
    expires_at: datetime
    session_id: Optional[str] = None
    client_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    custom_claims: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JWT payload."""
        claims = {
            "sub": self.user_id,
            "token_type": self.token_type.value,
            "scopes": [scope.value for scope in self.scopes],
            "iat": int(self.issued_at.timestamp()),
            "exp": int(self.expires_at.timestamp()),
        }
        if self.session_id:
            claims["session_id"] = self.session_id
        if self.client_id:
            claims["client_id"] = self.client_id
        if self.ip_address:
            claims["ip"] = self.ip_address
        if self.user_agent:
            claims["user_agent"] = self.user_agent
        if self.custom_claims:
            claims.update(self.custom_claims)
        return claims
        
    @classmethod
    def from_dict(cls, claims: Dict[str, Any]) -> 'TokenClaims':
        """Create from JWT payload dictionary."""
        return cls(
            user_id=claims["sub"],
            token_type=TokenType(claims["token_type"]),
            scopes=[TokenScope(scope) for scope in claims.get("scopes", [])],
            issued_at=datetime.fromtimestamp(claims["iat"], tz=timezone.utc),
            expires_at=datetime.fromtimestamp(claims["exp"], tz=timezone.utc),
            session_id=claims.get("session_id"),
            client_id=claims.get("client_id"),
            ip_address=claims.get("ip"),
            user_agent=claims.get("user_agent"),
            custom_claims={k: v for k, v in claims.items() if k not in ["sub", "token_type", "scopes", "iat", "exp", "session_id", "client_id", "ip", "user_agent"]}
        )


class JWTHandler:
    """JWT token handler with encryption and validation."""
    
    def __init__(
        self,
        secret_key: str,
        algorithm: str = "HS256",
        encryption_service: Optional[EncryptionService] = None,
        default_access_expiry: timedelta = timedelta(hours=1),
        default_refresh_expiry: timedelta = timedelta(days=7),
        issuer: str = "airtable-whatsapp-agent",
        audience: str = "airtable-whatsapp-agent"
    ):
        """Initialize JWT handler."""
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.encryption_service = encryption_service
        self.default_access_expiry = default_access_expiry
        self.default_refresh_expiry = default_refresh_expiry
        self.issuer = issuer
        self.audience = audience
        self._blacklisted_tokens = set()
        
    def create_token(
        self,
        user_id: str,
        token_type: TokenType,
        scopes: List[TokenScope],
        expiry: Optional[timedelta] = None,
        session_id: Optional[str] = None,
        client_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        custom_claims: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a JWT token."""
        now = datetime.now(timezone.utc)
        if expiry is None:
            if token_type == TokenType.ACCESS:
                expiry = self.default_access_expiry
            elif token_type == TokenType.REFRESH:
                expiry = self.default_refresh_expiry
            else:
                expiry = self.default_access_expiry   
        expires_at = now + expiry
        claims = TokenClaims(
            user_id=user_id,
            token_type=token_type,
            scopes=scopes,
            issued_at=now,
            expires_at=expires_at,
            session_id=session_id,
            client_id=client_id,
            ip_address=ip_address,
            user_agent=user_agent,
            custom_claims=custom_claims
        )
        payload = claims.to_dict()
        payload.update({"iss": self.issuer,"aud": self.audience,})
        try:
            token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
            if self.encryption_service:
                token = self.encryption_service.encrypt(token)
            return token
        except Exception as e:
            logger.error(f"Error creating JWT token: {str(e)}")
            raise ValueError(f"Failed to create token: {str(e)}")
            
    def verify_token(
        self,
        token: str,
        expected_type: Optional[TokenType] = None,
        required_scopes: Optional[List[TokenScope]] = None,
        validate_ip: Optional[str] = None
    ) -> TokenClaims:
        """Verify and decode a JWT token."""
        try:
            if self.encryption_service:
                token = self.encryption_service.decrypt(token)
            if token in self._blacklisted_tokens:
                raise ValueError("Token has been revoked")
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                issuer=self.issuer,
                audience=self.audience
            )
            claims = TokenClaims.from_dict(payload)
            if expected_type and claims.token_type != expected_type:
                raise ValueError(f"Invalid token type. Expected {expected_type.value}, got {claims.token_type.value}")
            if required_scopes:
                missing_scopes = set(required_scopes) - set(claims.scopes)
                if missing_scopes:
                    raise ValueError(f"Missing required scopes: {[s.value for s in missing_scopes]}")
            if validate_ip and claims.ip_address and claims.ip_address != validate_ip:
                raise ValueError("Token IP address mismatch")
            if claims.expires_at <= datetime.now(timezone.utc):
                raise ValueError("Token has expired")
            return claims
        except jwt.ExpiredSignatureError:
            raise ValueError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise ValueError(f"Invalid token: {str(e)}")
        except Exception as e:
            logger.error(f"Error verifying JWT token: {str(e)}")
            raise ValueError(f"Token verification failed: {str(e)}")
            
    def refresh_token(self, refresh_token: str, new_scopes: Optional[List[TokenScope]] = None) -> Dict[str, str]:
        """Refresh an access token using a refresh token."""
        try:
            claims = self.verify_token(refresh_token, expected_type=TokenType.REFRESH)
            scopes = new_scopes if new_scopes is not None else claims.scopes
            access_token = self.create_token(
                user_id=claims.user_id,
                token_type=TokenType.ACCESS,
                scopes=scopes,
                session_id=claims.session_id,
                client_id=claims.client_id,
                ip_address=claims.ip_address,
                user_agent=claims.user_agent
            )
            new_refresh_token = self.create_token(
                user_id=claims.user_id,
                token_type=TokenType.REFRESH,
                scopes=scopes,
                session_id=claims.session_id,
                client_id=claims.client_id,
                ip_address=claims.ip_address,
                user_agent=claims.user_agent
            )
            self.revoke_token(refresh_token)
            return {
                "access_token": access_token,
                "refresh_token": new_refresh_token,
                "token_type": "Bearer",
                "expires_in": int(self.default_access_expiry.total_seconds())
            }
        except Exception as e:
            logger.error(f"Error refreshing token: {str(e)}")
            raise ValueError(f"Token refresh failed: {str(e)}")
            
    def revoke_token(self, token: str):
        """Revoke a token by adding it to blacklist."""
        try:
            if self.encryption_service:
                decrypted_token = self.encryption_service.decrypt(token)
                self._blacklisted_tokens.add(decrypted_token)
            else:
                self._blacklisted_tokens.add(token)
        except Exception as e:
            logger.error(f"Error revoking token: {str(e)}")
            
    def revoke_user_tokens(self, user_id: str):
        """Revoke all tokens for a specific user."""
        # Note: This is a simplified implementation
        # In production, we might want to store active tokens in a database
        # and mark them as revoked there
        logger.info(f"Revoking all tokens for user: {user_id}")
        
    def create_api_key(self, user_id: str, scopes: List[TokenScope], name: str, expiry: Optional[timedelta] = None) -> Dict[str, Any]:
        """Create a long-lived API key."""
        if expiry is None:
            expiry = timedelta(days=365)  # 1 year default
        token = self.create_token(user_id=user_id, token_type=TokenType.API_KEY, scopes=scopes, expiry=expiry, custom_claims={"api_key_name": name})
        return {
            "api_key": token,
            "name": name,
            "scopes": [scope.value for scope in scopes],
            "expires_at": (datetime.now(timezone.utc) + expiry).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
    def create_webhook_token(self, webhook_id: str, expiry: Optional[timedelta] = None) -> str:
        """Create a token for webhook verification."""
        if expiry is None:
            expiry = timedelta(days=30)  # 30 days default
        return self.create_token(
            user_id=f"webhook_{webhook_id}",
            token_type=TokenType.WEBHOOK,
            scopes=[TokenScope.WEBHOOK],
            expiry=expiry,
            custom_claims={"webhook_id": webhook_id}
        )
        
    def validate_webhook_token(self, token: str, webhook_id: str) -> bool:
        """Validate a webhook token."""
        try:
            claims = self.verify_token(token, expected_type=TokenType.WEBHOOK)
            return (claims.custom_claims and claims.custom_claims.get("webhook_id") == webhook_id)
        except Exception:
            return False
            
    def get_token_info(self, token: str) -> Dict[str, Any]:
        """Get information about a token without full validation."""
        try:
            if self.encryption_service:
                token = self.encryption_service.decrypt(token)
            payload = jwt.decode(token, options={"verify_signature": False})
            return {
                "user_id": payload.get("sub"),
                "token_type": payload.get("token_type"),
                "scopes": payload.get("scopes", []),
                "issued_at": datetime.fromtimestamp(payload["iat"]).isoformat(),
                "expires_at": datetime.fromtimestamp(payload["exp"]).isoformat(),
                "is_expired": datetime.fromtimestamp(payload["exp"]) <= datetime.now(timezone.utc),
                "session_id": payload.get("session_id"),
                "client_id": payload.get("client_id")
            }
        except Exception as e:
            logger.error(f"Error getting token info: {str(e)}")
            return {}
            
    def cleanup_blacklist(self):
        """Remove expired tokens from blacklist."""
        # This is a simplified implementation
        # In production, you'd want to store blacklist with expiration times
        # and clean up based on those
        logger.info("Cleaning up token blacklist")
        
    def get_blacklist_size(self) -> int:
        """Get the current size of the token blacklist."""
        return len(self._blacklisted_tokens)
        
    def export_blacklist(self) -> List[str]:
        """Export blacklisted tokens (for backup/migration)."""
        return list(self._blacklisted_tokens)
        
    def import_blacklist(self, tokens: List[str]):
        """Import blacklisted tokens (for backup/migration)."""
        self._blacklisted_tokens.update(tokens)
        
    def create_admin_token(self, admin_id: str, expiry: Optional[timedelta] = None) -> str:
        """Create an admin token with full permissions."""
        if expiry is None:
            expiry = timedelta(hours=8)  # 8 hours default for admin sessions
        return self.create_token(user_id=admin_id, token_type=TokenType.ADMIN, scopes=[TokenScope.ADMIN, TokenScope.READ, TokenScope.WRITE], expiry=expiry)
        
    def validate_admin_token(self, token: str) -> bool:
        """Validate an admin token."""
        try:
            self.verify_token(token, expected_type=TokenType.ADMIN, required_scopes=[TokenScope.ADMIN])
            return True
        except Exception:
            return False