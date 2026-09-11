"""API routers, all mounted under the versioned prefix in app/main.py."""

from app.routers import audit, auth, cases, documents, users, evidence, search, departments, court

__all__ = ["auth", "users", "cases", "documents", "audit", "evidence", "search", "departments", "court"]
