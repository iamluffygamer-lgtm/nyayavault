"""document_search

Revision ID: 51750c135384
Revises: 0002
Create Date: 2026-08-30 05:03:30.976716
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '51750c135384'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('document_text',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('document_version_id', sa.Uuid(), nullable=False),
    sa.Column('extracted_text', sa.Text(), nullable=True),
    sa.Column('search_vector', postgresql.TSVECTOR(), sa.Computed("to_tsvector('english', coalesce(extracted_text, ''))", persisted=True), nullable=True),
    sa.Column('extraction_method', sa.Enum('NATIVE_TEXT', 'OCR', name='extractionmethod', native_enum=False, length=32), nullable=True),
    sa.Column('language', sa.String(length=16), nullable=True),
    sa.Column('extraction_status', sa.Enum('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', 'NOT_REQUIRED', name='extractionstatus', native_enum=False, length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['document_version_id'], ['document_versions.id'], name=op.f('fk_document_text_document_version_id_document_versions'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_document_text')),
    sa.UniqueConstraint('document_version_id', name=op.f('uq_document_text_document_version_id'))
    )

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
    
    op.create_index('ix_document_text_search_vector', 'document_text', ['search_vector'], postgresql_using='gin')


def downgrade() -> None:
    op.drop_index('ix_document_text_search_vector', table_name='document_text', postgresql_using='gin')
    op.drop_table('document_text')
    
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
        "'EVIDENCE_INTEGRITY_VERIFIED', 'EVIDENCE_ACCESS_DENIED'))"
    )

