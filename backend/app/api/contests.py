from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import get_current_user, get_space_or_403, require_teacher
from app.database import get_db
from app.models import (
    AttemptAnswer,
    AttemptStatus,
    CodingTest,
    Contest,
    ContestAssignment,
    ContestAttempt,
    ContestQuestion,
    QuestionType,
    RunStatus,
    SpaceMembership,
    User,
    UserRole,
)
from app.schemas import (
    AnswerPatchIn,
    AssignIn,
    CodingTestIn,
    ContestCreateIn,
    ContestPatchIn,
    QuestionCreateIn,
    QuestionPatchIn,
    QuestionReorderIn,
)
from app.services.grading import compare_stdout, grade_choice, grade_short_answer, partial_coding_score
from app.services.redis_client import enqueue_execute

router = APIRouter(tags=["contests"])


@router.post("/contests")
async def create_contest(data: ContestCreateIn, user: User = Depends(require_teacher), db: AsyncSession = Depends(get_db)):
    contest = Contest(
        owner_teacher_id=user.id,
        title=data.title,
        description=data.description,
        time_limit_sec=data.time_limit_sec,
        shuffle_questions=data.shuffle_questions,
        max_attempts=data.max_attempts,
    )
    db.add(contest)
    await db.flush()
    return {"id": contest.id, "title": contest.title}


@router.get("/contests")
async def list_contests(user: User = Depends(require_teacher), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Contest).where(Contest.owner_teacher_id == user.id).order_by(Contest.updated_at.desc()))
    return [{"id": c.id, "title": c.title, "description": c.description, "updated_at": c.updated_at.isoformat()} for c in result.scalars().all()]


@router.get("/contests/{contest_id}")
async def get_contest(contest_id: int, user: User = Depends(require_teacher), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Contest).where(Contest.id == contest_id, Contest.owner_teacher_id == user.id).options(selectinload(Contest.questions).selectinload(ContestQuestion.coding_tests))
    )
    contest = result.scalar_one_or_none()
    if not contest:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Not found"}})
    return {
        "id": contest.id,
        "title": contest.title,
        "description": contest.description,
        "time_limit_sec": contest.time_limit_sec,
        "shuffle_questions": contest.shuffle_questions,
        "max_attempts": contest.max_attempts,
        "questions": [
            {
                "id": q.id,
                "position": q.position,
                "type": q.type.value,
                "prompt": q.prompt,
                "points": q.points,
                "config": q.config,
                "tests": [{"id": t.id, "stdin": t.stdin, "expected_stdout": t.expected_stdout, "is_sample": t.is_sample, "weight": t.weight} for t in q.coding_tests],
            }
            for q in sorted(contest.questions, key=lambda x: x.position)
        ],
    }


@router.patch("/contests/{contest_id}")
async def patch_contest(contest_id: int, data: ContestPatchIn, user: User = Depends(require_teacher), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Contest).where(Contest.id == contest_id, Contest.owner_teacher_id == user.id))
    contest = result.scalar_one_or_none()
    if not contest:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Not found"}})
    for field in ("title", "description", "time_limit_sec", "shuffle_questions", "max_attempts"):
        val = getattr(data, field)
        if val is not None:
            setattr(contest, field, val)
    await db.flush()
    return {"ok": True}


@router.delete("/contests/{contest_id}")
async def delete_contest(contest_id: int, user: User = Depends(require_teacher), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Contest).where(Contest.id == contest_id, Contest.owner_teacher_id == user.id))
    contest = result.scalar_one_or_none()
    if not contest:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Not found"}})
    await db.delete(contest)
    return {"ok": True}


@router.post("/contests/{contest_id}/questions")
async def add_question(contest_id: int, data: QuestionCreateIn, user: User = Depends(require_teacher), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Contest).where(Contest.id == contest_id, Contest.owner_teacher_id == user.id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Not found"}})
    count = await db.execute(select(func.count()).select_from(ContestQuestion).where(ContestQuestion.contest_id == contest_id))
    position = count.scalar() or 0
    q = ContestQuestion(contest_id=contest_id, position=position, type=data.type, prompt=data.prompt, points=data.points, media_ref=data.media_ref, config=data.config)
    db.add(q)
    await db.flush()
    return {"id": q.id, "position": q.position}


@router.patch("/questions/{question_id}")
async def patch_question(question_id: int, data: QuestionPatchIn, user: User = Depends(require_teacher), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ContestQuestion).join(Contest).where(ContestQuestion.id == question_id, Contest.owner_teacher_id == user.id)
    )
    q = result.scalar_one_or_none()
    if not q:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Not found"}})
    for field in ("prompt", "points", "media_ref", "config"):
        val = getattr(data, field)
        if val is not None:
            setattr(q, field, val)
    await db.flush()
    return {"ok": True}


