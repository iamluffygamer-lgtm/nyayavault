import re

with open('backend/alembic/versions/51750c135384_document_search.py', 'r') as f:
    content = f.read()

upgrade_add = """
    # Update AuditAction enum constraint
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
    
    # Add GIN index for search_vector
    op.create_index('ix_document_text_search_vector', 'document_text', ['search_vector'], postgresql_using='gin')
"""

downgrade_add = """
    op.drop_index('ix_document_text_search_vector', table_name='document_text', postgresql_using='gin')
    
    # Revert AuditAction enum constraint
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
"""

content = content.replace("    # ### end Alembic commands ###", upgrade_add + "\n    # ### end Alembic commands ###", 1)
content = content.replace("    # ### end Alembic commands ###", downgrade_add + "\n    # ### end Alembic commands ###")

with open('backend/alembic/versions/51750c135384_document_search.py', 'w') as f:
    f.write(content)
