import enum
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserRole(str, enum.Enum):
    teacher = "teacher"
    student = "student"
    parent = "parent"


class SpaceKind(str, enum.Enum):
    single = "single"
    group = "group"


class MaterialType(str, enum.Enum):
    board = "board"
    code_snippet = "code_snippet"
    graph = "graph"
    pdf = "pdf"
    image = "image"
    lesson_template = "lesson_template"
    auto_note = "auto_note"


class CreatorRole(str, enum.Enum):
    teacher = "teacher"
    student = "student"


class QuestionType(str, enum.Enum):
    single_choice = "single_choice"
    multi_choice = "multi_choice"
    short_answer = "short_answer"
    flashcard = "flashcard"
    coding = "coding"


class JudgeMode(str, enum.Enum):
    exact = "exact"
    checker = "checker"


class AttemptStatus(str, enum.Enum):
    not_started = "not_started"
    in_progress = "in_progress"
    submitted = "submitted"
    graded = "graded"


class LessonStatus(str, enum.Enum):
    scheduled = "scheduled"
    live = "live"
    done = "done"
    cancelled = "cancelled"


class AvailabilityKind(str, enum.Enum):
    block = "block"
    open = "open"


class VisibilityLevel(str, enum.Enum):
    free_busy = "free_busy"
    full = "full"


class RunStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    done = "done"
    error = "error"
    timeout = "timeout"


class NotifChannel(str, enum.Enum):
    in_app = "in_app"
    telegram = "telegram"
    email = "email"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), nullable=False)
    timezone: Mapped[str] = mapped_column(Text, nullable=False, default="UTC")
    telegram_chat_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    storage_quota_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=5 * 1024**3)
    storage_bytes_used: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user")
    owned_spaces: Mapped[list["Space"]] = relationship(back_populates="teacher", foreign_keys="Space.teacher_id")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")

    __table_args__ = (Index("ix_refresh_tokens_user_id", "user_id"),)


class ParentLink(Base):
    __tablename__ = "parent_links"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    parent_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("parent_id", "student_id"),)


class Space(Base):
    __tablename__ = "spaces"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    teacher_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[SpaceKind] = mapped_column(Enum(SpaceKind, name="space_kind"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    rate_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    invite_code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    teacher: Mapped["User"] = relationship(back_populates="owned_spaces", foreign_keys=[teacher_id])
    memberships: Mapped[list["SpaceMembership"]] = relationship(back_populates="space", cascade="all, delete-orphan")
    folders: Mapped[list["Folder"]] = relationship(back_populates="space", cascade="all, delete-orphan")
    materials: Mapped[list["Material"]] = relationship(back_populates="space", cascade="all, delete-orphan")
    lessons: Mapped[list["Lesson"]] = relationship(back_populates="space", cascade="all, delete-orphan")
    lesson_series: Mapped[list["LessonSeries"]] = relationship(back_populates="space", cascade="all, delete-orphan")
    contest_assignments: Mapped[list["ContestAssignment"]] = relationship(back_populates="space", cascade="all, delete-orphan")


class SpaceMembership(Base):
    __tablename__ = "space_memberships"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    space_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    space: Mapped["Space"] = relationship(back_populates="memberships")
    user: Mapped["User"] = relationship()

    __table_args__ = (
        UniqueConstraint("space_id", "user_id"),
        Index("ix_space_memberships_user_id", "user_id"),
    )


class Folder(Base):
    __tablename__ = "folders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    space_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("folders.id", ondelete="CASCADE"), nullable=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    space: Mapped["Space"] = relationship(back_populates="folders")
    parent: Mapped["Folder | None"] = relationship(remote_side="Folder.id")
    materials: Mapped[list["Material"]] = relationship(back_populates="folder")


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    space_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False)
    folder_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("folders.id", ondelete="SET NULL"), nullable=True)
    type: Mapped[MaterialType] = mapped_column(Enum(MaterialType, name="material_type"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    created_by_role: Mapped[CreatorRole] = mapped_column(Enum(CreatorRole, name="creator_role"), nullable=False)
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    storage_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    space: Mapped["Space"] = relationship(back_populates="materials")
    folder: Mapped["Folder | None"] = relationship(back_populates="materials")
    creator: Mapped["User"] = relationship()

    __table_args__ = (
        Index("ix_materials_space_id_type", "space_id", "type"),
        Index("ix_materials_folder_id", "folder_id"),
        Index("ix_materials_created_by", "created_by"),
    )


class LessonSeries(Base):
    __tablename__ = "lesson_series"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    space_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False)
    weekday: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    duration_min: Mapped[int] = mapped_column(Integer, nullable=False)
    timezone: Mapped[str] = mapped_column(Text, nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    space: Mapped["Space"] = relationship(back_populates="lesson_series")
    lessons: Mapped[list["Lesson"]] = relationship(back_populates="series")


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    space_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False)
    series_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("lesson_series.id", ondelete="SET NULL"), nullable=True)
    scheduled_start_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scheduled_end_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[LessonStatus] = mapped_column(Enum(LessonStatus, name="lesson_status"), nullable=False, default=LessonStatus.scheduled)
    room_open: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    presented_tab_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("room_tabs.id", ondelete="SET NULL", use_alter=True), nullable=True)
    actual_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recording_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    space: Mapped["Space"] = relationship(back_populates="lessons")
    series: Mapped["LessonSeries | None"] = relationship(back_populates="lessons")
    tabs: Mapped[list["RoomTab"]] = relationship(back_populates="lesson", cascade="all, delete-orphan", foreign_keys="RoomTab.lesson_id")
    messages: Mapped[list["RoomMessage"]] = relationship(back_populates="lesson", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_lessons_space_id_scheduled_start", "space_id", "scheduled_start_utc"),
        Index("ix_lessons_scheduled_start_utc", "scheduled_start_utc"),
    )


