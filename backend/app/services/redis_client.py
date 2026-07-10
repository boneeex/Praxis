import json
from datetime import datetime, timezone

import redis.asyncio as aioredis

from app.config import get_settings

settings = get_settings()

_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=False)
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis:
        await _redis.close()
        _redis = None


def ydoc_key(material_id: int) -> str:
    return f"ydoc:{material_id}"


def ydoc_channel(material_id: int) -> str:
    return f"ydoc:channel:{material_id}"


def room_presence_key(lesson_id: int) -> str:
    return f"room:{lesson_id}:presence"


def room_edit_grants_key(lesson_id: int) -> str:
    return f"room:{lesson_id}:edit_grants"


def room_channel(lesson_id: int) -> str:
    return f"room:channel:{lesson_id}"


async def enqueue_execute(payload: dict) -> None:
    r = await get_redis()
    await r.rpush(settings.execute_queue_key, json.dumps(payload).encode())


async def publish_room_event(lesson_id: int, event: dict) -> None:
    r = await get_redis()
    await r.publish(room_channel(lesson_id), json.dumps(event).encode())


async def set_presence(lesson_id: int, user_id: int, data: dict, ttl: int = 120) -> None:
    r = await get_redis()
    key = room_presence_key(lesson_id)
    await r.hset(key, str(user_id), json.dumps(data).encode())
    await r.expire(key, ttl)


async def remove_presence(lesson_id: int, user_id: int) -> None:
    r = await get_redis()
    await r.hdel(room_presence_key(lesson_id), str(user_id))


async def get_presence(lesson_id: int) -> dict[int, dict]:
    r = await get_redis()
    raw = await r.hgetall(room_presence_key(lesson_id))
    result = {}
    for uid, val in raw.items():
        result[int(uid.decode())] = json.loads(val.decode())
    return result


async def set_edit_grant(lesson_id: int, user_id: int, granted: bool) -> None:
    r = await get_redis()
    key = room_edit_grants_key(lesson_id)
    if granted:
        await r.sadd(key, str(user_id))
    else:
        await r.srem(key, str(user_id))
    await r.expire(key, 86400)


async def get_edit_grants(lesson_id: int) -> set[int]:
    r = await get_redis()
    members = await r.smembers(room_edit_grants_key(lesson_id))
    return {int(m.decode()) for m in members}


async def has_edit_grant(lesson_id: int, user_id: int) -> bool:
    grants = await get_edit_grants(lesson_id)
    return user_id in grants
