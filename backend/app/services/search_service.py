import logging
from datetime import datetime
from typing import Any
import uuid

from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import TSQUERY

from app.models.case import Case, CaseAssignment
from app.models.document import Document, DocumentVersion, DocumentText
from app.models.user import User
from app.services.authorization import get_authorized_cases_query

logger = logging.getLogger(__name__)


def execute_search(
    db: Session,
    user: User,
    *,
    q: str | None = None,
    case_id: uuid.UUID | None = None,
    document_type: str | None = None,
    uploaded_by: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """Execute a strictly authorized search for documents."""
    
    # Base query for authorized cases
    authorized_cases = get_authorized_cases_query(user).subquery()

    # We want to select Document, DocumentVersion, and snippets
    # Join structure: Document -> DocumentVersion (current only) -> DocumentText
    from sqlalchemy.orm import joinedload
    stmt = (
        select(Document, DocumentVersion, DocumentText)
        .options(joinedload(Document.case))
        .options(joinedload(DocumentVersion.uploader))
        .join(authorized_cases, Document.case_id == authorized_cases.c.id)
        .join(DocumentVersion, and_(
            DocumentVersion.document_id == Document.id,
            DocumentVersion.version_number == Document.current_version
        ))
        .outerjoin(DocumentText, DocumentText.document_version_id == DocumentVersion.id)
    )

    if case_id:
        stmt = stmt.where(Document.case_id == case_id)
    if document_type:
        stmt = stmt.where(Document.document_type == document_type)
    if uploaded_by:
        stmt = stmt.where(DocumentVersion.uploaded_by == uploaded_by)
    if date_from:
        stmt = stmt.where(DocumentVersion.created_at >= date_from)
    if date_to:
        stmt = stmt.where(DocumentVersion.created_at <= date_to)

    if q:
        if db.bind and db.bind.dialect.name == "sqlite":
            # Fallback for SQLite tests since it lacks PostgreSQL FTS
            stmt = stmt.where(
                (DocumentText.extracted_text.contains(q)) |
                (Document.title.contains(q))
            )
            stmt = stmt.order_by(DocumentVersion.created_at.desc())
        else:
            # Use websearch_to_tsquery for safe parsing
            ts_query = func.websearch_to_tsquery('english', q)
            
            # Match against document title or extracted text
            title_vector = func.to_tsvector('english', Document.title)
            
            stmt = stmt.where(
                (DocumentText.search_vector.op("@@")(ts_query)) |
                (title_vector.op("@@")(ts_query))
            )
            
            # Rank by matching title first, then text
            rank_title = func.ts_rank(title_vector, ts_query)
            rank_text = func.coalesce(func.ts_rank(DocumentText.search_vector, ts_query), 0.0)
            stmt = stmt.order_by((rank_title * 2.0 + rank_text).desc())
    else:
        # If no query, just order by latest created
        stmt = stmt.order_by(DocumentVersion.created_at.desc())

    # Calculate total securely BEFORE pagination
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_count = db.execute(count_stmt).scalar_one()

    # Paginate
    page_size = min(max(1, page_size), 100)
    page = max(1, page)
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    results = db.execute(stmt).all()

    # Build Response
    items = []
    for doc, ver, dt in results:
        snippet = None
        if q and dt and dt.extracted_text:
            if db.bind and db.bind.dialect.name == "sqlite":
                snippet = "Snippet unavailable in test mode"
            else:
                # Generate snippet securely via postgres ts_headline
                ts_query = func.websearch_to_tsquery('english', q)
                snippet_stmt = select(func.ts_headline('english', dt.extracted_text, ts_query, 'MaxWords=30, MinWords=15, StartSel=***, StopSel=***'))
                snippet = db.execute(snippet_stmt).scalar_one_or_none()

        items.append({
            "document_id": doc.id,
            "title": doc.title,
            "case_id": doc.case_id,
            "case_number": doc.case.case_number,
            "document_type": doc.document_type,
            "version": ver.version_number,
            "uploaded_at": ver.created_at,
            "uploaded_by": ver.uploader.username,
            "snippet": snippet,
            "extraction_status": dt.extraction_status if dt else "NOT_REQUIRED"
        })

    return {
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "items": items
    }
