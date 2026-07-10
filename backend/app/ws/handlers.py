import asyncio
import json
import time
from collections import defaultdict

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.auth.jwt import decode_access_token
from app.config import get_settings
from app.database import async_session
from app.models import Lesson, Material, Space, SpaceMembership, User, UserRole
from app.services.redis_client import (
    get_edit_grants,
    get_redis,
    publish_room_event,
    remove_presence,
    room_channel,
    set_presence,
    ydoc_channel,
    ydoc_key,
)
from app.services.storage import get_bytes, put_bytes

settings = get_settings()

# Yjs sync protocol message types
MSG_SYNC = 0
MSG_AWARENESS = 1

_local_doc_clients: dict[int, set[WebSocket]] = defaultdict(set)
_local_room_clients: dict[int, set[WebSocket]] = defaultdict(set)
_pubsub_tasks: dict[str, asyncio.Task] = {}


async def _verify_material_access(material_id: int, user_id: int) -> Material | None:
    async with async_session() as db:
        result = await db.execute(select(Material).where(Material.id == material_id))
        material = result.scalar_one_or_none()
        if not material:
            return None
        space_result = await db.execute(select(Space).where(Space.id == material.space_id))
        space = space_result.scalar_one_or_none()
        if not space:
            return None
        if space.teacher_id == user_id:
            return material
        mem = await db.execute(
            select(SpaceMembership).where(SpaceMembership.space_id == material.space_id, SpaceMembership.user_id == user_id)
        )
        if mem.scalar_one_or_none():
            return material
    return None


async def _verify_lesson_access(lesson_id: int, user_id: int) -> Lesson | None:
    async with async_session() as db:
        result = await db.execute(select(Lesson).where(Lesson.id == lesson_id))
        lesson = result.scalar_one_or_none()
        if not lesson:
            return None
        space_result = await db.execute(select(Space).where(Space.id == lesson.space_id))
        space = space_result.scalar_one_or_none()
        if not space:
            return None
        if space.teacher_id == user_id:
            return lesson
        mem = await db.execute(
            select(SpaceMembership).where(SpaceMembership.space_id == lesson.space_id, SpaceMembership.user_id == user_id)
        )
        if mem.scalar_one_or_none():
            return lesson
    return None


async def _get_user(user_id: int) -> User | None:
    async with async_session() as db:
        return await db.get(User, user_id)


async def _ensure_ydoc_pubsub(material_id: int):
    channel = ydoc_channel(material_id)
    if channel in _pubsub_tasks:
        return

    async def listener():
        r = await get_redis()
        pubsub = r.pubsub()
        await pubsub.subscribe(channel)
        try:
            while True:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg["type"] == "message":
                    data = msg["data"]
                    dead = set()
                    for ws in list(_local_doc_clients.get(material_id, set())):
                        try:
                            await ws.send_bytes(data)
                        except Exception:
                            dead.add(ws)
                    for ws in dead:
                        _local_doc_clients[material_id].discard(ws)
        except asyncio.CancelledError:
            await pubsub.unsubscribe(channel)
            raise

    _pubsub_tasks[channel] = asyncio.create_task(listener())


async def _persist_ydoc(material_id: int, state: bytes):
    async with async_session() as db:
        material = await db.get(Material, material_id)
        if not material or not material.storage_ref:
            key = f"boards/{material_id}.ydoc"
            material.storage_ref = key
        put_bytes(material.storage_ref, state)
        material.size_bytes = len(state)
        await db.commit()


async def handle_docs_ws(websocket: WebSocket, material_id: int, token: str | None):
    if not token:
        await websocket.close(code=4001)
        return
    user_id = decode_access_token(token)
    if not user_id:
        await websocket.close(code=4001)
        return

    material = await _verify_material_access(material_id, user_id)
    if not material:
        await websocket.close(code=4003)
        return

    await websocket.accept()
    await _ensure_ydoc_pubsub(material_id)
    _local_doc_clients[material_id].add(websocket)

    r = await get_redis()
    key = ydoc_key(material_id)
    state = await r.get(key)
    if not state and material.storage_ref:
        blob = get_bytes(material.storage_ref)
        if blob:
            state = blob
            await r.set(key, state, ex=settings.ydoc_redis_ttl_sec)

    if state:
        # Send sync step 2 with full state (simplified y-protocols)
        header = bytes([MSG_SYNC, 1])
        await websocket.send_bytes(header + state)

    last_persist = time.time()

    try:
        while True:
            data = await websocket.receive_bytes()
            if len(data) < 2:
                continue
            msg_type = data[0]
            payload = data[1:]

            if msg_type == MSG_SYNC:
                current = await r.get(key) or b""
                merged = current + payload if payload else current
                await r.set(key, merged, ex=settings.ydoc_redis_ttl_sec)
                await r.publish(ydoc_channel(material_id), data)

                now = time.time()
                if now - last_persist > settings.ydoc_snapshot_debounce_sec:
                    await _persist_ydoc(material_id, merged)
                    last_persist = now

            elif msg_type == MSG_AWARENESS:
                await r.publish(ydoc_channel(material_id), data)

    except WebSocketDisconnect:
        pass
    finally:
        _local_doc_clients[material_id].discard(websocket)
        if not _local_doc_clients[material_id]:
            state = await r.get(key)
            if state:
                await _persist_ydoc(material_id, state)


async def _ensure_room_pubsub(lesson_id: int):
    channel = room_channel(lesson_id)
    if channel in _pubsub_tasks:
        return

    async def listener():
        r = await get_redis()
        pubsub = r.pubsub()
        await pubsub.subscribe(channel)
        try:
            while True:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg["type"] == "message":
                    dead = set()
                    for ws in list(_local_room_clients.get(lesson_id, set())):
                        try:
                            await ws.send_text(msg["data"].decode())
                        except Exception:
                            dead.add(ws)
                    for ws in dead:
                        _local_room_clients[lesson_id].discard(ws)
        except asyncio.CancelledError:
            await pubsub.unsubscribe(channel)
            raise

    _pubsub_tasks[channel] = asyncio.create_task(listener())


async def handle_room_ws(websocket: WebSocket, lesson_id: int, token: str | None):
    if not token:
        await websocket.close(code=4001)
        return
    user_id = decode_access_token(token)
    if not user_id:
        await websocket.close(code=4001)
        return

    lesson = await _verify_lesson_access(lesson_id, user_id)
    if not lesson:
        await websocket.close(code=4003)
        return

    user = await _get_user(user_id)
    if not user:
        await websocket.close(code=4001)
        return

    await websocket.accept()
    await _ensure_room_pubsub(lesson_id)
    _local_room_clients[lesson_id].add(websocket)

    await set_presence(lesson_id, user_id, {"display_name": user.display_name, "online": True})
    await publish_room_event(lesson_id, {"type": "presence", "user_id": user_id, "display_name": user.display_name, "online": True})

    try:
        while True:
            text = await websocket.receive_text()
            try:
                event = json.loads(text)
            except json.JSONDecodeError:
                continue
            event_type = event.get("type")
            if event_type == "cursor":
                await publish_room_event(lesson_id, {"type": "cursor", "user_id": user_id, **event})
            elif event_type == "ping":
                await set_presence(lesson_id, user_id, {"display_name": user.display_name, "online": True})
    except WebSocketDisconnect:
        pass
    finally:
        _local_room_clients[lesson_id].discard(websocket)
        await remove_presence(lesson_id, user_id)
        await publish_room_event(lesson_id, {"type": "presence", "user_id": user_id, "online": False})
