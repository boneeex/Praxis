from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import analytics, auth, contests, execute, folders, materials, rooms, scheduling, spaces
from app.config import get_settings
from app.database import engine
from app.models import Base
from app.services.redis_client import close_redis
from app.services.storage import ensure_bucket
from app.ws.handlers import handle_docs_ws, handle_room_ws

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS citext"))
        await conn.run_sync(Base.metadata.create_all)
    try:
        ensure_bucket()
    except Exception:
        pass
    yield
    await close_redis()


app = FastAPI(title="Praxis API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = FastAPI()
app.mount("/api", api)

api.include_router(auth.router)
api.include_router(spaces.router)
api.include_router(folders.router)
api.include_router(materials.router)
api.include_router(execute.router)
api.include_router(rooms.router)
api.include_router(scheduling.router)
api.include_router(contests.router)
api.include_router(analytics.router)


@api.get("/health")
async def health():
    return {"status": "ok"}


@app.websocket("/ws/docs/{material_id}")
async def ws_docs(websocket: WebSocket, material_id: int, token: str | None = Query(None)):
    await handle_docs_ws(websocket, material_id, token)


@app.websocket("/ws/rooms/{lesson_id}")
async def ws_rooms(websocket: WebSocket, lesson_id: int, token: str | None = Query(None)):
    await handle_room_ws(websocket, lesson_id, token)
