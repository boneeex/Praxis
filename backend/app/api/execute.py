import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models import CodeRun, RunStatus, User
from app.schemas import ExecuteIn, ExecuteOut, ExecuteResultOut
from app.services.redis_client import enqueue_execute, get_redis

router = APIRouter(tags=["execute"])
settings = get_settings()

_rate_limits: dict[int, list[float]] = {}


def _check_rate_limit(user_id: int) -> None:
    now = time.time()
    window = _rate_limits.setdefault(user_id, [])
    window[:] = [t for t in window if now - t < 60]
    if len(window) >= settings.execute_rate_limit_per_minute:
        raise HTTPException(status_code=429, detail={"error": {"code": "rate_limit", "message": "Too many requests"}})
    window.append(now)


@router.post("/execute", response_model=ExecuteOut)
async def execute_code(data: ExecuteIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if data.language != "python":
        raise HTTPException(status_code=400, detail={"error": {"code": "unsupported", "message": "Only python supported"}})
    if len(data.code) > 50000:
        raise HTTPException(status_code=400, detail={"error": {"code": "too_large", "message": "Code too large"}})

    _check_rate_limit(user.id)

    context_ref = None
    if data.context.get("material_id"):
        context_ref = str(data.context["material_id"])
    elif data.context.get("attempt_id") and data.context.get("question_id"):
        context_ref = f"{data.context['attempt_id']}:{data.context['question_id']}"

    run = CodeRun(
        requester_id=user.id,
        source=data.context.get("source", "board_cell"),
        context_ref=context_ref,
        language=data.language,
        code=data.code,
        stdin=data.stdin,
        status=RunStatus.queued,
    )
    db.add(run)
    await db.flush()

    payload = {
        "run_id": run.id,
        "language": data.language,
        "code": data.code,
        "stdin": data.stdin,
        "context": data.context,
        "requester_id": user.id,
    }
    await enqueue_execute(payload)
    return ExecuteOut(run_id=run.id, status=RunStatus.queued)


@router.get("/execute/{run_id}", response_model=ExecuteResultOut)
async def get_execute_result(run_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CodeRun).where(CodeRun.id == run_id, CodeRun.requester_id == user.id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Run not found"}})
    return ExecuteResultOut(
        status=run.status,
        stdout=run.stdout,
        stderr=run.stderr,
        exit_code=run.exit_code,
        duration_ms=run.duration_ms,
    )
