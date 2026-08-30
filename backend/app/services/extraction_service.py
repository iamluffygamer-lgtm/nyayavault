import logging
import uuid
import contextlib
from typing import BinaryIO

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.document import DocumentVersion, DocumentText, ExtractionMethod, ExtractionStatus
from app.storage import get_storage

logger = logging.getLogger(__name__)


def _extract_native_text(file_stream: BinaryIO) -> str:
    """Extract native text using pypdf."""
    from pypdf import PdfReader
    try:
        reader = PdfReader(file_stream)
        text = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text.append(page_text)
        return "\n".join(text).strip()
    except Exception as e:
        logger.warning(f"Native extraction failed: {e}")
        return ""


def _extract_ocr_text(file_stream: BinaryIO) -> str:
    """Extract text using tesseract OCR."""
    from pdf2image import convert_from_bytes
    import pytesseract
    try:
        file_bytes = file_stream.read()
        images = convert_from_bytes(file_bytes)
        text = []
        for img in images:
            page_text = pytesseract.image_to_string(img)
            if page_text:
                text.append(page_text)
        return "\n".join(text).strip()
    except Exception as e:
        logger.warning(f"OCR extraction failed: {e}")
        return ""


def extract_text_task(version_id: uuid.UUID, force_ocr: bool = False) -> None:
    """Background task to extract text and build the search index.
    
    Creates an independent DB session. Never modifies the original document or SHA-256.
    """
    db: Session
    with contextlib.closing(SessionLocal()) as db:
        version = db.get(DocumentVersion, version_id)
        if not version:
            return

        if version.mime_type not in ("application/pdf", "text/plain"):
            _upsert_document_text(db, version_id, None, None, ExtractionStatus.NOT_REQUIRED)
            return

        # Start processing
        _upsert_document_text(db, version_id, None, None, ExtractionStatus.PROCESSING)

        try:
            storage = get_storage()
            # We buffer to memory because pypdf and pdf2image need seekable streams / bytes
            buffer = b"".join(chunk for chunk in storage.stream(version.object_key))
            import io
            file_stream = io.BytesIO(buffer)

            if version.mime_type == "text/plain":
                text = buffer.decode("utf-8", errors="ignore").strip()
                _upsert_document_text(db, version_id, text, ExtractionMethod.NATIVE_TEXT, ExtractionStatus.COMPLETED)
                return

            if force_ocr:
                text = _extract_ocr_text(file_stream)
                _upsert_document_text(db, version_id, text, ExtractionMethod.OCR, ExtractionStatus.COMPLETED)
                return

            # Native Extraction first
            text = _extract_native_text(file_stream)
            if len(text) > 50:  # Arbitrary threshold for sufficient text
                _upsert_document_text(db, version_id, text, ExtractionMethod.NATIVE_TEXT, ExtractionStatus.COMPLETED)
            else:
                # Fallback to OCR
                file_stream.seek(0)
                text = _extract_ocr_text(file_stream)
                if text:
                    _upsert_document_text(db, version_id, text, ExtractionMethod.OCR, ExtractionStatus.COMPLETED)
                else:
                    _upsert_document_text(db, version_id, None, ExtractionMethod.OCR, ExtractionStatus.FAILED)

        except Exception as e:
            logger.error(f"Extraction failed for version {version_id}: {e}")
            _upsert_document_text(db, version_id, None, None, ExtractionStatus.FAILED)


def _upsert_document_text(
    db: Session,
    version_id: uuid.UUID,
    text: str | None,
    method: ExtractionMethod | None,
    status: ExtractionStatus,
) -> None:
    from sqlalchemy.dialects.postgresql import insert
    stmt = insert(DocumentText).values(
        document_version_id=version_id,
        extracted_text=text,
        extraction_method=method,
        extraction_status=status,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["document_version_id"],
        set_={
            "extracted_text": stmt.excluded.extracted_text,
            "extraction_method": stmt.excluded.extraction_method,
            "extraction_status": stmt.excluded.extraction_status,
        }
    )
    db.execute(stmt)
    db.commit()
