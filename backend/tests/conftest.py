"""Test fixtures.

The suite runs against SQLite plus the in-memory object storage backend, so
`pytest` needs neither PostgreSQL nor MinIO. Environment variables are set
before `app.config` is imported, because settings are read once at import time.
"""

from __future__ import annotations

import io
import os
import zipfile
from collections.abc import Iterator

import pytest

# --- environment must be configured before any application import ------------
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret-key-that-is-long-enough-1234567890")
os.environ.setdefault("MINIO_ACCESS_KEY", "test-access-key")
os.environ.setdefault("MINIO_SECRET_KEY", "test-secret-key")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("SEED_ADMIN_PASSWORD", "")
# Minimum bcrypt cost: the suite hashes dozens of passwords and the work factor
# is not what is under test. Production enforces a floor of 10 (app/security.py).
os.environ.setdefault("BCRYPT_ROUNDS", "4")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.database import get_db  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import (  # noqa: E402
    ROLE_DESCRIPTIONS,
    Base,
    Department,
    Role,
    RoleName,
    User,
)
from app.security import hash_password  # noqa: E402
from app.storage import InMemoryStorage, get_storage, init_storage  # noqa: E402

# Passwords used by the tests. They satisfy the production password policy so
# the tests exercise the same code path real users do.
PASSWORDS = {
    "admin": "Admin#Passw0rd!2026",
    "investigator": "Invest#Passw0rd!26",
    "investigator2": "Invest2#Passw0rd!6",
    "forensic": "Forens#Passw0rd!26",
    "auditor": "Audit#Passw0rd!2026",
    "legal": "Legal#Passw0rd!2026",
}


@pytest.fixture(scope="function")
def engine():
    """One shared in-memory SQLite database per test."""
    eng = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture(scope="function")
def db_session(engine) -> Iterator[Session]:
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def storage() -> InMemoryStorage:
    backend = InMemoryStorage()
    init_storage(backend)
    return backend


@pytest.fixture(scope="function")
def seeded(db_session: Session) -> dict:
    """Reference data plus one user per role."""
    roles = {}
    for name in RoleName:
        role = Role(name=name.value, description=ROLE_DESCRIPTIONS[name])
        db_session.add(role)
        roles[name.value] = role

    department = Department(name="Cyber Crime Cell", description="Digital forensics")
    db_session.add(department)
    db_session.flush()

    people = {
        "admin": RoleName.ADMIN,
        "investigator": RoleName.INVESTIGATOR,
        "investigator2": RoleName.INVESTIGATOR,
        "forensic": RoleName.FORENSIC_OFFICER,
        "auditor": RoleName.AUDITOR,
        "legal": RoleName.LEGAL_OFFICER,
    }

    users = {}
    for username, role_name in people.items():
        user = User(
            username=username,
            email=f"{username}@nyayavault.gov.in",
            full_name=username.title(),
            password_hash=hash_password(PASSWORDS[username]),
            role_id=roles[role_name.value].id,
            department_id=department.id,
            is_active=True,
        )
        db_session.add(user)
        users[username] = user

    db_session.commit()
    return {"roles": roles, "users": users, "department": department}


@pytest.fixture(scope="function")
def client(engine, storage, seeded) -> Iterator[TestClient]:
    app = create_app()
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db() -> Iterator[Session]:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_storage] = lambda: storage

    # Bypass the lifespan (it would try to reach a real MinIO); storage is
    # already injected above.
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ------------------------------------------------------------------- helpers


def login(client: TestClient, username: str) -> str:
    """Return a bearer token for one of the seeded users."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": PASSWORDS[username]},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def pdf_bytes(body: str = "NyayaVault test document") -> bytes:
    """A minimal but genuinely PDF-signatured payload."""
    return b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n" + body.encode("utf-8") + b"\n%%EOF\n"


def png_bytes() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def docx_bytes() -> bytes:
    """A ZIP with the internal layout that makes it a real .docx."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<document/>")
    return buffer.getvalue()


def upload_document(
    client: TestClient,
    token: str,
    case_id: str,
    *,
    filename: str = "chargesheet.pdf",
    content: bytes | None = None,
    title: str = "Charge Sheet",
    content_type: str = "application/pdf",
    document_type: str = "CHARGE_SHEET",
):
    return client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers=auth(token),
        files={"file": (filename, content if content is not None else pdf_bytes(), content_type)},
        data={"title": title, "document_type": document_type},
    )


def create_case(client: TestClient, token: str, title: str = "Test case") -> dict:
    response = client.post(
        "/api/v1/cases",
        headers=auth(token),
        json={"title": title, "description": "Created by the test suite."},
    )
    assert response.status_code == 201, response.text
    return response.json()