@router.delete("/questions/{question_id}")
async def delete_question(question_id: int, user: User = Depends(require_teacher), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ContestQuestion).join(Contest).where(ContestQuestion.id == question_id, Contest.owner_teacher_id == user.id)
    )
    q = result.scalar_one_or_none()
    if not q:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Not found"}})
    await db.delete(q)
    return {"ok": True}


@router.post("/contests/{contest_id}/questions/reorder")
async def reorder_questions(contest_id: int, data: QuestionReorderIn, user: User = Depends(require_teacher), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Contest).where(Contest.id == contest_id, Contest.owner_teacher_id == user.id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Not found"}})
    for i, qid in enumerate(data.order):
        q = await db.get(ContestQuestion, qid)
        if q and q.contest_id == contest_id:
            q.position = i
    await db.flush()
    return {"ok": True}


@router.post("/questions/{question_id}/tests")
async def add_test(question_id: int, data: CodingTestIn, user: User = Depends(require_teacher), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ContestQuestion).join(Contest).where(ContestQuestion.id == question_id, Contest.owner_teacher_id == user.id)
    )
    q = result.scalar_one_or_none()
    if not q:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Not found"}})
    count = await db.execute(select(func.count()).select_from(CodingTest).where(CodingTest.question_id == question_id))
    t = CodingTest(
        question_id=question_id,
        position=count.scalar() or 0,
        stdin=data.stdin,
        expected_stdout=data.expected_stdout,
        is_sample=data.is_sample,
        weight=data.weight,
    )
    db.add(t)
    await db.flush()
    return {"id": t.id}


@router.patch("/tests/{test_id}")
async def patch_test(test_id: int, data: CodingTestIn, user: User = Depends(require_teacher), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CodingTest).join(ContestQuestion).join(Contest).where(CodingTest.id == test_id, Contest.owner_teacher_id == user.id)
    )
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Not found"}})
    for field in ("stdin", "expected_stdout", "is_sample", "weight"):
        val = getattr(data, field)
        if val is not None:
            setattr(t, field, val)
    await db.flush()
    return {"ok": True}


@router.delete("/tests/{test_id}")
async def delete_test(test_id: int, user: User = Depends(require_teacher), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CodingTest).join(ContestQuestion).join(Contest).where(CodingTest.id == test_id, Contest.owner_teacher_id == user.id)
    )
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Not found"}})
    await db.delete(t)
    return {"ok": True}


@router.post("/contests/{contest_id}/assign")
async def assign_contest(contest_id: int, data: AssignIn, user: User = Depends(require_teacher), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Contest).where(Contest.id == contest_id, Contest.owner_teacher_id == user.id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Not found"}})
    if data.deadline_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=422, detail={"error": {"code": "past_deadline", "message": "Deadline in the past"}})
    space = await get_space_or_403(data.space_id, user, db)
    if space.teacher_id != user.id:
        raise HTTPException(status_code=403, detail={"error": {"code": "forbidden", "message": "Not your space"}})
    a = ContestAssignment(contest_id=contest_id, space_id=data.space_id, deadline_at=data.deadline_at, assigned_by=user.id)
    db.add(a)
    await db.flush()
    return {"id": a.id}


