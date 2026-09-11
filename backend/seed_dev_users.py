import sys
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.department import Department
from app.models.role import Role
from app.security import hash_password
from app.config import get_settings

def run():
    engine = create_engine(get_settings().database_url)
    with Session(engine) as db:
        inv_role = db.execute(select(Role).where(Role.name == "INVESTIGATOR")).scalar_one_or_none()
        if not inv_role:
            print("Roles not found! Make sure DB is migrated and seeded.")
            return
            
        colaba = db.execute(select(Department).where(Department.name == "Colaba Police Station")).scalar_one()
        bandra = db.execute(select(Department).where(Department.name == "Bandra Police Station")).scalar_one()
        mumbai = db.execute(select(Department).where(Department.name == "Mumbai Range")).scalar_one()
        
        users_to_create = [
            ("inv_colaba", colaba.id),
            ("inv_bandra", bandra.id),
            ("inv_mumbai", mumbai.id)
        ]
        
        for username, dept_id in users_to_create:
            if not db.execute(select(User).where(User.username == username)).scalar_one_or_none():
                user = User(
                    username=username,
                    email=f"{username}@nyayavault.gov.in",
                    full_name=f"Investigator {username.split('_')[1].title()}",
                    password_hash=hash_password("Dev#Passw0rd!2026"),
                    role_id=inv_role.id,
                    department_id=dept_id,
                    is_active=True
                )
                db.add(user)
                print(f"Created {username}")
        db.commit()

if __name__ == "__main__":
    run()
