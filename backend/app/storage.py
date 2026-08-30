"""Object storage abstraction.

The rest of the application talks to `ObjectStorage`, never to MinIO directly.
That gives us three things:

1. The test-suite swaps in `InMemoryStorage`, so tests need no running MinIO.
2. Object keys are produced in ONE place (`build_object_key`) and are always
   derived from server-side identifiers. A client can never influence a path.
3. Swapping MinIO for S3/Azure later touches a single module.

MinIO is never exposed to the browser. Downloads are streamed back through the
API so that every read is authorised and recorded in the audit trail.
"""

from __future__ import annotations

import io
import logging
import posixpath
import re
import threading
import uuid
from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import BinaryIO

from app.config import get_settings

logger = logging.getLogger(__name__)

_SAFE_SEGMENT = re.compile(r"[^A-Za-z0-9._-]+")


class StorageError(RuntimeError):
    """Raised when the object store cannot satisfy a request."""


class ObjectNotFound(StorageError):
    """Raised when a stored object is missing (possible tampering or data loss)."""


def sanitize_filename(filename: str, *, fallback: str = "document") -> str:
    """Reduce a client-supplied filename to a safe, flat, printable token.

    Strips directory components (defeats `../../etc/passwd` and absolute paths),
    replaces every character outside `[A-Za-z0-9._-]`, collapses leading dots
    and caps the length. The result is used for the *display* portion of the
    object key only; uniqueness always comes from a server-generated UUID.
    """
    # Handle both POSIX and Windows separators before taking the basename.
    candidate = filename.replace("\\", "/").split("/")[-1].strip()
    candidate = _SAFE_SEGMENT.sub("_", candidate).lstrip(".")
    if not candidate or candidate in {".", ".."}:
        candidate = fallback

    stem, dot, ext = candidate.rpartition(".")
    if dot:
        stem = stem[:100] or fallback
        ext = ext[:10]
        candidate = f"{stem}.{ext}"
    else:
        candidate = candidate[:110]
    return candidate


def build_object_key(*, case_id: str, document_id: str, version_number: int, filename: str) -> str:
    """Deterministic, server-generated storage key.

    Shape:  cases/<case_id>/documents/<document_id>/v<n>/<uuid>-<safe_name>

    Every component is either a UUID we generated or an integer we computed.
    The only client-derived part is the sanitised display name at the tail.
    """
    safe_name = sanitize_filename(filename)
    key = posixpath.join(
        "cases",
        str(case_id),
        "documents",
        str(document_id),
        f"v{int(version_number)}",
        f"{uuid.uuid4().hex}-{safe_name}",
    )
    # Defence in depth: the key must never escape its prefix.
    if ".." in key or key.startswith("/"):  # pragma: no cover - unreachable by construction
        raise StorageError("Refusing to generate an unsafe object key")
    return key


class ObjectStorage(ABC):
    """Minimal interface the application depends on."""

    @abstractmethod
    def ensure_bucket(self) -> None: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def put(self, key: str, data: BinaryIO, length: int, content_type: str) -> None: ...

    @abstractmethod
    def stream(self, key: str, chunk_size: int = 1024 * 1024) -> Iterator[bytes]: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...


class MinioStorage(ObjectStorage):
    def __init__(
        self,
        *,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool,
    ) -> None:
        from minio import Minio  # imported lazily so tests need no minio server

        self._bucket = bucket
        self._client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )

    def ensure_bucket(self) -> None:
        try:
            if not self._client.bucket_exists(self._bucket):
                self._client.make_bucket(self._bucket)
                logger.info("Created object storage bucket", extra={"bucket": self._bucket})
        except Exception as exc:  # noqa: BLE001 - surfaced as a startup failure
            raise StorageError(f"Unable to reach object storage: {exc}") from exc

    def exists(self, key: str) -> bool:
        from minio.error import S3Error

        try:
            self._client.stat_object(self._bucket, key)
            return True
        except S3Error as exc:
            if exc.code in {"NoSuchKey", "NoSuchObject", "NotFound"}:
                return False
            raise StorageError(str(exc)) from exc

    def put(self, key: str, data: BinaryIO, length: int, content_type: str) -> None:
        try:
            self._client.put_object(
                self._bucket, key, data, length=length, content_type=content_type
            )
        except Exception as exc:  # noqa: BLE001
            raise StorageError(f"Upload to object storage failed: {exc}") from exc

    def stream(self, key: str, chunk_size: int = 1024 * 1024) -> Iterator[bytes]:
        from minio.error import S3Error

        try:
            response = self._client.get_object(self._bucket, key)
        except S3Error as exc:
            if exc.code in {"NoSuchKey", "NoSuchObject", "NotFound"}:
                raise ObjectNotFound(key) from exc
            raise StorageError(str(exc)) from exc

        try:
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                yield chunk
        finally:
            response.close()
            response.release_conn()

    def delete(self, key: str) -> None:
        try:
            self._client.remove_object(self._bucket, key)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to delete orphaned object", extra={"key": key, "error": str(exc)})


class InMemoryStorage(ObjectStorage):
    """Process-local storage used by the test-suite.

    Never registered by the application factory in a real run.
    """

    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}
        self._lock = threading.Lock()

    def ensure_bucket(self) -> None:
        return None

    def exists(self, key: str) -> bool:
        with self._lock:
            return key in self._objects

    def put(self, key: str, data: BinaryIO, length: int, content_type: str) -> None:
        payload = data.read()
        if len(payload) != length:
            raise StorageError("Declared length does not match the payload")
        with self._lock:
            self._objects[key] = payload

    def stream(self, key: str, chunk_size: int = 1024 * 1024) -> Iterator[bytes]:
        with self._lock:
            if key not in self._objects:
                raise ObjectNotFound(key)
            payload = self._objects[key]
        buffer = io.BytesIO(payload)
        while chunk := buffer.read(chunk_size):
            yield chunk

    def delete(self, key: str) -> None:
        with self._lock:
            self._objects.pop(key, None)

    # -- test helper -----------------------------------------------------------
    def corrupt(self, key: str, replacement: bytes) -> None:
        """Simulate tampering at the storage layer (used by integrity tests)."""
        with self._lock:
            self._objects[key] = replacement


_storage: ObjectStorage | None = None


def init_storage(storage: ObjectStorage | None = None) -> ObjectStorage:
    """Create (or inject) the process-wide storage backend."""
    global _storage
    if storage is not None:
        _storage = storage
    else:
        settings = get_settings()
        _storage = MinioStorage(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            bucket=settings.minio_bucket,
            secure=settings.minio_secure,
        )
    return _storage


def get_storage() -> ObjectStorage:
    """FastAPI dependency returning the active storage backend."""
    if _storage is None:
        return init_storage()
    return _storage
