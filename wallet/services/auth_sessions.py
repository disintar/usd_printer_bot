"""Async authentication session management."""
from __future__ import annotations

import logging
from datetime import timedelta

from asgiref.sync import sync_to_async
from django.db import models, transaction

logger = logging.getLogger(__name__)
SESSION_TOKEN_PREFIX = "session_"


class PendingAuth(models.Model):
    token = models.CharField(max_length=64, unique=True)
    telegram_user_id = models.BigIntegerField(null=True)
    session_token = models.CharField(max_length=64, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True)

    @staticmethod
    def generate_token() -> str:
        import secrets
        return secrets.token_hex(16)

    @classmethod
    async def create_pending_auth(cls, token: str | None = None, ttl_seconds: int = 300) -> "PendingAuth":
        from django.utils import timezone
        if token is None:
            token = cls.generate_token()

        expires_at = timezone.now() + timedelta(seconds=ttl_seconds)

        pending, created = await cls.objects.aget_or_create(
            token=token,
            defaults={"expires_at": expires_at, "completed": False},
        )
        logger.info(f"PendingAuth.create: token={token}, created={created}, completed={pending.completed}")
        return pending

    @classmethod
    async def complete_auth(cls, token: str, telegram_user_id: int, session_token: str) -> "PendingAuth | None":
        from django.utils import timezone

        def _do_complete() -> "PendingAuth | None":
            with transaction.atomic():
                try:
                    pending = cls.objects.select_for_update().get(token=token)
                    logger.info(f"PendingAuth.complete: token={token}, current_completed={pending.completed}")

                    if pending.completed:
                        logger.warning(f"PendingAuth.complete: already done token={token}")
                        return pending

                    pending.completed = True
                    pending.completed_at = timezone.now()
                    pending.telegram_user_id = telegram_user_id
                    pending.session_token = session_token
                    pending.save()
                    logger.info(f"PendingAuth.complete: SUCCESS token={token}, session={session_token[:20]}...")
                    return pending
                except cls.DoesNotExist:
                    logger.error(f"PendingAuth.complete: NOT FOUND token={token}")
                    return None

        return await sync_to_async(_do_complete)()

    @classmethod
    async def get_pending(cls, token: str) -> "PendingAuth | None":
        from django.utils import timezone
        try:
            pending = await cls.objects.aget(token=token, completed=False)
            if pending.expires_at < timezone.now():
                logger.info(f"PendingAuth.get_pending: EXPIRED token={token}")
                return None
            logger.info(f"PendingAuth.get_pending: FOUND token={token}")
            return pending
        except cls.DoesNotExist:
            logger.info(f"PendingAuth.get_pending: NOT FOUND token={token}")
            return None


class AuthSession(models.Model):
    session_token = models.CharField(max_length=64, unique=True)
    telegram_user_id = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    @staticmethod
    def _normalize_candidates(token: str) -> list[str]:
        """Build lookup candidates to support prefixed and legacy tokens."""
        if token.startswith(SESSION_TOKEN_PREFIX):
            legacy_token = token[len(SESSION_TOKEN_PREFIX):]
            return [token, legacy_token]
        return [token, f"{SESSION_TOKEN_PREFIX}{token}"]

    @classmethod
    async def create_session(cls, telegram_user_id: int, ttl_seconds: int = 86400 * 7) -> "AuthSession":
        import secrets
        from django.utils import timezone
        token = f"{SESSION_TOKEN_PREFIX}{secrets.token_hex(24)}"
        expires_at = timezone.now() + timedelta(seconds=ttl_seconds)
        session = await cls.objects.acreate(
            session_token=token,
            telegram_user_id=telegram_user_id,
            expires_at=expires_at,
        )
        logger.info(f"AuthSession.create: session={token[:20]}..., user={telegram_user_id}")
        return session

    @classmethod
    async def validate_session(cls, token: str) -> "AuthSession | None":
        from django.utils import timezone
        token_candidates = cls._normalize_candidates(token)
        session = await cls.objects.filter(session_token__in=token_candidates).order_by("-created_at").afirst()
        if session is None:
            logger.warning(f"AuthSession.validate: NOT FOUND token={token[:20]}...")
            return None
        if session.expires_at < timezone.now():
            await session.adelete()
            logger.warning(f"AuthSession.validate: EXPIRED token={token[:20]}...")
            return None
        logger.info(f"AuthSession.validate: VALID token={token[:20]}...")
        return session
