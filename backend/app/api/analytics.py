from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, require_teacher
from app.database import get_db
from app.models import (
    ContestAssignment,
    ContestAttempt,
    Lesson,
    LessonStatus,
    Notification,
    Space,
    SpaceMembership,
    User,
)
from app.schemas import ActivityDayOut, AnalyticsOverviewOut

router = APIRouter(tags=["analytics"])


@router.get("/analytics/overview", response_model=AnalyticsOverviewOut)
async def analytics_overview(
    from_date: str = Query(alias="from"),
    to_date: str = Query(alias="to"),
    user: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    fd = date.fromisoformat(from_date)
    td = date.fromisoformat(to_date)
    start = datetime.combine(fd, datetime.min.time(), tzinfo=timezone.utc)
    end = datetime.combine(td, datetime.max.time(), tzinfo=timezone.utc)

    spaces = await db.execute(select(Space).where(Space.teacher_id == user.id))
    space_list = spaces.scalars().all()
    space_ids = [s.id for s in space_list]

    lessons_done = 0
    total_duration = 0
    lessons_cancelled = 0
    earnings = 0

    if space_ids:
        done_result = await db.execute(
            select(Lesson).where(
                Lesson.space_id.in_(space_ids),
                Lesson.status == LessonStatus.done,
                Lesson.actual_started_at >= start,
                Lesson.actual_started_at <= end,
            )
        )
        for lesson in done_result.scalars().all():
            lessons_done += 1
            if lesson.actual_started_at and lesson.actual_ended_at:
                total_duration += int((lesson.actual_ended_at - lesson.actual_started_at).total_seconds() / 60)
            space = next((s for s in space_list if s.id == lesson.space_id), None)
            if space and space.rate_cents:
                earnings += space.rate_cents

        cancel_result = await db.execute(
            select(func.count()).select_from(Lesson).where(
                Lesson.space_id.in_(space_ids),
                Lesson.status == LessonStatus.cancelled,
                Lesson.scheduled_start_utc >= start,
                Lesson.scheduled_start_utc <= end,
            )
        )
        lessons_cancelled = cancel_result.scalar() or 0

    members = await db.execute(
        select(func.count(func.distinct(SpaceMembership.user_id))).where(SpaceMembership.space_id.in_(space_ids))
    ) if space_ids else None
    student_count = members.scalar() if members else 0

    return AnalyticsOverviewOut(
        lessons_done=lessons_done,
        total_duration_min=total_duration,
        lessons_cancelled=lessons_cancelled,
        earnings_cents=earnings,
        storage_bytes_used=user.storage_bytes_used,
        storage_quota_bytes=user.storage_quota_bytes,
        student_count=student_count or 0,
    )


@router.get("/analytics/students/{student_id}")
async def student_analytics(student_id: int, user: User = Depends(require_teacher), db: AsyncSession = Depends(get_db)):
    spaces = await db.execute(select(Space).where(Space.teacher_id == user.id))
    space_ids = [s.id for s in spaces.scalars().all()]
    if not space_ids:
        return {"scores": []}

    attempts = await db.execute(
        select(ContestAttempt)
        .join(ContestAssignment, ContestAssignment.id == ContestAttempt.assignment_id)
        .where(ContestAttempt.student_id == student_id, ContestAssignment.space_id.in_(space_ids))
    )
    return {
        "scores": [
            {"attempt_id": a.id, "score": float(a.score) if a.score else 0, "max_score": float(a.max_score) if a.max_score else 0, "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None}
            for a in attempts.scalars().all()
        ]
    }


@router.get("/me/activity", response_model=list[ActivityDayOut])
async def my_activity(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.role.value == "teacher":
        spaces = await db.execute(select(Space).where(Space.teacher_id == user.id))
        space_ids = [s.id for s in spaces.scalars().all()]
    else:
        memberships = await db.execute(select(SpaceMembership).where(SpaceMembership.user_id == user.id))
        space_ids = [m.space_id for m in memberships.scalars().all()]

    if not space_ids:
        return []

    result = await db.execute(
        select(func.date(Lesson.actual_started_at), func.count())
        .where(Lesson.space_id.in_(space_ids), Lesson.status == LessonStatus.done, Lesson.actual_started_at.isnot(None))
        .group_by(func.date(Lesson.actual_started_at))
    )
    return [ActivityDayOut(date=str(d), count=c) for d, c in result.all()]


@router.get("/notifications")
async def list_notifications(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Notification).where(Notification.user_id == user.id).order_by(Notification.created_at.desc()).limit(50))
    return [{"id": n.id, "type": n.type, "payload": n.payload, "read_at": n.read_at.isoformat() if n.read_at else None, "created_at": n.created_at.isoformat()} for n in result.scalars().all()]


@router.post("/notifications/{notif_id}/read")
async def mark_read(notif_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Notification).where(Notification.id == notif_id, Notification.user_id == user.id))
    n = result.scalar_one_or_none()
    if n:
        n.read_at = datetime.now(timezone.utc)
    return {"ok": True}
