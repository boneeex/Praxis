from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from dateutil import rrule
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AvailabilityException,
    AvailabilityKind,
    AvailabilityRule,
    Lesson,
    LessonSeries,
    LessonStatus,
    Space,
    SpaceMembership,
)


def combine_local_to_utc(d: date, t: time, tz_name: str) -> datetime:
    tz = ZoneInfo(tz_name)
    local_dt = datetime.combine(d, t, tzinfo=tz)
    return local_dt.astimezone(timezone.utc)


async def materialize_series(
    db: AsyncSession,
    series: LessonSeries,
    horizon_weeks: int = 12,
) -> list[Lesson]:
    tz = ZoneInfo(series.timezone)
    start = series.starts_on
    end = series.ends_on
    if end is None:
        end = start + timedelta(weeks=horizon_weeks)

    created = []
    current = start
    while current <= end:
        if current.weekday() == series.weekday:
            start_utc = combine_local_to_utc(current, series.start_time, series.timezone)
            end_utc = start_utc + timedelta(minutes=series.duration_min)
            existing = await db.execute(
                select(Lesson).where(
                    Lesson.series_id == series.id,
                    Lesson.scheduled_start_utc == start_utc,
                )
            )
            if not existing.scalar_one_or_none():
                lesson = Lesson(
                    space_id=series.space_id,
                    series_id=series.id,
                    scheduled_start_utc=start_utc,
                    scheduled_end_utc=end_utc,
                    status=LessonStatus.scheduled,
                )
                db.add(lesson)
                created.append(lesson)
        current += timedelta(days=1)
    await db.flush()
    return created


def _time_in_range(t: time, start: time, end: time) -> bool:
    return start <= t < end


async def get_user_free_slots(
    db: AsyncSession,
    user_id: int,
    tz_name: str,
    from_date: date,
    to_date: date,
    duration_min: int,
    existing_lessons: list[tuple[datetime, datetime]],
) -> list[tuple[datetime, datetime]]:
    rules_result = await db.execute(select(AvailabilityRule).where(AvailabilityRule.user_id == user_id))
    rules = rules_result.scalars().all()
    exc_result = await db.execute(
        select(AvailabilityException).where(
            AvailabilityException.user_id == user_id,
            AvailabilityException.date >= from_date,
            AvailabilityException.date <= to_date,
        )
    )
    exceptions = {e.date: e for e in exc_result.scalars().all()}

    slots: list[tuple[datetime, datetime]] = []
    current = from_date
    while current <= to_date:
        weekday = current.weekday()
        day_rules = [r for r in rules if r.weekday == weekday]
        exc = exceptions.get(current)

        windows: list[tuple[time, time]] = []
        if exc:
            if exc.kind == AvailabilityKind.block:
                if exc.start_time is None:
                    windows = []
                else:
                    windows = [(time(0, 0), exc.start_time), (exc.end_time or time(23, 59), time(23, 59))]
            else:
                if exc.start_time and exc.end_time:
                    windows = [(exc.start_time, exc.end_time)]
        else:
            windows = [(r.start_time, r.end_time) for r in day_rules]

        for start_t, end_t in windows:
            slot_start = combine_local_to_utc(current, start_t, tz_name)
            slot_end = combine_local_to_utc(current, end_t, tz_name)
            cursor = slot_start
            while cursor + timedelta(minutes=duration_min) <= slot_end:
                candidate_end = cursor + timedelta(minutes=duration_min)
                conflict = any(
                    not (candidate_end <= ls or cursor >= le) for ls, le in existing_lessons
                )
                if not conflict:
                    slots.append((cursor, candidate_end))
                cursor += timedelta(minutes=15)
        current += timedelta(days=1)
    return slots


async def find_common_slots(
    db: AsyncSession,
    space: Space,
    from_date: date,
    to_date: date,
    duration_min: int,
) -> list[dict]:
    members_result = await db.execute(select(SpaceMembership).where(SpaceMembership.space_id == space.id))
    member_ids = [m.user_id for m in members_result.scalars().all()]
    user_ids = [space.teacher_id] + member_ids

    from app.models import User

    users_result = await db.execute(select(User).where(User.id.in_(user_ids)))
    users = {u.id: u for u in users_result.scalars().all()}

    lessons_result = await db.execute(
        select(Lesson).where(
            Lesson.space_id == space.id,
            Lesson.status != LessonStatus.cancelled,
            Lesson.scheduled_start_utc >= datetime.combine(from_date, time.min, tzinfo=timezone.utc),
            Lesson.scheduled_start_utc <= datetime.combine(to_date, time.max, tzinfo=timezone.utc),
        )
    )
    space_lessons = [(l.scheduled_start_utc, l.scheduled_end_utc) for l in lessons_result.scalars().all()]

    if not user_ids:
        return []

    all_slots = None
    for uid in user_ids:
        user = users[uid]
        user_lessons_result = await db.execute(
            select(Lesson).join(Space).where(
                or_(Space.teacher_id == uid, Space.id.in_(select(SpaceMembership.space_id).where(SpaceMembership.user_id == uid))),
                Lesson.status != LessonStatus.cancelled,
                Lesson.scheduled_start_utc >= datetime.combine(from_date, time.min, tzinfo=timezone.utc),
                Lesson.scheduled_start_utc <= datetime.combine(to_date, time.max, tzinfo=timezone.utc),
            )
        )
        user_lessons = [(l.scheduled_start_utc, l.scheduled_end_utc) for l in user_lessons_result.scalars().all()]
        slots = await get_user_free_slots(db, uid, user.timezone, from_date, to_date, duration_min, user_lessons)
        slot_set = set(slots)
        if all_slots is None:
            all_slots = slot_set
        else:
            all_slots &= slot_set

    if not all_slots:
        return []

    return [
        {"start_utc": s.isoformat(), "end_utc": e.isoformat()}
        for s, e in sorted(all_slots, key=lambda x: x[0])
    ]
