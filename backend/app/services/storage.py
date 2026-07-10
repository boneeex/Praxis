import json
import secrets
import string
from datetime import datetime, timedelta, timezone
from io import BytesIO
from urllib.parse import urlparse

from minio import Minio
from minio.error import S3Error

from app.config import get_settings

settings = get_settings()


def get_minio_client() -> Minio:
    endpoint = settings.minio_endpoint
    secure = settings.minio_secure
    if "://" in endpoint:
        parsed = urlparse(endpoint)
        endpoint = parsed.netloc or parsed.path
        secure = parsed.scheme == "https"
    return Minio(
        endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=secure,
    )


def ensure_bucket() -> None:
    client = get_minio_client()
    if not client.bucket_exists(settings.minio_bucket):
        client.make_bucket(settings.minio_bucket)


def generate_storage_key(prefix: str, suffix: str = "") -> str:
    token = secrets.token_hex(16)
    return f"{prefix}/{token}{suffix}"


def presigned_put_url(key: str, content_type: str, expires: timedelta = timedelta(hours=1)) -> str:
    client = get_minio_client()
    return client.presigned_put_object(settings.minio_bucket, key, expires=expires, content_type=content_type)


def presigned_get_url(key: str, expires: timedelta = timedelta(hours=1)) -> str:
    client = get_minio_client()
    return client.presigned_get_object(settings.minio_bucket, key, expires=expires)


def put_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> int:
    client = get_minio_client()
    client.put_object(settings.minio_bucket, key, BytesIO(data), length=len(data), content_type=content_type)
    return len(data)


def get_bytes(key: str) -> bytes | None:
    client = get_minio_client()
    try:
        response = client.get_object(settings.minio_bucket, key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()
    except S3Error:
        return None


def copy_object(src_key: str, dest_key: str) -> None:
    client = get_minio_client()
    from minio.commonconfig import CopySource
    client.copy_object(settings.minio_bucket, dest_key, CopySource(settings.minio_bucket, src_key))


def delete_object(key: str) -> None:
    client = get_minio_client()
    try:
        client.remove_object(settings.minio_bucket, key)
    except S3Error:
        pass


def empty_ydoc_snapshot() -> bytes:
    return b"\x00\x00"


def generate_invite_code(length: int = 8) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))
