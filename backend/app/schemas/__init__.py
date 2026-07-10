from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, EmailStr, Field

from app.models import (
    AttemptStatus,
    CreatorRole,
    LessonStatus,
    MaterialType,
    QuestionType,
    RunStatus,
    SpaceKind,
    UserRole,
)


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class UserOut(BaseModel):
    id: int
    email: str
    display_name: str
    role: UserRole
    timezone: str

    model_config = {"from_attributes": True}


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    display_name: str = Field(min_length=1)
    role: UserRole
    timezone: str = "UTC"


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RefreshIn(BaseModel):
    refresh: str


class AuthOut(BaseModel):
    access: str
    refresh: str
    user: UserOut


class RefreshOut(BaseModel):
    access: str
    refresh: str


class ProfilePatchIn(BaseModel):
    display_name: str | None = None
    timezone: str | None = None
    password: str | None = Field(default=None, min_length=8)


class SpaceCreateIn(BaseModel):
    kind: SpaceKind
    title: str
    rate_cents: int | None = None


class SpacePatchIn(BaseModel):
    title: str | None = None
    rate_cents: int | None = None


class SpaceOut(BaseModel):
    id: int
    teacher_id: int
    kind: SpaceKind
    title: str
    rate_cents: int | None
    invite_code: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MemberOut(BaseModel):
    user_id: int
    display_name: str
    joined_at: datetime


class JoinIn(BaseModel):
    invite_code: str


class FolderCreateIn(BaseModel):
    name: str
    parent_id: int | None = None


class FolderPatchIn(BaseModel):
    name: str | None = None
    parent_id: int | None = None


class FolderOut(BaseModel):
    id: int
    space_id: int
    parent_id: int | None
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MaterialCreateIn(BaseModel):
    type: MaterialType
    title: str
    folder_id: int | None = None
    config: dict | None = None


class MaterialUploadUrlIn(BaseModel):
    type: MaterialType
    title: str
    folder_id: int | None = None
    size_bytes: int
    content_type: str


class MaterialPatchIn(BaseModel):
    title: str | None = None
    folder_id: int | None = None
    config: dict | None = None


class MaterialOut(BaseModel):
    id: int
    space_id: int
    folder_id: int | None
    type: MaterialType
    title: str
    created_by: int
    created_by_role: CreatorRole
    config: dict | None
    storage_ref: str | None
    size_bytes: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UploadUrlOut(BaseModel):
    material_id: int
    put_url: str


class ContentOut(BaseModel):
    type: str
    config: dict | None = None
    url: str | None = None


class ExecuteIn(BaseModel):
    language: str = "python"
    code: str
    stdin: str | None = None
    context: dict


class ExecuteOut(BaseModel):
    run_id: int
    status: RunStatus


class ExecuteResultOut(BaseModel):
    status: RunStatus
    stdout: str | None = None
    stderr: str | None = None
    exit_code: int | None = None
    duration_ms: int | None = None


class LessonCreateIn(BaseModel):
    scheduled_start_utc: datetime
    duration_min: int


class SeriesCreateIn(BaseModel):
    weekday: int
    start_time: time
    duration_min: int
    timezone: str
    starts_on: date
    ends_on: date | None = None


class LessonPatchIn(BaseModel):
    scheduled_start_utc: datetime | None = None
    duration_min: int | None = None
    scope: str = "this"


class LessonCancelIn(BaseModel):
    scope: str = "this"


class LessonOut(BaseModel):
    id: int
    space_id: int
    series_id: int | None
    scheduled_start_utc: datetime
    scheduled_end_utc: datetime
    status: LessonStatus
    room_open: bool
    presented_tab_id: int | None
    actual_started_at: datetime | None
    actual_ended_at: datetime | None

    model_config = {"from_attributes": True}


class AvailabilityRuleIn(BaseModel):
    weekday: int
    start_time: time
    end_time: time


class AvailabilityExceptionIn(BaseModel):
    date: date
    kind: str
    start_time: time | None = None
    end_time: time | None = None


class VisibilityPatchIn(BaseModel):
    is_open: bool
    level: str | None = "free_busy"


class FindSlotsIn(BaseModel):
    duration_min: int
    from_date: date = Field(alias="from")
    to_date: date = Field(alias="to")

    model_config = {"populate_by_name": True}


class TabOpenIn(BaseModel):
    material_id: int


class PresentIn(BaseModel):
    tab_id: int | None = None


class GrantEditIn(BaseModel):
    user_id: int
    granted: bool


class MessageIn(BaseModel):
    body: str


class MessageOut(BaseModel):
    id: int
    lesson_id: int
    user_id: int
    body: str
    created_at: datetime
    display_name: str | None = None

    model_config = {"from_attributes": True}


class RoomTabOut(BaseModel):
    id: int
    lesson_id: int
    material_id: int
    position: int
    opened_at: datetime
    material: MaterialOut | None = None

    model_config = {"from_attributes": True}


class RoomOut(BaseModel):
    lesson: LessonOut
    tabs: list[RoomTabOut]
    presented_tab_id: int | None
    presence: list[dict]
    edit_grants: list[int]
    messages: list[MessageOut]


class ContestCreateIn(BaseModel):
    title: str
    description: str | None = None
    time_limit_sec: int | None = None
    shuffle_questions: bool = False
    max_attempts: int | None = None


class ContestPatchIn(BaseModel):
    title: str | None = None
    description: str | None = None
    time_limit_sec: int | None = None
    shuffle_questions: bool | None = None
    max_attempts: int | None = None


class QuestionCreateIn(BaseModel):
    type: QuestionType
    prompt: str
    points: int = 1
    media_ref: str | None = None
    config: dict = {}


class QuestionPatchIn(BaseModel):
    prompt: str | None = None
    points: int | None = None
    media_ref: str | None = None
    config: dict | None = None


class QuestionReorderIn(BaseModel):
    order: list[int]


class CodingTestIn(BaseModel):
    stdin: str | None = None
    expected_stdout: str | None = None
    is_sample: bool = False
    weight: int = 1


class AssignIn(BaseModel):
    space_id: int
    deadline_at: datetime


class AnswerPatchIn(BaseModel):
    question_id: int
    answer: dict


class AnalyticsOverviewOut(BaseModel):
    lessons_done: int
    total_duration_min: int
    lessons_cancelled: int
    earnings_cents: int
    storage_bytes_used: int
    storage_quota_bytes: int
    student_count: int


class ActivityDayOut(BaseModel):
    date: str
    count: int
