"""M0 initial schema

Creates the six specification entities plus `case_assignments` (case-level
access control), and enables the pgvector extension so the semantic-search
milestone has nothing to retrofit. No vector column is created yet.

Revision ID: 0001
Revises:
Create Date: 2026-01-01
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CASE_STATUSES = ("OPEN", "UNDER_INVESTIGATION", "SUBMITTED", "CLOSED", "ARCHIVED")
ACCESS_LEVELS = ("READ", "CONTRIBUTE", "MANAGE")
DOCUMENT_TYPES = (
    "FIR",
    "CHARGE_SHEET",
    "WITNESS_STATEMENT",
    "FORENSIC_REPORT",
    "SEIZURE_MEMO",
    "COURT_ORDER",
    "LEGAL_NOTICE",
    "EVIDENCE_PHOTO",
    "OTHER",
)
AUDIT_ACTIONS = (
    "LOGIN_SUCCEEDED",
    "LOGIN_FAILED",
    "USER_CREATED",
    "CASE_CREATED",
    "CASE_VIEWED",
    "CASE_STATUS_CHANGED",
    "CASE_ACCESS_DENIED",
    "CASE_MEMBER_ASSIGNED",
    "DOCUMENT_UPLOADED",
    "DOCUMENT_VERSION_CREATED",
    "DOCUMENT_DOWNLOADED",
    "DOCUMENT_INTEGRITY_VERIFIED",
    "DOCUMENT_INTEGRITY_FAILED",
    "UPLOAD_REJECTED",
)
AUDIT_RESULTS = ("SUCCESS", "FAILURE", "DENIED")


def _enum(values: tuple[str, ...], name: str, length: int) -> sa.Enum:
    # native_enum=False -> VARCHAR + CHECK constraint. Portable, and adding a
    # value later is a CHECK change rather than an ALTER TYPE.
    return sa.Enum(*values, name=name, native_enum=False, length=length)


def _json() -> sa.types.TypeEngine:
    return postgresql.JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    # pgvector is enabled now so the later semantic-search milestone is a pure
    # additive migration. Requires the pgvector/pgvector image (or the extension
    # installed on the server); harmless if it already exists.
    if op.get_bind().dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ------------------------------------------------------------------ roles
    op.create_table(
        "roles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_roles"),
    )
    # Unique AND indexed -> a single unique index, matching what the model emits.
    op.create_index("ix_roles_name", "roles", ["name"], unique=True)

    # ------------------------------------------------------------ departments
    op.create_table(
        "departments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_departments"),
    )
    op.create_index("ix_departments_name", "departments", ["name"], unique=True)

    # ------------------------------------------------------------------ users
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=160), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["role_id"], ["roles.id"], name="fk_users_role_id_roles", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["department_id"],
            ["departments.id"],
            name="fk_users_department_id_departments",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_role_id", "users", ["role_id"])
    op.create_index("ix_users_department_id", "users", ["department_id"])

    # ------------------------------------------------------------------ cases
    op.create_table(
        "cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_number", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", _enum(CASE_STATUSES, "case_status", 32), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name="fk_cases_created_by_users", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_cases"),
    )
    op.create_index("ix_cases_case_number", "cases", ["case_number"], unique=True)
    op.create_index("ix_cases_status", "cases", ["status"])
    op.create_index("ix_cases_created_by", "cases", ["created_by"])

    # ------------------------------------------------------- case_assignments
    op.create_table(
        "case_assignments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("access_level", _enum(ACCESS_LEVELS, "case_access_level", 16), nullable=False),
        sa.Column("assigned_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id"], ["cases.id"], name="fk_case_assignments_case_id_cases", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_case_assignments_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["assigned_by"],
            ["users.id"],
            name="fk_case_assignments_assigned_by_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_case_assignments"),
        sa.UniqueConstraint("case_id", "user_id", name="uq_case_assignment"),
    )
    op.create_index("ix_case_assignments_case_id", "case_assignments", ["case_id"])
    op.create_index("ix_case_assignments_user_id", "case_assignments", ["user_id"])

    # -------------------------------------------------------------- documents
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("document_type", _enum(DOCUMENT_TYPES, "document_type", 32), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("current_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id"], ["cases.id"], name="fk_documents_case_id_cases", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name="fk_documents_created_by_users", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_documents"),
    )
    op.create_index("ix_documents_case_id", "documents", ["case_id"])
    op.create_index("ix_documents_document_type", "documents", ["document_type"])
    op.create_index("ix_documents_created_by", "documents", ["created_by"])

    # ------------------------------------------------------ document_versions
    op.create_table(
        "document_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("sha256_hash", sa.String(length=64), nullable=False),
        sa.Column("uploaded_by", sa.Uuid(), nullable=False),
        sa.Column("change_reason", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_document_versions_document_id_documents",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by"],
            ["users.id"],
            name="fk_document_versions_uploaded_by_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_document_versions"),
        # These two constraints are what make "never overwrite a version" a
        # database guarantee rather than an application convention.
        sa.UniqueConstraint("document_id", "version_number", name="uq_document_version"),
        sa.UniqueConstraint("object_key", name="uq_document_version_object_key"),
        sa.CheckConstraint("version_number >= 1", name="ck_document_versions_version_number_positive"),
        sa.CheckConstraint("file_size >= 0", name="ck_document_versions_file_size_non_negative"),
    )
    op.create_index("ix_document_versions_document_id", "document_versions", ["document_id"])
    op.create_index("ix_document_versions_sha256_hash", "document_versions", ["sha256_hash"])
    op.create_index("ix_document_versions_uploaded_by", "document_versions", ["uploaded_by"])

    # ----------------------------------------------------------- audit_events
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("case_id", sa.Uuid(), nullable=True),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=True),
        sa.Column("action", _enum(AUDIT_ACTIONS, "audit_action", 48), nullable=False),
        sa.Column("result", _enum(AUDIT_RESULTS, "audit_result", 16), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", _json(), nullable=False),
        sa.Column("previous_event_hash", sa.String(length=64), nullable=False),
        sa.Column("event_hash", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], name="fk_audit_events_actor_id_users", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["case_id"], ["cases.id"], name="fk_audit_events_case_id_cases", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_events"),
    )
    op.create_index("ix_audit_events_actor_id", "audit_events", ["actor_id"])
    op.create_index("ix_audit_events_case_id", "audit_events", ["case_id"])
    op.create_index("ix_audit_events_timestamp", "audit_events", ["timestamp"])
    op.create_index("ix_audit_events_event_hash", "audit_events", ["event_hash"], unique=True)


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("document_versions")
    op.drop_table("documents")
    op.drop_table("case_assignments")
    op.drop_table("cases")
    op.drop_table("users")
    op.drop_table("departments")
    op.drop_table("roles")
    # The vector extension is deliberately NOT dropped: other schemas in the
    # same database may depend on it.