@router.get("/contests/{contest_id}/results")
async def contest_results(contest_id: int, user: User = Depends(require_teacher), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Contest).where(Contest.id == contest_id, Contest.owner_teacher_id == user.id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Not found"}})
    attempts = await db.execute(
        select(ContestAttempt, User)
        .join(User, User.id == ContestAttempt.student_id)
        .join(ContestAssignment)
        .where(ContestAssignment.contest_id == contest_id)
    )
    return [
        {"student_id": u.id, "display_name": u.display_name, "status": a.status.value, "score": float(a.score) if a.score else None, "max_score": float(a.max_score) if a.max_score else None}
        for a, u in attempts.all()
    ]


@router.get("/assignments")
async def list_assignments(
    space_id: int | None = None,
    status: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role != UserRole.student:
        raise HTTPException(status_code=403, detail={"error": {"code": "forbidden", "message": "Students only"}})
    memberships = await db.execute(select(SpaceMembership).where(SpaceMembership.user_id == user.id))
    space_ids = [m.space_id for m in memberships.scalars().all()]
    if not space_ids:
        return []
    query = select(ContestAssignment, Contest).join(Contest).where(ContestAssignment.space_id.in_(space_ids))
    if space_id:
        query = query.where(ContestAssignment.space_id == space_id)
    result = await db.execute(query)
    out = []
    for assignment, contest in result.all():
        attempt_result = await db.execute(
            select(ContestAttempt).where(ContestAttempt.assignment_id == assignment.id, ContestAttempt.student_id == user.id).order_by(ContestAttempt.created_at.desc())
        )
        attempt = attempt_result.scalars().first()
        out.append({
            "id": assignment.id,
            "contest_id": contest.id,
            "contest_title": contest.title,
            "space_id": assignment.space_id,
            "deadline_at": assignment.deadline_at.isoformat(),
            "attempt_status": attempt.status.value if attempt else "not_started",
            "score": float(attempt.score) if attempt and attempt.score else None,
        })
    return out


@router.get("/assignments/{assignment_id}")
async def get_assignment(assignment_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ContestAssignment, Contest).join(Contest).where(ContestAssignment.id == assignment_id))
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Not found"}})
    assignment, contest = row
    await get_space_or_403(assignment.space_id, user, db)
    return {"id": assignment.id, "contest": {"id": contest.id, "title": contest.title}, "deadline_at": assignment.deadline_at.isoformat()}


@router.post("/assignments/{assignment_id}/attempts")
async def start_attempt(assignment_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.role != UserRole.student:
        raise HTTPException(status_code=403, detail={"error": {"code": "forbidden", "message": "Students only"}})
    result = await db.execute(select(ContestAssignment, Contest).join(Contest).where(ContestAssignment.id == assignment_id))
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Not found"}})
    assignment, contest = row
    await get_space_or_403(assignment.space_id, user, db)
    if assignment.deadline_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=409, detail={"error": {"code": "deadline_passed", "message": "Deadline passed"}})

    existing = await db.execute(select(ContestAttempt).where(ContestAttempt.assignment_id == assignment_id, ContestAttempt.student_id == user.id))
    attempts = existing.scalars().all()
    if contest.max_attempts and len(attempts) >= contest.max_attempts:
        raise HTTPException(status_code=409, detail={"error": {"code": "max_attempts", "message": "Max attempts reached"}})

    questions = await db.execute(select(ContestQuestion).where(ContestQuestion.contest_id == contest.id))
    max_score = sum(q.points for q in questions.scalars().all())
    attempt = ContestAttempt(
        assignment_id=assignment_id,
        student_id=user.id,
        status=AttemptStatus.in_progress,
        started_at=datetime.now(timezone.utc),
        max_score=Decimal(max_score),
    )
    db.add(attempt)
    await db.flush()
    return {"id": attempt.id, "max_score": float(max_score)}


@router.get("/attempts/{attempt_id}")
async def get_attempt(attempt_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ContestAttempt).where(ContestAttempt.id == attempt_id))
    attempt = result.scalar_one_or_none()
    if not attempt:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Not found"}})
    assignment = await db.get(ContestAssignment, attempt.assignment_id)
    contest = await db.get(Contest, assignment.contest_id) if assignment else None
    is_student = attempt.student_id == user.id
    is_teacher = contest and contest.owner_teacher_id == user.id
    if not is_student and not is_teacher:
        raise HTTPException(status_code=403, detail={"error": {"code": "forbidden", "message": "Forbidden"}})

    questions = await db.execute(select(ContestQuestion).where(ContestQuestion.contest_id == contest.id).order_by(ContestQuestion.position))
    answers_result = await db.execute(select(AttemptAnswer).where(AttemptAnswer.attempt_id == attempt_id))
    answers = {a.question_id: a for a in answers_result.scalars().all()}
    show_correct = attempt.status in (AttemptStatus.submitted, AttemptStatus.graded) or is_teacher

    qs = []
    for q in questions.scalars().all():
        item = {"id": q.id, "type": q.type.value, "prompt": q.prompt, "points": q.points, "answer": answers.get(q.id, AttemptAnswer()).answer}
        if show_correct and q.type in (QuestionType.single_choice, QuestionType.multi_choice, QuestionType.short_answer):
            item["config"] = q.config
        qs.append(item)

    return {"id": attempt.id, "status": attempt.status.value, "score": float(attempt.score) if attempt.score else None, "max_score": float(attempt.max_score) if attempt.max_score else None, "questions": qs}


