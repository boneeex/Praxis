import asyncio
import json
import logging

from sqlalchemy import select

from app.config import get_settings
from app.database import async_session
from app.models import CodeRun, RunStatus
from app.services.redis_client import get_redis, publish_room_event
from worker.sandbox import run_python_sync

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("worker")
settings = get_settings()


async def update_run(run_id: int, **kwargs):
    async with async_session() as db:
        run = await db.get(CodeRun, run_id)
        if run:
            for k, v in kwargs.items():
                setattr(run, k, v)
            await db.commit()
            return run
    return None


async def process_task(payload: dict):
    run_id = payload["run_id"]
    code = payload["code"]
    stdin = payload.get("stdin") or ""
    context = payload.get("context", {})

    await update_run(run_id, status=RunStatus.running)

    loop = asyncio.get_event_loop()
    stdout, stderr, exit_code, duration_ms, status_str = await loop.run_in_executor(
        None, lambda: run_python_sync(code, stdin)
    )

    status = RunStatus.done if status_str == "done" else RunStatus.timeout if status_str == "timeout" else RunStatus.error
    run = await update_run(
        run_id,
        status=status,
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
        duration_ms=duration_ms,
    )

    lesson_id = context.get("lesson_id")
    if lesson_id:
        await publish_room_event(
            lesson_id,
            {
                "type": "run_result",
                "run_id": run_id,
                "stdout": stdout,
                "stderr": stderr,
                "status": status.value,
                "requester_id": payload.get("requester_id"),
            },
        )


async def main():
    logger.info("Worker started")
    r = await get_redis()
    sem = asyncio.Semaphore(settings.max_concurrent_runs)

    while True:
        result = await r.blpop(settings.execute_queue_key, timeout=5)
        if not result:
            continue
        _, raw = result
        try:
            payload = json.loads(raw.decode())
        except json.JSONDecodeError:
            continue

        async def job(p):
            async with sem:
                try:
                    await process_task(p)
                except Exception as e:
                    logger.exception("Task failed: %s", e)
                    await update_run(p["run_id"], status=RunStatus.error, stderr=str(e))

        asyncio.create_task(job(payload))


if __name__ == "__main__":
    asyncio.run(main())
