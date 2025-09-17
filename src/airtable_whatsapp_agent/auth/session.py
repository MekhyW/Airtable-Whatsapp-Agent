"""
Session management for authenticated users.
"""

import logging
import secrets
from typing import Dict, Optional
from datetime import datetime, timedelta

from ..models.auth import UserSession, SessionStatus
from ..models.airtable import AdminWhitelistRecord


logger = logging.getLogger(__name__)


class SessionManager:
    """Manages user sessions for authenticated administrators."""
    
    def __init__(self, session_timeout: int = 3600):  # 1 hour default
        """Initialize session manager."""
        self.session_timeout = session_timeout
        self.sessions: Dict[str, UserSession] = {}
        self.phone_to_session: Dict[str, str] = {}
        self.logger = logging.getLogger(__name__)
        
    async def create_session(
        self,
        admin_record: AdminWhitelistRecord,
        context: Optional[Dict] = None
    ) -> UserSession:
        """Create new session for authenticated admin."""
        # Generate secure session token
        session_token = secrets.token_urlsafe(32)
        
        # Calculate expiry time
        expires_at = datetime.utcnow() + timedelta(seconds=self.session_timeout)
        
        # Create session
        session = UserSession(
            session_id=session_token,
            phone_number=admin_record.phone_number,
            user_role=admin_record.role,
            permissions=admin_record.permissions,
            created_at=datetime.utcnow(),
            expires_at=expires_at,
            last_activity=datetime.utcnow(),
            status=SessionStatus.ACTIVE,
            context=context or {}
        )
        
        # Store session
        self.sessions[session_token] = session
        
        # Update phone number mapping (remove old session if exists)
        old_session_id = self.phone_to_session.get(admin_record.phone_number)
        if old_session_id and old_session_id in self.sessions:
            await self.invalidate_session(old_session_id)
            
        self.phone_to_session[admin_record.phone_number] = session_token
        
        self.logger.info(f"Created session for {admin_record.phone_number}")
        return session
        
    async def get_session(self, session_token: str) -> Optional[UserSession]:
        """Get session by token."""
        session = self.sessions.get(session_token)
        
        if not session:
            return None
            
        # Check if session is expired
        if datetime.utcnow() > session.expires_at:
            await self.invalidate_session(session_token)
            return None
            
        # Check if session is active
        if session.status != SessionStatus.ACTIVE:
            return None
            
        # Update last activity
        session.last_activity = datetime.utcnow()
        
        return session
        
    async def get_session_by_phone(self, phone_number: str) -> Optional[UserSession]:
        """Get active session by phone number."""
        session_token = self.phone_to_session.get(phone_number)
        if not session_token:
            return None
            
        return await self.get_session(session_token)
        
    async def invalidate_session(self, session_token: str) -> bool:
        """Invalidate session."""
        session = self.sessions.get(session_token)
        if not session:
            return False
            
        # Update session status
        session.status = SessionStatus.EXPIRED
        session.ended_at = datetime.utcnow()
        
        # Remove from active sessions
        self.sessions.pop(session_token, None)
        
        # Remove phone mapping
        if session.phone_number in self.phone_to_session:
            if self.phone_to_session[session.phone_number] == session_token:
                self.phone_to_session.pop(session.phone_number, None)
                
        self.logger.info(f"Invalidated session for {session.phone_number}")
        return True
        
    async def invalidate_user_sessions(self, phone_number: str) -> int:
        """Invalidate all sessions for a user."""
        invalidated_count = 0
        
        # Find all sessions for the user
        sessions_to_invalidate = []
        for session_token, session in self.sessions.items():
            if session.phone_number == phone_number:
                sessions_to_invalidate.append(session_token)
                
        # Invalidate each session
        for session_token in sessions_to_invalidate:
            if await self.invalidate_session(session_token):
                invalidated_count += 1
                
        return invalidated_count
        
    async def extend_session(
        self,
        session_token: str,
        extension_seconds: Optional[int] = None
    ) -> bool:
        """Extend session expiry time."""
        session = await self.get_session(session_token)
        if not session:
            return False
            
        # Use default timeout if not specified
        extension = extension_seconds or self.session_timeout
        
        # Extend expiry time
        session.expires_at = datetime.utcnow() + timedelta(seconds=extension)
        session.last_activity = datetime.utcnow()
        
        self.logger.info(f"Extended session for {session.phone_number}")
        return True
        
    async def update_session_context(
        self,
        session_token: str,
        context_updates: Dict
    ) -> bool:
        """Update session context."""
        session = await self.get_session(session_token)
        if not session:
            return False
            
        # Update context
        session.context.update(context_updates)
        session.last_activity = datetime.utcnow()
        
        return True
        
    async def get_active_sessions(self) -> Dict[str, UserSession]:
        """Get all active sessions."""
        active_sessions = {}
        
        for session_token, session in self.sessions.items():
            if (session.status == SessionStatus.ACTIVE and 
                datetime.utcnow() <= session.expires_at):
                active_sessions[session_token] = session
                
        return active_sessions
        
    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions."""
        expired_sessions = []
        current_time = datetime.utcnow()
        
        # Find expired sessions
        for session_token, session in self.sessions.items():
            if current_time > session.expires_at:
                expired_sessions.append(session_token)
                
        # Remove expired sessions
        cleanup_count = 0
        for session_token in expired_sessions:
            if await self.invalidate_session(session_token):
                cleanup_count += 1
                
        if cleanup_count > 0:
            self.logger.info(f"Cleaned up {cleanup_count} expired sessions")
            
        return cleanup_count
        
    async def get_session_stats(self) -> Dict:
        """Get session statistics."""
        total_sessions = len(self.sessions)
        active_sessions = len(await self.get_active_sessions())
        unique_users = len(set(session.phone_number for session in self.sessions.values()))
        
        return {
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
            "unique_users": unique_users,
            "session_timeout": self.session_timeout
        }
        
    async def is_session_valid(self, session_token: str) -> bool:
        """Check if session is valid."""
        session = await self.get_session(session_token)
        return session is not None
        
    async def get_user_session_history(self, phone_number: str) -> List[UserSession]:
        """Get session history for a user (active sessions only)."""
        user_sessions = []
        
        for session in self.sessions.values():
            if session.phone_number == phone_number:
                user_sessions.append(session)
                
        # Sort by creation time (newest first)
        return sorted(user_sessions, key=lambda x: x.created_at, reverse=True)