@router.patch("/attempts/{attempt_id}/answers")
async def save_answer(attempt_id: int, data: AnswerPatchIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ContestAttempt).where(ContestAttempt.id == attempt_id, ContestAttempt.student_id == user.id))
    attempt = result.scalar_one_or_none()
    if not attempt:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Not found"}})
    if attempt.status not in (AttemptStatus.in_progress, AttemptStatus.not_started):
        raise HTTPException(status_code=409, detail={"error": {"code": "closed", "message": "Attempt closed"}})

    existing = await db.execute(select(AttemptAnswer).where(AttemptAnswer.attempt_id == attempt_id, AttemptAnswer.question_id == data.question_id))
    ans = existing.scalar_one_or_none()
    if ans:
        ans.answer = data.answer
    else:
        ans = AttemptAnswer(attempt_id=attempt_id, question_id=data.question_id, answer=data.answer)
        db.add(ans)
    if attempt.status == AttemptStatus.not_started:
        attempt.status = AttemptStatus.in_progress
        attempt.started_at = datetime.now(timezone.utc)
    await db.flush()
    return {"ok": True}


@router.post("/attempts/{attempt_id}/submit")
async def submit_attempt(attempt_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.models import CodeRun

    result = await db.execute(select(ContestAttempt).where(ContestAttempt.id == attempt_id, ContestAttempt.student_id == user.id))
    attempt = result.scalar_one_or_none()
    if not attempt:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Not found"}})

    assignment = await db.get(ContestAssignment, attempt.assignment_id)
    contest = await db.get(Contest, assignment.contest_id)
    questions = await db.execute(
        select(ContestQuestion).where(ContestQuestion.contest_id == contest.id).options(selectinload(ContestQuestion.coding_tests))
    )
    answers_result = await db.execute(select(AttemptAnswer).where(AttemptAnswer.attempt_id == attempt_id))
    answers = {a.question_id: a for a in answers_result.scalars().all()}

    total_score = Decimal("0")
    for q in questions.scalars().all():
        ans = answers.get(q.id)
        if q.type in (QuestionType.single_choice, QuestionType.multi_choice):
            ratio, _ = grade_choice(ans.answer if ans else None, q.config)
            pts = Decimal(q.points) * ratio
        elif q.type == QuestionType.short_answer:
            ratio, _ = grade_short_answer(ans.answer if ans else None, q.config)
            pts = Decimal(q.points) * ratio
        elif q.type == QuestionType.flashcard:
            pts = Decimal("0")
        elif q.type == QuestionType.coding:
            code = (ans.answer or {}).get("code", q.config.get("starter_code", "")) if ans else q.config.get("starter_code", "")
            tests = [t for t in q.coding_tests if not t.is_sample or True]
            passed_weight = 0
            total_weight = sum(t.weight for t in tests) or 1
            run_results = []
            for t in tests:
                from worker.sandbox import run_python_sync
                stdout, stderr, exit_code, duration_ms, status = run_python_sync(code, t.stdin or "")
                passed = compare_stdout(stdout or "", t.expected_stdout or "")
                if passed:
                    passed_weight += t.weight
                run_results.append({"test_id": t.id, "passed": passed, "stdout": stdout, "stderr": stderr, "ms": duration_ms})
            if ans:
                ans.run_results = run_results
                ans.points_awarded = Decimal(q.points) * partial_coding_score(passed_weight, total_weight)
            pts = Decimal(q.points) * partial_coding_score(passed_weight, total_weight)
        else:
            pts = Decimal("0")

        if ans:
            ans.points_awarded = pts
        total_score += pts

    attempt.score = total_score
    attempt.status = AttemptStatus.graded
    attempt.submitted_at = datetime.now(timezone.utc)
    await db.flush()
    return {"score": float(total_score), "max_score": float(attempt.max_score or 0)}
