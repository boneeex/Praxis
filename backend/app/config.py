from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://praxis:praxis@localhost:5432/praxis"
    redis_url: str = "redis://localhost:6379/0"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "praxis"
    minio_public_endpoint: str = "localhost:9000"
    minio_secure: bool = False

    jwt_private_key_path: str = "pems/private.pem"
    jwt_public_key_path: str = "pems/public.pem"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    execute_queue_key: str = "execute:queue"
    max_concurrent_runs: int = 4
    execute_timeout_sec: int = 10
    execute_output_limit: int = 65536
    execute_rate_limit_per_minute: int = 30

    default_storage_quota_bytes: int = 5 * 1024 * 1024 * 1024
    ydoc_snapshot_debounce_sec: int = 8
    ydoc_redis_ttl_sec: int = 3600

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def jwt_private_key(self) -> str:
        path = Path(self.jwt_private_key_path)
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[2] / path
        return path.read_text()

    @property
    def jwt_public_key(self) -> str:
        path = Path(self.jwt_public_key_path)
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[2] / path
        return path.read_text()


@lru_cache
def get_settings() -> Settings:
    return Settings()
