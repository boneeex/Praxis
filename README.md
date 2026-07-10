# Praxis MVP

Рабочее пространство для репетитора и учеников: хранилище материалов, совместная доска, исполнение Python, контесты, расписание и аналитика.

## Стек

- **Backend:** Python 3.11, FastAPI, SQLAlchemy 2 (async), PostgreSQL, Redis, MinIO, Docker (песочница)
- **Frontend:** React 18, Vite, Yjs, Monaco Editor, perfect-freehand
- **Инфра:** Docker Compose, nginx

## Быстрый старт

### 1. JWT-ключи

```bash
python scripts/generate_keys.py
```

### 2. Docker Compose (полный стек)

```bash
docker compose up --build
```

- API: http://localhost:8000/api/health
- Frontend (prod): http://localhost:3000
- MinIO Console: http://localhost:9001 (minioadmin/minioadmin)

### 3. Локальная разработка

```bash
# Инфраструктура
docker compose up postgres redis minio -d

# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Worker (нужен Docker для песочницы)
python -m worker.main

# Frontend
cd frontend
npm install
npm run dev
```

Откройте http://localhost:5173

## Этапы MVP (реализовано)

| Этап | Функциональность |
|------|------------------|
| 0 | Регистрация/логин, JWT RS256, пространства, join по коду |
| 1 | Хранилище, папки, материалы, MinIO, доска/код/график, песочница Python |
| 2 | Живая комната, WebSocket, вкладки, чат, показ, права редактирования |
| 3 | Контесты: конструктор, назначение, прохождение, авто-оценка |
| 4 | Расписание, доступность, автоподбор слотов, серии занятий |
| 5 | Аналитика, тепловая карта активности |

## API

Базовый путь: `/api`. WebSocket: `/ws/docs/{material_id}`, `/ws/rooms/{lesson_id}`.

Полная спецификация — в `PRAXIS_SPEC.md`.

## Переменные окружения

См. `docker-compose.yml` и `backend/app/config.py`.

## Роли

- **teacher** — создаёт пространства, материалы, контесты, занятия
- **student** — подключается по коду, проходит задания, участвует в комнатах
