"""Upload validation.

Three independent checks must all agree before a file is accepted:

1. **Extension** — must be on the allow-list.
2. **Content sniffing** — the leading bytes must match a known signature. A
   `.pdf` that is really an HTML page or a script is rejected here. The
   `Content-Type` header sent by the client is treated as a hint only, never as
   evidence.
3. **Size** — enforced while streaming, so an oversized upload is abandoned
   partway instead of being buffered in memory first.

`libmagic` is deliberately avoided: it is a native dependency that behaves
differently across base images. The signature table below covers exactly the
formats this system accepts, which is a smaller and more auditable surface.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
import zipfile
from dataclasses import dataclass
from typing import BinaryIO

from app.config import ALLOWED_UPLOAD_TYPES
from app.errors import PayloadTooLargeError, UnsupportedMediaTypeError, ValidationError
from app.storage import sanitize_filename

CHUNK_SIZE = 1024 * 1024  # 1 MiB
SNIFF_BYTES = 8192
# Above this, the spooled upload moves from memory to a temp file on disk.
SPOOL_THRESHOLD = 4 * 1024 * 1024

# Extension -> mime, derived from the single allow-list in config.py.
EXTENSION_TO_MIME: dict[str, str] = {
    ext: mime for mime, exts in ALLOWED_UPLOAD_TYPES.items() for ext in exts
}


@dataclass
class InspectedUpload:
    """Result of streaming an upload to a spooled buffer."""

    handle: BinaryIO  # positioned at 0, caller must close
    sha256: str
    size: int
    mime_type: str
    safe_filename: str
    extension: str

    def close(self) -> None:
        try:
            self.handle.close()
        except Exception:  # pragma: no cover - best effort cleanup
            pass


def _extension_of(filename: str) -> str:
    return os.path.splitext(filename)[1].lower()


def _looks_like_zip(head: bytes) -> bool:
    return head[:4] in (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")


def sniff_mime(head: bytes, *, extension: str) -> str | None:
    """Identify the format from its leading bytes.

    Returns the detected mime type, or None when the content matches no format
    this system accepts.
    """
    if head[:5] == b"%PDF-":
        return "application/pdf"
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if head[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if head[:4] in (b"II*\x00", b"MM\x00*"):
        return "image/tiff"
    if head[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        # OLE2 compound file — legacy .doc (also .xls/.ppt, hence the
        # extension cross-check performed by the caller).
        return "application/msword"
    if _looks_like_zip(head):
        # OOXML files are ZIP containers; the caller confirms the internal
        # layout before trusting this.
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if extension == ".txt" and _is_probably_text(head):
        return "text/plain"
    return None


def _is_probably_text(head: bytes) -> bool:
    if b"\x00" in head:
        return False
    try:
        head.decode("utf-8")
    except UnicodeDecodeError:
        # Allow a truncated multi-byte sequence at the sniff boundary.
        try:
            head[:-4].decode("utf-8")
        except UnicodeDecodeError:
            return False
    return True


def _validate_docx_container(handle: BinaryIO) -> None:
    """Confirm a ZIP-shaped upload really is a WordprocessingML document.

    Without this, any ZIP archive (including one full of executables) would pass
    as a .docx.
    """
    position = handle.tell()
    try:
        handle.seek(0)
        with zipfile.ZipFile(handle) as archive:
            names = set(archive.namelist())
            if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                raise UnsupportedMediaTypeError(
                    "File has a .docx extension but is not a Word document."
                )
    except zipfile.BadZipFile as exc:
        raise UnsupportedMediaTypeError("File is not a readable .docx archive.") from exc
    finally:
        handle.seek(position)


def validate_filename(filename: str | None) -> tuple[str, str]:
    """Return `(safe_filename, extension)` or raise."""
    if not filename or not filename.strip():
        raise ValidationError("A filename is required.")
    if len(filename) > 255:
        raise ValidationError("Filename is too long (maximum 255 characters).")
    if "\x00" in filename:
        raise ValidationError("Filename contains an illegal null byte.")

    safe = sanitize_filename(filename)
    extension = _extension_of(safe)
    if extension not in EXTENSION_TO_MIME:
        allowed = ", ".join(sorted(EXTENSION_TO_MIME))
        raise UnsupportedMediaTypeError(f"File type '{extension or 'unknown'}' is not permitted. Allowed: {allowed}")
    return safe, extension


async def inspect_upload(
    upload,  # fastapi.UploadFile
    *,
    max_bytes: int,
    declared_content_type: str | None = None,
) -> InspectedUpload:
    """Stream, hash, size-check and identify an upload in a single pass.

    The SHA-256 is computed here — from the bytes as received, before anything
    touches the object store — so the recorded hash attests to what the officer
    actually submitted.
    """
    safe_filename, extension = validate_filename(getattr(upload, "filename", None))
    expected_mime = EXTENSION_TO_MIME[extension]

    digest = hashlib.sha256()
    spool: BinaryIO = tempfile.SpooledTemporaryFile(max_size=SPOOL_THRESHOLD)
    total = 0
    head = b""

    try:
        while True:
            chunk = await upload.read(CHUNK_SIZE)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise PayloadTooLargeError(
                    f"File exceeds the {max_bytes // (1024 * 1024)} MiB upload limit."
                )
            if len(head) < SNIFF_BYTES:
                head += chunk[: SNIFF_BYTES - len(head)]
            digest.update(chunk)
            spool.write(chunk)

        if total == 0:
            raise ValidationError("The uploaded file is empty.")

        detected = sniff_mime(head, extension=extension)
        if detected is None:
            raise UnsupportedMediaTypeError(
                "File content does not match any supported document format."
            )
        if detected != expected_mime:
            raise UnsupportedMediaTypeError(
                f"File content is '{detected}' but the extension '{extension}' "
                f"declares '{expected_mime}'. The upload was rejected."
            )
        if extension == ".docx":
            spool.seek(0)
            _validate_docx_container(spool)

        # The browser-supplied Content-Type is advisory. Disagreement is logged
        # by the caller but does not by itself decide acceptance, because the
        # sniffed content already did.
        if declared_content_type:
            declared = declared_content_type.split(";")[0].strip().lower()
            if declared and declared not in {expected_mime, "application/octet-stream"}:
                raise UnsupportedMediaTypeError(
                    f"Declared content type '{declared}' does not match the file contents."
                )

        spool.seek(0)
        return InspectedUpload(
            handle=spool,
            sha256=digest.hexdigest(),
            size=total,
            mime_type=expected_mime,
            safe_filename=safe_filename,
            extension=extension,
        )
    except Exception:
        spool.close()
        raise