class RoomTab(Base):
    __tablename__ = "room_tabs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    lesson_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False)
    material_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("materials.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lesson: Mapped["Lesson"] = relationship(back_populates="tabs", foreign_keys=[lesson_id])
    material: Mapped["Material"] = relationship()

    __table_args__ = (
        UniqueConstraint("lesson_id", "material_id"),
        Index("ix_room_tabs_lesson_id", "lesson_id"),
    )


class RoomMessage(Base):
    __tablename__ = "room_messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    lesson_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lesson: Mapped["Lesson"] = relationship(back_populates="messages")
    user: Mapped["User"] = relationship()

    __table_args__ = (Index("ix_room_messages_lesson_id_created_at", "lesson_id", "created_at"),)


class Contest(Base):
    __tablename__ = "contests"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    owner_teacher_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    time_limit_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shuffle_questions: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    max_attempts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    owner: Mapped["User"] = relationship()
    questions: Mapped[list["ContestQuestion"]] = relationship(back_populates="contest", cascade="all, delete-orphan")
    assignments: Mapped[list["ContestAssignment"]] = relationship(back_populates="contest", cascade="all, delete-orphan")


class ContestQuestion(Base):
    __tablename__ = "contest_questions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    contest_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("contests.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[QuestionType] = mapped_column(Enum(QuestionType, name="question_type"), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    media_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    contest: Mapped["Contest"] = relationship(back_populates="questions")
    coding_tests: Mapped[list["CodingTest"]] = relationship(back_populates="question", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("contest_id", "position"),)


class CodingTest(Base):
    __tablename__ = "coding_tests"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    question_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("contest_questions.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    stdin: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_stdout: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_sample: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    weight: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    question: Mapped["ContestQuestion"] = relationship(back_populates="coding_tests")

    __table_args__ = (UniqueConstraint("question_id", "position"),)


class ContestAssignment(Base):
    __tablename__ = "contest_assignments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    contest_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("contests.id", ondelete="CASCADE"), nullable=False)
    space_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False)
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    assigned_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    contest: Mapped["Contest"] = relationship(back_populates="assignments")
    space: Mapped["Space"] = relationship(back_populates="contest_assignments")
    attempts: Mapped[list["ContestAttempt"]] = relationship(back_populates="assignment", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_contest_assignments_space_id", "space_id"),
        Index("ix_contest_assignments_deadline_at", "deadline_at"),
    )


class ContestAttempt(Base):
    __tablename__ = "contest_attempts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    assignment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("contest_assignments.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[AttemptStatus] = mapped_column(Enum(AttemptStatus, name="attempt_status"), nullable=False, default=AttemptStatus.not_started)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    score: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    max_score: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    assignment: Mapped["ContestAssignment"] = relationship(back_populates="attempts")
    student: Mapped["User"] = relationship()
    answers: Mapped[list["AttemptAnswer"]] = relationship(back_populates="attempt", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_contest_attempts_assignment_id", "assignment_id"),
        Index("ix_contest_attempts_student_id", "student_id"),
    )


class AttemptAnswer(Base):
    __tablename__ = "attempt_answers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    attempt_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("contest_attempts.id", ondelete="CASCADE"), nullable=False)
    question_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("contest_questions.id", ondelete="CASCADE"), nullable=False)
    answer: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    points_awarded: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    run_results: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    attempt: Mapped["ContestAttempt"] = relationship(back_populates="answers")
    question: Mapped["ContestQuestion"] = relationship()

    __table_args__ = (UniqueConstraint("attempt_id", "question_id"),)


class AvailabilityRule(Base):
    __tablename__ = "availability_rules"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    weekday: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)


class AvailabilityException(Base):
    __tablename__ = "availability_exceptions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    kind: Mapped[AvailabilityKind] = mapped_column(Enum(AvailabilityKind, name="availability_kind"), nullable=False)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)

    __table_args__ = (Index("ix_availability_exceptions_user_id_date", "user_id", "date"),)


class CalendarVisibility(Base):
    __tablename__ = "calendar_visibility"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    grantor_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    grantee_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    level: Mapped[VisibilityLevel] = mapped_column(Enum(VisibilityLevel, name="visibility_level"), nullable=False, default=VisibilityLevel.free_busy)
    is_open: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("grantor_id", "grantee_id"),)


class ExternalCalendarLink(Base):
    __tablename__ = "external_calendar_links"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False, default="google")
    access_token_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CodeRun(Base):
    __tablename__ = "code_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    requester_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    context_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(Text, nullable=False, default="python")
    code: Mapped[str] = mapped_column(Text, nullable=False)
    stdin: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus, name="run_status"), nullable=False, default=RunStatus.queued)
    stdout: Mapped[str | None] = mapped_column(Text, nullable=True)
    stderr: Mapped[str | None] = mapped_column(Text, nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_code_runs_requester_id_created_at", "requester_id", "created_at"),)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[NotifChannel] = mapped_column(Enum(NotifChannel, name="notif_channel"), nullable=False, default=NotifChannel.in_app)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_notifications_user_id_read_at", "user_id", "read_at"),)
