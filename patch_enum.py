from sqlalchemy import create_engine, text
from app.config import get_settings

engine = create_engine(get_settings().database_url)
with engine.begin() as conn:
    conn.execute(text("DROP TYPE IF EXISTS anchorstatus CASCADE;"))
    print("Dropped anchorstatus")
