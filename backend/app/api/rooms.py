from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import get_current_user, get_space_or_403, require_teacher
from app.database import get_db
from app.models import (
    CreatorRole,
    Lesson,
    LessonStatus,
    Material,
    MaterialType,
    RoomMessage,
    RoomTab,
    Space,
    User,
    UserRole,
)
from app.schemas import (
    GrantEditIn,
    LessonOut,
    MessageIn,
    MessageOut,
    PresentIn,
    RoomOut,
    RoomTabOut,
    TabOpenIn,
)
from app.services.redis_client import (
    get_edit_grants,
    get_presence,
    publish_room_event,
    set_edit_grant,
)
from app.services.storage import empty_ydoc_snapshot, generate_storage_key, put_bytes

router = APIRouter(tags=["rooms"])


async def _get_lesson_with_access(lesson_id: int, user: User, db: AsyncSession) -> Lesson:
    result = await db.execute(select(Lesson).where(Lesson.id == lesson_id))
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Lesson not found"}})
    await get_space_or_403(lesson.space_id, user, db)
    return lesson


@router.post("/lessons/{lesson_id}/open", response_model=LessonOut)
async def open_room(lesson_id: int, user: User = Depends(require_teacher), db: AsyncSession = Depends(get_db)):
    lesson = await _get_lesson_with_access(lesson_id, user, db)
    space = await db.get(Space, lesson.space_id)
    if space.teacher_id != user.id:
        raise HTTPException(status_code=403, detail={"error": {"code": "forbidden", "message": "Teacher only"}})

    lesson.room_open = True
    lesson.status = LessonStatus.live
    lesson.actual_started_at = datetime.now(timezone.utc)

    tabs_result = await db.execute(select(RoomTab).where(RoomTab.lesson_id == lesson_id))
    if not tabs_result.scalars().first():
        storage_ref = generate_storage_key("boards", ".ydoc")
        size = put_bytes(storage_ref, empty_ydoc_snapshot())
        board = Material(
            space_id=lesson.space_id,
            type=MaterialType.board,
            title="Доска занятия",
            created_by=user.id,
            created_by_role=CreatorRole.teacher,
            storage_ref=storage_ref,
            size_bytes=size,
        )
        db.add(board)
        await db.flush()
        tab = RoomTab(lesson_id=lesson_id, material_id=board.id, position=0)
        db.add(tab)
        teacher = await db.get(User, space.teacher_id)
        if teacher:
            teacher.storage_bytes_used += size

    await db.flush()
    return LessonOut.model_validate(lesson)


@router.post("/lessons/{lesson_id}/close", response_model=LessonOut)
async def close_room(lesson_id: int, user: User = Depends(require_teacher), db: AsyncSession = Depends(get_db)):
    lesson = await _get_lesson_with_access(lesson_id, user, db)
    space = await db.get(Space, lesson.space_id)
    if space.teacher_id != user.id:
        raise HTTPException(status_code=403, detail={"error": {"code": "forbidden", "message": "Teacher only"}})

    lesson.room_open = False
    lesson.status = LessonStatus.done
    lesson.actual_ended_at = datetime.now(timezone.utc)
    await db.flush()
    await publish_room_event(lesson_id, {"type": "room_closed"})
    return LessonOut.model_validate(lesson)


