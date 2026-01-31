"""Redis client for call session state and caching."""

import json
from typing import Any

import redis.asyncio as aioredis
import structlog

from src.config import settings

logger = structlog.get_logger()

_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Get or create the global Redis connection."""
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis


async def close_redis() -> None:
    """Close the Redis connection on shutdown."""
    global _redis
    if _redis is not None:
        await _redis.close()
        _redis = None


class CallSessionStore:
    """Manages per-call session state in Redis.

    Each active phone call gets a session that tracks:
    - Caller phone number
    - Conversation state (greeting / collecting_info / confirming / done)
    - Collected reservation fields so far
    - Call start time and duration
    """

    KEY_PREFIX = "call_session:"
    TTL_SECONDS = 3600  # 1 hour

    def __init__(self, redis: aioredis.Redis) -> None:
        self._r = redis

    def _key(self, call_id: str) -> str:
        return f"{self.KEY_PREFIX}{call_id}"

    async def create(self, call_id: str, caller_phone: str) -> dict[str, Any]:
        """Create a new call session."""
        session = {
            "call_id": call_id,
            "caller_phone": caller_phone,
            "state": "greeting",
            "collected": {},
            "turn_count": 0,
        }
        await self._r.set(
            self._key(call_id),
            json.dumps(session, ensure_ascii=False),
            ex=self.TTL_SECONDS,
        )
        logger.info("call_session.created", call_id=call_id)
        return session

    async def get(self, call_id: str) -> dict[str, Any] | None:
        """Retrieve a call session."""
        data = await self._r.get(self._key(call_id))
        if data is None:
            return None
        return json.loads(data)

    async def update(self, call_id: str, updates: dict[str, Any]) -> None:
        """Merge updates into an existing call session."""
        session = await self.get(call_id)
        if session is None:
            logger.warning("call_session.not_found", call_id=call_id)
            return
        session.update(updates)
        session["turn_count"] = session.get("turn_count", 0) + 1
        await self._r.set(
            self._key(call_id),
            json.dumps(session, ensure_ascii=False),
            ex=self.TTL_SECONDS,
        )

    async def delete(self, call_id: str) -> None:
        """Remove a call session when the call ends."""
        await self._r.delete(self._key(call_id))
        logger.info("call_session.deleted", call_id=call_id)

    async def get_active_count(self) -> int:
        """Return the number of active call sessions."""
        keys = []
        async for key in self._r.scan_iter(match=f"{self.KEY_PREFIX}*"):
            keys.append(key)
        return len(keys)
