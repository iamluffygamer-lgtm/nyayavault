"""fix_audit_events_constraint

Revision ID: 1e3c75dd8878
Revises: dd14912ac6e8
Create Date: 2026-09-10 15:35:23.217052
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '1e3c75dd8878'
down_revision: Union[str, None] = 'dd14912ac6e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Safely drop the old constraint that SQLAlchemy created by default
    op.execute("ALTER TABLE audit_events DROP CONSTRAINT IF EXISTS ck_audit_events_audit_action")
    
    # We also ensure the constraint created in 51750c135384 has the latest values
    op.execute("ALTER TABLE audit_events DROP CONSTRAINT IF EXISTS audit_events_action_check")
    op.execute(
        "ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_check CHECK "
        "(action IN ('LOGIN_SUCCEEDED', 'LOGIN_FAILED', 'USER_CREATED', 'CASE_CREATED', "
        "'CASE_VIEWED', 'CASE_STATUS_CHANGED', 'CASE_ACCESS_DENIED', 'CASE_MEMBER_ASSIGNED', "
        "'DOCUMENT_UPLOADED', 'DOCUMENT_VERSION_CREATED', 'DOCUMENT_DOWNLOADED', "
        "'DOCUMENT_INTEGRITY_VERIFIED', 'DOCUMENT_INTEGRITY_FAILED', 'UPLOAD_REJECTED', "
        "'EVIDENCE_CREATED', 'EVIDENCE_SEALED', 'EVIDENCE_TRANSFER_CREATED', "
        "'EVIDENCE_TRANSFER_ACCEPTED', 'EVIDENCE_TRANSFER_REJECTED', 'EVIDENCE_ANALYSIS_STARTED', "
        "'EVIDENCE_ANALYSIS_COMPLETED', 'EVIDENCE_COURT_SUBMITTED', 'EVIDENCE_ARCHIVED', "
        "'EVIDENCE_INTEGRITY_VERIFIED', 'EVIDENCE_ACCESS_DENIED', 'SEARCH_PERFORMED'))"
    )

def downgrade() -> None:
    # Not strictly reverting anything here because it's just fixing a dangling constraint
    pass
