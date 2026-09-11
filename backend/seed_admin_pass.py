import sys
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.role import Role
from app.security import hash_password
from app.config import get_settings

def run():
    engine = create_engine(get_settings().database_url)
    with Session(engine) as db:
        admin_role = db.execute(select(Role).where(Role.name == "ADMIN")).scalar_one()
        admin = db.execute(select(User).where(User.username == "admin")).scalar_one_or_none()
        if admin:
            admin.password_hash = hash_password("Admin#Passw0rd!2026")
            print("Admin password updated")
        else:
            print("No admin user found")
        db.commit()

run()
