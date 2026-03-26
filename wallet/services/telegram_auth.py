"""Telegram Login Widget authentication service."""
from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass
from typing import Any

from .auth_sessions import AuthSession as PersistentAuthSession


@dataclass
class TelegramUser:
    """Represents a Telegram user from Login Widget."""
    user_id: int
    username: str
    first_name: str
    last_name: str | None
    photo_url: str | None
    auth_date: int


@dataclass
class AuthSession:
    """Session for authenticated user."""
    session_token: str
    user_id: int
    created_at: float
    expires_at: float


class TelegramAuthService:
    """Service for Telegram Login Widget authentication."""
    
    def __init__(self, bot_token: str) -> None:
        self.bot_token = bot_token

    @staticmethod
    def _from_persistent(session: PersistentAuthSession) -> AuthSession:
        """Map DB session model to DTO used by Telegram auth helpers."""
        created_at = session.created_at.timestamp()
        expires_at = session.expires_at.timestamp()
        return AuthSession(
            session_token=session.session_token,
            user_id=session.telegram_user_id,
            created_at=created_at,
            expires_at=expires_at,
        )
    
    def verify_login_widget_data(self, data: dict[str, Any]) -> TelegramUser | None:
        """
        Verify Telegram Login Widget data.
        
        Data should contain: id, first_name, auth_date, hash
        Optional: last_name, username, photo_url
        """
        try:
            # Extract required fields
            user_id = int(data.get("id", 0))
            first_name = data.get("first_name", "")
            auth_date = int(data.get("auth_date", 0))
            received_hash = data.get("hash", "")
            
            if not all([user_id, first_name, auth_date, received_hash]):
                return None
            
            # Check auth_date is not too old (max 24 hours)
            if abs(time.time() - auth_date) > 86400:
                return None
            
            # Build the data check string (sorted by key)
            data_check_string = "\n".join(
                f"{key}={value}" for key, value in sorted(data.items())
                if key != "hash"
            )
            
            # Compute secret using HMAC-SHA256(bot_token, "WebAppData")
            secret = hmac.new(
                b"WebAppData",
                self.bot_token.encode(),
                hashlib.sha256
            ).digest()
            
            # Compute expected hash
            expected_hash = hmac.new(
                secret,
                data_check_string.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Verify hash matches
            if not hmac.compare_digest(expected_hash, received_hash):
                return None
            
            return TelegramUser(
                user_id=user_id,
                username=data.get("username", ""),
                first_name=first_name,
                last_name=data.get("last_name"),
                photo_url=data.get("photo_url"),
                auth_date=auth_date,
            )
            
        except Exception:
            return None
    
    def create_session(self, user_id: int) -> AuthSession:
        """Create a persisted DB session for authenticated user."""
        session = PersistentAuthSession.create_session(user_id)
        return self._from_persistent(session)

    def validate_session(self, session_token: str) -> AuthSession | None:
        """Validate a persisted session token."""
        session = PersistentAuthSession.validate_session(session_token)
        if session is None:
            return None
        return self._from_persistent(session)


def validate_telegram_login_data(bot_token: str, data: dict[str, Any]) -> TelegramUser | None:
    """Standalone function to validate Telegram login widget data."""
    service = TelegramAuthService(bot_token)
    return service.verify_login_widget_data(data)


def create_user_session(user_id: int) -> AuthSession:
    """Create a session for a user."""
    service = TelegramAuthService("")  # Token not needed for session creation
    return service.create_session(user_id)


def validate_session(session_token: str) -> AuthSession | None:
    """Validate a session token."""
    service = TelegramAuthService("")
    return service.validate_session(session_token)
