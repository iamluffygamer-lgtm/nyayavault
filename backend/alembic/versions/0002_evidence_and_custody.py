"""Add evidence and custody models

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-29
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enum(values: tuple[str, ...], name: str, length: int) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, length=length)


EVIDENCE_STATUSES = (
    "COLLECTED",
    "REGISTERED",
    "SEALED",
    "IN_CUSTODY",
    "TRANSFER_PENDING",
    "UNDER_ANALYSIS",
    "ANALYZED",
    "COURT_SUBMITTED",
    "ARCHIVED",
)

TRANSFER_STATUSES = ("PENDING", "COMPLETED", "REJECTED")

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
    "EVIDENCE_CREATED",
    "EVIDENCE_SEALED",
    "EVIDENCE_TRANSFER_CREATED",
    "EVIDENCE_TRANSFER_ACCEPTED",
    "EVIDENCE_TRANSFER_REJECTED",
    "EVIDENCE_ANALYSIS_STARTED",
    "EVIDENCE_ANALYSIS_COMPLETED",
    "EVIDENCE_COURT_SUBMITTED",
    "EVIDENCE_ARCHIVED",
    "EVIDENCE_INTEGRITY_VERIFIED",
    "EVIDENCE_ACCESS_DENIED"
)

def upgrade() -> None:
    # ------------------------------------------------------------- evidence
    op.create_table(
        "evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_number", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("evidence_type", sa.String(length=64), nullable=False),
        sa.Column("status", _enum(EVIDENCE_STATUSES, "evidence_status", 32), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("collected_location", sa.String(length=255), nullable=True),
        sa.Column("collected_by", sa.Uuid(), nullable=True),
        sa.Column("current_custodian", sa.Uuid(), nullable=True),
        sa.Column("source_document_id", sa.Uuid(), nullable=True),
        sa.Column("sha256_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], name="fk_evidence_case_id_cases", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["collected_by"], ["users.id"], name="fk_evidence_collected_by_users", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["current_custodian"], ["users.id"], name="fk_evidence_current_custodian_users", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_document_id"], ["documents.id"], name="fk_evidence_source_document_id_documents", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_evidence"),
        sa.UniqueConstraint("case_id", "evidence_number", name="uq_evidence_case_number")
    )
    op.create_index("ix_evidence_case_id", "evidence", ["case_id"])
    op.create_index("ix_evidence_evidence_number", "evidence", ["evidence_number"])
    op.create_index("ix_evidence_status", "evidence", ["status"])
    op.create_index("ix_evidence_evidence_type", "evidence", ["evidence_type"])
    op.create_index("ix_evidence_collected_by", "evidence", ["collected_by"])
    op.create_index("ix_evidence_current_custodian", "evidence", ["current_custodian"])
    op.create_index("ix_evidence_source_document_id", "evidence", ["source_document_id"])

    # ------------------------------------------------------------- evidence_transfers
    op.create_table(
        "evidence_transfers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        sa.Column("from_user_id", sa.Uuid(), nullable=False),
        sa.Column("to_user_id", sa.Uuid(), nullable=False),
        sa.Column("transferred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("status", _enum(TRANSFER_STATUSES, "transfer_status", 32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["evidence_id"], ["evidence.id"], name="fk_evidence_transfers_evidence_id_evidence", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["from_user_id"], ["users.id"], name="fk_evidence_transfers_from_user_id_users", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["to_user_id"], ["users.id"], name="fk_evidence_transfers_to_user_id_users", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_evidence_transfers")
    )
    op.create_index("ix_evidence_transfers_evidence_id", "evidence_transfers", ["evidence_id"])
    op.create_index("ix_evidence_transfers_from_user_id", "evidence_transfers", ["from_user_id"])
    op.create_index("ix_evidence_transfers_to_user_id", "evidence_transfers", ["to_user_id"])
    op.create_index("ix_evidence_transfers_status", "evidence_transfers", ["status"])

    op.execute("ALTER TABLE audit_events DROP CONSTRAINT IF EXISTS audit_action")
    op.execute("ALTER TABLE audit_events DROP CONSTRAINT IF EXISTS ck_audit_events_audit_action")
    op.execute("ALTER TABLE audit_events DROP CONSTRAINT IF EXISTS audit_events_action_check")
    op.create_check_constraint(
        "audit_action",
        "audit_events",
        sa.column("action").in_(AUDIT_ACTIONS)
    )

def downgrade() -> None:
    OLD_AUDIT_ACTIONS = (
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
    op.drop_constraint("audit_action", "audit_events", type_="check")
    op.create_check_constraint(
        "audit_action",
        "audit_events",
        sa.column("action").in_(OLD_AUDIT_ACTIONS)
    )
    op.drop_table("evidence_transfers")
    op.drop_table("evidence")