@router.get("/lessons/{lesson_id}/room", response_model=RoomOut)
async def get_room(lesson_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    lesson = await _get_lesson_with_access(lesson_id, user, db)
    tabs_result = await db.execute(
        select(RoomTab).where(RoomTab.lesson_id == lesson_id).order_by(RoomTab.position).options(selectinload(RoomTab.material))
    )
    tabs = tabs_result.scalars().all()
    msgs_result = await db.execute(
        select(RoomMessage, User)
        .join(User, User.id == RoomMessage.user_id)
        .where(RoomMessage.lesson_id == lesson_id)
        .order_by(RoomMessage.created_at)
    )
    messages = [
        MessageOut(id=m.id, lesson_id=m.lesson_id, user_id=m.user_id, body=m.body, created_at=m.created_at, display_name=u.display_name)
        for m, u in msgs_result.all()
    ]
    presence = await get_presence(lesson_id)
    grants = await get_edit_grants(lesson_id)
    return RoomOut(
        lesson=LessonOut.model_validate(lesson),
        tabs=[RoomTabOut.model_validate(t) for t in tabs],
        presented_tab_id=lesson.presented_tab_id,
        presence=[{"user_id": uid, **data} for uid, data in presence.items()],
        edit_grants=list(grants),
        messages=messages,
    )


@router.post("/lessons/{lesson_id}/tabs", response_model=RoomTabOut)
async def open_tab(
    lesson_id: int,
    data: TabOpenIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    lesson = await _get_lesson_with_access(lesson_id, user, db)
    material = await db.get(Material, data.material_id)
    if not material or material.space_id != lesson.space_id:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Material not found"}})

    existing = await db.execute(
        select(RoomTab).where(RoomTab.lesson_id == lesson_id, RoomTab.material_id == data.material_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail={"error": {"code": "already_open", "message": "Tab already open"}})

    count = await db.execute(select(RoomTab).where(RoomTab.lesson_id == lesson_id))
    position = len(count.scalars().all())
    tab = RoomTab(lesson_id=lesson_id, material_id=data.material_id, position=position)
    db.add(tab)
    await db.flush()
    await publish_room_event(lesson_id, {"type": "tab_opened", "tab": {"id": tab.id, "material_id": tab.material_id, "position": tab.position}})
    return RoomTabOut.model_validate(tab)


@router.delete("/lessons/{lesson_id}/tabs/{tab_id}")
async def close_tab(
    lesson_id: int,
    tab_id: int,
    user: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    lesson = await _get_lesson_with_access(lesson_id, user, db)
    result = await db.execute(select(RoomTab).where(RoomTab.id == tab_id, RoomTab.lesson_id == lesson_id))
    tab = result.scalar_one_or_none()
    if not tab:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Tab not found"}})
    if lesson.presented_tab_id == tab_id:
        lesson.presented_tab_id = None
    await db.delete(tab)
    await publish_room_event(lesson_id, {"type": "tab_closed", "tab_id": tab_id})
    return {"ok": True}


@router.post("/lessons/{lesson_id}/present", response_model=LessonOut)
async def present_tab(
    lesson_id: int,
    data: PresentIn,
    user: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    lesson = await _get_lesson_with_access(lesson_id, user, db)
    lesson.presented_tab_id = data.tab_id
    await db.flush()
    await publish_room_event(lesson_id, {"type": "present_changed", "tab_id": data.tab_id})
    return LessonOut.model_validate(lesson)


@router.post("/lessons/{lesson_id}/grant-edit")
async def grant_edit(
    lesson_id: int,
    data: GrantEditIn,
    user: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    await _get_lesson_with_access(lesson_id, user, db)
    await set_edit_grant(lesson_id, data.user_id, data.granted)
    await publish_room_event(lesson_id, {"type": "edit_grant_changed", "user_id": data.user_id, "granted": data.granted})
    return {"ok": True}


@router.get("/lessons/{lesson_id}/messages", response_model=list[MessageOut])
async def list_messages(lesson_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _get_lesson_with_access(lesson_id, user, db)
    result = await db.execute(
        select(RoomMessage, User)
        .join(User, User.id == RoomMessage.user_id)
        .where(RoomMessage.lesson_id == lesson_id)
        .order_by(RoomMessage.created_at)
    )
    return [
        MessageOut(id=m.id, lesson_id=m.lesson_id, user_id=m.user_id, body=m.body, created_at=m.created_at, display_name=u.display_name)
        for m, u in result.all()
    ]


@router.post("/lessons/{lesson_id}/messages", response_model=MessageOut)
async def post_message(
    lesson_id: int,
    data: MessageIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_lesson_with_access(lesson_id, user, db)
    if len(data.body) > 5000:
        raise HTTPException(status_code=400, detail={"error": {"code": "too_long", "message": "Message too long"}})
    msg = RoomMessage(lesson_id=lesson_id, user_id=user.id, body=data.body)
    db.add(msg)
    await db.flush()
    out = MessageOut(
        id=msg.id,
        lesson_id=msg.lesson_id,
        user_id=msg.user_id,
        body=msg.body,
        created_at=msg.created_at,
        display_name=user.display_name,
    )
    await publish_room_event(lesson_id, {"type": "chat", "message": out.model_dump(mode="json")})
    return out
