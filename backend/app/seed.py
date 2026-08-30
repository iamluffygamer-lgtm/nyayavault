"""Idempotent reference-data seeding.

Run with:  python -m app.seed

Creates the five roles and a small set of departments. It creates the bootstrap
ADMIN account ONLY if SEED_ADMIN_PASSWORD is set in the environment — there is
deliberately no default admin password anywhere in this repository, so a
deployment can never accidentally ship with known credentials.

Safe to run repeatedly: existing rows are left untouched.
"""

from __future__ import annotations

import logging
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.logging_config import configure_logging
from app.models.department import Department
from app.models.role import ROLE_DESCRIPTIONS, Role, RoleName
from app.models.user import User
from app.security import PasswordPolicyError, hash_password, validate_password_policy

logger = logging.getLogger("app.seed")

DEPARTMENTS = [
    ("Criminal Investigation Department", "Primary investigating wing for serious offences."),
    ("Cyber Crime Cell", "Digital forensics and cyber-enabled crime."),
    ("Forensic Science Laboratory", "Laboratory analysis and expert reports."),
    ("Prosecution Wing", "Legal review, filings and court liaison."),
    ("Internal Audit", "Independent oversight of case and evidence handling."),
]


def seed_roles(db: Session) -> dict[str, Role]:
    existing = {r.name: r for r in db.execute(select(Role)).scalars().all()}
    for name in RoleName:
        if name.value not in existing:
            role = Role(name=name.value, description=ROLE_DESCRIPTIONS[name])
            db.add(role)
            existing[name.value] = role
            logger.info("seed_role_created", extra={"role": name.value})
    db.flush()
    return existing


def seed_departments(db: Session) -> dict[str, Department]:
    existing = {d.name: d for d in db.execute(select(Department)).scalars().all()}
    for name, description in DEPARTMENTS:
        if name not in existing:
            department = Department(name=name, description=description)
            db.add(department)
            existing[name] = department
            logger.info("seed_department_created", extra={"department": name})
    db.flush()
    return existing


def seed_admin(db: Session, roles: dict[str, Role], departments: dict[str, Department]) -> None:
    settings = get_settings()
    password = settings.seed_admin_password

    if not password:
        logger.warning(
            "seed_admin_skipped",
            extra={"reason": "SEED_ADMIN_PASSWORD is not set — no admin account was created."},
        )
        return

    username = settings.seed_admin_username
    if db.execute(select(User).where(User.username == username)).scalar_one_or_none():
        logger.info("seed_admin_exists", extra={"username": username})
        return

    try:
        validate_password_policy(password)
    except PasswordPolicyError as exc:
        logger.error("seed_admin_rejected", extra={"reason": str(exc)})
        raise SystemExit(1) from exc

    admin = User(
        username=username,
        email=settings.seed_admin_email.lower(),
        full_name="System Administrator",
        password_hash=hash_password(password),
        role_id=roles[RoleName.ADMIN.value].id,
        department_id=departments["Internal Audit"].id,
        is_active=True,
    )
    db.add(admin)
    logger.info("seed_admin_created", extra={"username": username})


def main() -> int:
    configure_logging(get_settings().log_level)
    with SessionLocal() as db:
        roles = seed_roles(db)
        departments = seed_departments(db)
        seed_admin(db, roles, departments)
        db.commit()
    logger.info("seed_complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
