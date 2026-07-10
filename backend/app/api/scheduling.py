from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, get_space_or_403, require_teacher
from app.database import get_db
from app.models import (
    AvailabilityException,
    AvailabilityKind,
    AvailabilityRule,
    CalendarVisibility,
    ContestAssignment,
    Lesson,
    LessonSeries,
    LessonStatus,
    Space,
    SpaceMembership,
    User,
    VisibilityLevel,
)
from app.schemas import (
    AvailabilityExceptionIn,
    AvailabilityRuleIn,
    FindSlotsIn,
    LessonCancelIn,
    LessonCreateIn,
    LessonOut,
    LessonPatchIn,
    SeriesCreateIn,
    VisibilityPatchIn,
)
from app.services.scheduling import find_common_slots, materialize_series

router = APIRouter(tags=["scheduling"])


@router.get("/me/availability")
async def get_availability(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rules = await db.execute(select(AvailabilityRule).where(AvailabilityRule.user_id == user.id))
    exceptions = await db.execute(select(AvailabilityException).where(AvailabilityException.user_id == user.id))
    return {
        "rules": [
            {"id": r.id, "weekday": r.weekday, "start_time": r.start_time.isoformat(), "end_time": r.end_time.isoformat()}
            for r in rules.scalars().all()
        ],
        "exceptions": [
            {
                "id": e.id,
                "date": e.date.isoformat(),
                "kind": e.kind.value,
                "start_time": e.start_time.isoformat() if e.start_time else None,
                "end_time": e.end_time.isoformat() if e.end_time else None,
            }
            for e in exceptions.scalars().all()
        ],
    }


@router.put("/me/availability/rules")
async def put_availability_rules(
    rules: list[AvailabilityRuleIn],
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(AvailabilityRule).where(AvailabilityRule.user_id == user.id))
    for r in existing.scalars().all():
        await db.delete(r)
    for rule in rules:
        db.add(AvailabilityRule(user_id=user.id, weekday=rule.weekday, start_time=rule.start_time, end_time=rule.end_time))
    await db.flush()
    return {"ok": True}


@router.post("/me/availability/exceptions")
async def add_exception(
    data: AvailabilityExceptionIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    exc = AvailabilityException(
        user_id=user.id,
        date=data.date,
        kind=AvailabilityKind(data.kind),
        start_time=data.start_time,
        end_time=data.end_time,
    )
    db.add(exc)
    await db.flush()
    return {"id": exc.id}


@router.delete("/me/availability/exceptions/{exc_id}")
async def delete_exception(exc_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AvailabilityException).where(AvailabilityException.id == exc_id, AvailabilityException.user_id == user.id))
    exc = result.scalar_one_or_none()
    if not exc:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Not found"}})
    await db.delete(exc)
    return {"ok": True}


@router.get("/calendar")
async def get_calendar(
    from_date: str = Query(alias="from"),
    to_date: str = Query(alias="to"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from datetime import date as date_type
    fd = date_type.fromisoformat(from_date)
    td = date_type.fromisoformat(to_date)
    start_utc = datetime.combine(fd, datetime.min.time(), tzinfo=timezone.utc)
    end_utc = datetime.combine(td, datetime.max.time(), tzinfo=timezone.utc)

    if user.role.value == "teacher":
        spaces = await db.execute(select(Space).where(Space.teacher_id == user.id))
        space_ids = [s.id for s in spaces.scalars().all()]
    else:
        memberships = await db.execute(select(SpaceMembership).where(SpaceMembership.user_id == user.id))
        space_ids = [m.space_id for m in memberships.scalars().all()]

    lessons = []
    if space_ids:
        result = await db.execute(
            select(Lesson).where(
                Lesson.space_id.in_(space_ids),
                Lesson.scheduled_start_utc >= start_utc,
                Lesson.scheduled_start_utc <= end_utc,
            )
        )
        lessons = [
            {
                "id": l.id,
                "space_id": l.space_id,
                "start_utc": l.scheduled_start_utc.isoformat(),
                "end_utc": l.scheduled_end_utc.isoformat(),
                "status": l.status.value,
                "room_open": l.room_open,
            }
            for l in result.scalars().all()
        ]

    assignments = []
    if space_ids:
        assign_result = await db.execute(
            select(ContestAssignment).where(
                ContestAssignment.space_id.in_(space_ids),
                ContestAssignment.deadline_at >= start_utc,
                ContestAssignment.deadline_at <= end_utc,
            )
        )
        assignments = [
            {"id": a.id, "contest_id": a.contest_id, "space_id": a.space_id, "deadline_at": a.deadline_at.isoformat()}
            for a in assign_result.scalars().all()
        ]

    visibility = await db.execute(
        select(CalendarVisibility).where(CalendarVisibility.grantee_id == user.id, CalendarVisibility.is_open == True)
    )
    free_busy = []
    for vis in visibility.scalars().all():
        grantor_lessons = await db.execute(
            select(Lesson)
            .join(Space)
            .where(
                or_(Space.teacher_id == vis.grantor_id, Space.id.in_(select(SpaceMembership.space_id).where(SpaceMembership.user_id == vis.grantor_id))),
                Lesson.scheduled_start_utc >= start_utc,
                Lesson.scheduled_start_utc <= end_utc,
                Lesson.status != LessonStatus.cancelled,
            )
        )
        for l in grantor_lessons.scalars().all():
            free_busy.append({"user_id": vis.grantor_id, "start_utc": l.scheduled_start_utc.isoformat(), "end_utc": l.scheduled_end_utc.isoformat(), "busy": True})

    return {"lessons": lessons, "deadlines": assignments, "free_busy": free_busy, "timezone": user.timezone}


@router.get("/calendar/visibility")
async def get_visibility(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    granted = await db.execute(select(CalendarVisibility).where(CalendarVisibility.grantor_id == user.id))
    received = await db.execute(select(CalendarVisibility).where(CalendarVisibility.grantee_id == user.id))
    return {
        "granted": [{"grantee_id": v.grantee_id, "is_open": v.is_open, "level": v.level.value} for v in granted.scalars().all()],
        "received": [{"grantor_id": v.grantor_id, "is_open": v.is_open, "level": v.level.value} for v in received.scalars().all()],
    }


@router.put("/calendar/visibility/{grantee_id}")
async def set_visibility(
    grantee_id: int,
    data: VisibilityPatchIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CalendarVisibility).where(CalendarVisibility.grantor_id == user.id, CalendarVisibility.grantee_id == grantee_id)
    )
    vis = result.scalar_one_or_none()
    if not vis:
        vis = CalendarVisibility(
            grantor_id=user.id,
            grantee_id=grantee_id,
            is_open=data.is_open,
            level=VisibilityLevel(data.level or "free_busy"),
        )
        db.add(vis)
    else:
        vis.is_open = data.is_open
        if data.level:
            vis.level = VisibilityLevel(data.level)
    await db.flush()
    return {"ok": True}


@router.post("/spaces/{space_id}/find-slots")
async def find_slots(
    space_id: int,
    data: FindSlotsIn,
    user: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    space = await get_space_or_403(space_id, user, db)
    if space.teacher_id != user.id:
        raise HTTPException(status_code=403, detail={"error": {"code": "forbidden", "message": "Teacher only"}})
    slots = await find_common_slots(db, space, data.from_date, data.to_date, data.duration_min)
    return {"slots": slots}


@router.post("/spaces/{space_id}/lessons", response_model=LessonOut)
async def create_lesson(
    space_id: int,
    data: LessonCreateIn,
    user: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    space = await get_space_or_403(space_id, user, db)
    if space.teacher_id != user.id:
        raise HTTPException(status_code=403, detail={"error": {"code": "forbidden", "message": "Teacher only"}})
    end = data.scheduled_start_utc + timedelta(minutes=data.duration_min)
    lesson = Lesson(
        space_id=space_id,
        scheduled_start_utc=data.scheduled_start_utc,
        scheduled_end_utc=end,
        status=LessonStatus.scheduled,
    )
    db.add(lesson)
    await db.flush()
    return LessonOut.model_validate(lesson)


@router.post("/spaces/{space_id}/series")
async def create_series(
    space_id: int,
    data: SeriesCreateIn,
    user: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    space = await get_space_or_403(space_id, user, db)
    if space.teacher_id != user.id:
        raise HTTPException(status_code=403, detail={"error": {"code": "forbidden", "message": "Teacher only"}})
    series = LessonSeries(
        space_id=space_id,
        weekday=data.weekday,
        start_time=data.start_time,
        duration_min=data.duration_min,
        timezone=data.timezone,
        starts_on=data.starts_on,
        ends_on=data.ends_on,
    )
    db.add(series)
    await db.flush()
    lessons = await materialize_series(db, series)
    return {"series_id": series.id, "lessons_created": len(lessons)}


@router.get("/lessons/{lesson_id}", response_model=LessonOut)
async def get_lesson(lesson_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Lesson).where(Lesson.id == lesson_id))
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Not found"}})
    await get_space_or_403(lesson.space_id, user, db)
    return LessonOut.model_validate(lesson)


@router.patch("/lessons/{lesson_id}", response_model=LessonOut)
async def patch_lesson(
    lesson_id: int,
    data: LessonPatchIn,
    user: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Lesson).where(Lesson.id == lesson_id))
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Not found"}})
    space = await db.get(Space, lesson.space_id)
    if not space or space.teacher_id != user.id:
        raise HTTPException(status_code=403, detail={"error": {"code": "forbidden", "message": "Teacher only"}})

    if data.scheduled_start_utc is not None:
        lesson.scheduled_start_utc = data.scheduled_start_utc
    duration = data.duration_min or int((lesson.scheduled_end_utc - lesson.scheduled_start_utc).total_seconds() / 60)
    if data.scheduled_start_utc is not None or data.duration_min is not None:
        start = data.scheduled_start_utc or lesson.scheduled_start_utc
        lesson.scheduled_end_utc = start + timedelta(minutes=duration)

    await db.flush()
    return LessonOut.model_validate(lesson)


@router.post("/lessons/{lesson_id}/cancel", response_model=LessonOut)
async def cancel_lesson(
    lesson_id: int,
    data: LessonCancelIn,
    user: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Lesson).where(Lesson.id == lesson_id))
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Not found"}})
    space = await db.get(Space, lesson.space_id)
    if not space or space.teacher_id != user.id:
        raise HTTPException(status_code=403, detail={"error": {"code": "forbidden", "message": "Teacher only"}})
    lesson.status = LessonStatus.cancelled
    await db.flush()
    return LessonOut.model_validate(lesson)
