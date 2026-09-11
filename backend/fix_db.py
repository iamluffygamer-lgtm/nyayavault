from sqlalchemy import create_engine, text
from app.config import get_settings

engine = create_engine(get_settings().database_url)
with engine.begin() as conn:
    conn.execute(text("ALTER TABLE audit_events DROP CONSTRAINT IF EXISTS ck_audit_events_audit_action"))
    print("Dropped old constraint")
